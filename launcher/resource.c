#include <windows.h>

// Embed the server binary - use correct path
1 RCDATA "../server/server.exe"

// Icon (optional)
// IDI_ICON1 ICON "icon.ico"

// Version information
VS_VERSION_INFO VERSIONINFO
FILEVERSION     1,0,0,0
PRODUCTVERSION  1,0,0,0
FILEFLAGSMASK   0x3fL
FILEFLAGS       0x0L
FILEOS          VOS_NT_WINDOWS32
FILETYPE        VFT_APP
FILESUBTYPE     0x0L
BEGIN
    BLOCK "StringFileInfo"
    BEGIN
        BLOCK "040904b0"
        BEGIN
            VALUE "CompanyName", "Media Gallery"
            VALUE "FileDescription", "Local Media Gallery Launcher"
            VALUE "FileVersion", "1.0.0.0"
            VALUE "InternalName", "MediaGallery"
            VALUE "LegalCopyright", "Open Source"
            VALUE "OriginalFilename", "MediaGallery.exe"
            VALUE "ProductName", "Media Gallery Launcher"
            VALUE "ProductVersion", "1.0.0.0"
        END
    END
    BLOCK "VarFileInfo"
    BEGIN
        VALUE "Translation", 0x409, 1200
    END
END
