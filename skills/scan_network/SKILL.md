---
name: scan_network
description: Perform network scanning, port discovery, service detection, DNS resolution, and connectivity diagnostics
---

# Scan Network

Perform network reconnaissance and diagnostics using standard CLI tools.

## When to Use

- User asks to **scan**, **probe**, or **check** a network, host, or service
- Diagnosing connectivity issues (timeouts, refused connections, DNS failures)
- Discovering open ports and running services on a host
- Checking if a service or API endpoint is reachable
- Auditing local network interfaces and listening ports

## ⚠️ Important

> [!CAUTION]
> **Only scan networks and hosts you own or have explicit permission to scan.** Unauthorized network scanning may violate laws and terms of service. Always confirm scope with the user before scanning external hosts.

## Environment Context

The user has 4 active workspaces (Corpora), some of which might relate to network systems:
- `/Users/yamai/ai/Raphael` -> `/Users/yamai/ai/Raphael`
- `/Users/yamai/ai/agent_ecosystem` -> `/Users/yamai/ai/agent_ecosystem`
- `/Users/yamai/ai/network_observatory` -> `Yamai7354/network_observatory`
- `/Users/yamai/ai/portfolio` -> `/Users/yamai/ai/portfolio`

## Workflow

### 1. Identify the Target

Ask the user to confirm:
- **Target**: IP address, hostname, or CIDR range
- **Scope**: Which ports, protocols, or services to check
- **Permission**: Confirm they own or have authorization to scan the target

### 2. Choose the Right Tool

| Task                 | Command                | Availability     |
| -------------------- | ---------------------- | ---------------- |
| Check if host is up  | `ping`                 | Built-in         |
| Check specific port  | `nc` (netcat)          | Built-in (macOS) |
| HTTP endpoint test   | `curl`                 | Built-in         |
| DNS resolution       | `dig` / `nslookup`     | Built-in         |
| List local listeners | `lsof -i -P`           | Built-in         |
| Port scan            | `nmap`                 | Requires install |
| Route tracing        | `traceroute`           | Built-in         |
| Network interfaces   | `ifconfig` / `ip addr` | Built-in         |

### 3. Execute Scans

#### Connectivity Check
```bash
# Ping test (5 packets)
ping -c 5 target_host

# Check if specific port is open
nc -zv target_host 80 2>&1

# Check multiple ports
for port in 22 80 443 3000 5432 8080; do
    nc -zv -w 2 target_host $port 2>&1
done
```

#### HTTP/API Endpoint Check
```bash
# Basic connectivity + response code
curl -s -o /dev/null -w "%{http_code} %{time_total}s" https://api.example.com/health

# Verbose with headers
curl -vI https://api.example.com/health 2>&1

# Test with timeout
curl -s --connect-timeout 5 --max-time 10 https://api.example.com/health
```

#### DNS Resolution
```bash
# Forward lookup
dig +short example.com

# Reverse lookup
dig -x 93.184.216.34

# Check specific record types
dig example.com MX
dig example.com TXT
dig example.com NS

# Use specific DNS server
dig @8.8.8.8 example.com
```

#### Local Network State
```bash
# Show all listening ports
lsof -i -P -n | grep LISTEN

# Show specific port usage
lsof -i :8080

# Network interfaces
ifconfig | grep -A 4 'inet '

# Routing table
netstat -rn
```

#### Port Scanning (nmap)
```bash
# Quick scan of common ports
nmap -F target_host

# Scan specific ports
nmap -p 22,80,443,3000,5432 target_host

# Service version detection
nmap -sV -p 22,80,443 target_host

# OS detection (requires sudo)
sudo nmap -O target_host

# Scan a subnet
nmap -sn 192.168.1.0/24
```

#### Route Tracing
```bash
# Trace route to host
traceroute target_host

# TCP traceroute (often works through firewalls)
traceroute -T -p 443 target_host
```

### 4. Report Results

Present findings in a structured format:

```markdown
## Network Scan Results — target_host

| Port | State  | Service | Version     |
| ---- | ------ | ------- | ----------- |
| 22   | Open   | SSH     | OpenSSH 8.9 |
| 80   | Open   | HTTP    | nginx 1.24  |
| 443  | Open   | HTTPS   | nginx 1.24  |
| 3306 | Closed | —       | —           |

**Host**: target_host (93.184.216.34)
**Latency**: 12ms average
**OS Guess**: Ubuntu 22.04 (Linux 5.15)
```

## Python-Based Scanning

For more advanced scanning without nmap:

```python
import socket
import concurrent.futures

def scan_port(host, port, timeout=2):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            result = s.connect_ex((host, port))
            return port, result == 0
    except Exception:
        return port, False

host = "target_host"
ports = range(1, 1025)

with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
    futures = {executor.submit(scan_port, host, p): p for p in ports}
    for future in concurrent.futures.as_completed(futures):
        port, is_open = future.result()
        if is_open:
            print(f"Port {port}: OPEN")
```

## Error Handling

- **nmap not installed**: Use `nc`, `curl`, or the Python socket scanner as fallback
- **Permission denied**: Some scans (OS detection, SYN scan) require `sudo`
- **Timeouts**: Increase timeout values; host may be behind a firewall dropping packets
- **DNS failures**: Try IP address directly; check `/etc/resolv.conf`
