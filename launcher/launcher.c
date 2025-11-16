#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <shlwapi.h>
#include <shellapi.h>

#define SERVER_EXE_RESOURCE 1
#define BUFFER_SIZE 4096
#define SERVER_PORT "8443" // Define port here


// Extract embedded server.exe from resources
BOOL ExtractServerBinary(const char* outputPath) {
    HRSRC hResInfo = FindResource(NULL, MAKEINTRESOURCE(SERVER_EXE_RESOURCE), RT_RCDATA);
    if (!hResInfo) return FALSE;
    
    HGLOBAL hResData = LoadResource(NULL, hResInfo);
    if (!hResData) return FALSE;
    
    DWORD size = SizeofResource(NULL, hResInfo);
    void* data = LockResource(hResData);
    if (!data) return FALSE;
    
    // Try to delete existing file first (with retries)
    for (int i = 0; i < MAX_RETRIES; i++) {
        if (!PathFileExists(outputPath)) break;
        
        DeleteFile(outputPath);
        if (!PathFileExists(outputPath)) break;
        
        Sleep(RETRY_DELAY);
    }
    
    // If file still exists, try with a unique name
    char uniquePath[MAX_PATH];
    if (PathFileExists(outputPath)) {
        snprintf(uniquePath, sizeof(uniquePath), "%s.%d.exe", outputPath, (int)time(NULL));
        strcpy((char*)outputPath, uniquePath);
    }
    
    HANDLE hFile = CreateFile(outputPath, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 
                              FILE_ATTRIBUTE_NORMAL | FILE_FLAG_DELETE_ON_CLOSE, NULL);
    if (hFile == INVALID_HANDLE_VALUE) {
        return FALSE;
    }
    
    DWORD written;
    BOOL result = WriteFile(hFile, data, size, &written, NULL);
    CloseHandle(hFile);
    
    return result && (written == size);
}

// Get current working directory
void GetCurrentDir(char* buffer, size_t size) {
    GetModuleFileName(NULL, buffer, size);
    PathRemoveFileSpec(buffer);
}

// Launch browser with certificate bypass
void LaunchBrowser(const char* url) {
    Sleep(2000); // Wait for server to start
    
    char cmd[BUFFER_SIZE];
    
    // Try Chrome first
    snprintf(cmd, sizeof(cmd), 
        "\"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe\" --ignore-certificate-errors \"%s\"", 
        url);
    
    STARTUPINFO si = {sizeof(si)};
    PROCESS_INFORMATION pi;
    
    if (!CreateProcess(NULL, cmd, NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi)) {
        // Try Edge as fallback
        snprintf(cmd, sizeof(cmd), 
            "\"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe\" --ignore-certificate-errors \"%s\"", 
            url);
        
        if (!CreateProcess(NULL, cmd, NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi)) {
            // Fallback to default browser (without cert bypass)
            ShellExecute(NULL, "open", url, NULL, NULL, SW_SHOWNORMAL);
            return;
        }
    }
    
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
}
    
    // Try Edge
    const char* edgePaths[] = {
        "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
        "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
    };
    
    for (int i = 0; i < 2; i++) {
        if (PathFileExists(edgePaths[i])) {
            snprintf(cmd, sizeof(cmd), "\"%s\" --ignore-certificate-errors --new-window \"%s\"", 
                    edgePaths[i], url);
            
            if (CreateProcess(NULL, cmd, NULL, NULL, FALSE, CREATE_NO_WINDOW, 
                            NULL, NULL, &si, &pi)) {
                CloseHandle(pi.hProcess);
                CloseHandle(pi.hThread);
                return;
            }
        }
    }
    
    // Fallback to default browser (without cert bypass)
    ShellExecute(NULL, "open", url, NULL, NULL, SW_SHOWNORMAL);
}

// Forcefully terminate process
void TerminateServerProcess(HANDLE hProcess, DWORD processId) {
    // First try graceful termination
    if (hProcess && hProcess != INVALID_HANDLE_VALUE) {
        DWORD exitCode;
        if (GetExitCodeProcess(hProcess, &exitCode) && exitCode == STILL_ACTIVE) {
            // Try Ctrl+C first
            GenerateConsoleCtrlEvent(CTRL_C_EVENT, processId);
            
            // Wait up to 3 seconds for graceful exit
            if (WaitForSingleObject(hProcess, 3000) == WAIT_TIMEOUT) {
                // Force terminate
                TerminateProcess(hProcess, 0);
                WaitForSingleObject(hProcess, 1000);
            }
        }
    }
}

