Option Explicit
On Error Resume Next
Dim stream, message, voice, description
If WScript.Arguments.Count <> 1 Then
    WScript.Echo "Speech text file is missing."
    WScript.Quit 1
End If
Set stream = CreateObject("ADODB.Stream")
If Err.Number <> 0 Then
    WScript.Echo "Cannot read speech text: " & Err.Description
    WScript.Quit 1
End If
stream.Type = 2
stream.Charset = "utf-8"
stream.Open
stream.LoadFromFile WScript.Arguments(0)
message = stream.ReadText
If Err.Number <> 0 Then
    WScript.Echo "Cannot read speech text: " & Err.Description
    WScript.Quit 1
End If
stream.Close
Set stream = Nothing
Set voice = CreateObject("SAPI.SpVoice")
If Err.Number <> 0 Then
    WScript.Echo "Cannot create a Windows speech voice: " & Err.Description
    WScript.Quit 1
End If
If voice.GetVoices.Count = 0 Then
    WScript.Echo "No Windows SAPI voice is installed."
    WScript.Quit 1
End If
' 16 = SVSFIsNotXML: the text is spoken literally.
voice.Speak message, 16
If Err.Number <> 0 Then
    description = Err.Description
    Set voice = Nothing
    WScript.Echo "Windows speech failed: " & description
    WScript.Quit 1
End If
Set voice = Nothing
WScript.Quit 0
