package main

import (
	"context"
	"crypto/rand"
	"crypto/rsa"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"embed"
	"encoding/json"
	"encoding/pem"
	"io/fs"
	"net"
	"log"
	"math/big"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"time"
	"fmt"
)

//go:embed web/*
var webFiles embed.FS

var (
	Version   = "dev"
	BuildTime = "unknown"
)

type ApiResponse struct {
    Files       []FileInfo `json:"files"`
    Directories []string   `json:"directories"`
}

type FileInfo struct {
	Path     string `json:"path"`
	Name     string `json:"name"`
	Size     int64  `json:"size"`
	Modified string `json:"modified"`
	IsVideo  bool   `json:"isVideo"`
}

func main() {
	log.Printf("Media Browser Server %s (built %s)", Version, BuildTime)
	log.Printf("Server started with arguments: %v", os.Args) 
    
	mediaDir, err := os.Getwd()
	if err != nil {
		log.Fatal(err)
	}

	// Read arguments: [0]=program, [1]=mediaDir, [2]=port, [3]=nobrowser, [4]=timeout
	port := "8987"
	noBrowser := false
	timeoutMinutes := 0
	
	if len(os.Args) > 1 {
		mediaDir = os.Args[1]
	}
	if len(os.Args) > 2 {
		port = os.Args[2]
	}
	if len(os.Args) > 3 && os.Args[3] == "nobrowser" {
		noBrowser = true
		log.Println("Browser auto-launch disabled (nobrowser flag)")
	}
	if len(os.Args) > 4 {
		fmt.Sscanf(os.Args[4], "%d", &timeoutMinutes)
		if timeoutMinutes > 0 {
			idleTimeout = time.Duration(timeoutMinutes) * time.Minute
			log.Printf("Idle timeout set to %d minutes", timeoutMinutes)
		}
	}

	log.Printf("Serving media from: %s", mediaDir)

	// Setup routes
	setupRoutes(mediaDir)

	// Generate self-signed certificate
	cert, err := generateOrLoadCertificate()
	if err != nil {
		log.Fatalf("Failed to generate certificate: %v", err)
	}

	url := "https://localhost:" + port
	log.Printf("🚀 Gallery ready at: %s", url)
	if idleTimeout > 0 {
		log.Printf("⏰ Auto-shutdown after %v of inactivity", idleTimeout)
	}
	log.Printf("Press Ctrl+C to stop")

	// Only auto-open browser if NOT launched by launcher AND not explicitly disabled
	if !noBrowser {
		log.Println("Auto-opening browser...")
		go func() {
			time.Sleep(1500 * time.Millisecond)
			openBrowser(url)
		}()
	}

	// Initialize activity tracking
	lastActivity = time.Now()
	
	// Start idle monitor if timeout is set
	if idleTimeout > 0 {
		startIdleMonitor()
	}

	// Create HTTPS server
	server := &http.Server{
		Addr:         ":" + port,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
		TLSConfig: &tls.Config{
			Certificates: []tls.Certificate{cert},
			MinVersion:   tls.VersionTLS12,
		},
	}

	// Start server in goroutine
	go func() {
		if err := server.ListenAndServeTLS("", ""); err != nil && err != http.ErrServerClosed {
			log.Printf("Server error: %v", err)
		}
	}()

	// Wait for shutdown signal (either from idle timeout or Ctrl+C)
	<-shutdownSignal

	// Graceful shutdown
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	log.Println("Gracefully shutting down server...")
	if err := server.Shutdown(ctx); err != nil {
		log.Printf("Server shutdown error: %v", err)
	}
	log.Println("Server stopped")
}

var (
    lastActivity     time.Time
    activityMutex    sync.Mutex
    idleTimeout      = 30 * time.Minute // Configurable timeout
    shutdownSignal   = make(chan bool)
)

func updateActivity() {
    activityMutex.Lock()
    lastActivity = time.Now()
    activityMutex.Unlock()
}

func activityMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        updateActivity()
        next.ServeHTTP(w, r)
    })
}

func startIdleMonitor() {
    ticker := time.NewTicker(1 * time.Minute)
    go func() {
        for {
            select {
            case <-ticker.C:
                activityMutex.Lock()
                idle := time.Since(lastActivity)
                activityMutex.Unlock()
                
                if idle > idleTimeout {
                    log.Printf("⏰ No activity for %v, shutting down...", idleTimeout)
                    shutdownSignal <- true
                    return
                }
            }
        }
    }()
}

