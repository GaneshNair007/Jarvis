"""
Automated verification tests for Privacy Gate DLP & secret redaction.
"""

from jarvis.core.privacy_gate import privacy_gate

def test_secret_redaction_patterns():
    text = (
        "OpenAI: sk-abcdefghijklmnopqrstuvwxyz123456\n"
        "AWS: AKIA1234567890ABCDEF\n"
        "GitHub: ghp_123456789012345678901234567890123456\n"
        "OTP code: 948201\n"
        "Credit Card: 4532015012345678"
    )

    redacted, findings = privacy_gate.inspect_and_redact(text)
    assert "[REDACTED_OPENAI_KEY]" in redacted
    assert "[REDACTED_AWS_KEY]" in redacted
    assert "[REDACTED_GITHUB_TOKEN]" in redacted
    assert "[REDACTED_OTP]" in redacted
    assert "[REDACTED_CREDIT_CARD]" in redacted
    assert len(findings) >= 5

def test_context_minimization():
    large_text = "start directives " + ("x" * 20000) + " end summary"
    minimized = privacy_gate.minimize_context(large_text, max_chars=4000)
    assert len(minimized) < 6000
    assert "start directives" in minimized
    assert "end summary" in minimized
    assert "Context Minimized" in minimized
