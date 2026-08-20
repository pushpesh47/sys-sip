from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pjsua2


PROJECT_DIR = Path(__file__).resolve().parent
ENV_FILE = PROJECT_DIR / ".env"
PROVISIONER = PROJECT_DIR / "jio_fiber_sip_provisioner.py"


def load_env() -> dict[str, str]:
    if not ENV_FILE.exists():
        print(".env was not found.")
        print("Running the Jio Fiber SIP provisioner...")

        subprocess.run(
            [sys.executable, str(PROVISIONER)],
            cwd=PROJECT_DIR,
            check=True,
        )

    if not ENV_FILE.exists():
        raise RuntimeError("Provisioner completed but .env was not created.")

    values: dict[str, str] = {}

    with ENV_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")

    return values


def require_env(values: dict[str, str], key: str) -> str:
    value = values.get(key, "").strip()

    if not value:
        raise RuntimeError(f"Missing required .env value: {key}")

    return value


class JioCall(pjsua2.Call):
    def __init__(self, account: pjsua2.Account, call_id: int = -1) -> None:
        super().__init__(account, call_id)

    def onCallState(self, prm: pjsua2.OnCallStateParam) -> None:
        call_info = self.getInfo()

        print(
            f"[CALL] state={call_info.stateText} "
            f"code={call_info.lastStatusCode} "
            f"reason={call_info.lastReason}"
        )

    def onCallMediaState(self, prm: pjsua2.OnCallMediaStateParam) -> None:
        call_info = self.getInfo()

        for media_index, media in enumerate(call_info.media):
            if media.type != pjsua2.PJMEDIA_TYPE_AUDIO:
                continue

            if media.status != pjsua2.PJSUA_CALL_MEDIA_ACTIVE:
                continue

            audio_media = self.getAudioMedia(media_index)
            endpoint = pjsua2.Endpoint.instance()

            capture_device = endpoint.audDevManager().getCaptureDevMedia()
            playback_device = endpoint.audDevManager().getPlaybackDevMedia()

            audio_media.startTransmit(playback_device)
            capture_device.startTransmit(audio_media)

            print("[CALL] Audio media connected.")


class JioAccount(pjsua2.Account):
    def onRegState(self, prm: pjsua2.OnRegStateParam) -> None:
        account_info = self.getInfo()

        print(
            f"[SIP] registration={account_info.regStatus} "
            f"code={account_info.regStatus} "
            f"reason={account_info.regReason}"
        )


def create_endpoint(values: dict[str, str]) -> pjsua2.Endpoint:
    endpoint = pjsua2.Endpoint()
    endpoint.libCreate()

    endpoint_config = pjsua2.EpConfig()
    endpoint_config.logConfig.level = int(values.get("LOG_LEVEL", "4"))
    endpoint_config.logConfig.consoleLevel = int(values.get("LOG_LEVEL", "4"))

    endpoint.libInit(endpoint_config)

    tls_config = pjsua2.TlsConfig()
    tls_config.verifyServer = values.get("TLS_VERIFY", "0") == "1"

    transport_config = pjsua2.TransportConfig()
    transport_config.port = int(values.get("LOCAL_PORT", "5061"))
    transport_config.tlsConfig = tls_config

    endpoint.transportCreate(
        pjsua2.PJSIP_TRANSPORT_TLS,
        transport_config,
    )

    endpoint.libStart()

    return endpoint


def create_account(endpoint: pjsua2.Endpoint, values: dict[str, str]) -> JioAccount:
    public_id = require_env(values, "PUBLIC_ID")
    username = require_env(values, "SIP_AUTH_USER")
    password = require_env(values, "SIP_PASSWORD")
    realm = require_env(values, "SIP_REALM")
    registrar_host = require_env(values, "REGISTRAR_HOST")
    registrar_port = int(require_env(values, "REGISTRAR_PORT"))
    proxy_host = require_env(values, "PROXY_HOST")
    proxy_port = int(require_env(values, "PROXY_PORT"))

    account_config = pjsua2.AccountConfig()
    account_config.natConfig.sipOutboundInstanceId = "<urn:uuid:00000000-0000-1000-8000-000026214437>"
    account_config.natConfig.sipOutboundRegId = "1"
    )

    account_config.idUri = public_id

    account_config.regConfig.registrarUri = (
        f"sips:{registrar_host}:{registrar_port};transport=tls"
    )

    account_config.regConfig.timeoutSec = 60

    account_config.sipConfig.authCreds.push_back(
        pjsua2.AuthCredInfo(
            "digest",
            realm,
            username,
            0,
            password,
        )
    )

    account_config.sipConfig.proxies.push_back(
        f"sips:{proxy_host}:{proxy_port};transport=tls"
    )

    account_config.videoConfig.autoTransmitOutgoing = False
    account_config.videoConfig.autoShowIncoming = False

    account = JioAccount()
    account.create(account_config)

    return account


def make_call(account: JioAccount, number: str) -> JioCall:
    values = load_env()
    realm = require_env(values, "SIP_REALM")

    number = number.strip()

    if not number:
        raise RuntimeError("Phone number cannot be empty.")

    if number.startswith("sip:"):
        destination = number
    elif number.startswith("+"):
        destination = f"sip:{number}@{realm}"
    else:
        destination = f"sip:+91{number}@{realm}"

    print(f"[CALL] Destination: {destination}")

    call = JioCall(account)

    call_parameters = pjsua2.CallOpParam(True)
    call.makeCall(destination, call_parameters)

    return call


def main() -> None:
    values = load_env()

    endpoint = None
    account = None
    call = None

    try:
        endpoint = create_endpoint(values)

        print(f"[SIP] PJSUA2: {endpoint.libVersion().full}")
        print(
            f"[SIP] Registrar: "
            f"{require_env(values, 'REGISTRAR_HOST')}:"
            f"{require_env(values, 'REGISTRAR_PORT')}"
        )

        account = create_account(endpoint, values)

        print("[SIP] Waiting for registration...")

        for _ in range(60):
            account_info = account.getInfo()

            if account_info.regStatus == 200:
                print("[SIP] Registration successful.")
                break

            if account_info.regStatus >= 300:
                raise RuntimeError(
                    f"SIP registration failed: "
                    f"{account_info.regStatus} {account_info.regReason}"
                )

            time.sleep(1)
        else:
            raise RuntimeError("SIP registration timed out.")

        number = input("Enter number to call: ").strip()

        call = make_call(account, number)

        print("[CALL] Call initiated.")
        print("[CALL] Press Ctrl+C to hang up.")

        while True:
            call_info = call.getInfo()

            if call_info.state >= pjsua2.PJSIP_INV_STATE_DISCONNECTED:
                break

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[CALL] Hanging up...")

    finally:
        if call is not None:
            try:
                call.hangup(pjsua2.CallOpParam())
            except Exception:
                pass

        if account is not None:
            try:
                account.shutdown()
            except Exception:
                pass

        if endpoint is not None:
            try:
                endpoint.libDestroy()
            except Exception:
                pass


if __name__ == "__main__":
    main()
