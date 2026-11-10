<#
.SYNOPSIS
    JARVIS Windows Native Speech Recognition Listener Daemon (R1)
.DESCRIPTION
    Host-native background speech recognition bridge using System.Speech.Recognition.
    Operates with dual grammars (Wake Word + continuous DictationGrammar).
    Streams recognition events as JSON lines to standard output with immediate flush.
.PARAMETER Mode
    Input mode: 'mic' (default) for live host microphone, 'wav' for single wave file recognition.
.PARAMETER WaveFile
    Path to wave file when Mode is 'wav'.
.PARAMETER HeartbeatInterval
    Seconds between periodic heartbeat events (default: 10).
#>
param(
    [string]$Mode = "mic",
    [string]$WaveFile = "",
    [int]$HeartbeatInterval = 10
)

$ErrorActionPreference = "Continue"

function Write-JsonEvent {
    param(
        [string]$EventName,
        [hashtable]$Data = @{}
    )
    $obj = [ordered]@{
        event     = $EventName
        type      = $EventName
        timestamp = [double](Get-Date -UFormat %s)
    }
    if ($Data -ne $null) {
        foreach ($k in $Data.Keys) {
            $obj[$k] = $Data[$k]
        }
    }
    $json = ConvertTo-Json -Compress $obj
    [Console]::Out.WriteLine($json)
    [Console]::Out.Flush()
}

try {
    Add-Type -AssemblyName System.Speech
} catch {
    Write-JsonEvent "ERROR" @{
        message    = "Failed to load System.Speech assembly: $($_.Exception.Message)"
        error_type = "ASSEMBLY_LOAD_ERROR"
    }
    exit 1
}

$engine = $null

