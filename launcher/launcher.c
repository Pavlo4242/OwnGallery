#include <windows.h>
#include <rpc.h> // Required for UuidCreate function prototype
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
#define ID_TRAY_HELP 1004
#define ID_TRAY_EXIT 1001
#define ID_TRAY_CHANGE_FOLDER 1002
#define ID_TRAY_OPEN_BROWSER 1003

const char CLASS_NAME[] = "MediaBrowserLauncherWindow";

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

    // Delete any existing file with retries
    for (int i = 0; i < MAX_RETRIES; i++) {
        if (!PathFileExists(outputPath)) break;
        SetFileAttributes(outputPath, FILE_ATTRIBUTE_NORMAL);
        DeleteFile(outputPath);
        Sleep(RETRY_DELAY);
    }

    // No fallback to ".123456.exe" — we already chose a unique name!
    // Just write directly

    HANDLE hFile = CreateFile(outputPath, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                              FILE_ATTRIBUTE_NORMAL, NULL);
    if (hFile == INVALID_HANDLE_VALUE) return FALSE;
   
    DWORD written;
    BOOL result = WriteFile(hFile, data, size, &written, NULL);
    CloseHandle(hFile);
    return result && (written == size);
}

void GetCurrentDir(char* buffer, size_t size) {
    if (!GetCurrentDirectory(size, buffer)) {
        // Fallback to exe location if CWD fails
        GetModuleFileName(NULL, buffer, size);
        PathRemoveFileSpec(buffer);
    }
}

void LaunchBrowser(const char* url) {
    Sleep(2800);  // Give server time to bind HTTPS

    // This is the ONLY reliable way on Windows
    HINSTANCE result = ShellExecuteA(NULL, "open", url, NULL, NULL, SW_SHOWNORMAL);

    // ShellExecute returns >32 on success, <=32 on error
    if ((intptr_t)result <= 32) {
        MessageBoxA(NULL,
            "Could not open your default browser automatically.\n\n"
            "Please open this URL manually:\n"
            "https://localhost:8987",
            "Media Browser", MB_ICONINFORMATION | MB_OK);
    }
}

void TerminateServerProcess(HANDLE hProcess, DWORD processId) {
    if (!hProcess || hProcess == INVALID_HANDLE_VALUE)
        return;

    DWORD exitCode;
    if (GetExitCodeProcess(hProcess, &exitCode) && exitCode == STILL_ACTIVE) {
        GenerateConsoleCtrlEvent(CTRL_C_EVENT, processId);  // Target our group only

        if (WaitForSingleObject(hProcess, 5000) == WAIT_TIMEOUT) {
            TerminateProcess(hProcess, 1);
        }
    }

    WaitForSingleObject(hProcess, INFINITE);
    CloseHandle(hProcess);
}

void CleanupWithRetries(const char* serverPath, const char* tempPath) {
    // Delete server exe
    for (int i = 0; i < MAX_RETRIES; i++) {
        if (!PathFileExists(serverPath)) break;
        SetFileAttributes(serverPath, FILE_ATTRIBUTE_NORMAL);
        if (DeleteFile(serverPath)) break;
        Sleep(RETRY_DELAY);
    }

    // Delete entire temp folder recursively
    char doubleNullPath[MAX_PATH + 2] = {0};
    strcpy(doubleNullPath, tempPath);
    int len = strlen(doubleNullPath);
    if (len > 0 && doubleNullPath[len-1] == '\\') doubleNullPath[len-1] = 0; // remove trailing \

    SHFILEOPSTRUCT shOp = {0};
    shOp.wFunc = FO_DELETE;
    shOp.pFrom = doubleNullPath;
    shOp.fFlags = FOF_SILENT | FOF_NOERRORUI | FOF_NOCONFIRMATION;
    SHFileOperation(&shOp);
}