func setupRoutes(mediaDir string) {
	// Serve embedded web files
	webFS, err := fs.Sub(webFiles, "web")
	if err != nil {
		log.Fatal(err)
	}
	http.Handle("/", activityMiddleware(corsMiddleware(http.FileServer(http.FS(webFS)))))

	// Serve media files from current directory
	http.Handle("/media/", activityMiddleware(corsMiddleware(
		http.StripPrefix("/media/", http.FileServer(http.Dir(mediaDir))))))

	// ──────────────────────────────────────────────────────────────
	// API – File listing & sources
	// ──────────────────────────────────────────────────────────────
	http.HandleFunc("/api/files", func(w http.ResponseWriter, r *http.Request) {
		updateActivity()

		source := r.URL.Query().Get("source")
		format := r.URL.Query().Get("format") // Add format parameter

		files, directories, err := getDetailedFileListAndFolders(mediaDir, source)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		// Support different response formats
		switch format {
		case "simple":
			var paths []string
			for _, file := range files {
				paths = append(paths, file.Path)
			}
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(paths)
		case "minimal":
			type MinimalFile struct {
				Path    string `json:"path"`
				IsVideo bool   `json:"isVideo"`
			}
			var minimalFiles []MinimalFile
			for _, file := range files {
				minimalFiles = append(minimalFiles, MinimalFile{
					Path:    file.Path,
					IsVideo: file.IsVideo,
				})
			}
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(minimalFiles)
		default:
			response := ApiResponse{
				Files:       files,
				Directories: directories,
			}
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(response)
		}
	})

	http.HandleFunc("/api/sources", func(w http.ResponseWriter, r *http.Request) {
		updateActivity()
		matches, _ := filepath.Glob(filepath.Join(mediaDir, "*.json"))
		var sources []string
		for _, m := range matches {
			sources = append(sources, filepath.Base(m))
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(sources)
	})

	// ──────────────────────────────────────────────────────────────
	// API – Direct JSON / directory info
	// ──────────────────────────────────────────────────────────────
	http.HandleFunc("/api/json/", func(w http.ResponseWriter, r *http.Request) {
		updateActivity()
		jsonFile := strings.TrimPrefix(r.URL.Path, "/api/json/")
		jsonPath := filepath.Join(mediaDir, jsonFile)

		if strings.Contains(jsonFile, "..") || strings.Contains(jsonFile, "/") {
			http.Error(w, "Invalid path", http.StatusBadRequest)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Cache-Control", "no-cache")
		http.ServeFile(w, r, jsonPath)
	})

	http.HandleFunc("/api/directory", func(w http.ResponseWriter, r *http.Request) {
		updateActivity()
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{
			"directory": mediaDir,
		})
	})

	http.HandleFunc("/api/root_dir", func(w http.ResponseWriter, r *http.Request) {
		updateActivity()
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{
			"root_dir": mediaDir,
		})
	})

	// ──────────────────────────────────────────────────────────────
	// API – Utility endpoints
	// ──────────────────────────────────────────────────────────────
	http.HandleFunc("/api/open_explorer", func(w http.ResponseWriter, r *http.Request) {
		updateActivity()
		err := openFileExplorer(mediaDir)
		if err != nil {
			http.Error(w, "Failed to open explorer: "+err.Error(), http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{
			"status":  "success", 
			"message": "File explorer opened",
		})
	})

	http.HandleFunc("/api/health", func(w http.ResponseWriter, r *http.Request) {
		updateActivity()
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":     "ok",
			"version":    Version,
			"directory":  mediaDir,
			"sources":    getAvailableSources(mediaDir),
			"timestamp":  time.Now().Format(time.RFC3339),
		})
	})

	// ──────────────────────────────────────────────────────────────
	// API – Admin / shutdown
	// ──────────────────────────────────────────────────────────────
	http.HandleFunc("/api/quit", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}
		w.Write([]byte("Server shutting down..."))
		go func() {
			time.Sleep(500 * time.Millisecond)
			os.Exit(0)
		}()
	})

	http.HandleFunc("/api/shutdown", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{
			"status":  "shutting_down",
			"message": "Server will shutdown shortly",
		})

		go func() {
			time.Sleep(500 * time.Millisecond)
			os.Exit(0)
		}()
	})
} // <-- This was missing in your original code

func getAvailableSources(mediaDir string) []string {
    matches, _ := filepath.Glob(filepath.Join(mediaDir, "*.json"))
    var sources []string
    for _, m := range matches {
        sources = append(sources, filepath.Base(m))
    }
    return sources
}

