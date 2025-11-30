
import http.server
import socketserver
import os
import json
import urllib.parse

# CONFIGURATION
PORT = 8000
DIRECTORY = os.getcwd()
THUMBNAILS_DIR = os.path.join(DIRECTORY, 'thumbnails')




class MediaGalleryHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        path = urllib.parse.unquote(self.path)
        
        # --- API ENDPOINT: /api/shutdown ---
        if path == '/api/shutdown' and self.command == 'POST':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'shutting down'}).encode())
            
            # Flush the response to ensure it's sent
            self.wfile.flush()
            
            # Shutdown after a brief delay to allow response to be sent
            import threading
            import time
            
            def shutdown():
                start_time = time.time()
                print(f"\nServer shutdown requested via web interface at {time.strftime('%H:%M:%S')}")
                print("Initiating shutdown sequence...")
                
                # Small delay to ensure response is sent
                time.sleep(0.5)
                
                shutdown_start = time.time()
                print("Calling httpd.shutdown()...")
                httpd.shutdown()
                print("Calling httpd.server_close()...")
                httpd.server_close()
                
                end_time = time.time()
                total_time = end_time - start_time
                shutdown_duration = end_time - shutdown_start
                
                print(f"✓ Server successfully shut down at {time.strftime('%H:%M:%S')}")
                print(f"⏱️  Total shutdown time: {total_time:.2f} seconds")
                print(f"⏱️  Actual shutdown duration: {shutdown_duration:.2f} seconds")
                
                # Force exit to prevent hanging
                import os
                os._exit(0)
            
            # Use regular thread instead of daemon
            shutdown_thread = threading.Thread(target=shutdown)
            shutdown_thread.start()
            return
            
    def do_GET(self):
        # Decode the URL (handle spaces, special chars)
        path = urllib.parse.unquote(self.path)
        
        
        # --- API ENDPOINT: /api/directory ---
        if path == '/api/directory':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'directory': os.path.basename(DIRECTORY)}).encode())
            return  # <-- RETURN RIGHT HERE to stop further processing
                
        # This scans the folder and returns the list of images to the HTML
        # --- API ENDPOINT: /api/files ---
        if path == '/api/files':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            file_list = []
            # Extensions to look for
            valid_exts = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'}
            video_exts = {'.mp4', '.webm', '.mov', '.mkv'}
            all_exts = valid_exts.union(video_exts)
            
            # Only scan the thumbnails directory if it exists
            if os.path.exists(THUMBNAILS_DIR) and os.path.isdir(THUMBNAILS_DIR):
                # Walk through only the thumbnails folder
                for root, dirs, files in os.walk(THUMBNAILS_DIR):
                    for f in files:
                        ext = os.path.splitext(f)[1].lower()
                        if ext in all_exts:
                            # Get relative path from thumbnails directory
                            full_path = os.path.join(root, f)
                            rel_path = os.path.relpath(full_path, THUMBNAILS_DIR).replace('\\', '/')
                            
                            # Add to list
                            file_list.append({
                                'path': f'thumbnails/{rel_path}',  # Prefix with thumbnails/
                                'name': f,
                                'isVideo': ext in video_exts
                            })
            
            # Send JSON back to browser
            self.wfile.write(json.dumps(file_list).encode())
            return

        # --- MEDIA HANDLING ---
        # The HTML asks for "/media/folder/img.jpg", we map it to "./folder/img.jpg"
        if path.startswith('/media/'):
            # Strip the "/media" prefix so the server finds the file on disk
            self.path = path.replace('/media/', '/', 1)
            
        # --- DEFAULT BEHAVIOR ---
        # Serve index.html, javascript, css, images, json, etc.
        return http.server.SimpleHTTPRequestHandler.do_GET(self)
        
      
if __name__ == "__main__":
    print(f"Starting Gallery Server...")
    print(f"Scanning Root: {DIRECTORY}")
    print(f"Open your browser to: http://localhost:{PORT}")
    
    # Allow address reuse to prevent "Address already in use" errors on restart
    socketserver.TCPServer.allow_reuse_address = True
    
    with socketserver.TCPServer(("", PORT), MediaGalleryHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
            httpd.shutdown() 