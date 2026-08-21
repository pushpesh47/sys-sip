"""Shared environment loading and SIP configuration helpers."""

import os
from pathlib import Path

# Find project root by looking for .env file
def find_project_root() -> Path:
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / ".env").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent.parent

PROJECT_ROOT = find_project_root()


def load_env():
    """Load .env file into os.environ."""
    for line in (PROJECT_ROOT / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ[key] = value


class SipConfig:
    """SIP configuration derived from environment variables."""

    def __init__(self):
        self.sip_number = os.environ["SIP_NUMBER"]
        self.sip_password = os.environ["SIP_PASSWORD"]
        self.sip_realm = os.environ["SIP_REALM"]
        self.sip_home_network_domain = os.environ["SIP_HOME_NETWORK_DOMAIN"]
        self.sip_instance = os.environ["SIP_INSTANCE"]
        self.sip_reg_id = os.environ["SIP_REG_ID"]
        self.sip_contact_video = os.environ.get("SIP_CONTACT_VIDEO", "true").lower() == "true"
        self.sip_q_value = os.environ.get("SIP_Q_VALUE", "0.5")
        self.p_access_network_info = os.environ["P_ACCESS_NETWORK_INFO"]
        self.sip_icsi_ref = os.environ["SIP_ICSI_REF"]
        self.sip_iari_ref = os.environ["SIP_IARI_REF"]
        self.sip_gsma_rcs_telephony = os.environ["SIP_GSMA_RCS_TELEPHONY"]
        self.ipv4_address = os.environ["IPV4_ADDRESS"]
        self.local_port = int(os.environ["LOCAL_PORT"])
        self.rtp_port = int(os.environ["RTP_PORT"])
        self.registrar_host = os.environ["REGISTRAR_HOST"]
        self.registrar_port = int(os.environ["REGISTRAR_PORT"])
        self.user_agent = os.environ.get("USER_AGENT", "JFVoice/1.0")
        self.proxy_host = os.environ.get("SIP_P_CSCF_ADDRESS", self.registrar_host)
        # Remove port from proxy_host if present
        if ":" in self.proxy_host:
            self.proxy_host = self.proxy_host.split(":")[0]

    @property
    def sip_number_no_plus(self) -> str:
        """SIP number without leading + (e.g., 916546317451)."""
        return self.sip_number.lstrip("+")

    @property
    def public_id(self) -> str:
        """Public SIP identity: sip:+916546317451@br.wln.ims.jio.com"""
        return f"sip:{self.sip_number}@{self.sip_home_network_domain}"

    @property
    def private_id(self) -> str:
        """Private SIP identity: sip:916546317451@br.wln.ims.jio.com"""
        return f"sip:{self.sip_number_no_plus}@{self.sip_home_network_domain}"

    @property
    def auth_username(self) -> str:
        """Authentication username: 916546317451@br.wln.ims.jio.com"""
        return f"{self.sip_number_no_plus}@{self.sip_home_network_domain}"

    @property
    def contact_uri(self) -> str:
        """Contact URI for signaling: sip:+916546317451@<ipv4>:<port>;transport=tls"""
        return f"sip:{self.sip_number}@{self.ipv4_address}:{self.local_port};transport=tls"

    @property
    def contact_header(self) -> str:
        """Full Contact header value with instance, reg-id, and capabilities."""
        parts = [
            f"<{self.contact_uri}>",
            f'+sip.instance="{self.sip_instance}"',
            f"reg-id={self.sip_reg_id}",
        ]
        if self.sip_contact_video:
            parts.append("video")
        parts.append(f'+g.3pp.icsi-ref="urn%3Aurn-7%3A3gpp-service.ims.icsi.mmtel"')
        parts.append(f'+g.3gpp.iari-ref="urn%3Aurn-7%3A3gpp-application.ims.iari.rcs.jio.eucr"')
        parts.append(f'+g.gsma.rcs.telephony="{self.sip_gsma_rcs_telephony}"')
        parts.append(f'q={self.sip_q_value}')
        return ";".join(parts)

    @property
    def p_preferred_identity(self) -> str:
        """P-Preferred-Identity header value."""
        return f"<{self.public_id}>"

    @property
    def registrar_uri(self) -> str:
        """Registrar URI for registration."""
        return f"sip:{self.registrar_host}:{self.registrar_port}"

    @property
    def proxy_uri(self) -> str:
        """Proxy URI for outbound proxy."""
        return f"sip:{self.proxy_host}:{self.registrar_port};transport=tls"

    def build_callee_uri(self, callee_number: str) -> str:
        """Build callee URI with phone-context."""
        return f"sip:{callee_number}@{self.sip_home_network_domain}?phone-context={self.sip_home_network_domain}&user=phone"

    def build_register_contact(self) -> str:
        """Build Contact header for REGISTER (simpler than INVITE contact)."""
        parts = [
            f"<{self.contact_uri}>",
            f'+sip.instance="{self.sip_instance}"',
            f"reg-id={self.sip_reg_id}",
        ]
        if self.sip_contact_video:
            parts.append("video")
        return ";".join(parts)

    def build_prack_contact(self) -> str:
        """Build Contact header for PRACK/UPDATE."""
        return f"<{self.contact_uri}>"

    def build_register_contact_params(self) -> str:
        """Build contactParams for REGISTER (without angle brackets, for pjsua2)."""
        parts = [
            f'+sip.instance="<{self.sip_instance}>"',
            f"reg-id={self.sip_reg_id}",
            f'+g.3pp.icsi-ref="urn%3Aurn-7%3A3gpp-service.ims.icsi.mmtel"',
        ]
        if self.sip_contact_video:
            parts.append("video")
        return ";" + ";".join(parts)

    def build_invite_contact_params(self) -> str:
        """Build contactParams for INVITE (without angle brackets, for pjsua2)."""
        return self.build_register_contact_params()