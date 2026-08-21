import hashlib
import os
import sys
import re
import socket
import ssl
import time
from pathlib import Path

# Add project root to sys.path so sip_config can be imported when run directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sip_config import SipConfig, load_env


def recv_sip(sock, timeout=5):
    sock.settimeout(timeout)
    data = b""

    try:
        while True:
            chunk = sock.recv(65535)
            if not chunk:
                break

            data += chunk

            if b"\r\n\r\n" in data:
                header, body = data.split(b"\r\n\r\n", 1)
                match = re.search(rb"Content-Length:\s*(\d+)", header, re.IGNORECASE)

                if match:
                    content_length = int(match.group(1))
                    if len(body) >= content_length:
                        break
                else:
                    break

    except socket.timeout:
        pass

    return data.decode(errors="replace")


def build_register(
    registrar_host,
    ipv4_address,
    local_port,
    public_id,
    instance,
    reg_id,
    pan_info,
    cseq,
    call_id,
    branch,
    tag,
    sip_contact_video,
    authorization=None,
):
    contact = (
        f"<sip:{public_id}@{ipv4_address}:{local_port};transport=tls>;"
        f'+sip.instance="{instance}";'
        f"reg-id={reg_id};"
        f'{"video" if sip_contact_video else ""}'
    )

    message = (
        f"REGISTER sip:{registrar_host} SIP/2.0\r\n"
        f"Via: SIP/2.0/TLS {ipv4_address}:{local_port};branch={branch};rport\r\n"
        f"Max-Forwards: 70\r\n"
        f"From: <{public_id}>;tag={tag}\r\n"
        f"To: <{public_id}>\r\n"
        f"Call-ID: {call_id}\r\n"
        f"CSeq: {cseq} REGISTER\r\n"
        f"Contact: {contact}\r\n"
        f"P-Access-Network-Info: {pan_info}\r\n"
        f"Expires: 300\r\n"
    )

    if authorization:
        message += f"Authorization: {authorization}\r\n"

    message += "Content-Length: 0\r\n\r\n"

    return message


