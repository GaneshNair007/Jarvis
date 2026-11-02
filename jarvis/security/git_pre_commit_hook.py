#!/usr/bin/env python3
"""
JARVIS Git Pre-Commit Secret Shield Hook
Audits staged git diffs against the 10-Layer Security Shield's EntropySecretDetector
and blocked regex patterns before allowing commits. Blocks any commit containing
plaintext API keys, tokens, or credentials.
"""

import sys
import subprocess
from jarvis.security.ten_layer_shield import GitShield


def main() -> int:
    try:
        # Run git diff --cached to inspect staged changes
        res = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
        diff_text = res.stdout
    except Exception as exc:
        print(f"[JARVIS-SECURITY] Warning: Could not inspect git diff: {exc}")
        return 0

    if not diff_text.strip():
        return 0

    shield = GitShield()
    passed, violations = shield.audit_git_diff(diff_text)

    if not passed:
        print("\n" + "=" * 78)
        print("[JARVIS 10-LAYER SHIELD] PRE-COMMIT BLOCKED: SENSITIVE CREDENTIAL DETECTED")
        print("=" * 78)
        for v in violations:
            print(f"  ❌ {v}")
        print("\nPlease redact secrets or use environment variables before committing.")
        print("=" * 78 + "\n")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