BOOL StartServer(const char* mediaDir, const char* port) {
    if (hServerProcess) {
        TerminateServerProcess(hServerProcess, serverProcessInfo.dwProcessId);
        CloseHandle(hServerProcess);
        CloseHandle(serverProcessInfo.hThread);
        hServerProcess = NULL;
    }

    STARTUPINFO si = { sizeof(si) };
    PROCESS_INFORMATION pi = { 0 };

    DWORD creationFlags;
    if (showConsole) {
        creationFlags = CREATE_NEW_CONSOLE | CREATE_NEW_PROCESS_GROUP;
        si.dwFlags = STARTF_USESHOWWINDOW;
        si.wShowWindow = SW_SHOW;
    } else {
        creationFlags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP;
        si.dwFlags = STARTF_USESHOWWINDOW;
        si.wShowWindow = SW_HIDE;
    }

    char cmdLine[BUFFER_SIZE];
    snprintf(cmdLine, sizeof(cmdLine), "\"%s\" \"%s\" %s nobrowser",
             serverExePath, mediaDir, port);

    BOOL ok = CreateProcessA(
        NULL, cmdLine, NULL, NULL, FALSE,
        creationFlags, NULL, tempExePath, &si, &pi
    );

    if (!ok) {
        char msg[1024];
        snprintf(msg, sizeof(msg),
            "Failed to start server\n"
            "Path: %s\n"
            "Error: %lu\n"
            "Try disabling antivirus temporarily.", 
            serverExePath, GetLastError());
        MessageBoxA(NULL, msg, "Start Failed", MB_ICONERROR);
        return FALSE;
    }

    CloseHandle(pi.hThread);
    hServerProcess = pi.hProcess;
    serverProcessInfo = pi;

    strcpy_s(currentMediaDir, sizeof(currentMediaDir), mediaDir);
    strcpy_s(currentPort, sizeof(currentPort), port);

    return TRUE;
}

