import os
import sys
import time
import select
import termios
import tty
from pathlib import Path

# Add project root to sys.path so sip_config can be imported when run directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pjsua2

from sip_config import SipConfig, load_env


class SipCall(pjsua2.Call):
    def __init__(self, account):
        super().__init__(account)
        self._audio_media = None

    def onCallSdpCreated(self, prm):
        sdp = prm.sdp.wholeSdp
        lines = sdp.splitlines()
        new_lines = []
        
        for line in lines:
            # Fix origin line: o=- -> o=Juice with fixed session id
            if line.startswith("o="):
                line = f"o=Juice 1737281838294729 1737281838294729 IN IP4 {os.environ.get('IPV4_ADDRESS', '127.0.0.1')}"
            # Fix session name: s=pjmedia -> s=-
            elif line.startswith("s="):
                line = "s=-"
            # Remove unwanted attributes
            elif line.startswith("a=X-nat:"):
                continue
            elif line.startswith("a=rtcp:"):
                continue
            elif line.startswith("a=ssrc:"):
                continue
            # Fix telephone-event fmtp: 0-16 -> 0-15
            elif line.startswith("a=fmtp:") and "0-16" in line:
                line = line.replace("0-16", "0-15")
            new_lines.append(line)
        
        # Add ptime and maxptime if not present
        has_ptime = any(l.startswith("a=ptime:") for l in new_lines)
        has_maxptime = any(l.startswith("a=maxptime:") for l in new_lines)
        
        # Insert ptime and maxptime before a=sendrecv
        final_lines = []
        for line in new_lines:
            if line.startswith("a=sendrecv"):
                if not has_ptime:
                    final_lines.append("a=ptime:20")
                if not has_maxptime:
                    final_lines.append("a=maxptime:240")
            final_lines.append(line)
        
        # Add session-level c= line after s= line if not present
        final_sdp_lines = []
        has_session_c = any(l.startswith("c=IN IP4") for l in final_lines if not l.startswith("m="))
        for line in final_lines:
            final_sdp_lines.append(line)
            if line.startswith("s=") and not has_session_c:
                final_sdp_lines.append(f"c=IN IP4 {os.environ.get('IPV4_ADDRESS', '127.0.0.1')}")
        
        final_sdp = "\r\n".join(final_sdp_lines) + "\r\n"
        
        # Fix bandwidth lines: replace b=AS:XX and b=TIAS:XX with proper values
        final_sdp = final_sdp.replace("b=AS:41\r\n", "b=AS:37\r\nb=RS:462\r\nb=RR:1387\r\n")
        final_sdp = final_sdp.replace("b=AS:84\r\n", "b=AS:37\r\nb=RS:462\r\nb=RR:1387\r\n")
        final_sdp = final_sdp.replace("b=TIAS:23850\r\n", "")
        final_sdp = final_sdp.replace("b=TIAS:64000\r\n", "")
        
        # Add AMR-WB fmtp (mode-change-capability=2;max-red=0) if not present
        if "a=rtpmap:96 AMR-WB/16000" in final_sdp and "a=fmtp:96 " not in final_sdp:
            final_sdp = final_sdp.replace(
                "a=rtpmap:96 AMR-WB/16000\r\n",
                "a=rtpmap:96 AMR-WB/16000\r\na=fmtp:96 mode-change-capability=2;max-red=0\r\n"
            )
        
        # Add AMR fmtp (mode-change-capability=2;max-red=0) if not present
        if "a=rtpmap:97 AMR/8000" in final_sdp and "a=fmtp:97 " not in final_sdp:
            final_sdp = final_sdp.replace(
                "a=rtpmap:97 AMR/8000\r\n",
                "a=rtpmap:97 AMR/8000\r\na=fmtp:97 mode-change-capability=2;max-red=0\r\n"
            )
        
        prm.sdp.wholeSdp = final_sdp

    def onCallMediaState(self, prm):
        call_info = self.getInfo()

        for media_index, media in enumerate(call_info.media):
            if media.type != pjsua2.PJMEDIA_TYPE_AUDIO:
                continue

            if media.status != pjsua2.PJSUA_CALL_MEDIA_ACTIVE:
                continue

            self._audio_media = self.getAudioMedia(media_index)
            audio_media = self._audio_media
            endpoint = pjsua2.Endpoint.instance()

            capture_device = endpoint.audDevManager().getCaptureDevMedia()
            playback_device = endpoint.audDevManager().getPlaybackDevMedia()

            audio_media.startTransmit(playback_device)
            capture_device.startTransmit(audio_media)

            print("[CALL] Audio media connected.")

    def set_microphone_muted(self, muted):
        endpoint = pjsua2.Endpoint.instance()
        capture_device = endpoint.audDevManager().getCaptureDevMedia()

        if not self._audio_media:
            print("[CALL] Audio media is not available.")
            return

        if muted:
            capture_device.stopTransmit(self._audio_media)
        else:
            capture_device.startTransmit(self._audio_media)

        print(f"[CALL] Microphone {'muted' if muted else 'unmuted'}.")