// Clean up with retries
void CleanupWithRetries(const char* serverPath, const char* tempPath) {
    // Try to delete server.exe with retries
    for (int i = 0; i < MAX_RETRIES; i++) {
        if (!PathFileExists(serverPath)) break;
        
        SetFileAttributes(serverPath, FILE_ATTRIBUTE_NORMAL);
        if (DeleteFile(serverPath)) break;
        
        Sleep(RETRY_DELAY);
    }
    
    // Try to remove directory with retries
    for (int i = 0; i < MAX_RETRIES; i++) {
        if (!PathFileExists(tempPath)) break;
        
        if (RemoveDirectory(tempPath)) break;
        
        Sleep(RETRY_DELAY);
    }
}

// Main entry point
int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {
    char currentDir[MAX_PATH];
    char tempPath[MAX_PATH];
    char serverPath[MAX_PATH];
    
    // Get current directory (where images are)
    GetCurrentDir(currentDir, sizeof(currentDir));
    
    // Create unique temp directory
    GetTempPath(sizeof(tempPath), tempPath);
    snprintf(tempPath + strlen(tempPath), sizeof(tempPath) - strlen(tempPath), 
             "MediaGallery_%d\\", GetCurrentProcessId());
    
    // Create directory (ignore if exists)
    CreateDirectory(tempPath, NULL);

    // Get port from command line or use default 8443 for HTTPS
       char port[10] = "8443"; 
       if (lpCmdLine && strlen(lpCmdLine) > 0) {
         strncpy(port, lpCmdLine, sizeof(port) - 1);
         port[sizeof(port) - 1] = '\0';
     }
    
    // Extract server binary
    snprintf(serverPath, sizeof(serverPath), "%sserver.exe", tempPath);
    
    if (!ExtractServerBinary(serverPath)) {
        char errMsg[512];
        snprintf(errMsg, sizeof(errMsg), 
                "Failed to extract server binary to:\n%s\n\nError code: %lu\n\n"
                "Try running as Administrator or check antivirus settings.",
                serverPath, GetLastError());
        MessageBox(NULL, errMsg, "Extraction Error", MB_ICONERROR | MB_OK);
        return 1;
    }
    
    // Verify extraction succeeded
    if (!PathFileExists(serverPath)) {
        MessageBox(NULL, "Server binary extraction failed - file not found after extraction", 
                  "Error", MB_ICONERROR);
        return 1;
    }
    
     // Launch server with current directory as working dir AND the port
    STARTUPINFO si = {sizeof(si)};
    PROCESS_INFORMATION pi;
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_HIDE;
    
    char cmdLine[BUFFER_SIZE];
    // Pass currentDir (as context) and the port number
    snprintf(cmdLine, sizeof(cmdLine), "\"%s\" \"%s\" %s", serverPath, currentDir, port); 
    
    if (!CreateProcess(NULL, cmdLine, NULL, NULL, FALSE, 
                      CREATE_NO_WINDOW, NULL, currentDir, &si, &pi)) {
        MessageBox(NULL, "Failed to start server", "Error", MB_ICONERROR);
        return 1;
    }
    
    HANDLE hProcess = pi.hProcess;
    DWORD processId = pi.dwProcessId;
    
        // Launch browser
    char url[BUFFER_SIZE];
    snprintf(url, sizeof(url), "https://localhost:%s", port);
    LaunchBrowser(url); // Updated LaunchBrowser to use the passed URL
   
// Create system tray icon
    NOTIFYICONDATA nid = {sizeof(nid)};
    nid.hWnd = GetConsoleWindow();
    nid.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP;
    nid.uCallbackMessage = WM_USER + 1;
    nid.hIcon = LoadIcon(NULL, IDI_APPLICATION);
    strcpy(nid.szTip, "Media Gallery Running");
    Shell_NotifyIcon(NIM_ADD, &nid);
    
    // Wait for server process to exit
    WaitForSingleObject(hProcess, INFINITE);
    
    // Cleanup system tray
    Shell_NotifyIcon(NIM_DELETE, &nid);
    
    // Force terminate if still running
    TerminateServerProcess(hProcess, processId);
    
    // Close handles
    CloseHandle(hProcess);
    CloseHandle(pi.hThread);
    
    // Wait a bit for file handles to be released
    Sleep(1000);
    
    // Cleanup temp files with retries
    CleanupWithRetries(serverPath, tempPath);
    
    return 0;
}