func getDetailedFileListAndFolders(dir, source string) ([]FileInfo, []string, error) {
    // 1. Automatic Priority: If no source specified, check for priority manifests
    if source == "" {
        // List of files to look for in order of priority
        priorityFiles := []string{"image_scores.json", "representative_gallery.json", "clustering_output.json", "gallery.json"}
        for _, fName := range priorityFiles {
            if _, err := os.Stat(filepath.Join(dir, fName)); err == nil {
                log.Printf("✨ Auto-detected manifest: %s", fName)
                source = fName
                break
            }
        }
    }

	// 2. If a specific JSON source is requested (and not "disk"), try to load it
	if source != "" && source != "disk" {
		manifestPath := filepath.Join(dir, source)
		if _, err := os.Stat(manifestPath); err == nil {
			log.Printf("📄 Loading manifest: %s", source)
			return loadFromManifest(dir, manifestPath)
		}
	}

	// 3. Fallback/Default: Walk directory (Disk Scan)
	log.Println("📂 Scanning directory structure...")
	extensions := map[string]bool{
		".jpg": false, ".jpeg": false, ".png": false, ".webp": false,
		".gif": false, ".mp4": true, ".webm": true, ".ogg": true,
		".bmp": false, ".svg": false, ".mov": true, ".avi": true,
	}

	var files []FileInfo
	var directories []string // New list for directories
	
	err := filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		// If there is an error accessing the path (e.g. permission denied), skip it
		if err != nil {
			log.Printf("⚠️ Error accessing path %q: %v", path, err)
			if info != nil && info.IsDir() {
				return filepath.SkipDir
			}
			return nil
		}

		if strings.HasPrefix(info.Name(), ".") { // Skip hidden files/folders
			return nil // Skip hidden files
		}

		// If it's a directory, add its relative path to the list
		if info.IsDir() {
			// Don't add the root directory itself, only subdirectories
			if path != dir {
				relPath, _ := filepath.Rel(dir, path)
				directories = append(directories, filepath.ToSlash(relPath))
			}
			return nil // Continue walking
		}

		// Existing logic for processing files
		ext := strings.ToLower(filepath.Ext(path))
		if isVideo, exists := extensions[ext]; exists {
			relPath, _ := filepath.Rel(dir, path)
			files = append(files, FileInfo{
				Path:     filepath.ToSlash(relPath),
				Name:     info.Name(),
				Size:     info.Size(),
				Modified: info.ModTime().Format(time.RFC3339),
				IsVideo:  isVideo,
			})
		}
		return nil
	})

	return files, directories, err
}

// loadFromManifest reads a pre-generated JSON manifest and handles multiple formats
func loadFromManifest(baseDir, manifestPath string) ([]FileInfo, []string, error) {
    data, err := os.ReadFile(manifestPath)
    if err != nil {
        return nil, nil, err
    }

    // Flexible structure to handle "files" (standard) or "gallery" (clustering output) keys
    var rawData struct {
        Files []struct {
            Path     string `json:"path"`
            Name     string `json:"name"`
            Filename string `json:"filename"` // Handle 'filename' vs 'name'
        } `json:"files"`
        Gallery []struct {
            Path     string `json:"path"`
            Filename string `json:"filename"`
        } `json:"gallery"`
        Directories []string `json:"directories"`
    }

    if err := json.Unmarshal(data, &rawData); err != nil {
        return nil, nil, err
    }

    // Standardize the list
    var fileList []FileInfo
    var dirList []string = rawData.Directories
    
    // Use 'gallery' if 'files' is empty
    type rawItem struct { Path, Name, Filename string }
    var sourceList []rawItem
    
    if len(rawData.Gallery) > 0 {
        for _, item := range rawData.Gallery {
            sourceList = append(sourceList, rawItem{Path: item.Path, Filename: item.Filename})
        }
    } else {
        for _, item := range rawData.Files {
            sourceList = append(sourceList, rawItem{Path: item.Path, Name: item.Name, Filename: item.Filename})
        }
    }

    // Convert to FileInfo
    extensions := map[string]bool{
        ".mp4": true, ".webm": true, ".ogg": true, ".mov": true, ".avi": true,
    }

    seenDirs := make(map[string]bool)
    if len(dirList) > 0 {
        for _, d := range dirList { seenDirs[filepath.ToSlash(d)] = true }
    }

    for _, item := range sourceList {
        // Fix path: remove absolute prefix if present (common in Python scripts)
        relPath := item.Path
        // Basic check if path contains baseDir, strip it
        if strings.Contains(relPath, baseDir) {
            relPath, _ = filepath.Rel(baseDir, relPath)
        }
        relPath = filepath.ToSlash(relPath)
        
        // Handle name
        name := item.Name
        if name == "" { name = item.Filename }
        if name == "" { name = filepath.Base(relPath) }

        // Check if file actually exists to get size/modtime
        fullPath := filepath.Join(baseDir, relPath)
        info, err := os.Stat(fullPath)
        if err != nil { continue } // Skip missing files

        ext := strings.ToLower(filepath.Ext(name))
        isVideo := extensions[ext]

        fileList = append(fileList, FileInfo{
            Path: relPath,
            Name: name,
            Size: info.Size(),
            Modified: info.ModTime().Format(time.RFC3339),
            IsVideo: isVideo,
        })

        // Auto-generate directories if missing
        if len(dirList) == 0 {
            d := filepath.Dir(relPath)
            d = filepath.ToSlash(d)
            if d != "." && d != "" && !seenDirs[d] {
                seenDirs[d] = true
                dirList = append(dirList, d)
            }
        }
    }
    
    return fileList, dirList, nil
}