def build_invite(
    ipv4_address,
    local_port,
    rtp_port,
    public_id,
    instance,
    reg_id,
    pan_info,
    domain,
    sip_contact_video,
    sip_q_value,
    sip_icsi_ref,
    sip_iari_ref,
    sip_gsma_rcs_telephony,
    sip_number,
):
    destination = "XXXXXXXX"  # Hardcoded destination number for the invite

    sdp = (
        f"v=0\r\n"
        f"o=Juice 1737281838294729 1737281838294729 IN IP4 {ipv4_address}\r\n"
        f"s=-\r\n"
        f"c=IN IP4 {ipv4_address}\r\n"
        f"t=0 0\r\n"
        f"m=audio {rtp_port} RTP/AVP 126 125 124 123 122 121\r\n"
        f"b=AS:37\r\n"
        f"b=RS:462\r\n"
        f"b=RR:1387\r\n"
        f"a=rtpmap:126 AMR-WB/16000\r\n"
        f"a=fmtp:126 mode-change-capability=2;max-red=0\r\n"
        f"a=rtpmap:125 AMR-WB/16000\r\n"
        f"a=fmtp:125 octet-align=1;mode-change-capability=2;max-red=0\r\n"
        f"a=rtpmap:124 AMR/8000\r\n"
        f"a=fmtp:124 mode-change-capability=2;max-red=0\r\n"
        f"a=rtpmap:123 AMR/8000\r\n"
        f"a=fmtp:123 octet-align=1;mode-change-capability=2;max-red=0\r\n"
        f"a=rtpmap:122 telephone-event/16000\r\n"
        f"a=fmtp:122 0-15\r\n"
        f"a=rtpmap:121 telephone-event/8000\r\n"
        f"a=fmtp:121 0-15\r\n"
        f"a=ptime:20\r\n"
        f"a=maxptime:240\r\n"
        f"a=sendrecv\r\n"
    )

    token = f"{int(time.time())}"
    branch = f"z9hG4bK-python-invite-{token}"
    tag = f"python-invite-{token}"
    call_id = f"python-invite-{token}@jio-fiber-sip"

    contact = (
        f"<sip:{sip_number}@{ipv4_address}:{local_port};transport=tls>;"
        f'+sip.instance="{instance}";'
        f"reg-id={reg_id};"
        f'+g.3pp.icsi-ref="urn%3Aurn-7%3A3gpp-service.ims.icsi.mmtel";'
        f"video;"
        f'+g.3gpp.iari-ref="urn%3Aurn-7%3A3gpp-application.ims.iari.rcs.jio.eucr";'
        f'+g.gsma.rcs.telephony="{sip_gsma_rcs_telephony}";'
        f'q={sip_q_value}'
    )

    invite = (
        f"INVITE sip:{destination}@{domain}?phone-context={domain}&user=phone SIP/2.0\r\n"
        f"Via: SIP/2.0/TLS {ipv4_address}:{local_port};rport;branch={branch}\r\n"
        f"Max-Forwards: 70\r\n"
        f"From: <{public_id}>;tag={tag}\r\n"
        f"To: <sip:{destination}@{domain}?phone-context={domain}&user=phone>\r\n"
        f"Call-ID: {call_id}\r\n"
        f"CSeq: 1 INVITE\r\n"
        f"Contact: {contact}\r\n"
        f"P-Preferred-Identity: <{public_id}>\r\n"
        f"P-Access-Network-Info: {pan_info}\r\n"
        f"Allow: INVITE, ACK, CANCEL, OPTIONS, BYE, REFER, NOTIFY, UPDATE, PRACK, INFO\r\n"
        f"Supported: outbound, path, gruu, replaces, timer, norefersub, 100rel\r\n"
        f"Session-Expires: 1800\r\n"
        f"Min-SE: 90\r\n"
        f"Content-Type: application/sdp\r\n"
        f"User-Agent: JFVoice/1.0\r\n"
        f"Content-Length: {len(sdp.encode())}\r\n"
        f"\r\n"
        f"{sdp}"
    )

    return invite


