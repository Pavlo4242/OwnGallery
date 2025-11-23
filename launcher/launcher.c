#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <shlwapi.h>
#include <shellapi.h>
#include <shlobj.h>
#include <time.h>

// Definitions
#define MAX_RETRIES 3
#define RETRY_DELAY 500
#define SERVER_EXE_RESOURCE 1
#define BUFFER_SIZE 4096

// Tray Icon definitions
#define WM_TRAY_ICON (WM_USER + 1)
#define IDI_TRAY_ICON 101
#define ID_TRAY_EXIT 1001
#define ID_TRAY_CHANGE_FOLDER 1002
#define ID_TRAY_OPEN_BROWSER 1003

const char CLASS_NAME[] = "MediaGalleryLauncherWindow";

// Global Handles
PROCESS_INFORMATION serverProcessInfo;
HANDLE hServerProcess = NULL;
char serverExePath[MAX_PATH];
char tempExePath[MAX_PATH];
char currentMediaDir[MAX_PATH];
char currentPort[10] = "8987";
HWND hMainWindow = NULL;
BOOL showConsole = FALSE;
NOTIFYICONDATA nid = {0};

// Forward declarations
void LaunchBrowser(const char* url);
void TerminateServerProcess(HANDLE hProcess, DWORD processId);
void CleanupWithRetries(const char* serverPath, const char* tempPath);
BOOL ExtractServerBinary(char* outputPath);
void GetCurrentDir(char* buffer, size_t size);
BOOL StartServer(const char* mediaDir, const char* port);
void UpdateTrayTooltip(const char* dir);

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

BOOL StartServer(const char* mediaDir, const char* port) {
    if (hServerProcess) {
        TerminateServerProcess(hServerProcess, serverProcessInfo.dwProcessId);
        CloseHandle(hServerProcess);
        CloseHandle(serverProcessInfo.hThread);
        hServerProcess = NULL;
    }

    STARTUPINFO si = {sizeof(si)};
    PROCESS_INFORMATION pi;
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_HIDE;
    
    char cmdLine[BUFFER_SIZE];
    snprintf(cmdLine, sizeof(cmdLine), "\"%s\" \"%s\" %s nobrowser", 
             serverExePath, mediaDir, port);
    
    if (!CreateProcess(NULL, cmdLine, NULL, NULL, FALSE, 
                      CREATE_NO_WINDOW, NULL, NULL, &si, &pi)) {
        MessageBox(NULL, "Failed to start server", "Error", MB_ICONERROR);
        return FALSE;
    }
    
    serverProcessInfo = pi;
    hServerProcess = pi.hProcess;
    strcpy(currentMediaDir, mediaDir);
    strcpy(currentPort, port);
    
    return TRUE;
}

void UpdateTrayTooltip(const char* dir) {
    char tooltip[256];
    char shortDir[64];
    
    const char* lastSlash = strrchr(dir, '\\');
    if (lastSlash) {
        strncpy(shortDir, lastSlash + 1, sizeof(shortDir) - 1);
    } else {
        strncpy(shortDir, dir, sizeof(shortDir) - 1);
    }
    shortDir[sizeof(shortDir) - 1] = '\0';
    
    snprintf(tooltip, sizeof(tooltip), "Media Gallery - %s", shortDir);
    strcpy(nid.szTip, tooltip);
    Shell_NotifyIcon(NIM_MODIFY, &nid);
}

int CALLBACK BrowseCallbackProc(HWND hwnd, UINT uMsg, LPARAM lParam, LPARAM lpData) {
    if (uMsg == BFFM_INITIALIZED) {
        SendMessage(hwnd, BFFM_SETSELECTION, TRUE, lpData);
    }
    return 0;
}

void ChangeFolderAndRestart() {
    char newFolder[MAX_PATH] = {0};
    
    BROWSEINFO bi = {0};
    bi.hwndOwner = hMainWindow;
    bi.lpszTitle = "Select Media Folder";
    bi.ulFlags = BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE | BIF_USENEWUI;
    bi.lpfn = BrowseCallbackProc;
    bi.lParam = (LPARAM)currentMediaDir;
    
    LPITEMIDLIST pidl = SHBrowseForFolder(&bi);
    if (pidl) {
        if (SHGetPathFromIDList(pidl, newFolder)) {
            if (StartServer(newFolder, currentPort)) {
                UpdateTrayTooltip(newFolder);
                
                char url[BUFFER_SIZE];
                snprintf(url, sizeof(url), "https://localhost:%s", currentPort);
                LaunchBrowser(url);
            }
        }
        CoTaskMemFree(pidl);
    }
}

