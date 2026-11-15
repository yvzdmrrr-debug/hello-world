' AgentOS Supreme - terminal penceresi acmadan baslatir.
Set kabuk = CreateObject("WScript.Shell")
klasor = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
kabuk.Run """" & klasor & "\node_modules\electron\dist\electron.exe"" """ & klasor & """", 1, False
