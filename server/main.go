package main

import (
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
	"time"
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
	log.Printf("Media Gallery Server %s (built %s)", Version, BuildTime)

	mediaDir, err := os.Getwd()
	if err != nil {
		log.Fatal(err)
	}

	// Read arguments: [0]=program, [1]=mediaDir, [2]=port, [3]=nobrowser flag
	port := "8987"
	noBrowser := false
	
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
	log.Printf("Press Ctrl+C to stop")

	// FIXED: Only auto-open browser if NOT launched by launcher
	if !noBrowser {
		log.Println("Auto-opening browser...")
		go func() {
			time.Sleep(1500 * time.Millisecond)
			openBrowser(url)
		}()
	}

	// Start HTTPS server
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

	log.Fatal(server.ListenAndServeTLS("", ""))
}

func setupRoutes(mediaDir string) {
	// Serve embedded web files
	webFS, err := fs.Sub(webFiles, "web")
	if err != nil {
		log.Fatal(err)
	}
	http.Handle("/", corsMiddleware(http.FileServer(http.FS(webFS))))

	// Serve media files from current directory
	http.Handle("/media/", corsMiddleware(
		http.StripPrefix("/media/", http.FileServer(http.Dir(mediaDir)))))

	// API endpoint for file list (with details)
	http.HandleFunc("/api/files", func(w http.ResponseWriter, r *http.Request) {
		 files, directories, err := getDetailedFileListAndFolders(mediaDir)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		response := ApiResponse{
        Files:       files,
        Directories: directories,
			}
		
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(files)
	})

	// Health check endpoint
	http.HandleFunc("/api/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{
			"status":  "ok",
			"version": Version,
		})
	})
}

func getDetailedFileListAndFolders(dir string) ([]FileInfo, []string, error) {
    extensions := map[string]bool{
        ".jpg": false, ".jpeg": false, ".png": false, ".webp": false,
        ".gif": false, ".mp4": true, ".webm": true, ".ogg": true,
        ".bmp": false, ".svg": false, ".mov": true, ".avi": true,
    }

    var files []FileInfo
    var directories []string // New list for directories
    
    err := filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
        if err != nil {
            return err
        }
        if strings.HasPrefix(info.Name(), ".") { // Skip hidden files/folders
            if info.IsDir() {
                return filepath.SkipDir // Don't descend into hidden folders
            }
            return nil
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

func generateOrLoadCertificate() (tls.Certificate, error) {
	certFile := filepath.Join(os.TempDir(), "mediagallery_cert.pem")
	keyFile := filepath.Join(os.TempDir(), "mediagallery_key.pem")

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
			Organization: []string{"Media Gallery Local Server"},
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
