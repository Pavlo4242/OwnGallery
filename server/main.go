1       package main
2       
3       import (
4       	"crypto/rand"
5       	"crypto/rsa"
6       	"crypto/tls"
7       	"crypto/x509"
8       	"crypto/x509/pkix"
9       	"embed"
10      	"encoding/json"
11      	"encoding/pem"
12      	"io/fs"
13      	"net"
14      	"log"
15      	"math/big"
16      	"net/http"
17      	"os"
18      	"os/exec"
19      	"path/filepath"
20      	"runtime"
21      	"strings"
22      	"time"
23      	"fmt" // Added for creating errors and logging
24      )
25      
26      //go:embed web/*
27      var webFiles embed.FS
28      
29      var (
30      	Version   = "dev"
31      	BuildTime = "unknown"
32      )
33      
34      type ApiResponse struct {
35          Files       []FileInfo `json:"files"`
36          Directories []string   `json:"directories"`
37      }
38      
39      type FileInfo struct {
40      	Path     string `json:"path"`
41      	Name     string `json:"name"`
42      	Size     int64  `json:"size"`
43      	Modified string `json:"modified"`
44      	IsVideo  bool   `json:"isVideo"`
45      }
46      
47      func main() {
48      	log.Printf("Media Gallery Server %s (built %s)", Version, BuildTime)
49      	log.Printf("Server started with arguments: %v", os.Args) 
50          
51          log.Printf("Media Gallery Server %s (built %s)", Version, BuildTime)
52      
53      	mediaDir, err := os.Getwd()
54      	if err != nil {
55      		log.Fatal(err)
56      	}
57      
58      	// Read arguments: [0]=program, [1]=mediaDir, [2]=port, [3]=nobrowser flag
59      	port := "8987"
60      	noBrowser := false
61      	
62      	if len(os.Args) > 1 {
63      		mediaDir = os.Args[1]
64      	}
65      	if len(os.Args) > 2 {
66      		port = os.Args[2]
67      	}
68      	if len(os.Args) > 3 && os.Args[3] == "nobrowser" {
69      		noBrowser = true
70      		log.Println("Browser auto-launch disabled (nobrowser flag)")
71      	}
72      
73      	log.Printf("Serving media from: %s", mediaDir)
74      
75      	// Setup routes
76      	setupRoutes(mediaDir)
77      
78      	// Generate self-signed certificate
79      	cert, err := generateOrLoadCertificate()
80      	if err != nil {
81      		log.Fatalf("Failed to generate certificate: %v", err)
82      	}
83      
84      	url := "https://localhost:" + port
85      	log.Printf("🚀 Gallery ready at: %s", url)
86      	log.Printf("Press Ctrl+C to stop")
87      
88      	// Only auto-open browser if NOT launched by launcher AND not explicitly disabled
89      	if !noBrowser {
90      		log.Println("Auto-opening browser...")
91      		go func() {
92      			time.Sleep(1500 * time.Millisecond)
93      			openBrowser(url)
94      		}()
95      	}
96      
97      	// Start HTTPS server
98      	server := &http.Server{
99      		Addr:         ":" + port,
100     		ReadTimeout:  15 * time.Second,
101     		WriteTimeout: 15 * time.Second,
102     		IdleTimeout:  60 * time.Second,
103     		TLSConfig: &tls.Config{
104     			Certificates: []tls.Certificate{cert},
105     			MinVersion:   tls.VersionTLS12,
106     		},
107     	}
108     
109     	log.Fatal(server.ListenAndServeTLS("", ""))
110     }
111     
112     func setupRoutes(mediaDir string) {
113     	// Serve embedded web files
114     	webFS, err := fs.Sub(webFiles, "web")
115     	if err != nil {
116     		log.Fatal(err)
117     	}
118     	http.Handle("/", corsMiddleware(http.FileServer(http.FS(webFS))))
119     
120     	// Serve media files from current directory
121     	http.Handle("/media/", corsMiddleware(
122     		http.StripPrefix("/media/", http.FileServer(http.Dir(mediaDir)))))
123     
124     	// API endpoint for file list (with details)
125     	http.HandleFunc("/api/files", func(w http.ResponseWriter, r *http.Request) {
126     		 files, directories, err := getDetailedFileListAndFolders(mediaDir)
127     		if err != nil {
128     			http.Error(w, err.Error(), http.StatusInternalServerError)
129     			return
130     		}
131     
132     		response := ApiResponse{
133             Files:       files,
134             Directories: directories,
135     			}
136     		
137     		w.Header().Set("Content-Type", "application/json")
138     		json.NewEncoder(w).Encode(response)
139     	})
140     	
141     	// NEW: API endpoint to return the current root directory path
142         http.HandleFunc("/api/root_dir", func(w http.ResponseWriter, r *http.Request) {
143             w.Header().Set("Content-Type", "application/json")
144             json.NewEncoder(w).Encode(map[string]string{
145                 "root_dir": mediaDir,
146             })
147         })
148     
149         // NEW: API endpoint to open the directory in the native file explorer
150         http.HandleFunc("/api/open_explorer", func(w http.ResponseWriter, r *http.Request) {
151             err := openFileExplorer(mediaDir)
152             if err != nil {
153                 http.Error(w, "Failed to open explorer: "+err.Error(), http.StatusInternalServerError)
154                 return
155             }
156             w.WriteHeader(http.StatusOK)
157         })
158     
159     
160     	// Health check endpoint
161     	http.HandleFunc("/api/health", func(w http.ResponseWriter, r *http.Request) {
162     		w.Header().Set("Content-Type", "application/json")
163     		json.NewEncoder(w).Encode(map[string]string{
164     			"status":  "ok",
165     			"version": Version,
166     		})
167     	})
168     }
169     
170     func getDetailedFileListAndFolders(dir string) ([]FileInfo, []string, error) {
171         extensions := map[string]bool{
172             ".jpg": false, ".jpeg": false, ".png": false, ".webp": false,
173             ".gif": false, ".mp4": true, ".webm": true, ".ogg": true,
174             ".bmp": false, ".svg": false, ".mov": true, ".avi": true,
175         }
176     
177         var files []FileInfo
178         var directories []string // New list for directories
179         
180         err := filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
181             if err != nil {
182                 return err
183             }
184             if strings.HasPrefix(info.Name(), ".") { // Skip hidden files/folders
185                 if info.IsDir() {
186                     return filepath.SkipDir // Don't descend into hidden folders
187                 }
188                 return nil // Skip hidden files
189             }
190     
191             // If it's a directory, add its relative path to the list
192             if info.IsDir() {
193                 // Don't add the root directory itself, only subdirectories
194                 if path != dir {
195                     relPath, _ := filepath.Rel(dir, path)
196                     directories = append(directories, filepath.ToSlash(relPath))
197                 }
198                 return nil // Continue walking
199             }
200     
201             // Existing logic for processing files
202             ext := strings.ToLower(filepath.Ext(path))
203             if isVideo, exists := extensions[ext]; exists {
204                 relPath, _ := filepath.Rel(dir, path)
205                 files = append(files, FileInfo{
206                     Path:     filepath.ToSlash(relPath),
207                     Name:     info.Name(),
208                     Size:     info.Size(),
209                     Modified: info.ModTime().Format(time.RFC3339),
210                     IsVideo:  isVideo,
211                 })
212             }
213             return nil
214         })
215     
216         return files, directories, err
217     }
218     
219     func generateOrLoadCertificate() (tls.Certificate, error) {
220     	certFile := filepath.Join(os.TempDir(), "mediagallery_cert.pem")
221     	keyFile := filepath.Join(os.TempDir(), "mediagallery_key.pem")
222     
223     	// Try to load existing certificate
224     	if _, err := os.Stat(certFile); err == nil {
225     		if _, err := os.Stat(keyFile); err == nil {
226     			cert, err := tls.LoadX509KeyPair(certFile, keyFile)
227     			if err == nil {
228     				log.Println("✅ Loaded existing certificate")
229     				return cert, nil
230     			}
231     		}
232     	}
233     
234     	// Generate new certificate
235     	log.Println("Generating new certificate (first run)...")
236     	priv, err := rsa.GenerateKey(rand.Reader, 2048)
237     	if err != nil {
238     		return tls.Certificate{}, err
239     	}
240     
241     	serialNumber, err := rand.Int(rand.Reader, new(big.Int).Lsh(big.NewInt(1), 128))
242     	if err != nil {
243     		return tls.Certificate{}, err
244     	}
245     
246     	template := x509.Certificate{
247     		SerialNumber: serialNumber,
248     		Subject: pkix.Name{
249     			Organization: []string{"Media Gallery Local Server"},
250     			CommonName:   "localhost",
251     		},
252     		NotBefore:             time.Now(),
253     		NotAfter:              time.Now().Add(3650 * 24 * time.Hour), // 10 years
254     		KeyUsage:              x509.KeyUsageKeyEncipherment | x509.KeyUsageDigitalSignature,
255     		ExtKeyUsage:           []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
256     		BasicConstraintsValid: true,
257     		DNSNames:              []string{"localhost"},
258     		IPAddresses:           []net.IP{net.ParseIP("127.0.0.1"), net.ParseIP("::1")},
259     	}
260     
261     	certDER, err := x509.CreateCertificate(rand.Reader, &template, &template, &priv.PublicKey, priv)
262     	if err != nil {
263     		return tls.Certificate{}, err
264     	}
265     
266     	certPEM := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: certDER})
267     	keyPEM := pem.EncodeToMemory(&pem.Block{Type: "RSA PRIVATE KEY", Bytes: x509.MarshalPKCS1PrivateKey(priv)})
268     
269     	// Save certificate to disk
270     	os.WriteFile(certFile, certPEM, 0644)
271     	os.WriteFile(keyFile, keyPEM, 0600)
272     
273     	log.Println("✅ Certificate saved for future use")
274     	return tls.X509KeyPair(certPEM, keyPEM)
275     }
276     
277     func corsMiddleware(next http.Handler) http.Handler {
278     	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
279     		w.Header().Set("Access-Control-Allow-Origin", "*")
280     		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
281     		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
282     		w.Header().Set("Cache-Control", "public, max-age=3600")
283     
284     		if r.Method == "OPTIONS" {
285     			w.WriteHeader(http.StatusOK)
286     			return
287     		}
288     
289     		next.ServeHTTP(w, r)
290     	})
291     }
292     
293     // Helper function to open the native file explorer to the given path
294     func openFileExplorer(path string) error {
295     	var cmd *exec.Cmd
296     
297     	switch runtime.GOOS {
298     	case "windows":
299     		// Windows: use 'explorer' command
300     		cmd = exec.Command("explorer", path)
301     	case "darwin":
302     		// macOS: use 'open' command
303     		cmd = exec.Command("open", path)
304     	case "linux":
305     		// Linux: use 'xdg-open' command (common cross-desktop utility)
306     		cmd = exec.Command("xdg-open", path)
307     	default:
308     		return fmt.Errorf("unsupported operating system: %s", runtime.GOOS)
309     	}
310     
311     	// Start the command asynchronously
312     	if err := cmd.Start(); err != nil {
313     		return fmt.Errorf("failed to start file explorer: %w", err)
314     	}
315     	log.Printf("Opened file explorer to: %s", path)
316     	return nil
317     }
318     
319     func openBrowser(url string) {
320     	var cmd *exec.Cmd
321     
322     	switch runtime.GOOS {
323     	case "windows":
324     		// Try Chrome with cert bypass
325     		chromePath := findChrome()
326     		if chromePath != "" {
327     			cmd = exec.Command(chromePath, "--ignore-certificate-errors", "--new-window", url)
328     			if err := cmd.Start(); err == nil {
329     				log.Println("Opened in Chrome")
330     				return
331     			}
332     		}
333     
334     		// Try Edge with cert bypass
335     		edgePath := findEdge()
336     		if edgePath != "" {
337     			cmd = exec.Command(edgePath, "--ignore-certificate-errors", "--new-window", url)
338     			if err := cmd.Start(); err == nil {
339     				log.Println("Opened in Edge")
340     				return
341     			}
342     		}
343     
344     		// Fallback to default browser
345     		cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
346     		cmd.Start()
347     
348     	case "darwin":
349     		cmd = exec.Command("open", url)
350     		cmd.Start()
351     
352     	case "linux":
353     		cmd = exec.Command("xdg-open", url)
354     		cmd.Start()
355     	}
356     }
357     
358     func findChrome() string {
359     	paths := []string{
360     		"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
361     		"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
362     		os.Getenv("LOCALAPPDATA") + "\\Google\\Chrome\\Application\\chrome.exe",
363     	}
364     	for _, p := range paths {
365     		if _, err := os.Stat(p); err == nil {
366     			return p
367     		}
368     	}
369     	return ""
370     }
371     
372     func findEdge() string {
373     	paths := []string{
374     		"C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
375     		"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
376     	}
377     	for _, p := range paths {
378     		if _, err := os.Stat(p); err == nil {
379     			return p
380     		}
381     	}
382     	return ""
383     }