class SipAccount(pjsua2.Account):
    def __init__(self, config):
        super().__init__()
        self.config = config

    def onRegState(self, prm):
        info = self.getInfo()
        print(f"REGISTRATION: code={prm.code} reason={prm.reason} active={info.regIsActive}")

        if prm.code == 200 and info.regIsActive:
            self.call = SipCall(self)

            # Callee number - change this to call different destinations
            callee_number = "0XXXXXXXXXX"

            call_parameters = pjsua2.CallOpParam(True)
            # Use query parameter format like raw implementation
            call_parameters.txOption.targetUri = self.config.build_callee_uri(callee_number)

            preferred_identity = pjsua2.SipHeader()
            preferred_identity.hName = "P-Preferred-Identity"
            preferred_identity.hValue = self.config.p_preferred_identity
            call_parameters.txOption.headers.append(preferred_identity)

            access_network_info = pjsua2.SipHeader()
            access_network_info.hName = "P-Access-Network-Info"
            access_network_info.hValue = self.config.p_access_network_info
            call_parameters.txOption.headers.append(access_network_info)

            # Add missing Supported headers
            supported = pjsua2.SipHeader()
            supported.hName = "Supported"
            supported.hValue = "outbound, path, gruu, replaces, timer, norefersub, 100rel"
            call_parameters.txOption.headers.append(supported)

            # Add Allow header matching raw
            allow = pjsua2.SipHeader()
            allow.hName = "Allow"
            allow.hValue = "INVITE, ACK, CANCEL, OPTIONS, BYE, REFER, NOTIFY, UPDATE, PRACK, INFO"
            call_parameters.txOption.headers.append(allow)

            self.call.makeCall(
                self.config.build_callee_uri(callee_number),
                call_parameters
            )

    def onCallState(self, prm):
        self.call = pjsua2.Call(self, prm.callId)
        info = self.call.getInfo()
        print(
            f"CALL STATE: id={prm.callId} state={info.stateText} "
            f"status={info.lastStatusCode} reason={info.lastReason}"
        )