try {
    $engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine

    # 1. Wake Phrase Grammar (Acoustic keyword detection)
    $wakePhrases = @("Hey Jarvis", "Jarvis", "Ok Jarvis", "Hey Jervis", "Jervis")
    $choices = New-Object System.Speech.Recognition.Choices
    $choices.Add([string[]]$wakePhrases)

    $builder = New-Object System.Speech.Recognition.GrammarBuilder
    $builder.Append($choices)

    $wakeGrammar = New-Object System.Speech.Recognition.Grammar($builder)
    $wakeGrammar.Name = "WakeWord"
    $engine.LoadGrammar($wakeGrammar)

    # 2. Continuous Dictation Grammar for Spoken Commands
    $dictGrammar = New-Object System.Speech.Recognition.DictationGrammar
    $dictGrammar.Name = "Dictation"
    $engine.LoadGrammar($dictGrammar)

    # 3. Register Recognition Event Handler
    Register-ObjectEvent -InputObject $engine -EventName "SpeechRecognized" -Action {
        $res = $Event.SourceEventArgs.Result
        if ($res -ne $null) {
            $dur = 0.0
            if ($res.Audio) {
                $dur = [double]$res.Audio.Duration.TotalSeconds
            }
            $grammarName = if ($res.Grammar) { $res.Grammar.Name } else { "Unknown" }
            $text = $res.Text
            $conf = [math]::Round([double]$res.Confidence, 3)

            $lower = $text.ToLower().Trim()
            $isWakeOnly = ($grammarName -eq "WakeWord")

            # Check if text starts with wake phrase
            $matchedWake = $null
            foreach ($wp in @("hey jarvis", "jarvis", "ok jarvis", "hey jervis", "jervis")) {
                if ($lower -eq $wp) {
                    $matchedWake = $wp
                    $isWakeOnly = $true
                    break
                } elseif ($lower.StartsWith($wp + " ") -or $lower.StartsWith($wp + ",")) {
                    $matchedWake = $wp
                    break
                }
            }

            if ($isWakeOnly) {
                Write-JsonEvent "WAKE" @{
                    phrase       = $text
                    confidence   = $conf
                    duration_sec = [math]::Round($dur, 3)
                    grammar      = $grammarName
                }
            } elseif ($matchedWake -ne $null) {
                # Compound utterance e.g. "Hey Jarvis, check system health"
                Write-JsonEvent "WAKE" @{
                    phrase       = $matchedWake
                    full_text    = $text
                    confidence   = $conf
                    duration_sec = [math]::Round($dur, 3)
                    grammar      = $grammarName
                }
                # Also emit the SPEECH part
                $cmd = $text.Substring($matchedWake.Length).Trim(" ,.:;!")
                if ($cmd.Length -gt 0) {
                    Write-JsonEvent "SPEECH" @{
                        text         = $cmd
                        confidence   = $conf
                        duration_sec = [math]::Round($dur, 3)
                        grammar      = $grammarName
                    }
                }
            } else {
                # General Dictation Speech
                Write-JsonEvent "SPEECH" @{
                    text         = $text
                    confidence   = $conf
                    duration_sec = [math]::Round($dur, 3)
                    grammar      = $grammarName
                }
            }
        }
    } | Out-Null

    # 4. Register Recognition Error Handler
    Register-ObjectEvent -InputObject $engine -EventName "RecognizeCompleted" -Action {
        $e = $Event.SourceEventArgs
        if ($e.Error -ne $null) {
            Write-JsonEvent "ERROR" @{
                message    = $e.Error.Message
                error_type = "RECOGNITION_ERROR"
            }
        }
    } | Out-Null

    # 5. Background Stdin listener thread for clean shutdown commands (in mic mode)
    if ($Mode -eq "mic") {
        $stdinThread = [System.Threading.Thread]::new([System.Threading.ThreadStart]{
            try {
                while ($true) {
                    $line = [Console]::In.ReadLine()
                    if ($line -eq $null -or $line -eq "quit" -or $line -eq "exit") {
                        [Console]::Out.WriteLine('{"event":"STOPPED","type":"STOPPED","timestamp":' + [double](Get-Date -UFormat %s) + '}')
                        [Console]::Out.Flush()
                        [System.Environment]::Exit(0)
                    }
                }
            } catch {
                # Stdin closed or interrupted
                [System.Environment]::Exit(0)
            }
        })
        $stdinThread.IsBackground = $true
        $stdinThread.Start()
    }

    # 6. Configure Audio Input
    if ($Mode -eq "wav") {
        if (-not (Test-Path $WaveFile)) {
            Write-JsonEvent "ERROR" @{
                message    = "Wave file not found: $WaveFile"
                error_type = "FILE_NOT_FOUND"
            }
            exit 1
        }
        $fullPath = (Resolve-Path $WaveFile).Path
        $engine.SetInputToWaveFile($fullPath)
        Write-JsonEvent "READY" @{
            mode       = "wav"
            file       = $fullPath
            recognizer = $engine.RecognizerInfo.Name
        }
        $res = $engine.Recognize()
        if ($res -ne $null) {
            $dur = 0.0
            if ($res.Audio) {
                $dur = [double]$res.Audio.Duration.TotalSeconds
            }
            $grammarName = if ($res.Grammar) { $res.Grammar.Name } else { "Unknown" }
            $text = $res.Text
            $conf = [math]::Round([double]$res.Confidence, 3)

            $lower = $text.ToLower().Trim()
            $isWakeOnly = ($grammarName -eq "WakeWord")
            $matchedWake = $null
            foreach ($wp in @("hey jarvis", "jarvis", "ok jarvis", "hey jervis", "jervis")) {
                if ($lower -eq $wp) {
                    $matchedWake = $wp
                    $isWakeOnly = $true
                    break
                } elseif ($lower.StartsWith($wp + " ") -or $lower.StartsWith($wp + ",")) {
                    $matchedWake = $wp
                    break
                }
            }

            if ($isWakeOnly) {
                Write-JsonEvent "WAKE" @{
                    phrase       = $text
                    confidence   = $conf
                    duration_sec = [math]::Round($dur, 3)
                    grammar      = $grammarName
                }
            } elseif ($matchedWake -ne $null) {
                Write-JsonEvent "WAKE" @{
                    phrase       = $matchedWake
                    full_text    = $text
                    confidence   = $conf
                    duration_sec = [math]::Round($dur, 3)
                    grammar      = $grammarName
                }
                $cmd = $text.Substring($matchedWake.Length).Trim(" ,.:;!")
                if ($cmd.Length -gt 0) {
                    Write-JsonEvent "SPEECH" @{
                        text         = $cmd
                        confidence   = $conf
                        duration_sec = [math]::Round($dur, 3)
                        grammar      = $grammarName
                    }
                }
            } else {
                Write-JsonEvent "SPEECH" @{
                    text         = $text
                    confidence   = $conf
                    duration_sec = [math]::Round($dur, 3)
                    grammar      = $grammarName
                }
            }
        }
        return
    } else {
        # Mic mode
        $engine.SetInputToDefaultAudioDevice()
        Write-JsonEvent "READY" @{
            mode       = "mic"
            recognizer = $engine.RecognizerInfo.Name
        }
        $engine.RecognizeAsync([System.Speech.Recognition.RecognizeMode]::Multiple)

        # Main event loop with periodic heartbeats
        $lastHeartbeat = [double](Get-Date -UFormat %s)
        while ($true) {
            Wait-Event -Timeout 1 | Out-Null
            $now = [double](Get-Date -UFormat %s)
            if (($now - $lastHeartbeat) -ge $HeartbeatInterval) {
                Write-JsonEvent "HEARTBEAT" @{
                    status = "listening"
                    device = "default"
                }
                $lastHeartbeat = $now
            }
        }
    }
} catch {
    Write-JsonEvent "ERROR" @{
        message    = $_.Exception.Message
        error_type = "AUDIO_INIT_ERROR"
    }
    exit 1
} finally {
    if ($engine -ne $null) {
        try {
            # Only cancel if actively running
            if ($Mode -eq "mic") {
                $engine.RecognizeAsyncCancel()
            }
        } catch {}
        try {
            $engine.Dispose()
        } catch {}
    }
}
exit 0
