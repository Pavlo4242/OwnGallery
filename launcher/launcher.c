#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <shlwapi.h>
#include <shellapi.h>
#include <time.h>

// Definitions
#define MAX_RETRIES 3
#define RETRY_DELAY 500 // 500ms
#define SERVER_EXE_RESOURCE 1
#define BUFFER_SIZE 4096

// --- New definitions for Tray Icon ---
#define WM_TRAY_ICON (WM_USER + 1)
#define ID_TRAY_EXIT 1001
const char CLASS_NAME[] = "MediaGalleryLauncherWindow";

// --- Global Handles ---
PROCESS_INFORMATION serverProcessInfo;
HANDLE hServerProcess = NULL;
char serverExePath[MAX_PATH]; // Store path for cleanup
char tempExePath[MAX_PATH];   // Store path for cleanup

// (ExtractServerBinary, GetCurrentDir, LaunchBrowser remain unchanged)
BOOL ExtractServerBinary(char* outputPath) {
    HRSRC hResInfo = FindResource(NULL, MAKEINTRESOURCE(SERVER_EXE_RESOURCE), RT_RCDATA);
    if (!hResInfo) return FALSE;
    HGLOBAL hResData = LoadResource(NULL, hResInfo);
    if (!hResData) return FALSE;
    DWORD size = SizeofResource(NULL, hResInfo);
    void* data = LockResource(hResData);
    if (!data) return FALSE;

    for (int i = 0; i < MAX_RETRIES; i++) {
        if (!PathFileExists(outputPath)) break;
        DeleteFile(outputPath);
        if (!PathFileExists(outputPath)) break;
        Sleep(RETRY_DELAY);
    }

    char uniquePath[MAX_PATH];
    if (PathFileExists(outputPath)) {
        snprintf(uniquePath, sizeof(uniquePath), "%s.%d.exe", outputPath, (int)time(NULL));
        strcpy(outputPath, uniquePath);
    }

    HANDLE hFile = CreateFile(outputPath, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 
                              FILE_ATTRIBUTE_NORMAL, NULL);
    if (hFile == INVALID_HANDLE_VALUE) return FALSE;
    
    DWORD written;
    BOOL result = WriteFile(hFile, data, size, &written, NULL);
    CloseHandle(hFile);
    return result && (written == size);
}

void GetCurrentDir(char* buffer, size_t size) {
    GetModuleFileName(NULL, buffer, size);
    PathRemoveFileSpec(buffer);
}

void LaunchBrowser(const char* url) {
    Sleep(2000);
    char cmd[BUFFER_SIZE];
    snprintf(cmd, sizeof(cmd), 
        "\"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe\" --ignore-certificate-errors \"%s\"", url);
    
    STARTUPINFO si = {sizeof(si)};
    PROCESS_INFORMATION pi;
    
    if (!CreateProcess(NULL, cmd, NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi)) {
        snprintf(cmd, sizeof(cmd), 
            "\"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe\" --ignore-certificate-errors \"%s\"", url);
        
        if (!CreateProcess(NULL, cmd, NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi)) {
            ShellExecute(NULL, "open", url, NULL, NULL, SW_SHOWNORMAL);
            return;
        }
    }
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
}


// (TerminateServerProcess and CleanupWithRetries remain unchanged)
void TerminateServerProcess(HANDLE hProcess, DWORD processId) {
    if (hProcess && hProcess != INVALID_HANDLE_VALUE) {
        DWORD exitCode;
        if (GetExitCodeProcess(hProcess, &exitCode) && exitCode == STILL_ACTIVE) {
            GenerateConsoleCtrlEvent(CTRL_C_EVENT, processId);
            if (WaitForSingleObject(hProcess, 3000) == WAIT_TIMEOUT) {
                TerminateProcess(hProcess, 0);
                WaitForSingleObject(hProcess, 1000);
            }
        }
    }
}

void CleanupWithRetries(const char* serverPath, const char* tempPath) {
    for (int i = 0; i < MAX_RETRIES; i++) {
        if (!PathFileExists(serverPath)) break;
        SetFileAttributes(serverPath, FILE_ATTRIBUTE_NORMAL);
        if (DeleteFile(serverPath)) break;
        Sleep(RETRY_DELAY);
    }
    for (int i = 0; i < MAX_RETRIES; i++) {
        if (!PathFileExists(tempPath)) break;
        if (RemoveDirectory(tempPath)) break;
        Sleep(RETRY_DELAY);
    }
}