func generateOrLoadCertificate() (tls.Certificate, error) {
	certFile := filepath.Join(os.TempDir(), "mediabrowser_cert.pem")
	keyFile := filepath.Join(os.TempDir(), "mediabrowser_key.pem")

	// Try to load existing certificate
	if _, err := os.Stat(certFile); err == nil {
		if _, err := os.Stat(keyFile); err == nil {
			cert, err := tls.LoadX509KeyPair(certFile, keyFile)
			if err == nil {
				log.Println("✅ Loaded existing certificate")
				return cert, nil
			}
		}
	}

	// Generate new certificate
	log.Println("Generating new certificate (first run)...")
	priv, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		return tls.Certificate{}, err
	}

	serialNumber, err := rand.Int(rand.Reader, new(big.Int).Lsh(big.NewInt(1), 128))
	if err != nil {
		return tls.Certificate{}, err
	}

	template := x509.Certificate{
		SerialNumber: serialNumber,
		Subject: pkix.Name{
			Organization: []string{"Media Browser Local Server"},
			CommonName:   "localhost",
		},
		NotBefore:             time.Now(),
		NotAfter:              time.Now().Add(3650 * 24 * time.Hour), // 10 years
		KeyUsage:              x509.KeyUsageKeyEncipherment | x509.KeyUsageDigitalSignature,
		ExtKeyUsage:           []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
		BasicConstraintsValid: true,
		DNSNames:              []string{"localhost"},
		IPAddresses:           []net.IP{net.ParseIP("127.0.0.1"), net.ParseIP("::1")},
	}

	certDER, err := x509.CreateCertificate(rand.Reader, &template, &template, &priv.PublicKey, priv)
	if err != nil {
		return tls.Certificate{}, err
	}

	certPEM := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: certDER})
	keyPEM := pem.EncodeToMemory(&pem.Block{Type: "RSA PRIVATE KEY", Bytes: x509.MarshalPKCS1PrivateKey(priv)})

	// Save certificate to disk
	os.WriteFile(certFile, certPEM, 0644)
	os.WriteFile(keyFile, keyPEM, 0600)

	log.Println("✅ Certificate saved for future use")
	return tls.X509KeyPair(certPEM, keyPEM)
}

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		w.Header().Set("Cache-Control", "public, max-age=3600")

		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}

		next.ServeHTTP(w, r)
	})
}

// Helper function to open the native file explorer to the given path
func openFileExplorer(path string) error {
	var cmd *exec.Cmd

	switch runtime.GOOS {
	case "windows":
		// Windows: use 'explorer' command
		cmd = exec.Command("explorer", path)
	case "darwin":
		// macOS: use 'open' command
		cmd = exec.Command("open", path)
	case "linux":
		// Linux: use 'xdg-open' command (common cross-desktop utility)
		cmd = exec.Command("xdg-open", path)
	default:
		return fmt.Errorf("unsupported operating system: %s", runtime.GOOS)
	}

	// Start the command asynchronously
	if err := cmd.Start(); err != nil {
		return fmt.Errorf("failed to start file explorer: %w", err)
	}
	log.Printf("Opened file explorer to: %s", path)
	return nil
}

func openBrowser(url string) {
	var cmd *exec.Cmd

	switch runtime.GOOS {
	case "windows":
		// Try Chrome with cert bypass
		chromePath := findChrome()
		if chromePath != "" {
			cmd = exec.Command(chromePath, "--ignore-certificate-errors", "--new-window", url)
			if err := cmd.Start(); err == nil {
				log.Println("Opened in Chrome")
				return
			}
		}

		// Try Edge with cert bypass
		edgePath := findEdge()
		if edgePath != "" {
			cmd = exec.Command(edgePath, "--ignore-certificate-errors", "--new-window", url)
			if err := cmd.Start(); err == nil {
				log.Println("Opened in Edge")
				return
			}
		}

		// Fallback to default browser
		cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
		cmd.Start()

	case "darwin":
		cmd = exec.Command("open", url)
		cmd.Start()

	case "linux":
		cmd = exec.Command("xdg-open", url)
		cmd.Start()
	}
}

func findChrome() string {
	paths := []string{
		"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
		"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
		os.Getenv("LOCALAPPDATA") + "\\Google\\Chrome\\Application\\chrome.exe",
	}
	for _, p := range paths {
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}
	return ""
}

func findEdge() string {
	paths := []string{
		"C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
		"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
	}
	for _, p := range paths {
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}
	return ""
}
