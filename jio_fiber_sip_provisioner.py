#!/usr/bin/env python3
"""
Flow:
- Try http://jiofiber.local.html:8080/request_account
  - If DNS fails, prompt for router LAN IP and retry
  - If still unreachable, explain prerequisites and exit
- Drive OTP flow against https://<router>:8443/ using a deterministic MAC
  derived from the hardcoded hostname "ParikaSIPProxy" (JFC hashing logic)
- Parse SIP config to obtain password and username
- Generate a .env in the project root with Jio-friendly defaults

Notes:
- This script intentionally keeps only the MAC/OTP logic from jfc_configure.py
  and omits any MicroSIP file generation. UA is set to "ParikaProxy/1.0".
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional, Tuple
from http.cookies import SimpleCookie
import ssl


import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

JIO_DEFAULT_HOST = "jiofiber.local.html"
REQ_PORT = 8080
IMS_PORT = 8443
HARD_HOSTNAME = "ParikaSIPProxy"

# JFC hashing constants/logic (kept as-is)
HASH_MULTIPLIER = 33


def calculate_hash(hval: int, key: bytearray) -> int:
    for b in key:
        hval = (hval * HASH_MULTIPLIER) + b
        hval &= 0xFFFFFFFF
    return hval


def convert_to_hex(hval: int) -> str:
    hex_val = f"{hval:08X}"
    return "".join(reversed([hex_val[i : i + 2] for i in range(0, len(hex_val), 2)]))


def get_hash(s: str) -> int:
    return calculate_hash(0, bytearray(s, "utf-8"))


def hex_to_mac(hex_string: str) -> str:
    hex_string = hex_string.zfill(12).lower()
    return ":".join(hex_string[i : i + 2] for i in range(0, len(hex_string), 2))


def mac_from_hostname(hostname: str) -> str:
    h = get_hash(hostname)
    return hex_to_mac(convert_to_hex(h))


class RawResponse:
    def __init__(self, status_code: int, headers: dict[str, str], body: bytes, raw: bytes):
        self.status_code = status_code
        self.headers = headers
        self.text = body.decode(errors="replace")
        self.raw = raw


def raw_https_get(url: str) -> RawResponse:
    """Mimic the original raw_http_request over HTTPS with verify disabled."""
    parsed = requests.utils.urlparse(url)
    host = parsed.hostname
    port = parsed.port or 443
    path = parsed.path or "/"
    q = ("?" + parsed.query) if parsed.query else ""
    full_path = path + q

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    sock = ctx.wrap_socket(socket.create_connection((host, port)), server_hostname=host)
    try:
        req_lines = [
            f"GET {full_path} HTTP/1.1",
            f"Host: {host}",
            "Connection: close",
            "",
            "",
        ]
        sock.sendall("\r\n".join(req_lines).encode())

        resp = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            resp += chunk

        header_blob, body = resp.split(b"\r\n\r\n", 1)
        lines = header_blob.split(b"\r\n")
        status = int(lines[0].split(b" ")[1])
        hdrs: dict[str, str] = {}
        for ln in lines[1:]:
            if b":" in ln:
                k, v = ln.split(b":", 1)
                hdrs[k.decode().lower()] = v.strip().decode()
        return RawResponse(status, hdrs, body, resp)
    finally:
        try:
            sock.close()
        except Exception:
            pass


def resolve_host(host: str) -> Optional[str]:
    try:
        return socket.gethostbyname(host)
    except socket.gaierror:
        return None


def get_local_ipv4() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "0.0.0.0"
    finally:
        try:
            s.close()
        except Exception:
            pass
    return ip


def request_account(base: str) -> dict:
    url = f"http://{base}:{REQ_PORT}/request_account"
    r = requests.get(url, timeout=5)
    r.raise_for_status()
    return r.json()


def ims_request(base: str, hostname: str, mac: str, operation: str, no_otp: bool = False, session: Optional[requests.Session] = None):
    url = f"https://{base}:{IMS_PORT}/"
    params = {
        "terminal_sw_version": "RCSAndrd",
        "terminal_vendor": hostname,
        "terminal_model": hostname,
        "SMS_port": 0,
        "act_type": "volatile",
        "IMSI": "",
        "msisdn": "",
        "IMEI": "",
        "vers": 0,
        "token": "",
        "rcs_state": 0,
        "rcs_version": "5.1B",
        "rcs_profile": "joyn_blackbird",
        "client_vendor": "JUIC",
        "default_sms_app": 2,
        "default_vvm_app": 0,
        "device_type": "vvm",
        "client_version": "JSEAndrd-1.0",
        "mac_address": mac,
        "alias": hostname,
        "nwk_intf": "wifi" if not no_otp else "eth",
    }
    if operation in {"add", "remove"}:
        # Mirror the Jio provisioning request: build query string manually and do a raw HTTPS GET
        params["op_type"] = operation
        get_url = f"{url}?" + "&".join(f"{k}={v}" for k, v in params.items())
        return raw_https_get(get_url)
    client = session or requests
    return client.get(url, params=params, verify=False, timeout=8)


def remove_device(base: str, hostname: str, mac: str) -> RawResponse:
    print(f"Removing authorized device '{hostname}' with MAC {mac}...")
    response = ims_request(base, hostname, mac, operation="remove")
    if response.status_code != 200:
        print(f"Device removal failed: HTTP {response.status_code}")
        if response.text:
            print(response.text)
        sys.exit(5)

    print("Device removal response:")
    print(response.text)
    return response


def otp_verify(base: str, otp: int, session: requests.Session):
    """Verify OTP using the same session (cookies auto-carried)."""
    url = f"https://{base}:{IMS_PORT}/"
    return session.get(url, params={"OTP": otp}, verify=False, timeout=8, allow_redirects=False)


def fetch_sip_config(base: str, hostname: str, mac: str, session: Optional[requests.Session] = None) -> ET.Element:
    resp = ims_request(base, hostname, mac, operation="fetch", session=session)
    resp.raise_for_status()
    return ET.fromstring(resp.text)


def parse_sip_values(root: ET.Element) -> dict:
    wanted = {
        "realm",
        "username",
        "userpwd",
        "home_network_domain_name",
        "address",
        "private_user_identity",
        "public_user_identity",
    }
    out: dict = {}
    for p in root.findall(".//parm"):
        n = p.attrib.get("name")
        v = p.attrib.get("value")
        if n in wanted:
            out[n] = v
    return out


def ensure_endpoint_ready(host_or_ip: Optional[str]) -> Tuple[str, dict]:
    host = host_or_ip or JIO_DEFAULT_HOST
    ip = resolve_host(host)
    if not ip:
        print("Couldn't resolve jiofiber.local.html. Enter your Jio router LAN IP (e.g., 192.168.x.y).")
        router_ip = input("Router IP: ").strip()
        if not router_ip:
            fail_prereq()
        host = router_ip
    # Try request_account
    try:
        acc = request_account(host)
        return host, acc
    except Exception as e:
        print("request_account endpoint not reachable.")
        fail_prereq()
        raise e  # unreachable


def fail_prereq():
    print("\nCannot proceed without access to the Jio router.")
    print("Make sure:")
    print("- You are on the same LAN as the router")
    print("- Router is in AP mode and SIP endpoints are enabled")
    print("- Run the script from the guide to enable SIP on the router:")
    print("  https://gist.github.com/ankurpandeyvns/03d11b7137ecbebc9bf7775489b30774")
    print("Then rerun this provisioner.")
    sys.exit(2)


def write_env(env_path: str, values: dict):
    lines = []
    for k, v in values.items():
        lines.append(f"{k}={v}")
    content = "\n".join(lines) + "\n"
    # Backup existing
    if os.path.exists(env_path):
        os.replace(env_path, env_path + ".bak")
    with open(env_path, "w") as f:
        f.write(content)


def main():
    parser = argparse.ArgumentParser(description="JioFiber SIP Proxy .env provisioner")
    parser.add_argument("--remove", action="store_true", help="Remove the deterministic SIP device from the Jio authorized devices list.")
    args = parser.parse_args()

    print("JioFiber SIP Proxy .env provisioner")
    print("This will contact your Jio router to fetch account info and drive OTP.")

    # Step 1: request_account
    host, acc = ensure_endpoint_ready(None)

    if args.remove:
        mac = mac_from_hostname(HARD_HOSTNAME)
        print(f"Using deterministic MAC from hostname '{HARD_HOSTNAME}': {mac}")
        remove_device(host, HARD_HOSTNAME, mac)
        return
    # acc example fields: imsi, msisdn, mcc, mnc, ...
    msisdn = acc.get("msisdn")
    if not msisdn:
        print("Unexpected response from request_account; cannot determine msisdn:")
        print(json.dumps(acc, indent=2))
        fail_prereq()

    # Step 2: OTP flow against 8443 with deterministic MAC from HARD_HOSTNAME
    mac = mac_from_hostname(HARD_HOSTNAME)
    print(f"Using deterministic MAC from hostname '{HARD_HOSTNAME}': {mac}")
    print("Requesting OTP (you will receive an SMS on the Jio number)...")
    sess = requests.Session()
    sess.verify = False
    add_resp = ims_request(host, HARD_HOSTNAME, mac, operation="add", session=sess)
    if add_resp.status_code != 200:
        print(f"Registration request failed: HTTP {add_resp.status_code}\n{add_resp.text}")
        fail_prereq()

    target_msisdn = add_resp.headers.get("x-amn", "<unknown>")
    print(f"OTP sent to: {target_msisdn}")

    # Build a cookie jar from Set-Cookie as a fallback (some routers are picky)
    set_cookie_raw = add_resp.headers.get("set-cookie", "")
    sc = SimpleCookie()
    try:
        sc.load(set_cookie_raw)
    except Exception:
        sc = SimpleCookie()  # ignore parsing errors
    fallback_cookie_jar = requests.cookies.cookiejar_from_dict({k: m.value for k, m in sc.items()})
    
    for key, morsel in sc.items():
        sess.cookies.set(key, morsel.value)
        print(f"Provisioning cookies received: {list(sess.cookies.keys())}")

    ok = False
    for attempt in range(3):
        try:
            otp = int(input("Enter OTP: ").strip())
        except Exception:
            print("Invalid OTP format. Use digits only.")
            continue
        verify = otp_verify(host, otp, session=sess)
        if verify.status_code == 200:
            print("OTP verified successfully.")
            ok = True
            break
        else:
            # Fallback: try explicit cookies if session-based attempt failed
            verify2 = requests.get(
                f"https://{host}:{IMS_PORT}/",
                params={"OTP": otp},
                cookies=fallback_cookie_jar,
                verify=False,
                timeout=8,
            )
            if verify2.status_code == 200:
                print("OTP verified successfully (fallback cookies).")
                ok = True
                break
            print(f"OTP failed (HTTP {verify.status_code}/{verify2.status_code}). Try again.")

    if not ok:
        print("Failed to verify OTP after 3 attempts.")
        sys.exit(3)

    # Step 3: fetch SIP config XML to obtain realm/username/password
    root = fetch_sip_config(host, HARD_HOSTNAME, mac, session=sess)
    sip = parse_sip_values(root)
    realm = sip.get("realm", "ue.wln.ims.jio.com")
    username = sip.get("username") or msisdn
    userpwd = sip.get("userpwd")
    if not userpwd:
        print("Could not obtain SIP password from router config. Aborting.")
        sys.exit(4)

    # Step 4: generate .env
    local_ip = get_local_ipv4()
    env_values = {
        "CONTAINER_NAME": "jfc-pjsua",
        "HOSTNAME_OVERRIDE": HARD_HOSTNAME,
        "USER_AGENT": "ParikaProxy/1.0",
        # Local bind/public IP for Contact shaping
        "IPV4_ADDRESS": local_ip,
        "LOCAL_PORT": "5061",
        "TLS_PORT": "5068",
        "RTP_PORT": "52000",
        # SIP/IMS identities
        "PUBLIC_ID": f"sip:+91{msisdn}@{realm}",
        "SIP_AUTH_USER": msisdn,
        "SIP_PASSWORD": userpwd,
        "SIP_REALM": realm,
        # Upstream proxy/registrar are the router on TLS 5068
        "REGISTRAR_HOST": host,
        "REGISTRAR_PORT": "5068",
        "PROXY_HOST": host,
        "PROXY_PORT": "5068",
        # DNS inside container: prefer router
        "DNS_SERVERS": host,
        # Defaults/tuning
        "LOG_LEVEL": "5",
        "KEEPALIVE": "15",
        "MAX_CALLS": "2",
        # Helpful toggles (can be changed later)
        "TLS_VERIFY": "0",
    }

    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(script_dir, ".env")
    write_env(env_path, env_values)

    print("\nWrote .env with the following key values:")
    for k in [
        "HOSTNAME_OVERRIDE",
        "IPV4_ADDRESS",
        "PUBLIC_ID",
        "SIP_AUTH_USER",
        "SIP_REALM",
        "REGISTRAR_HOST",
        "PROXY_HOST",
        "DNS_SERVERS",
        "USER_AGENT",
    ]:
        print(f"- {k}={env_values[k]}")
    print(f"\nDone. You can now run the proxy with your .env: \n  docker run --rm --name jio-sip --env-file {env_path} --network host ankurpandeyvns/jiofiber-sip-proxy:latest")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