// --- NEW: Window Procedure to handle tray icon messages ---
LRESULT CALLBACK WindowProc(HWND hwnd, UINT uMsg, WPARAM wParam, LPARAM lParam) {
    switch (uMsg) {
        case WM_TRAY_ICON:
            // Message from the tray icon
            if (lParam == WM_RBUTTONUP) {
                // Show right-click menu
                POINT curPoint;
                GetCursorPos(&curPoint);
                HMENU hMenu = CreatePopupMenu();
                AppendMenu(hMenu, MF_STRING, ID_TRAY_EXIT, "Exit Media Gallery");
                
                SetForegroundWindow(hwnd); // Required for menu to work
                TrackPopupMenu(hMenu, TPM_RIGHTBUTTON, curPoint.x, curPoint.y, 0, hwnd, NULL);
                PostMessage(hwnd, WM_NULL, 0, 0); // Required
                DestroyMenu(hMenu);
            }
            break;
        case WM_COMMAND:
            // Menu item clicked
            if (LOWORD(wParam) == ID_TRAY_EXIT) {
                PostMessage(hwnd, WM_CLOSE, 0, 0); // Trigger window close
            }
            break;
        case WM_CLOSE:
            DestroyWindow(hwnd);
            break;
        case WM_DESTROY:
            // 1. Remove tray icon
            NOTIFYICONDATA nid = {sizeof(nid)};
            nid.hWnd = hwnd;
            Shell_NotifyIcon(NIM_DELETE, &nid);

            // 2. Terminate the server process
            TerminateServerProcess(hServerProcess, serverProcessInfo.dwProcessId);
            
            // 3. Tell the message loop to exit
            PostQuitMessage(0);
            break;
        default:
            return DefWindowProc(hwnd, uMsg, wParam, lParam);
    }
    return 0;
}

// --- NEW: Function to create the invisible window ---
HWND CreateHostWindow(HINSTANCE hInstance) {
    WNDCLASS wc = {0};
    wc.lpfnWndProc = WindowProc;
    wc.hInstance = hInstance;
    wc.lpszClassName = CLASS_NAME;
    
    RegisterClass(&wc);
    
    // Create an invisible message-only window
    return CreateWindowEx(
        0, CLASS_NAME, "Media Gallery Host", 0,
        0, 0, 0, 0,
        HWND_MESSAGE, NULL, hInstance, NULL
    );
}


// --- UPDATED: Main entry point ---
int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {
    char currentDir[MAX_PATH];
    HWND hMainWnd;
    
    // Get current directory
    GetCurrentDir(currentDir, sizeof(currentDir));
    
    // Create unique temp directory
    GetTempPath(sizeof(tempExePath), tempExePath);
    snprintf(tempExePath + strlen(tempExePath), sizeof(tempExePath) - strlen(tempExePath), 
             "MediaGallery_%d\\", GetCurrentProcessId());
    CreateDirectory(tempExePath, NULL);

    // Get port
    char port[10] = "8987"; // Your new default port
    if (lpCmdLine && strlen(lpCmdLine) > 0) {
       strncpy(port, lpCmdLine, sizeof(port) - 1);
       port[sizeof(port) - 1] = '\0';
    }
    
    // Extract server binary
    snprintf(serverExePath, sizeof(serverExePath), "%sserver.exe", tempExePath);
    if (!ExtractServerBinary(serverExePath)) {
        // (Error message box)
        return 1;
    }
    if (!PathFileExists(serverExePath)) {
        // (Error message box)
        return 1;
    }

    // --- NEW: Create the host window BEFORE launching server ---
    hMainWnd = CreateHostWindow(hInstance);
    if (hMainWnd == NULL) {
        MessageBox(NULL, "Failed to create host window", "Error", MB_ICONERROR);
        return 1;
    }
    
    // Launch server
    STARTUPINFO si = {sizeof(si)};
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_HIDE;
    
    char cmdLine[BUFFER_SIZE];
    snprintf(cmdLine, sizeof(cmdLine), "\"%s\" \"%s\" %s", serverExePath, currentDir, port); 
    
    if (!CreateProcess(NULL, cmdLine, NULL, NULL, FALSE, 
                      CREATE_NO_WINDOW, NULL, NULL, &si, &pi)) {
        MessageBox(NULL, "Failed to start server", "Error", MB_ICONERROR);
        DestroyWindow(hMainWnd); // Clean up window
        return 1;
    }
    
    // Store process info globally
    serverProcessInfo = pi;
    hServerProcess = pi.hProcess;
    
    // Launch browser
    char url[BUFFER_SIZE];
    snprintf(url, sizeof(url), "https://localhost:%s", port);
    LaunchBrowser(url);
    
    // --- FIXED: Create system tray icon ---
    NOTIFYICONDATA nid = {sizeof(nid)};
    nid.hWnd = hMainWnd; // Attach to our new invisible window
    nid.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP;
    nid.uCallbackMessage = WM_TRAY_ICON; // Send messages to our WindowProc
    nid.hIcon = LoadIcon(NULL, IDI_APPLICATION);
    strcpy(nid.szTip, "Media Gallery Running (Right-click to Exit)");
    Shell_NotifyIcon(NIM_ADD, &nid);
    
    // --- NEW: Run the message loop ---
    // This will run until PostQuitMessage(0) is called (by our tray menu)
    MSG msg = {0};
    while (GetMessage(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }
    
    // --- Cleanup (after message loop exits) ---
    CloseHandle(hServerProcess);
    CloseHandle(serverProcessInfo.hThread);
    
    Sleep(1000); // Wait for file handles to be released
    
    CleanupWithRetries(serverExePath, tempExePath);
    
    return 0;
}
