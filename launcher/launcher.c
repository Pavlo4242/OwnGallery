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
    
    // Get just the folder name
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

// Callback for SHBrowseForFolder to set initial directory
int CALLBACK BrowseCallbackProc(HWND hwnd, UINT uMsg, LPARAM lParam, LPARAM lpData) {
    if (uMsg == BFFM_INITIALIZED) {
        // Set the initial directory to the current media directory
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
    bi.lParam = (LPARAM)currentMediaDir; // Pass current directory
    
    LPITEMIDLIST pidl = SHBrowseForFolder(&bi);
    if (pidl) {
        if (SHGetPathFromIDList(pidl, newFolder)) {
            // Restart server with new folder
            if (StartServer(newFolder, currentPort)) {
                UpdateTrayTooltip(newFolder);
                
                // Open browser to new location
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
                // Double-click opens browser
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
    
    // Get current directory
    GetCurrentDir(currentDir, sizeof(currentDir));
    
    // Create unique temp directory
    GetTempPath(sizeof(tempExePath), tempExePath);
    snprintf(tempExePath + strlen(tempExePath), sizeof(tempExePath) - strlen(tempExePath), 
             "MediaGallery_%d\\", GetCurrentProcessId());
    CreateDirectory(tempExePath, NULL);

    // Get port from command line if provided
    if (lpCmdLine && strlen(lpCmdLine) > 0) {
       strncpy(currentPort, lpCmdLine, sizeof(currentPort) - 1);
       currentPort[sizeof(currentPort) - 1] = '\0';
    }
    
    // Extract server binary
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

    // Create the host window
    hMainWindow = CreateHostWindow(hInstance);
    if (hMainWindow == NULL) {
        MessageBox(NULL, "Failed to create host window", "Error", MB_ICONERROR);
        return 1;
    }
    
    // Start server (with nobrowser flag)
    if (!StartServer(currentDir, currentPort)) {
        DestroyWindow(hMainWindow);
        return 1;
    }
    
    // Launch browser ONLY from launcher
    char url[BUFFER_SIZE];
    snprintf(url, sizeof(url), "https://localhost:%s", currentPort);
    LaunchBrowser(url);
    
    // Create system tray icon
    nid.cbSize = sizeof(nid);
    nid.hWnd = hMainWindow;
    nid.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP;
    nid.uCallbackMessage = WM_TRAY_ICON;
    
    // Try to load custom icon, fallback to default
    HICON hIcon = (HICON)LoadImage(hInstance, MAKEINTRESOURCE(IDI_TRAY_ICON), 
                                    IMAGE_ICON, 0, 0, LR_DEFAULTCOLOR | LR_DEFAULTSIZE);
    if (hIcon == NULL) {
        // Fallback to built-in Windows icon if custom icon fails
        hIcon = LoadIcon(NULL, IDI_APPLICATION);
    }
    nid.hIcon = hIcon;
    
    UpdateTrayTooltip(currentDir);
    Shell_NotifyIcon(NIM_ADD, &nid);
    
    // Run message loop
    MSG msg = {0};
    while (GetMessage(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }
    
    // Cleanup
    if (nid.hIcon && nid.hIcon != LoadIcon(NULL, IDI_APPLICATION)) {
        DestroyIcon(nid.hIcon);
    }
    CloseHandle(hServerProcess);
    CloseHandle(serverProcessInfo.hThread);
    Sleep(1000);
    CleanupWithRetries(serverExePath, tempExePath);
    
    CoUninitialize();
    return 0;
}