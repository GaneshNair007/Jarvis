Add-Type -AssemblyName System.Speech

try {
    $engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine
    $choices = New-Object System.Speech.Recognition.Choices
    $choices.Add([string[]]@("Hey Jarvis", "Jarvis", "Ok Jarvis"))
    $builder = New-Object System.Speech.Recognition.GrammarBuilder
    $builder.Append($choices)
    $grammar = New-Object System.Speech.Recognition.Grammar($builder)
    $engine.LoadGrammar($grammar)
    Write-Output "SUCCESS: Windows native speech recognition grammar loaded cleanly."
} catch {
    Write-Output "ERROR: $($_.Exception.Message)"
}

