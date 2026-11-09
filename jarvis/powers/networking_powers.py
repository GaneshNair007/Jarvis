"""
JARVIS Networking Powers (PWR-127 to PWR-143)
Full-stack network diagnostics and monitoring:
  - Ping, traceroute, DNS lookup, port scanning
  - Internet connectivity checks, SSL cert inspection
  - Public IP, speed estimates, bandwidth monitoring
  - ARP table, netstat, DNS flush, WiFi scan, VPN status
"""

from __future__ import annotations

import hashlib
import os
import re
import socket
import ssl
import subprocess
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class NetworkingPowers:
    """Network diagnostics, scanning, and monitoring powers."""

    # Default ports to scan when none specified
    DEFAULT_PORTS: List[int] = [22, 80, 443, 3000, 5432, 6379, 8000, 11434]

    # ------------------------------------------------------------------ #
    # PWR-127  Ping
    # ------------------------------------------------------------------ #
    @staticmethod
    def ping(host: str, count: int = 4) -> Dict[str, Any]:
        """PWR-127: ICMP/TCP ping with latency statistics."""
        try:
            flag = "-n" if os.name == "nt" else "-c"
            result = subprocess.run(
                ["ping", flag, str(count), host],
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout + result.stderr

            # Parse latency stats from Windows ping output
            stats: Dict[str, Any] = {"raw": output.strip()}
            # Windows: Minimum = 1ms, Maximum = 3ms, Average = 2ms
            avg_match = re.search(r"Average\s*=\s*(\d+)\s*ms", output, re.IGNORECASE)
            min_match = re.search(r"Minimum\s*=\s*(\d+)\s*ms", output, re.IGNORECASE)
            max_match = re.search(r"Maximum\s*=\s*(\d+)\s*ms", output, re.IGNORECASE)
            # Linux: rtt min/avg/max/mdev = ...
            rtt_match = re.search(
                r"rtt\s+min/avg/max/mdev\s*=\s*([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)",
                output,
            )

            if avg_match:
                stats["avg_ms"] = float(avg_match.group(1))
            if min_match:
                stats["min_ms"] = float(min_match.group(1))
            if max_match:
                stats["max_ms"] = float(max_match.group(1))
            if rtt_match:
                stats["min_ms"] = float(rtt_match.group(1))
                stats["avg_ms"] = float(rtt_match.group(2))
                stats["max_ms"] = float(rtt_match.group(3))

            # Packet loss
            loss_match = re.search(r"(\d+)%\s*(packet\s+)?loss", output, re.IGNORECASE)
            if loss_match:
                stats["packet_loss_pct"] = int(loss_match.group(1))

            reachable = result.returncode == 0
            return {
                "power_id": "PWR-127",
                "status": "success" if reachable else "host_unreachable",
                "host": host,
                "count": count,
                "reachable": reachable,
                **stats,
            }
        except subprocess.TimeoutExpired:
            return {"power_id": "PWR-127", "status": "timeout", "host": host, "message": "Ping timed out"}
        except Exception as e:
            return {"power_id": "PWR-127", "status": "error", "host": host, "message": str(e)}

    # ------------------------------------------------------------------ #
    # PWR-128  Traceroute
    # ------------------------------------------------------------------ #
    @staticmethod
    def traceroute(host: str) -> Dict[str, Any]:
        """PWR-128: Multi-hop network path trace."""
        try:
            cmd = ["tracert", "-d", host] if os.name == "nt" else ["traceroute", "-n", host]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            output = (result.stdout + result.stderr).strip()

            hops: List[Dict[str, Any]] = []
            for line in output.splitlines():
                # Windows: "  1    <1 ms    <1 ms    <1 ms  192.168.1.1"
                hop_match = re.match(r"\s*(\d+)\s+(.+?)\s+([\d.]+)\s*$", line)
                if hop_match:
                    hops.append(
                        {
                            "hop": int(hop_match.group(1)),
                            "ip": hop_match.group(3),
                            "timing": hop_match.group(2).strip(),
                        }
                    )

            return {
                "power_id": "PWR-128",
                "status": "success",
                "host": host,
                "hop_count": len(hops),
                "hops": hops,
                "raw": output,
            }
        except subprocess.TimeoutExpired:
            return {"power_id": "PWR-128", "status": "timeout", "host": host, "message": "Traceroute timed out (60s)"}
        except Exception as e:
            return {"power_id": "PWR-128", "status": "error", "host": host, "message": str(e)}

    # ------------------------------------------------------------------ #
    # PWR-129  DNS Lookup
    # ------------------------------------------------------------------ #
    @staticmethod
    def dns_lookup(domain: str, record_type: str = "A") -> Dict[str, Any]:
        """PWR-129: DNS resolution using socket and nslookup fallback."""
        try:
            results: List[str] = []

            if record_type.upper() == "A":
                # Fast path via socket
                infos = socket.getaddrinfo(domain, None, socket.AF_INET, socket.SOCK_STREAM)
                results = list({info[4][0] for info in infos})
            elif record_type.upper() == "AAAA":
                infos = socket.getaddrinfo(domain, None, socket.AF_INET6, socket.SOCK_STREAM)
                results = list({info[4][0] for info in infos})
            else:
                # Fallback to nslookup for MX, CNAME, TXT, etc.
                proc = subprocess.run(
                    ["nslookup", f"-type={record_type}", domain],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                results = [proc.stdout.strip()]

            return {
                "power_id": "PWR-129",
                "status": "success",
                "domain": domain,
                "record_type": record_type.upper(),
                "addresses": results,
            }
        except socket.gaierror as e:
            return {
                "power_id": "PWR-129",
                "status": "dns_failure",
                "domain": domain,
                "record_type": record_type.upper(),
                "message": str(e),
            }
        except Exception as e:
            return {"power_id": "PWR-129", "status": "error", "domain": domain, "message": str(e)}

    # ------------------------------------------------------------------ #
    # PWR-130  Port Scan
    # ------------------------------------------------------------------ #
    def port_scan(self, host: str = "127.0.0.1", ports: Optional[List[int]] = None) -> Dict[str, Any]:
        """PWR-130: TCP connect scan on specified or common ports."""
        scan_ports = ports or self.DEFAULT_PORTS
        open_ports: List[Dict[str, Any]] = []
        closed_ports: List[int] = []

        try:
            for port in scan_ports:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1.0)
                try:
                    result = sock.connect_ex((host, port))
                    if result == 0:
                        # Try to grab service banner
                        service = ""
                        try:
                            service = socket.getservbyport(port, "tcp")
                        except OSError:
                            pass
                        open_ports.append({"port": port, "state": "open", "service": service})
                    else:
                        closed_ports.append(port)
                finally:
                    sock.close()

            return {
                "power_id": "PWR-130",
                "status": "success",
                "host": host,
                "open_ports": open_ports,
                "closed_ports": closed_ports,
                "total_scanned": len(scan_ports),
            }
        except Exception as e:
            return {"power_id": "PWR-130", "status": "error", "host": host, "message": str(e)}

    # ------------------------------------------------------------------ #
    # PWR-131  Internet Connectivity Check
    # ------------------------------------------------------------------ #
    @staticmethod
    def check_internet() -> Dict[str, Any]:
        """PWR-131: Quick internet connectivity test via DNS + TCP."""
        checks: Dict[str, Any] = {"dns": False, "tcp": False}
        try:
            # DNS resolution test
            addr = socket.getaddrinfo("google.com", 443, socket.AF_INET, socket.SOCK_STREAM)
            if addr:
                checks["dns"] = True
                ip = addr[0][4][0]

                # TCP connect test
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                try:
                    sock.connect((ip, 443))
                    checks["tcp"] = True
                finally:
                    sock.close()

            connected = checks["dns"] and checks["tcp"]
            return {
                "power_id": "PWR-131",
                "status": "connected" if connected else "limited",
                "checks": checks,
                "connected": connected,
            }
        except Exception as e:
            return {
                "power_id": "PWR-131",
                "status": "disconnected",
                "checks": checks,
                "connected": False,
                "message": str(e),
            }

    # ------------------------------------------------------------------ #
    # PWR-132  Network Interfaces
    # ------------------------------------------------------------------ #
    @staticmethod
    def get_network_interfaces() -> Dict[str, Any]:
        """PWR-132: List local network interfaces and IP addresses."""
        try:
            interfaces: List[Dict[str, Any]] = []

            # Try psutil first for rich info
            try:
                import psutil

                addrs = psutil.net_if_addrs()
                stats = psutil.net_if_stats()
                for iface_name, addr_list in addrs.items():
                    iface_info: Dict[str, Any] = {
                        "name": iface_name,
                        "addresses": [],
                    }
                    if iface_name in stats:
                        s = stats[iface_name]
                        iface_info["is_up"] = s.isup
                        iface_info["speed_mbps"] = s.speed
                        iface_info["mtu"] = s.mtu

                    for addr in addr_list:
                        entry: Dict[str, str] = {"address": addr.address}
                        if addr.family == socket.AF_INET:
                            entry["family"] = "IPv4"
                        elif addr.family == socket.AF_INET6:
                            entry["family"] = "IPv6"
                        else:
                            entry["family"] = "MAC" if addr.family.name == "AF_LINK" else str(addr.family)
                        if addr.netmask:
                            entry["netmask"] = addr.netmask
                        iface_info["addresses"].append(entry)

                    interfaces.append(iface_info)
            except ImportError:
                # Fallback: hostname-based
                hostname = socket.gethostname()
                ips = socket.getaddrinfo(hostname, None)
                seen = set()
                for info in ips:
                    ip = info[4][0]
                    if ip not in seen:
                        seen.add(ip)
                        interfaces.append({"name": "unknown", "addresses": [{"address": ip}]})

            return {
                "power_id": "PWR-132",
                "status": "success",
                "hostname": socket.gethostname(),
                "interface_count": len(interfaces),
                "interfaces": interfaces,
            }
        except Exception as e:
            return {"power_id": "PWR-132", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------ #
    # PWR-133  Whois Lookup
    # ------------------------------------------------------------------ #
    @staticmethod
    def whois_lookup(domain: str) -> Dict[str, Any]:
        """PWR-133: Basic WHOIS lookup via subprocess."""
        try:
            # Try system whois command
            result = subprocess.run(
                ["whois", domain],
                capture_output=True,
                text=True,
                timeout=15,
            )
            output = (result.stdout + result.stderr).strip()

            if result.returncode != 0 and not output:
                return {
                    "power_id": "PWR-133",
                    "status": "unavailable",
                    "domain": domain,
                    "message": "whois command not found or failed. Install a whois client.",
                }

            # Parse common fields
            parsed: Dict[str, str] = {}
            for key in ["Registrar", "Creation Date", "Expiration Date", "Name Server", "Domain Name"]:
                match = re.search(rf"{key}:\s*(.+)", output, re.IGNORECASE)
                if match:
                    parsed[key.lower().replace(" ", "_")] = match.group(1).strip()

            return {
                "power_id": "PWR-133",
                "status": "success",
                "domain": domain,
                "parsed": parsed,
                "raw": output[:2000],
            }
        except FileNotFoundError:
            return {
                "power_id": "PWR-133",
                "status": "unavailable",
                "domain": domain,
                "message": "whois command not found on this system.",
            }
        except subprocess.TimeoutExpired:
            return {"power_id": "PWR-133", "status": "timeout", "domain": domain, "message": "Whois timed out"}
        except Exception as e:
            return {"power_id": "PWR-133", "status": "error", "domain": domain, "message": str(e)}

    # ------------------------------------------------------------------ #
    # PWR-135  Speed Test Estimate
    # ------------------------------------------------------------------ #
    @staticmethod
    def speed_test_estimate() -> Dict[str, Any]:
        """PWR-135: Rough download speed estimate by timing a small HTTP fetch."""
        try:
            import urllib.request

            # ~1 MB test file from a public CDN
            test_urls = [
                "http://speedtest.tele2.net/1MB.zip",
                "http://proof.ovh.net/files/1Mb.dat",
            ]

            for url in test_urls:
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "JARVIS-SpeedTest/1.0"})
                    start = time.perf_counter()
                    with urllib.request.urlopen(req, timeout=20) as resp:
                        data = resp.read()
                    elapsed = time.perf_counter() - start

                    bytes_downloaded = len(data)
                    mbps = (bytes_downloaded * 8) / (elapsed * 1_000_000)

                    return {
                        "power_id": "PWR-135",
                        "status": "success",
                        "url": url,
                        "bytes_downloaded": bytes_downloaded,
                        "elapsed_seconds": round(elapsed, 3),
                        "estimated_mbps": round(mbps, 2),
                        "note": "Rough estimate based on a small file download",
                    }
                except Exception:
                    continue

            return {
                "power_id": "PWR-135",
                "status": "error",
                "message": "All test URLs failed. Check internet connectivity.",
            }
        except Exception as e:
            return {"power_id": "PWR-135", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------ #
    # PWR-136  Public IP
    # ------------------------------------------------------------------ #
    @staticmethod
    def get_public_ip() -> Dict[str, Any]:
        """PWR-136: Fetch the machine's public IP address."""
        try:
            import urllib.request
            import json

            services = [
                ("https://httpbin.org/ip", lambda d: json.loads(d).get("origin", "")),
                ("https://api.ipify.org?format=json", lambda d: json.loads(d).get("ip", "")),
                ("https://ifconfig.me/ip", lambda d: d.strip()),
            ]

            for url, parser in services:
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        raw = resp.read().decode("utf-8")
                    ip = parser(raw)
                    if ip:
                        return {
                            "power_id": "PWR-136",
                            "status": "success",
                            "public_ip": ip,
                            "source": url,
                        }
                except Exception:
                    continue

            return {"power_id": "PWR-136", "status": "error", "message": "All public IP services unreachable."}
        except Exception as e:
            return {"power_id": "PWR-136", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------ #
    # PWR-137  SSL Certificate Check
    # ------------------------------------------------------------------ #
    @staticmethod
    def check_ssl_cert(host: str, port: int = 443) -> Dict[str, Any]:
        """PWR-137: TLS handshake to inspect remote SSL certificate."""
        try:
            context = ssl.create_default_context()
            with socket.create_connection((host, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()

            if not cert:
                return {"power_id": "PWR-137", "status": "error", "host": host, "message": "No certificate returned"}

            not_after = cert.get("notAfter", "")
            not_before = cert.get("notBefore", "")
            subject = dict(x[0] for x in cert.get("subject", ()))
            issuer = dict(x[0] for x in cert.get("issuer", ()))

            # Parse expiry
            days_remaining = None
            if not_after:
                try:
                    expiry_dt = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
                    days_remaining = (expiry_dt - datetime.now(timezone.utc)).days
                except ValueError:
                    pass

            return {
                "power_id": "PWR-137",
                "status": "success",
                "host": host,
                "port": port,
                "subject": subject,
                "issuer": issuer,
                "not_before": not_before,
                "not_after": not_after,
                "days_remaining": days_remaining,
                "san": [entry[1] for entry in cert.get("subjectAltName", ())],
                "serial_number": cert.get("serialNumber", ""),
                "expired": days_remaining is not None and days_remaining < 0,
            }
        except ssl.SSLCertVerificationError as e:
            return {"power_id": "PWR-137", "status": "cert_invalid", "host": host, "message": str(e)}
        except Exception as e:
            return {"power_id": "PWR-137", "status": "error", "host": host, "message": str(e)}

    # ------------------------------------------------------------------ #
    # PWR-138  ARP Table
    # ------------------------------------------------------------------ #
    @staticmethod
    def arp_table() -> Dict[str, Any]:
        """PWR-138: Dump the local ARP cache."""
        try:
            result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=10)
            output = result.stdout.strip()

            entries: List[Dict[str, str]] = []
            for line in output.splitlines():
                # Windows: "  192.168.1.1          aa-bb-cc-dd-ee-ff     dynamic"
                match = re.match(
                    r"\s*([\d.]+)\s+([\da-fA-F:-]+)\s+(\w+)",
                    line,
                )
                if match:
                    entries.append(
                        {
                            "ip": match.group(1),
                            "mac": match.group(2),
                            "type": match.group(3),
                        }
                    )

            return {
                "power_id": "PWR-138",
                "status": "success",
                "entry_count": len(entries),
                "entries": entries,
                "raw": output,
            }
        except Exception as e:
            return {"power_id": "PWR-138", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------ #
    # PWR-139  Netstat Listeners
    # ------------------------------------------------------------------ #
    @staticmethod
    def netstat_listeners() -> Dict[str, Any]:
        """PWR-139: List active listening ports via netstat."""
        try:
            result = subprocess.run(
                ["netstat", "-an"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            output = result.stdout.strip()

            listeners: List[Dict[str, Any]] = []
            for line in output.splitlines():
                if "LISTENING" in line or "LISTEN" in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        local_addr = parts[1]
                        # Split address and port
                        if ":" in local_addr:
                            sep_idx = local_addr.rfind(":")
                            addr = local_addr[:sep_idx]
                            port_str = local_addr[sep_idx + 1 :]
                            try:
                                port_num = int(port_str)
                            except ValueError:
                                port_num = port_str
                            listeners.append(
                                {
                                    "protocol": parts[0],
                                    "local_address": addr,
                                    "port": port_num,
                                    "state": "LISTENING",
                                }
                            )

            return {
                "power_id": "PWR-139",
                "status": "success",
                "listener_count": len(listeners),
                "listeners": listeners,
            }
        except Exception as e:
            return {"power_id": "PWR-139", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------ #
    # PWR-140  DNS Flush
    # ------------------------------------------------------------------ #
    @staticmethod
    def dns_flush() -> Dict[str, Any]:
        """PWR-140: Flush the local DNS resolver cache."""
        try:
            if os.name == "nt":
                result = subprocess.run(
                    ["ipconfig", "/flushdns"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            else:
                # Linux: systemd-resolve --flush-caches
                result = subprocess.run(
                    ["systemd-resolve", "--flush-caches"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

            output = (result.stdout + result.stderr).strip()
            success = result.returncode == 0

            return {
                "power_id": "PWR-140",
                "status": "success" if success else "error",
                "message": output,
            }
        except Exception as e:
            return {"power_id": "PWR-140", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------ #
    # PWR-141  Bandwidth Monitor
    # ------------------------------------------------------------------ #
    @staticmethod
    def bandwidth_monitor() -> Dict[str, Any]:
        """PWR-141: Snapshot of current network bytes sent/received."""
        try:
            import psutil

            counters = psutil.net_io_counters()
            per_nic = psutil.net_io_counters(pernic=True)

            nic_stats: List[Dict[str, Any]] = []
            for nic, c in per_nic.items():
                nic_stats.append(
                    {
                        "interface": nic,
                        "bytes_sent": c.bytes_sent,
                        "bytes_recv": c.bytes_recv,
                        "packets_sent": c.packets_sent,
                        "packets_recv": c.packets_recv,
                        "errin": c.errin,
                        "errout": c.errout,
                        "dropin": c.dropin,
                        "dropout": c.dropout,
                    }
                )

            return {
                "power_id": "PWR-141",
                "status": "success",
                "total": {
                    "bytes_sent": counters.bytes_sent,
                    "bytes_recv": counters.bytes_recv,
                    "bytes_sent_mb": round(counters.bytes_sent / (1024 * 1024), 2),
                    "bytes_recv_mb": round(counters.bytes_recv / (1024 * 1024), 2),
                    "packets_sent": counters.packets_sent,
                    "packets_recv": counters.packets_recv,
                },
                "per_interface": nic_stats,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except ImportError:
            return {
                "power_id": "PWR-141",
                "status": "unavailable",
                "message": "psutil is required for bandwidth monitoring. Install via: pip install psutil",
            }
        except Exception as e:
            return {"power_id": "PWR-141", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------ #
    # PWR-142  WiFi Networks
    # ------------------------------------------------------------------ #
    @staticmethod
    def wifi_networks() -> Dict[str, Any]:
        """PWR-142: Scan nearby WiFi SSIDs (Windows netsh)."""
        try:
            if os.name != "nt":
                return {
                    "power_id": "PWR-142",
                    "status": "unsupported",
                    "message": "WiFi scan via netsh is only available on Windows.",
                }

            result = subprocess.run(
                ["netsh", "wlan", "show", "networks", "mode=bssid"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            output = result.stdout.strip()

            if "is not running" in output.lower() or result.returncode != 0:
                return {
                    "power_id": "PWR-142",
                    "status": "unavailable",
                    "message": "WLAN service is not running or no wireless adapter found.",
                    "raw": output,
                }

            networks: List[Dict[str, str]] = []
            current: Dict[str, str] = {}
            for line in output.splitlines():
                line = line.strip()
                if line.startswith("SSID") and "BSSID" not in line:
                    if current and current.get("ssid"):
                        networks.append(current)
                    ssid_match = re.match(r"SSID\s+\d+\s*:\s*(.*)", line)
                    current = {"ssid": ssid_match.group(1).strip() if ssid_match else ""}
                elif line.startswith("Signal"):
                    sig_match = re.match(r"Signal\s*:\s*(\d+%)", line)
                    if sig_match:
                        current["signal"] = sig_match.group(1)
                elif line.startswith("Authentication"):
                    auth_match = re.match(r"Authentication\s*:\s*(.*)", line)
                    if auth_match:
                        current["authentication"] = auth_match.group(1).strip()
                elif line.startswith("Encryption"):
                    enc_match = re.match(r"Encryption\s*:\s*(.*)", line)
                    if enc_match:
                        current["encryption"] = enc_match.group(1).strip()
                elif line.startswith("Channel"):
                    ch_match = re.match(r"Channel\s*:\s*(\d+)", line)
                    if ch_match:
                        current["channel"] = ch_match.group(1)

            if current and current.get("ssid"):
                networks.append(current)

            return {
                "power_id": "PWR-142",
                "status": "success",
                "network_count": len(networks),
                "networks": networks,
            }
        except Exception as e:
            return {"power_id": "PWR-142", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------ #
    # PWR-143  VPN Status
    # ------------------------------------------------------------------ #
    @staticmethod
    def vpn_status() -> Dict[str, Any]:
        """PWR-143: Check if a VPN adapter/tunnel is currently active."""
        try:
            vpn_indicators = ["vpn", "tun", "tap", "wg", "wireguard", "proton", "mullvad", "nord", "openvpn"]
            vpn_adapters: List[Dict[str, Any]] = []

            try:
                import psutil

                interfaces = psutil.net_if_stats()
                addrs = psutil.net_if_addrs()
                for iface_name, stat in interfaces.items():
                    name_lower = iface_name.lower()
                    if stat.isup and any(vpn_key in name_lower for vpn_key in vpn_indicators):
                        adapter_info: Dict[str, Any] = {
                            "name": iface_name,
                            "is_up": stat.isup,
                            "speed_mbps": stat.speed,
                        }
                        if iface_name in addrs:
                            adapter_info["addresses"] = [
                                a.address for a in addrs[iface_name] if a.family == socket.AF_INET
                            ]
                        vpn_adapters.append(adapter_info)
            except ImportError:
                # Fallback: check ipconfig output
                result = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=10)
                output = result.stdout.lower()
                for keyword in vpn_indicators:
                    if keyword in output:
                        vpn_adapters.append({"name": keyword, "detected_in": "ipconfig"})
                        break

            vpn_active = len(vpn_adapters) > 0

            return {
                "power_id": "PWR-143",
                "status": "success",
                "vpn_active": vpn_active,
                "vpn_adapters": vpn_adapters,
                "message": "VPN tunnel detected" if vpn_active else "No VPN adapter detected",
            }
        except Exception as e:
            return {"power_id": "PWR-143", "status": "error", "message": str(e)}


# Module-level singleton
networking_powers = NetworkingPowers()
