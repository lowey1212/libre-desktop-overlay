Option Explicit

Dim shell, fileSystem, folder, batchFile
Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")
folder = fileSystem.GetParentFolderName(WScript.ScriptFullName)
batchFile = folder & "\Start LibreView Overlay.bat"

shell.Run "cmd.exe /c """ & batchFile & """ /hidden", 0, False