def main():
    load_env()
    config = SipConfig()

    username = config.auth_username
    password = config.sip_password
    realm = config.sip_realm
    host = config.registrar_host

    endpoint = pjsua2.Endpoint()
    endpoint.libCreate()

    ep_config = pjsua2.EpConfig()
    ep_config.uaConfig.userAgent = config.user_agent
    ep_config.logConfig.level = 5
    ep_config.logConfig.consoleLevel = 5
    # Set ptime to 20ms
    ep_config.medConfig.ptime = 20
    ep_config.medConfig.ecOptions = 1
    ep_config.medConfig.ecTailLen = 200
    ep_config.medConfig.audioFramePtime = 20
    endpoint.libInit(ep_config)

    # Disable all unwanted codecs by setting priority to 0 (PJMEDIA_CODEC_PRIO_DISABLED)
    unwanted = [
        "speex/16000", "speex/8000", "speex/32000",
        "iLBC/8000", "GSM/8000",
        "PCMU/8000", "PCMA/8000", "G722/16000",
        "L16/44100/1", "L16/44100/2"
    ]
    for codec_id in unwanted:
        try:
            endpoint.codecSetPriority(codec_id, 0)
        except Exception as e:
            print(f"Warning: failed to disable {codec_id}: {e}")

    # Set AMR and AMR-WB to highest priority
    endpoint.codecSetPriority("AMR-WB/16000", 255)
    endpoint.codecSetPriority("AMR/8000", 254)

    # Configure AMR-WB fmtp parameters (use decFmtp for SDP generation)
    codec_param = endpoint.codecGetParam("AMR-WB/16000")
    codec_fmtp = pjsua2.CodecFmtp()
    codec_fmtp.name = "mode-change-capability"
    codec_fmtp.val = "2"
    codec_param.setting.decFmtp.append(codec_fmtp)
    codec_fmtp2 = pjsua2.CodecFmtp()
    codec_fmtp2.name = "max-red"
    codec_fmtp2.val = "0"
    codec_param.setting.decFmtp.append(codec_fmtp2)
    codec_fmtp3 = pjsua2.CodecFmtp()
    codec_fmtp3.name = "mode-set"
    codec_fmtp3.val = "0,1,2,3"
    codec_param.setting.decFmtp.append(codec_fmtp3)
    endpoint.codecSetParam("AMR-WB/16000", codec_param)

    # Configure AMR fmtp parameters
    codec_param = endpoint.codecGetParam("AMR/8000")
    codec_fmtp = pjsua2.CodecFmtp()
    codec_fmtp.name = "mode-change-capability"
    codec_fmtp.val = "2"
    codec_param.setting.decFmtp.append(codec_fmtp)
    codec_fmtp2 = pjsua2.CodecFmtp()
    codec_fmtp2.name = "max-red"
    codec_fmtp2.val = "0"
    codec_param.setting.decFmtp.append(codec_fmtp2)
    codec_fmtp3 = pjsua2.CodecFmtp()
    codec_fmtp3.name = "mode-set"
    codec_fmtp3.val = "0,1,2,3,4,5,6,7"
    codec_param.setting.decFmtp.append(codec_fmtp3)
    endpoint.codecSetParam("AMR/8000", codec_param)

    # Use local port 5061 for TLS transport (matching raw implementation)
    transport_config = pjsua2.TransportConfig()
    transport_config.port = config.local_port
    transport_config.tlsConfig.verifyServer = False

    transport_id = endpoint.transportCreate(
        pjsua2.PJSIP_TRANSPORT_TLS,
        transport_config
    )

    endpoint.libStart()

    account_config = pjsua2.AccountConfig()
    account_config.natConfig.sipOutboundUse = False
    account_config.idUri = config.public_id

    account_config.regConfig.registrarUri = config.registrar_uri
    account_config.sipConfig.proxies.append(config.proxy_uri)

    account_config.regConfig.headers = pjsua2.SipHeaderVector()

    header = pjsua2.SipHeader()
    header.hName = "P-Access-Network-Info"
    header.hValue = config.p_access_network_info
    account_config.regConfig.headers.append(header)

    # Contact parameters for REGISTER - shortened to avoid buffer overflow
    account_config.regConfig.contactParams = config.build_register_contact_params()

    # Contact parameters for all SIP messages (including INVITE) - shortened
    account_config.sipConfig.contactParams = config.build_invite_contact_params()

    account_config.sipConfig.transportId = transport_id

    cred = pjsua2.AuthCredInfo()
    cred.scheme = "Digest"
    cred.realm = realm
    cred.username = username
    cred.data = password
    cred.dataType = 0

    account_config.sipConfig.authCreds = pjsua2.AuthCredInfoVector()
    account_config.sipConfig.authCreds.append(cred)

    account = SipAccount(config)
    account.create(account_config)

    print("PJSUA2 account created.")
    print(f"Registrar: {host}:{config.registrar_port}")
    print(f"Username:  {username}")
    print("Waiting for registration and call...")

    muted = False
    old_terminal_settings = termios.tcgetattr(sys.stdin)
    tty.setcbreak(sys.stdin.fileno())
    # Wait for call completion
    try:
        while True:
            endpoint.libHandleEvents(100)

            if hasattr(account, 'call') and account.call:
                ready, _, _ = select.select([sys.stdin], [], [], 0)

                if ready:
                    command = sys.stdin.read(1)

                    if command.lower() == "m":
                        muted = not muted
                        account.call.set_microphone_muted(muted)

            if hasattr(account, 'call') and account.call:
                try:
                    if account.call.getId() < 0:
                        continue

                    call_info = account.call.getInfo()
                    if call_info.stateText == "DISCONNECTED":
                        break
                except pjsua2.Error:
                    continue
    except KeyboardInterrupt:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_terminal_settings)
        print("\nCaller hangup requested.")

        if hasattr(account, 'call') and account.call:
            try:
                call_info = account.call.getInfo()
                if call_info.stateText != "DISCONNECTED":
                    account.call.hangup(pjsua2.CallOpParam())
            except pjsua2.Error as e:
                print(f"Hangup error: {e}")

        while True:
            endpoint.libHandleEvents(1000)

            if hasattr(account, 'call') and account.call:
                try:
                    call_info = account.call.getInfo()
                    if call_info.stateText == "DISCONNECTED":
                        break
                except pjsua2.Error:
                    break

    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_terminal_settings)
    account.call = None
    account.shutdown()
    endpoint.libDestroy()


if __name__ == "__main__":
    main()