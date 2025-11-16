#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <shlwapi.h>
#include <shellapi.h>

#define SERVER_EXE_RESOURCE 1
#define BUFFER_SIZE 4096

// Extract embedded server.exe from resources
BOOL ExtractServerBinary(const char* outputPath) {
    HRSRC hResInfo = FindResource(NULL, MAKEINTRESOURCE(SERVER_EXE_RESOURCE), RT_RCDATA);
    if (!hResInfo) return FALSE;
    
    HGLOBAL hResData = LoadResource(NULL, hResInfo);
    if (!hResData) return FALSE;
    
    DWORD size = SizeofResource(NULL, hResInfo);
    void* data = LockResource(hResData);
    
    HANDLE hFile = CreateFile(outputPath, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hFile == INVALID_HANDLE_VALUE) return FALSE;
    
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

// Main entry point
int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {
    char currentDir[MAX_PATH];
    char tempPath[MAX_PATH];
    char serverPath[MAX_PATH];
    
    // Get current directory (where images are)
    GetCurrentDir(currentDir, sizeof(currentDir));
    
    // Create temp directory for server binary
    GetTempPath(sizeof(tempPath), tempPath);
    strcat(tempPath, "MediaGallery\\");
    CreateDirectory(tempPath, NULL);
    
    // Extract server binary
    snprintf(serverPath, sizeof(serverPath), "%sserver.exe", tempPath);
    
    if (!ExtractServerBinary(serverPath)) {
        MessageBox(NULL, "Failed to extract server binary", "Error", MB_ICONERROR);
        return 1;
    }
    
    // Launch server with current directory as working dir
    STARTUPINFO si = {sizeof(si)};
    PROCESS_INFORMATION pi;
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_HIDE;
    
    char cmdLine[BUFFER_SIZE];
    snprintf(cmdLine, sizeof(cmdLine), "\"%s\"", serverPath);
    
    if (!CreateProcess(NULL, cmdLine, NULL, NULL, FALSE, 
                      CREATE_NO_WINDOW, NULL, currentDir, &si, &pi)) {
        MessageBox(NULL, "Failed to start server", "Error", MB_ICONERROR);
        return 1;
    }
    
    // Launch browser
    LaunchBrowser("https://localhost:8443");
    
    // Create system tray icon
    NOTIFYICONDATA nid = {sizeof(nid)};
    nid.hWnd = GetConsoleWindow();
    nid.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP;
    nid.uCallbackMessage = WM_USER + 1;
    nid.hIcon = LoadIcon(NULL, IDI_APPLICATION);
    strcpy(nid.szTip, "Media Gallery Running");
    Shell_NotifyIcon(NIM_ADD, &nid);
    
    // Wait for server process
    WaitForSingleObject(pi.hProcess, INFINITE);
    
    // Cleanup
    Shell_NotifyIcon(NIM_DELETE, &nid);
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
    
    // Delete temp files
    DeleteFile(serverPath);
    RemoveDirectory(tempPath);
    
    return 0;
}