def main():
    load_env()
    config = SipConfig()

    registrar_host = config.registrar_host
    registrar_port = config.registrar_port
    ipv4_address = config.ipv4_address
    local_port = config.local_port
    rtp_port = config.rtp_port
    public_id = config.public_id
    username = config.auth_username
    password = config.sip_password
    realm = config.sip_realm
    instance = config.sip_instance
    reg_id = config.sip_reg_id
    pan_info = config.p_access_network_info
    domain = config.sip_home_network_domain

    register_call_id = f"python-register-{int(time.time())}@jio-fiber-sip"

    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    raw_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    raw_socket.bind((ipv4_address, local_port))
    raw_socket.settimeout(10)

    tls_socket = context.wrap_socket(
        raw_socket,
        server_hostname=registrar_host,
    )

    tls_socket.connect((registrar_host, registrar_port))

    print(f"TLS connected: {registrar_host}:{registrar_port}")
    print(f"Local signaling: {ipv4_address}:{local_port}")
    print()
    print("STEP 1: REGISTER without authentication")

    register = build_register(
        registrar_host,
        ipv4_address,
        local_port,
        public_id,
        instance,
        reg_id,
        pan_info,
        1,
        register_call_id,
        "z9hG4bK-python-register-001",
        "python-register-001",
        config.sip_contact_video,
    )

    tls_socket.sendall(register.encode())

    response = recv_sip(tls_socket)

    print(response)

    challenge = re.search(
        r'WWW-Authenticate:\s*Digest\s+nonce="([^"]+)"',
        response,
        re.IGNORECASE,
    )

    if not challenge:
        print("ERROR: No Digest challenge received.")
        tls_socket.close()
        return

    nonce = challenge.group(1)

    print()
    print("STEP 2: REGISTER with Digest authentication")
    print(f"Nonce: {nonce}")

    uri = f"sip:{registrar_host}"
    ha1 = hashlib.md5(f"{username}:{realm}:{password}".encode()).hexdigest()
    ha2 = hashlib.md5(f"REGISTER:{uri}".encode()).hexdigest()
    digest_response = hashlib.md5(
        f"{ha1}:{nonce}:{ha2}".encode()
    ).hexdigest()

    authorization = (
        f'Digest username="{username}",'
        f'realm="{realm}",'
        f'nonce="{nonce}",'
        f'uri="{uri}",'
        f'response="{digest_response}",'
        f"algorithm=MD5"
    )

    register = build_register(
        registrar_host,
        ipv4_address,
        local_port,
        public_id,
        instance,
        reg_id,
        pan_info,
        2,
        register_call_id,
        "z9hG4bK-python-register-002",
        "python-register-001",
        config.sip_contact_video,
        authorization,
    )

    tls_socket.sendall(register.encode())

    response = recv_sip(tls_socket)

    print(response)

    if not re.search(r"^SIP/2\.0 200 ", response, re.MULTILINE):
        print("ERROR: Registration did not return SIP 200 OK.")
        tls_socket.close()
        return

    print()
    print("REGISTRATION SUCCESSFUL")
    print()
    print("STEP 3: Sending IPv4 INVITE to +91 81493 84995")

    invite = build_invite(
        ipv4_address,
        local_port,
        rtp_port,
        public_id,
        instance,
        reg_id,
        pan_info,
        domain,
        config.sip_contact_video,
        config.sip_q_value,
        config.sip_icsi_ref,
        config.sip_iari_ref,
        config.sip_gsma_rcs_telephony,
        config.sip_number,
    )

    tls_socket.sendall(invite.encode())

    tls_socket.settimeout(1)

    invite_branch = re.search(r"^Via:.*?branch=([^;\r\n]+)", invite, re.MULTILINE).group(1)
    invite_tag = re.search(r"^From:.*?;tag=([^;\r\n]+)", invite, re.MULTILINE).group(1)
    invite_call_id = re.search(r"^Call-ID:\s*(.+)$", invite, re.MULTILINE).group(1).strip()

    prack_cseq = 2
    end_time = time.time() + 30

    while time.time() < end_time:
        try:
            data = tls_socket.recv(65535)

            if not data:
                print()
                print("TLS CONNECTION CLOSED BY PEER")
                break

            response = data.decode(errors="replace")
            print(response, end="")

            if (
                re.search(r"^SIP/2\.0 183 ", response, re.MULTILINE)
                and re.search(r"^Require:.*100rel", response, re.MULTILINE | re.IGNORECASE)
            ):
                rseq_match = re.search(r"^RSeq:\s*(\d+)", response, re.MULTILINE | re.IGNORECASE)
                to_match = re.search(r"^To:\s*(.+)$", response, re.MULTILINE | re.IGNORECASE)
                contact_match = re.search(r"^Contact:\s*(.+)$", response, re.MULTILINE | re.IGNORECASE)

                if not rseq_match or not to_match or not contact_match:
                    print("ERROR: 183 reliable provisional response is missing RSeq, To, or Contact.")
                    continue

                rseq = rseq_match.group(1)
                remote_to = to_match.group(1).strip()
                remote_contact = contact_match.group(1).strip()

                contact_uri_match = re.search(r"<([^>]+)>", remote_contact)

                if contact_uri_match:
                    request_uri = contact_uri_match.group(1)
                else:
                    request_uri = remote_contact.split(";", 1)[0].strip()

                prack_branch = f"z9hG4bK-python-prack-{int(time.time() * 1000)}"

                prack = (
                    f"PRACK {request_uri} SIP/2.0\r\n"
                    f"Via: SIP/2.0/TLS {ipv4_address}:{local_port};rport;branch={prack_branch}\r\n"
                    f"Max-Forwards: 70\r\n"
                    f"From: <{public_id}>;tag={invite_tag}\r\n"
                    f"To: {remote_to}\r\n"
                    f"Call-ID: {invite_call_id}\r\n"
                    f"CSeq: {prack_cseq} PRACK\r\n"
                    f"RAck: {rseq} 1 INVITE\r\n"
                    f"Contact: {config.build_prack_contact()}\r\n"
                    f"Supported: outbound, path, gruu, replaces, timer, norefersub, 100rel\r\n"
                    f"User-Agent: JFVoice/1.0\r\n"
                    f"Content-Length: 0\r\n"
                    f"\r\n"
                )

                print()
                print("STEP 4: Sending PRACK")
                print(prack, end="")

                tls_socket.sendall(prack.encode())
                prack_cseq += 1

            #Handle incoming UPDATE
            if re.search(r"^UPDATE\s+", response, re.MULTILINE):
                update_request_uri_match = re.search(
                    r"^UPDATE\s+(\S+)\s+SIP/2\.0",
                    response,
                    re.MULTILINE,
                )
                update_via_match = re.search(
                    r"^Via:\s*(.+)$",
                    response,
                    re.MULTILINE | re.IGNORECASE,
                )
                update_from_match = re.search(
                    r"^From:\s*(.+)$",
                    response,
                    re.MULTILINE | re.IGNORECASE,
                )
                update_to_match = re.search(
                    r"^To:\s*(.+)$",
                    response,
                    re.MULTILINE | re.IGNORECASE,
                )
                update_call_id_match = re.search(
                    r"^Call-ID:\s*(.+)$",
                    response,
                    re.MULTILINE | re.IGNORECASE,
                )
                update_cseq_match = re.search(
                    r"^CSeq:\s*(\d+)\s+UPDATE",
                    response,
                    re.MULTILINE | re.IGNORECASE,
                )

                if all([
                    update_request_uri_match,
                    update_via_match,
                    update_from_match,
                    update_to_match,
                    update_call_id_match,
                    update_cseq_match,
                ]):
                    update_sdp = (
                        f"v=0\r\n"
                        f"o=Juice 1737281838294729 1737281838294730 IN IP4 {ipv4_address}\r\n"
                        f"s=-\r\n"
                        f"c=IN IP4 {ipv4_address}\r\n"
                        f"t=0 0\r\n"
                        f"m=audio {rtp_port} RTP/AVP 126 122\r\n"
                        f"a=rtpmap:126 AMR-WB/16000\r\n"
                        f"a=fmtp:126 mode-set=0,1,2,3;mode-change-capability=2;max-red=0\r\n"
                        f"a=rtpmap:122 telephone-event/16000\r\n"
                        f"a=fmtp:122 0-15\r\n"
                        f"a=ptime:20\r\n"
                        f"a=maxptime:80\r\n"
                        f"a=sendrecv\r\n"
                    )

                    update_ok = (
                        f"SIP/2.0 200 OK\r\n"
                        f"Via: {update_via_match.group(1)}\r\n"
                        f"From: {update_from_match.group(1)}\r\n"
                        f"To: {update_to_match.group(1)}\r\n"
                        f"Call-ID: {update_call_id_match.group(1).strip()}\r\n"
                        f"CSeq: {update_cseq_match.group(1)} UPDATE\r\n"
                        f"Contact: {config.build_prack_contact()}\r\n"
                        f"Supported: outbound, path, gruu, replaces, timer, norefersub, 100rel\r\n"
                        f"User-Agent: JFVoice/1.0\r\n"
                        f"Content-Type: application/sdp\r\n"
                        f"Content-Length: {len(update_sdp.encode())}\r\n"
                        f"\r\n"
                        f"{update_sdp}"
                    )

                    print()
                    print("STEP 5: Sending UPDATE 200 OK")
                    print(update_ok, end="")

                    tls_socket.sendall(update_ok.encode())

            if re.search(r"^SIP/2\.0 200 ", response, re.MULTILINE):
                cseq_match = re.search(
                    r"^CSeq:\s*(\d+)\s+(\S+)",
                    response,
                    re.MULTILINE | re.IGNORECASE,
                )

                if cseq_match and cseq_match.group(2).upper() == "PRACK":
                    print()
                    print("PRACK SUCCESSFUL: SIP 200 OK received.")

        except socket.timeout:
            continue

    tls_socket.close()


if __name__ == "__main__":
    main()