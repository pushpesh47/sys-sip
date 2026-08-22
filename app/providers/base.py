"""Provider abstraction for SIP providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from app.config.settings import SipProviderConfig


class ProvisioningState:
    """Provisioning state enumeration."""
    IDLE = "idle"
    WAITING_OTP = "waiting_otp"        # OTP requested, waiting for user input
    VERIFYING_OTP = "verifying_otp"    # OTP submitted, verifying with server
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class ProvisioningResult:
    """Result of a provisioning operation."""

    success: bool
    config: Optional[SipProviderConfig] = None
    error: Optional[str] = None
    requires_otp: bool = False
    otp_sent_to: Optional[str] = None
    state: str = ProvisioningState.IDLE


class SipProvider(ABC):
    """Abstract base class for SIP providers."""

    def __init__(self, config: SipProviderConfig):
        self.config = config

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""
        pass

    @property
    @abstractmethod
    def supports_provisioning(self) -> bool:
        """Return True if this provider supports automatic provisioning."""
        pass

    @abstractmethod
    def provision(self, otp: Optional[str] = None) -> ProvisioningResult:
        """
        Provision SIP credentials.

        Args:
            otp: Optional OTP code for providers that require it.

        Returns:
            ProvisioningResult with success status and config.
        """
        pass

    @abstractmethod
    def remove_account(self) -> ProvisioningResult:
        """Remove the provisioned account."""
        pass

    def get_config(self) -> SipProviderConfig:
        """Get the provider configuration."""
        return self.config

    def update_config(self, config: SipProviderConfig) -> None:
        """Update the provider configuration."""
        self.config = config


class GenericSipProvider(SipProvider):
    """Generic SIP provider - manual configuration only."""

    @property
    def provider_name(self) -> str:
        return "Generic SIP"

    @property
    def supports_provisioning(self) -> bool:
        return False

    def provision(self, otp: Optional[str] = None) -> ProvisioningResult:
        return ProvisioningResult(
            success=False,
            error="Generic SIP provider does not support automatic provisioning",
        )

    def remove_account(self) -> ProvisioningResult:
        return ProvisioningResult(
            success=True,
            config=None,
        )