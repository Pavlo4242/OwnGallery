gopackage main

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

func main() {
	mediaDir, _ := os.Getwd()
	
	// Generate filelist.json
	if err := generateFileList(mediaDir); err != nil {
		log.Printf("Warning: Could not generate filelist: %v", err)
	}

	// Serve embedded web files
	webFS, _ := fs.Sub(webFiles, "web")
	http.Handle("/", http.FileServer(http.FS(webFS)))

	// Serve media from current directory
	http.Handle("/media/", http.StripPrefix("/media/",
		addCORSHeaders(http.FileServer(http.Dir(mediaDir)))))

	// Generate self-signed certificate
	cert, err := generateCertificate()
	if err != nil {
		log.Fatal(err)
	}

	url := "https://localhost:8443"
	log.Printf("🚀 Gallery ready at: %s", url)

	// Auto-open browser
	go openBrowser(url)

	server := &http.Server{
		Addr: ":8443",
		TLSConfig: &tls.Config{
			Certificates: []tls.Certificate{cert},
		},
	}

	log.Fatal(server.ListenAndServeTLS("", ""))
}

func generateFileList(dir string) error {
	extensions := map[string]bool{
		".jpg": true, ".jpeg": true, ".png": true, ".webp": true,
		".gif": true, ".mp4": true, ".webm": true, ".ogg": true,
	}

	var files []string
	err := filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return err
		}

		ext := strings.ToLower(filepath.Ext(path))
		if extensions[ext] {
			relPath, _ := filepath.Rel(dir, path)
			files = append(files, filepath.ToSlash(relPath))
		}
		return nil
	})

	if err != nil {
		return err
	}

	data, _ := json.Marshal(files)
	return os.WriteFile(filepath.Join(dir, "filelist.json"), data, 0644)
}

func generateCertificate() (tls.Certificate, error) {
	priv, _ := rsa.GenerateKey(rand.Reader, 2048)

	template := x509.Certificate{
		SerialNumber: big.NewInt(1),
		Subject: pkix.Name{
			Organization: []string{"Local Gallery"},
		},
		NotBefore:             time.Now(),
		NotAfter:              time.Now().Add(365 * 24 * time.Hour),
		KeyUsage:              x509.KeyUsageKeyEncipherment | x509.KeyUsageDigitalSignature,
		ExtKeyUsage:           []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
		BasicConstraintsValid: true,
		DNSNames:              []string{"localhost"},
	}

	certDER, _ := x509.CreateCertificate(rand.Reader, &template, &template, &priv.PublicKey, priv)

	certPEM := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: certDER})
	keyPEM := pem.EncodeToMemory(&pem.Block{Type: "RSA PRIVATE KEY", Bytes: x509.MarshalPKCS1PrivateKey(priv)})

	return tls.X509KeyPair(certPEM, keyPEM)
}

func addCORSHeaders(h http.Handler) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
		h.ServeHTTP(w, r)
	}
}

func openBrowser(url string) {
	time.Sleep(1 * time.Second)

	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "windows":
		cmd = exec.Command("cmd", "/c", "start", "chrome", "--ignore-certificate-errors", url)
		if err := cmd.Run(); err != nil {
			// Fallback to Edge
			cmd = exec.Command("cmd", "/c", "start", "msedge", "--ignore-certificate-errors", url)
			cmd.Run()
		}
	case "darwin":
		cmd = exec.Command("open", url)
		cmd.Run()
	case "linux":
		cmd = exec.Command("xdg-open", url)
		cmd.Run()
	}
}