"""Centralized configuration management."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class SipProviderConfig:
    """Generic SIP provider configuration."""

    name: str
    username: str = ""
    password: str = ""
    domain: str = ""
    registrar_host: str = ""
    registrar_port: int = 5060
    proxy_host: str = ""
    proxy_port: int = 5060
    transport: str = "TLS"
    realm: str = ""
    user_agent: str = "JioSip/1.0"
    local_port: int = 5061
    rtp_port: int = 52000
    ipv4_address: str = "127.0.0.1"
    instance_id: str = ""
    reg_id: str = "1"
    contact_video: bool = True
    q_value: str = "0.5"
    p_access_network_info: str = ""
    icsi_ref: str = ""
    iari_ref: str = ""
    gsma_rcs_telephony: str = "none"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "username": self.username,
            "password": self.password,
            "domain": self.domain,
            "registrar_host": self.registrar_host,
            "registrar_port": self.registrar_port,
            "proxy_host": self.proxy_host,
            "proxy_port": self.proxy_port,
            "transport": self.transport,
            "realm": self.realm,
            "user_agent": self.user_agent,
            "local_port": self.local_port,
            "rtp_port": self.rtp_port,
            "ipv4_address": self.ipv4_address,
            "instance_id": self.instance_id,
            "reg_id": self.reg_id,
            "contact_video": self.contact_video,
            "q_value": self.q_value,
            "p_access_network_info": self.p_access_network_info,
            "icsi_ref": self.icsi_ref,
            "iari_ref": self.iari_ref,
            "gsma_rcs_telephony": self.gsma_rcs_telephony,
        }

    def build_p_preferred_identity(self) -> str:
        """Build P-Preferred-Identity header value."""
        username = self.username
        if not username.startswith("+"):
            username = f"+{username}"
        return f"<sip:{username}@{self.domain}>"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SipProviderConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_env(cls, env_vars: dict[str, str]) -> "SipProviderConfig":
        """Create config from environment variables (Jio Fiber format)."""
        return cls(
            name="Jio Fiber",
            username=env_vars.get("SIP_NUMBER", "").lstrip("+"),
            password=env_vars.get("SIP_PASSWORD", ""),
            domain=env_vars.get("SIP_HOME_NETWORK_DOMAIN", ""),
            registrar_host=env_vars.get("REGISTRAR_HOST", ""),
            registrar_port=int(env_vars.get("REGISTRAR_PORT", "5068")),
            proxy_host=env_vars.get("SIP_P_CSCF_ADDRESS", "").split(":")[0],
            proxy_port=int(env_vars.get("REGISTRAR_PORT", "5068")),
            transport=env_vars.get("SIP_SIGNALING_TRANSPORT", "TLS"),
            realm=env_vars.get("SIP_REALM", ""),
            user_agent=env_vars.get("USER_AGENT", "ParikaProxy/1.0"),
            local_port=int(env_vars.get("LOCAL_PORT", "5061")),
            rtp_port=int(env_vars.get("RTP_PORT", "52000")),
            ipv4_address=env_vars.get("IPV4_ADDRESS", "127.0.0.1"),
            instance_id=env_vars.get("SIP_INSTANCE", ""),
            reg_id=env_vars.get("SIP_REG_ID", "1"),
            contact_video=env_vars.get("SIP_CONTACT_VIDEO", "true").lower() == "true",
            q_value=env_vars.get("SIP_Q_VALUE", "0.5"),
            p_access_network_info=env_vars.get("P_ACCESS_NETWORK_INFO", ""),
            icsi_ref=env_vars.get("SIP_ICSI_REF", ""),
            iari_ref=env_vars.get("SIP_IARI_REF", ""),
            gsma_rcs_telephony=env_vars.get("SIP_GSMA_RCS_TELEPHONY", "none"),
        )


@dataclass
class Settings:
    """Application settings."""

    providers: list[SipProviderConfig] = field(default_factory=list)
    active_provider_index: int = -1
    config_dir: Path = field(default_factory=lambda: Path.home() / ".config" / "jio-sip")

    def __post_init__(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)

    @property
    def active_provider(self) -> Optional[SipProviderConfig]:
        if 0 <= self.active_provider_index < len(self.providers):
            return self.providers[self.active_provider_index]
        return None

    def add_provider(self, provider: SipProviderConfig) -> None:
        self.providers.append(provider)
        if self.active_provider_index == -1:
            self.active_provider_index = 0

    def remove_provider(self, index: int) -> None:
        if 0 <= index < len(self.providers):
            self.providers.pop(index)
            if self.active_provider_index >= len(self.providers):
                self.active_provider_index = len(self.providers) - 1

    def set_active_provider(self, index: int) -> None:
        if 0 <= index < len(self.providers):
            self.active_provider_index = index


def find_project_root() -> Path:
    """Find project root by looking for .env file."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / ".env").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent.parent.parent


def load_env_file(env_path: Optional[Path] = None) -> dict[str, str]:
    """Load .env file into a dictionary."""
    if env_path is None:
        env_path = find_project_root() / ".env"

    env_vars = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env_vars[key] = value
    return env_vars


def load_settings() -> Settings:
    """Load application settings from .env and config file."""
    env_vars = load_env_file()
    settings = Settings()

    if env_vars:
        jio_config = SipProviderConfig.from_env(env_vars)
        if jio_config.username and jio_config.password:
            settings.add_provider(jio_config)

    return settings