void ShowHelp() {
    const char* helpText = 
        "\n"
        "═══════════════════════════════════════════════════════\n"
        "           Media Browser Launcher - Help\n"
        "═══════════════════════════════════════════════════════\n\n"
        "USAGE: MediaBrowser.exe [OPTIONS] [DIRECTORY] [PORT]\n\n"
        "OPTIONS:\n"
        "  /help, -help, /?     Show this help message\n"
        "  /w, -w               Show console window (debug mode)\n"
        "  /d <path>            Specify media directory\n"
        "  /p <port>            Specify port (default: 8987)\n\n"
        "EXAMPLES:\n"
        "  MediaBrowser.exe\n"
        "  MediaBrowser.exe /w\n"
        "  MediaBrowser.exe \"C:\\Photos\"\n"
        "  MediaBrowser.exe /d \"D:\\Videos\" /p 9000\n"
        "  MediaBrowser.exe /w \"C:\\Media\" 8080\n\n"
        "TRAY ICON:\n"
        "  Double-click:  Open in browser\n"
        "  Right-click:   Menu (change folder, exit)\n\n"
        "═══════════════════════════════════════════════════════\n\n";
    
    // Try to allocate console if not already present
    if (AllocConsole() || GetConsoleWindow() != NULL) {
        // Console mode - print to stdout
        HANDLE hConsole = GetStdHandle(STD_OUTPUT_HANDLE);
        DWORD written;
        WriteConsole(hConsole, helpText, strlen(helpText), &written, NULL);
        
        printf("Press any key to exit...\n");
        getchar();
    } else {
        // GUI mode - show message box
        MessageBox(NULL, helpText, "Media Browser - Help", MB_ICONINFORMATION | MB_OK);
    }
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
    
    snprintf(tooltip, sizeof(tooltip), "Media Browser - %s", shortDir);
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
        case WM_TIMER:
            if (wParam == 1) {
                // Check if server process is still running
                if (WaitForSingleObject(hServerProcess, 0) == WAIT_OBJECT_0) {
                    // Server has exited, close the launcher
                    DestroyWindow(hwnd);
                }
            }
            break;

        case WM_TRAY_ICON:

            if (lParam == WM_RBUTTONUP) {
                POINT curPoint;
                GetCursorPos(&curPoint);
                HMENU hMenu = CreatePopupMenu();
                
                AppendMenu(hMenu, MF_STRING, ID_TRAY_CHANGE_FOLDER, "Change Folder...");
                AppendMenu(hMenu, MF_STRING, ID_TRAY_OPEN_BROWSER, "Open in Browser");
                AppendMenu(hMenu, MF_SEPARATOR, 0, NULL);
                AppendMenu(hMenu, MF_STRING, ID_TRAY_HELP, "Help");
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
                case ID_TRAY_HELP:
                    ShowHelp();
                    break;
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
        0, CLASS_NAME, "Media Browser Host", 0,
        0, 0, 0, 0,
        HWND_MESSAGE, NULL, hInstance, NULL
    );
}

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {
    char currentDir[MAX_PATH];
    char specifiedDir[MAX_PATH] = {0};
    
    CoInitialize(NULL);
    
    // --- Enhanced argument parsing with help and directory support ---
    int argc;
    LPWSTR *argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (argv) {
        // First pass: check for help flag
        for (int i = 1; i < argc; i++) {
            if (wcscmp(argv[i], L"/help") == 0 || 
                wcscmp(argv[i], L"-help") == 0 ||
                wcscmp(argv[i], L"--help") == 0 ||
                wcscmp(argv[i], L"/?") == 0 ||
                wcscmp(argv[i], L"-?") == 0) {
                ShowHelp();
                LocalFree(argv);
                CoUninitialize();
                return 0;
            }
        }
        
        // Second pass: parse other arguments
        for (int i = 1; i < argc; i++) {
            if (wcscmp(argv[i], L"/w") == 0 || wcscmp(argv[i], L"-w") == 0) {
                showConsole = TRUE;
            } else if (wcscmp(argv[i], L"/p") == 0 || wcscmp(argv[i], L"-p") == 0) {
                if (i + 1 < argc) {
                    i++;
                    WideCharToMultiByte(CP_ACP, 0, argv[i], -1, currentPort, sizeof(currentPort), NULL, NULL);
                }
            } else if (wcscmp(argv[i], L"/d") == 0 || wcscmp(argv[i], L"-d") == 0) {
                if (i + 1 < argc) {
                    i++;
                    WideCharToMultiByte(CP_UTF8, 0, argv[i], -1, specifiedDir, sizeof(specifiedDir), NULL, NULL);
                }
            } else {
                // Implicit argument parsing
                char arg[MAX_PATH];
                WideCharToMultiByte(CP_UTF8, 0, argv[i], -1, arg, sizeof(arg), NULL, NULL);
                
                if (strchr(arg, '\\') || strchr(arg, '/') || strchr(arg, ':')) {
                    strncpy(specifiedDir, arg, sizeof(specifiedDir) - 1);
                } else {
                    BOOL isNumeric = TRUE;
                    for (int j = 0; arg[j] != '\0'; j++) {
                        if (!isdigit(arg[j])) {
                            isNumeric = FALSE;
                            break;
                        }
                    }
                    if (isNumeric) {
                        snprintf(currentPort, sizeof(currentPort), "%s", arg);
                    }
                }
            }
        }
        LocalFree(argv);
    }
    
    // Determine which directory to use
    if (specifiedDir[0] != '\0') {
        if (PathFileExists(specifiedDir) && PathIsDirectory(specifiedDir)) {
            strncpy(currentDir, specifiedDir, sizeof(currentDir) - 1);
            currentDir[sizeof(currentDir) - 1] = '\0';
        } else {
            char errMsg[512];
            snprintf(errMsg, sizeof(errMsg), 
                     "Specified directory does not exist or is invalid:\n%s\n\n"
                     "Please provide a valid directory path.\n\n"
                     "Run with /help for usage information.",
                     specifiedDir);
            MessageBox(NULL, errMsg, "Invalid Directory", MB_ICONERROR | MB_OK);
            CoUninitialize();
            return 1;
        }
    } else {
        GetCurrentDir(currentDir, sizeof(currentDir));
    }
    
// === FIXED: Secure, unique temp directory + exe name ===
    GetTempPath(sizeof(tempExePath), tempExePath);
    
    // Use GUID + tick count for true uniqueness (no PID reuse issues)
    UUID uuid;
    UuidCreate(&uuid);
    char uuidStr[64];
    snprintf(uuidStr, sizeof(uuidStr), "MediaBrowser_%08x%04x%04x",
             GetTickCount(), uuid.Data4[0] << 8 | uuid.Data4[1], uuid.Data4[2] << 8 | uuid.Data4[3]);

    strcat(tempExePath, uuidStr);
    strcat(tempExePath, "\\");
    CreateDirectory(tempExePath, NULL);

    // Always use a fully unique server exe name
   snprintf(serverExePath, sizeof(serverExePath), "%sserver.exe", tempExePath);



    if (!ExtractServerBinary(serverExePath)) {
        char errMsg[512];
        snprintf(errMsg, sizeof(errMsg),
                 "Failed to extract server binary to:\n%s\n\nError code: %lu\n\n"
                 "Try running as Administrator or check antivirus settings.",
                 serverExePath, GetLastError());
        MessageBox(NULL, errMsg, "Extraction Error", MB_ICONERROR | MB_OK);
        CleanupWithRetries(serverExePath, tempExePath);
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
    // This line is REQUIRED for the WM_TIMER event to fire:
    SetTimer(hMainWindow, 1, 1000, NULL);
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