LRESULT CALLBACK WindowProc(HWND hwnd, UINT uMsg, WPARAM wParam, LPARAM lParam) {
    switch (uMsg) {
        case WM_TRAY_ICON:
            if (lParam == WM_RBUTTONUP) {
                POINT curPoint;
                GetCursorPos(&curPoint);
                HMENU hMenu = CreatePopupMenu();
                
                AppendMenu(hMenu, MF_STRING, ID_TRAY_CHANGE_FOLDER, "Change Folder...");
                AppendMenu(hMenu, MF_STRING, ID_TRAY_OPEN_BROWSER, "Open in Browser");
                AppendMenu(hMenu, MF_SEPARATOR, 0, NULL);
                AppendMenu(hMenu, MF_STRING, ID_TRAY_EXIT, "Exit");
                
                SetForegroundWindow(hwnd);
                TrackPopupMenu(hMenu, TPM_RIGHTBUTTON, curPoint.x, curPoint.y, 0, hwnd, NULL);
                PostMessage(hwnd, WM_NULL, 0, 0);
                DestroyMenu(hMenu);
            } else if (lParam == WM_LBUTTONDBLCLK) {
                char url[BUFFER_SIZE];
                snprintf(url, sizeof(url), "https://localhost:%s", currentPort);
                LaunchBrowser(url);
            }
            break;
            
        case WM_COMMAND:
            switch (LOWORD(wParam)) {
                case ID_TRAY_CHANGE_FOLDER:
                    ChangeFolderAndRestart();
                    break;
                case ID_TRAY_OPEN_BROWSER: {
                    char url[BUFFER_SIZE];
                    snprintf(url, sizeof(url), "https://localhost:%s", currentPort);
                    LaunchBrowser(url);
                    break;
                }
                case ID_TRAY_EXIT:
                    PostMessage(hwnd, WM_CLOSE, 0, 0);
                    break;
            }
            break;
            
        case WM_CLOSE:
            DestroyWindow(hwnd);
            break;
            
        case WM_DESTROY:
            Shell_NotifyIcon(NIM_DELETE, &nid);
            TerminateServerProcess(hServerProcess, serverProcessInfo.dwProcessId);
            PostQuitMessage(0);
            break;
            
        default:
            return DefWindowProc(hwnd, uMsg, wParam, lParam);
    }
    return 0;
}

HWND CreateHostWindow(HINSTANCE hInstance) {
    WNDCLASS wc = {0};
    wc.lpfnWndProc = WindowProc;
    wc.hInstance = hInstance;
    wc.lpszClassName = CLASS_NAME;
    
    RegisterClass(&wc);
    
    return CreateWindowEx(
        0, CLASS_NAME, "Media Gallery Host", 0,
        0, 0, 0, 0,
        HWND_MESSAGE, NULL, hInstance, NULL
    );
}

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {
    char currentDir[MAX_PATH];
    
    CoInitialize(NULL);
    
    // --- New, more robust argument parsing ---
    int argc;
    LPWSTR *argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (argv) {
        for (int i = 1; i < argc; i++) { // Start at 1 to skip the program name
            if (wcscmp(argv[i], L"/w") == 0 || wcscmp(argv[i], L"-w") == 0) {
                showConsole = TRUE; // Set our flag if /w is found
            } else {
                // Assume any other argument is the port number
                // Convert wide-char string to multi-byte string for our port variable
                WideCharToMultiByte(CP_ACP, 0, argv[i], -1, currentPort, sizeof(currentPort), NULL, NULL);
            }
        }
        LocalFree(argv);
    }
GetCurrentDir(currentDir, sizeof(currentDir));
    
    GetTempPath(sizeof(tempExePath), tempExePath);
    snprintf(tempExePath + strlen(tempExePath), sizeof(tempExePath) - strlen(tempExePath), 
             "MediaGallery_%d\\", GetCurrentProcessId());
    CreateDirectory(tempExePath, NULL);
    
    snprintf(serverExePath, sizeof(serverExePath), "%sserver.exe", tempExePath);
    if (!ExtractServerBinary(serverExePath)) {
         char errMsg[512];
         snprintf(errMsg, sizeof(errMsg), 
                  "Failed to extract server binary to:\n%s\n\nError code: %lu\n\n"
                  "Try running as Administrator or check antivirus settings.",
                  serverExePath, GetLastError());
         MessageBox(NULL, errMsg, "Extraction Error", MB_ICONERROR | MB_OK);
        return 1;
    }

    hMainWindow = CreateHostWindow(hInstance);
    if (hMainWindow == NULL) {
        MessageBox(NULL, "Failed to create host window", "Error", MB_ICONERROR);
        return 1;
    }
    
    if (!StartServer(currentDir, currentPort)) {
        DestroyWindow(hMainWindow);
        return 1;
    }
    
    char url[BUFFER_SIZE];
    snprintf(url, sizeof(url), "https://localhost:%s", currentPort);
    LaunchBrowser(url);
    
    nid.cbSize = sizeof(nid);
    nid.hWnd = hMainWindow;
    nid.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP;
    nid.uCallbackMessage = WM_TRAY_ICON;
    nid.hIcon = LoadIcon(hInstance, MAKEINTRESOURCE(IDI_TRAY_ICON));
    UpdateTrayTooltip(currentDir);
    Shell_NotifyIcon(NIM_ADD, &nid);
    
    MSG msg = {0};
    while (GetMessage(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }
    
    CloseHandle(hServerProcess);
    CloseHandle(serverProcessInfo.hThread);
    Sleep(1000);
    CleanupWithRetries(serverExePath, tempExePath);
    
    CoUninitialize();
    return 0;
}
