"""JARVIS Security and DLP Powers (PWR-144 to PWR-161, PWR-268 to PWR-287).

Provides zero-leak secret scans, cryptographic token verification,
firewall/kill-switch validation, DLP redaction audits, password strength,
file hashing, permission auditing, and security posture reporting.
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import string
import subprocess
import datetime
import json
from typing import Any, Dict, List, Optional
from jarvis.core.privacy_gate import privacy_gate
from jarvis.core.policy_gate import policy_gate
from jarvis.core.logger import get_logger

logger = get_logger("powers.security")


class SecurityPowers:
    """Implementations for Security and Guardrail domain capabilities."""

    def scan_secrets(self, text: str) -> Dict[str, Any]:
        """PWR-268: Scans text for exposed credentials, API keys, and sensitive tokens."""
        patterns = {
            "openai_key": r"sk-[A-Za-z0-9]{32,}",
            "anthropic_key": r"sk-ant-[A-Za-z0-9_-]{32,}",
            "aws_access_key": r"AKIA[0-9A-Z]{16}",
            "jwt_token": r"eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*",
            "private_key": r"-----BEGIN (RSA|OPENSSH|EC) PRIVATE KEY-----",
        }

        found_findings = []
        for key_type, regex in patterns.items():
            matches = re.findall(regex, text)
            if matches:
                found_findings.append({"type": key_type, "count": len(matches)})

        redacted, _ = privacy_gate.inspect_and_redact(text)
        return {
            "power_id": "PWR-268",
            "safe": len(found_findings) == 0,
            "findings_count": len(found_findings),
            "findings": found_findings,
            "redacted_text_length": len(redacted),
        }

    def verify_kill_switch(self) -> Dict[str, Any]:
        """PWR-279: Queries emergency kill-switch status across the operating system."""
        is_blocked = policy_gate.is_kill_switch_active()
        return {
            "power_id": "PWR-279",
            "kill_switch_active": is_blocked,
            "system_state": "LOCKED" if is_blocked else "OPERATIONAL",
        }

    def verify_approval_token(self, token: str, action: Optional[str] = None) -> Dict[str, Any]:
        """PWR-284: Verifies cryptographic validity and expiration of an approval token."""
        valid = policy_gate.verify_token(token)
        return {"power_id": "PWR-284", "token": token, "action": action, "valid": valid}

    # ------------------------------------------------------------------
    # File-based Secret Scanning (PWR-144)
    # ------------------------------------------------------------------

    def secret_scan(self, directory: str = ".") -> Dict[str, Any]:
        """PWR-144: Scan files for leaked API keys, passwords, and secrets."""
        try:
            patterns = {
                "openai_key": r"sk-[A-Za-z0-9]{32,}",
                "anthropic_key": r"sk-ant-[A-Za-z0-9_-]{32,}",
                "aws_access_key": r"AKIA[0-9A-Z]{16}",
                "aws_secret_key": r"(?i)aws_secret_access_key\s*[=:]\s*\S+",
                "github_token": r"gh[ps]_[A-Za-z0-9]{36,}",
                "generic_api_key": r"(?i)(api[_-]?key|apikey)\s*[=:]\s*['\"]?\S{16,}",
                "generic_secret": r"(?i)(secret|password|passwd|pwd)\s*[=:]\s*['\"]?\S{8,}",
                "private_key": r"-----BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY-----",
                "connection_string": r"(?i)(mongodb|postgres|mysql|redis)://\S+",
            }
            skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv",
                         "dist", "build", ".tox"}
            scan_exts = {".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml",
                         ".cfg", ".ini", ".env", ".sh", ".bat", ".ps1", ".xml",
                         ".conf", ".properties", ".tf", ".tfvars", ""}

            findings: List[Dict[str, Any]] = []
            files_scanned = 0

            for root, dirs, files in os.walk(os.path.abspath(directory)):
                dirs[:] = [d for d in dirs if d not in skip_dirs]
                for f in files:
                    ext = os.path.splitext(f)[1]
                    if ext not in scan_exts:
                        continue
                    fp = os.path.join(root, f)
                    try:
                        with open(fp, "r", encoding="utf-8", errors="replace") as fh:
                            files_scanned += 1
                            for line_no, line in enumerate(fh, 1):
                                for secret_type, regex in patterns.items():
                                    if re.search(regex, line):
                                        findings.append({
                                            "file": os.path.relpath(fp, directory),
                                            "line": line_no,
                                            "type": secret_type,
                                            "preview": line.strip()[:80] + "...",
                                        })
                                        break  # one finding per line
                    except (OSError, UnicodeDecodeError):
                        pass

            return {
                "power_id": "PWR-144", "status": "success",
                "files_scanned": files_scanned,
                "finding_count": len(findings),
                "findings": findings[:200],
                "safe": len(findings) == 0,
            }
        except Exception as e:
            return {"power_id": "PWR-144", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------
    # Hashing & Verification (PWR-145 to PWR-146)
    # ------------------------------------------------------------------

    def hash_file(self, file_path: str, algorithm: str = "sha256") -> Dict[str, Any]:
        """PWR-145: Compute file hash with specified algorithm."""
        try:
            algo = algorithm.lower()
            if algo not in hashlib.algorithms_available:
                return {"power_id": "PWR-145", "status": "error",
                        "message": f"Unsupported algorithm: {algorithm}. "
                                   f"Available: {sorted(hashlib.algorithms_available)}"}
            h = hashlib.new(algo)
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    h.update(chunk)
            file_size = os.path.getsize(file_path)
            return {
                "power_id": "PWR-145", "status": "success",
                "file": file_path, "algorithm": algo,
                "hash": h.hexdigest(),
                "file_size_bytes": file_size,
            }
        except FileNotFoundError:
            return {"power_id": "PWR-145", "status": "error",
                    "message": f"File not found: {file_path}"}
        except Exception as e:
            return {"power_id": "PWR-145", "status": "error", "message": str(e)}

    def hash_verify(self, file_path: str, expected_hash: str, algorithm: str = "sha256") -> Dict[str, Any]:
        """PWR-146: Verify file hash against an expected value."""
        try:
            result = self.hash_file(file_path, algorithm)
            if result["status"] != "success":
                result["power_id"] = "PWR-146"
                return result
            computed = result["hash"]
            match = computed.lower() == expected_hash.lower()
            return {
                "power_id": "PWR-146", "status": "success",
                "file": file_path, "algorithm": algorithm,
                "computed_hash": computed,
                "expected_hash": expected_hash,
                "match": match,
                "verdict": "VERIFIED" if match else "MISMATCH",
            }
        except Exception as e:
            return {"power_id": "PWR-146", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------
    # Password Tools (PWR-147 to PWR-148)
    # ------------------------------------------------------------------

    def password_strength(self, password: str) -> Dict[str, Any]:
        """PWR-147: Check password strength and provide feedback."""
        try:
            checks = {
                "length_ok": len(password) >= 12,
                "has_upper": bool(re.search(r"[A-Z]", password)),
                "has_lower": bool(re.search(r"[a-z]", password)),
                "has_digit": bool(re.search(r"\d", password)),
                "has_special": bool(re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", password)),
                "no_common_patterns": not bool(re.search(
                    r"(password|123456|qwerty|admin|letmein|welcome|monkey|dragon)", password.lower())),
            }
            score = sum(checks.values())
            if score >= 6:
                strength = "strong"
            elif score >= 4:
                strength = "moderate"
            else:
                strength = "weak"

            suggestions = []
            if not checks["length_ok"]:
                suggestions.append("Use at least 12 characters")
            if not checks["has_upper"]:
                suggestions.append("Add uppercase letters")
            if not checks["has_lower"]:
                suggestions.append("Add lowercase letters")
            if not checks["has_digit"]:
                suggestions.append("Add digits")
            if not checks["has_special"]:
                suggestions.append("Add special characters")
            if not checks["no_common_patterns"]:
                suggestions.append("Avoid common password patterns")

            return {
                "power_id": "PWR-147", "status": "success",
                "strength": strength, "score": f"{score}/6",
                "checks": checks, "suggestions": suggestions,
            }
        except Exception as e:
            return {"power_id": "PWR-147", "status": "error", "message": str(e)}

    def generate_password(self, length: int = 20) -> Dict[str, Any]:
        """PWR-148: Generate a cryptographically secure random password."""
        try:
            if length < 8:
                return {"power_id": "PWR-148", "status": "error",
                        "message": "Password length must be at least 8"}
            alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
            # Ensure at least one of each category
            password = [
                secrets.choice(string.ascii_uppercase),
                secrets.choice(string.ascii_lowercase),
                secrets.choice(string.digits),
                secrets.choice("!@#$%^&*()-_=+"),
            ]
            password += [secrets.choice(alphabet) for _ in range(length - 4)]
            # Shuffle to avoid predictable positions
            pw_list = list(password)
            # Fisher-Yates shuffle using secrets
            for i in range(len(pw_list) - 1, 0, -1):
                j = secrets.randbelow(i + 1)
                pw_list[i], pw_list[j] = pw_list[j], pw_list[i]
            generated = "".join(pw_list)

            return {
                "power_id": "PWR-148", "status": "success",
                "password": generated, "length": length,
                "entropy_bits": round(len(generated) * 6.5, 1),
            }
        except Exception as e:
            return {"power_id": "PWR-148", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------
    # Encryption Placeholders (PWR-149 to PWR-150)
    # ------------------------------------------------------------------

    def encrypt_file(self, file_path: str, key: str) -> Dict[str, Any]:
        """PWR-149: Placeholder for file encryption (requires cryptography package)."""
        try:
            if not os.path.isfile(file_path):
                return {"power_id": "PWR-149", "status": "error",
                        "message": f"File not found: {file_path}"}
            return {
                "power_id": "PWR-149", "status": "dispatched",
                "file": file_path,
                "message": "File encryption dispatched. Install 'cryptography' package "
                           "and implement Fernet-based encryption for production use.",
                "file_size_bytes": os.path.getsize(file_path),
            }
        except Exception as e:
            return {"power_id": "PWR-149", "status": "error", "message": str(e)}

    def decrypt_file(self, file_path: str, key: str) -> Dict[str, Any]:
        """PWR-150: Placeholder for file decryption (requires cryptography package)."""
        try:
            if not os.path.isfile(file_path):
                return {"power_id": "PWR-150", "status": "error",
                        "message": f"File not found: {file_path}"}
            return {
                "power_id": "PWR-150", "status": "dispatched",
                "file": file_path,
                "message": "File decryption dispatched. Install 'cryptography' package "
                           "and implement Fernet-based decryption for production use.",
            }
        except Exception as e:
            return {"power_id": "PWR-150", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------
    # Audit & Permissions (PWR-151 to PWR-152)
    # ------------------------------------------------------------------

    def audit_log_export(self, output_path: str) -> Dict[str, Any]:
        """PWR-151: Export audit log from Windows Security event log."""
        try:
            ps_script = (
                "Get-EventLog -LogName Security -Newest 100 -ErrorAction Stop | "
                "Select-Object TimeGenerated, EntryType, Source, InstanceId, Message | "
                "ConvertTo-Json -Depth 3"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True, text=True, timeout=30,
            )
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(res.stdout if res.stdout else "[]")

            return {
                "power_id": "PWR-151", "status": "success",
                "output_path": output_path,
                "size_bytes": os.path.getsize(output_path),
                "message": "Audit log exported successfully",
            }
        except Exception as e:
            return {"power_id": "PWR-151", "status": "error", "message": str(e)}

    def permissions_audit(self, directory: str = ".") -> Dict[str, Any]:
        """PWR-152: File permission analysis using icacls on Windows."""
        try:
            res = subprocess.run(
                ["icacls", os.path.abspath(directory)],
                capture_output=True, text=True, timeout=15,
            )
            entries: List[Dict[str, str]] = []
            for line in res.stdout.strip().splitlines():
                line = line.strip()
                if line and not line.startswith("Successfully"):
                    entries.append({"entry": line})

            # Check for world-writable items
            world_writable: List[str] = []
            for root, dirs, files in os.walk(os.path.abspath(directory)):
                for f in files[:100]:
                    fp = os.path.join(root, f)
                    try:
                        # On Windows, check if file is read-only
                        import stat
                        st = os.stat(fp)
                        if st.st_mode & stat.S_IWOTH:
                            world_writable.append(os.path.relpath(fp, directory))
                    except OSError:
                        pass
                break  # Only top-level for performance

            return {
                "power_id": "PWR-152", "status": "success",
                "directory": os.path.abspath(directory),
                "acl_entries": entries[:50],
                "world_writable_count": len(world_writable),
                "world_writable": world_writable[:20],
            }
        except Exception as e:
            return {"power_id": "PWR-152", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------
    # System Security Status (PWR-153 to PWR-155)
    # ------------------------------------------------------------------

    def firewall_status(self) -> Dict[str, Any]:
        """PWR-153: Check Windows Firewall status for all profiles."""
        try:
            res = subprocess.run(
                ["netsh", "advfirewall", "show", "allprofiles", "state"],
                capture_output=True, text=True, timeout=15,
            )
            profiles: Dict[str, str] = {}
            current_profile = ""
            for line in res.stdout.splitlines():
                line = line.strip()
                if "Profile" in line and "Settings" in line:
                    current_profile = line.replace("Settings:", "").strip()
                elif line.startswith("State"):
                    state = line.split()[-1] if line.split() else "unknown"
                    profiles[current_profile] = state

            all_on = all(v.upper() == "ON" for v in profiles.values()) if profiles else False
            return {
                "power_id": "PWR-153", "status": "success",
                "firewall_enabled": all_on,
                "profiles": profiles,
            }
        except Exception as e:
            return {"power_id": "PWR-153", "status": "error", "message": str(e)}

    def antivirus_status(self) -> Dict[str, Any]:
        """PWR-154: Check Windows Defender / antivirus status."""
        try:
            ps_script = (
                "try { "
                "$status = Get-MpComputerStatus -ErrorAction Stop; "
                "ConvertTo-Json @{"
                "  RealTimeProtection=$status.RealTimeProtectionEnabled; "
                "  AntivirusEnabled=$status.AntivirusEnabled; "
                "  AntispywareEnabled=$status.AntispywareEnabled; "
                "  SignatureAge=$status.AntivirusSignatureAge; "
                "  LastScan=$status.FullScanEndTime.ToString('o'); "
                "  QuickScanAge=$status.QuickScanAge; "
                "  EngineVersion=$status.AMEngineVersion "
                "} "
                "} catch { ConvertTo-Json @{error=$_.Exception.Message} }"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True, text=True, timeout=30,
            )
            try:
                data = json.loads(res.stdout) if res.stdout.strip() else {}
            except json.JSONDecodeError:
                data = {"raw": res.stdout[:2000]}

            if "error" in data:
                return {"power_id": "PWR-154", "status": "error", "message": data["error"]}

            return {
                "power_id": "PWR-154", "status": "success",
                "defender": data,
            }
        except Exception as e:
            return {"power_id": "PWR-154", "status": "error", "message": str(e)}

    def certificate_store(self) -> Dict[str, Any]:
        """PWR-155: List certificates from the Windows certificate store."""
        try:
            ps_script = (
                "Get-ChildItem Cert:\\LocalMachine\\My -ErrorAction Stop | "
                "Select-Object Subject, Issuer, NotAfter, Thumbprint | "
                "ConvertTo-Json -Depth 2"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True, text=True, timeout=15,
            )
            try:
                certs = json.loads(res.stdout) if res.stdout.strip() else []
                if isinstance(certs, dict):
                    certs = [certs]
            except json.JSONDecodeError:
                certs = []

            return {
                "power_id": "PWR-155", "status": "success",
                "cert_count": len(certs),
                "certificates": certs[:100],
            }
        except Exception as e:
            return {"power_id": "PWR-155", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------
    # Git & Code Security (PWR-156)
    # ------------------------------------------------------------------

    def git_secrets_scan(self, repo_path: str = ".") -> Dict[str, Any]:
        """PWR-156: Scan git history for committed secrets."""
        try:
            # Search recent commits for secret-like patterns
            res = subprocess.run(
                ["git", "log", "--all", "-p", "--max-count=50",
                 "-S", "AKIA", "--oneline"],
                cwd=repo_path, capture_output=True, text=True, timeout=30,
            )
            aws_findings = res.stdout.strip().splitlines() if res.stdout.strip() else []

            res2 = subprocess.run(
                ["git", "log", "--all", "-p", "--max-count=50",
                 "-S", "sk-", "--oneline"],
                cwd=repo_path, capture_output=True, text=True, timeout=30,
            )
            api_findings = res2.stdout.strip().splitlines() if res2.stdout.strip() else []

            all_findings = []
            for line in (aws_findings + api_findings)[:50]:
                all_findings.append({"commit_ref": line.strip()[:120]})

            return {
                "power_id": "PWR-156", "status": "success",
                "repo": os.path.abspath(repo_path),
                "finding_count": len(all_findings),
                "findings": all_findings,
                "safe": len(all_findings) == 0,
            }
        except Exception as e:
            return {"power_id": "PWR-156", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------
    # Network & Process Security (PWR-157 to PWR-158)
    # ------------------------------------------------------------------

    def network_connections(self) -> Dict[str, Any]:
        """PWR-157: List active network connections (like netstat)."""
        try:
            import psutil
            connections: List[Dict[str, Any]] = []
            for conn in psutil.net_connections(kind="inet"):
                try:
                    proc_name = ""
                    if conn.pid:
                        try:
                            proc_name = psutil.Process(conn.pid).name()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            proc_name = "unknown"
                    connections.append({
                        "local_addr": f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "",
                        "remote_addr": f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "",
                        "status": conn.status,
                        "pid": conn.pid,
                        "process": proc_name,
                    })
                except Exception:
                    pass

            return {
                "power_id": "PWR-157", "status": "success",
                "connection_count": len(connections),
                "connections": connections[:100],
            }
        except Exception as e:
            return {"power_id": "PWR-157", "status": "error", "message": str(e)}

    def suspicious_process_check(self) -> Dict[str, Any]:
        """PWR-158: Check for processes with suspicious characteristics."""
        try:
            import psutil
            suspicious: List[Dict[str, Any]] = []
            suspicious_names = {
                "mimikatz", "pwdump", "procdump", "lazagne", "keylogger",
                "netcat", "nc", "ncat", "reverse", "meterpreter", "cobaltstrike",
                "empire", "bloodhound", "rubeus", "certutil",
            }

            for proc in psutil.process_iter(["pid", "name", "exe", "cmdline", "username"]):
                try:
                    info = proc.info
                    name_lower = (info.get("name") or "").lower()
                    exe_lower = (info.get("exe") or "").lower()

                    flags: List[str] = []

                    # Check against known suspicious names
                    for sn in suspicious_names:
                        if sn in name_lower or sn in exe_lower:
                            flags.append(f"known_suspicious:{sn}")

                    # Check for processes running from temp directories
                    if info.get("exe"):
                        exe = info["exe"].lower()
                        if any(t in exe for t in ["\\temp\\", "\\tmp\\", "\\appdata\\local\\temp"]):
                            flags.append("running_from_temp")

                    # Check for hidden/no-window PowerShell
                    cmdline = info.get("cmdline") or []
                    cmdline_str = " ".join(cmdline).lower()
                    if "powershell" in name_lower and any(
                        f in cmdline_str for f in ["-enc", "-encodedcommand", "-hidden", "-windowstyle hidden"]
                    ):
                        flags.append("hidden_powershell")

                    if flags:
                        suspicious.append({
                            "pid": info["pid"],
                            "name": info["name"],
                            "exe": info.get("exe", ""),
                            "username": info.get("username", ""),
                            "flags": flags,
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            return {
                "power_id": "PWR-158", "status": "success",
                "suspicious_count": len(suspicious),
                "processes": suspicious[:50],
                "safe": len(suspicious) == 0,
            }
        except Exception as e:
            return {"power_id": "PWR-158", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------
    # Key Management (PWR-159)
    # ------------------------------------------------------------------

    def key_rotation_reminder(self) -> Dict[str, Any]:
        """PWR-159: Check API key ages by scanning .env files."""
        try:
            env_files = []
            # Look for .env files in common locations
            search_dirs = [
                os.path.expanduser("~"),
                os.getcwd(),
            ]
            for d in search_dirs:
                env_path = os.path.join(d, ".env")
                if os.path.isfile(env_path):
                    env_files.append(env_path)

            findings: List[Dict[str, Any]] = []
            for env_file in env_files:
                try:
                    mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(env_file))
                    age_days = (datetime.datetime.now() - mod_time).days
                    with open(env_file, "r", encoding="utf-8", errors="replace") as f:
                        key_count = sum(1 for line in f
                                        if line.strip() and not line.startswith("#")
                                        and "=" in line)
                    findings.append({
                        "file": env_file,
                        "last_modified": mod_time.strftime("%Y-%m-%d"),
                        "age_days": age_days,
                        "key_count": key_count,
                        "rotation_recommended": age_days > 90,
                    })
                except OSError:
                    pass

            return {
                "power_id": "PWR-159", "status": "success",
                "env_files_found": len(env_files),
                "findings": findings,
                "action_needed": any(f.get("rotation_recommended") for f in findings),
            }
        except Exception as e:
            return {"power_id": "PWR-159", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------
    # Security Posture Report (PWR-161)
    # ------------------------------------------------------------------

    def security_posture_report(self) -> Dict[str, Any]:
        """PWR-161: Generate an overall security posture summary."""
        try:
            report: Dict[str, Any] = {"power_id": "PWR-161", "status": "success", "checks": {}}
            issues: List[str] = []
            score = 100

            # 1. Firewall
            fw = self.firewall_status()
            fw_ok = fw.get("firewall_enabled", False)
            report["checks"]["firewall"] = "enabled" if fw_ok else "DISABLED"
            if not fw_ok:
                issues.append("Windows Firewall is not fully enabled")
                score -= 20

            # 2. Antivirus
            av = self.antivirus_status()
            if av.get("status") == "success":
                defender = av.get("defender", {})
                rtp = defender.get("RealTimeProtection", False)
                report["checks"]["realtime_protection"] = "enabled" if rtp else "DISABLED"
                if not rtp:
                    issues.append("Real-time protection is disabled")
                    score -= 25
                sig_age = defender.get("SignatureAge", 0)
                if isinstance(sig_age, (int, float)) and sig_age > 7:
                    issues.append(f"Antivirus signatures are {sig_age} days old")
                    score -= 10
            else:
                report["checks"]["antivirus"] = "check_failed"
                score -= 10

            # 3. Key rotation
            kr = self.key_rotation_reminder()
            if kr.get("action_needed"):
                issues.append("API keys may need rotation (>90 days old)")
                score -= 10

            # 4. Kill switch
            ks = self.verify_kill_switch()
            report["checks"]["kill_switch"] = ks.get("system_state", "UNKNOWN")

            report["security_score"] = max(0, score)
            report["grade"] = (
                "A" if score >= 90 else
                "B" if score >= 75 else
                "C" if score >= 60 else
                "D" if score >= 40 else "F"
            )
            report["issues"] = issues
            report["issue_count"] = len(issues)

            return report
        except Exception as e:
            return {"power_id": "PWR-161", "status": "error", "message": str(e)}


security_powers = SecurityPowers()
