' HedgeFund AI — Sessiz başlatıcı
' Konsol penceresi göstermez, streamlit'i arka planda çalıştırır,
' tarayıcıyı 5 saniye sonra açar.

Set fso = CreateObject("Scripting.FileSystemObject")
appDir   = fso.GetParentFolderName(WScript.ScriptFullName)
batPath  = appDir & "\start_app.bat"

Set ws = CreateObject("WScript.Shell")
' 0 = pencere gizli, False = bekleme
ws.Run """" & batPath & """", 0, False

' Server başlasın diye 5 saniye bekle, sonra tarayıcıyı aç
WScript.Sleep 5000
ws.Run "http://localhost:8501", 1, False
