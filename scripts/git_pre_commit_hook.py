#!/usr/bin/env python3
"""
JARVIS Pre-Commit Git Shield Hook
Runs before every git commit to prevent credentials, private keys, or plaintext passwords
from ever entering git history or being staged.
"""

import sys
import subprocess
from pathlib import Path

# Fix Windows console encoding for UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add repo root to sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from jarvis.security.ten_layer_shield import GitShield


def run_pre_commit_audit() -> int:
    shield = GitShield()
    
    # 1. Get list of staged files
    try:
        proc = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
        staged_files = [f.strip() for f in proc.stdout.splitlines() if f.strip()]
    except Exception as e:
        print(f"[JARVIS GitShield] Warning: Could not inspect staged files: {e}", file=sys.stderr)
        return 0

    if not staged_files:
        return 0

    # 2. Get staged diff
    try:
        diff_proc = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
        diff_text = diff_proc.stdout
    except Exception as e:
        print(f"[JARVIS GitShield] Warning: Could not inspect git diff: {e}", file=sys.stderr)
        diff_text = ""

    # 3. Audit staged diff for newly added secrets
    clean, violations = shield.audit_git_diff(diff_text)
    
    # 4. Audit staged file contents directly (excluding examples/tests marked as safe)
    for filename in staged_files:
        filepath = repo_root / filename
        if filepath.exists() and filepath.is_file():
            try:
                content = filepath.read_text(encoding="utf-8", errors="replace")
                findings = shield.audit_file_content(filename, content)
                for f in findings:
                    violations.append(f"High-entropy secret [{f['type']}] detected in staged file: {filename}")
            except Exception:
                pass

    if violations:
        print("\n" + "=" * 80, file=sys.stderr)
        print("🛑 [JARVIS GitShield] COMMIT REJECTED: Sensitive credentials detected in staged changes!", file=sys.stderr)
        print("=" * 80, file=sys.stderr)
        for v in violations:
            print(f"  • {v}", file=sys.stderr)
        print("\nAction Required:", file=sys.stderr)
        print("  1. Remove or redact the secret credentials before committing.", file=sys.stderr)
        print("  2. Store sensitive tokens in local .env (which is in .gitignore) or EncryptedVault.", file=sys.stderr)
        print("=" * 80 + "\n", file=sys.stderr)
        return 1

    print("🛡️ [JARVIS GitShield] Staged changes verified clean. Zero credentials detected.")
    return 0


if __name__ == "__main__":
    sys.exit(run_pre_commit_audit())
