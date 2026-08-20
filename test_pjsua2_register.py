import os
import time
from pathlib import Path

import pjsua2


PROJECT_ROOT = Path(__file__).resolve().parent


def load_env():
    for line in (PROJECT_ROOT / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ[key] = value


class SipAccount(pjsua2.Account):
    def onRegState(self, prm):
        info = self.getInfo()
        print(f"REGISTRATION: code={prm.code} reason={prm.reason} active={info.regIsActive}")


def main():
    load_env()

    username = os.environ["SIP_AUTH_USER"]
    password = os.environ["SIP_PASSWORD"]
    realm = os.environ["SIP_REALM"]
    host = os.environ["REGISTRAR_HOST"]

    endpoint = pjsua2.Endpoint()
    endpoint.libCreate()

    ep_config = pjsua2.EpConfig()
    ep_config.uaConfig.userAgent = "ParikaProxy/1.0"
    ep_config.logConfig.level = 5
    ep_config.logConfig.consoleLevel = 5
    endpoint.libInit(ep_config)

    transport_config = pjsua2.TransportConfig()
    transport_config.port = int(os.environ.get("REGISTRAR_PORT", 5068))
    transport_config.tlsConfig.verifyServer = False

    transport_id = endpoint.transportCreate(
        pjsua2.PJSIP_TRANSPORT_TLS,
        transport_config
    )

    endpoint.libStart()

    account_config = pjsua2.AccountConfig()
    account_config.natConfig.sipOutboundUse = False
    account_config.idUri = os.environ["PUBLIC_ID"]

    account_config.regConfig.registrarUri = f"sip:{host}:{os.environ['REGISTRAR_PORT']}"

    account_config.regConfig.headers = pjsua2.SipHeaderVector()

    header = pjsua2.SipHeader()
    header.hName = "P-Access-Network-Info"
    header.hValue = os.environ["P_ACCESS_NETWORK_INFO"]
    account_config.regConfig.headers.append(header)

    account_config.regConfig.contactParams = (
        f";+sip.instance=\"<{os.environ['SIP_INSTANCE']}>\""
        f";reg-id={os.environ['SIP_REG_ID']}"
        + (";video" if os.environ.get("SIP_CONTACT_VIDEO", "").lower() == "true" else "")
    )

    account_config.sipConfig.transportId = transport_id

    cred = pjsua2.AuthCredInfo()
    cred.scheme = "Digest"
    cred.realm = realm
    cred.username = username
    cred.data = password
    cred.dataType = 0

    account_config.sipConfig.authCreds = pjsua2.AuthCredInfoVector()
    account_config.sipConfig.authCreds.append(cred)

    account = SipAccount()
    account.create(account_config)

    print("PJSUA2 account created.")
    print(f"Registrar: {host}:5068")
    print(f"Username:  {username}")
    print("Waiting for registration...")

    for _ in range(15):
        endpoint.libHandleEvents(1000)

    account.shutdown()
    endpoint.libDestroy()


if __name__ == "__main__":
    main()
