"""SIP application service layer."""

import threading
from typing import Callable, Optional

from app.config.settings import SipProviderConfig, Settings, load_settings
from app.providers import ProviderRegistry, create_default_provider
from app.providers.base import ProvisioningResult, SipProvider
from app.sip.engine import RegistrationState, CallState, SipEngine


class SipApplicationService:
    """
    Application service coordinating providers, SIP engine, and GUI.

    This is the main interface for the GUI to interact with the SIP system.
    """

    def __init__(self):
        self._settings = load_settings()
        self._providers: dict[int, SipProvider] = {}
        self._engine: Optional[SipEngine] = None
        self._provisioning_provider: Optional[SipProvider] = None
        self._provisioning_index: int = -1

        # Initialize providers from settings
        for i, provider_config in enumerate(self._settings.providers):
            provider = ProviderRegistry.create_provider(
                "jio_fiber" if provider_config.name == "Jio Fiber" else "generic",
                provider_config
            )
            self._providers[i] = provider

        # Qt event bridge for thread-safe GUI updates
        # Imported lazily to keep SIP engine Qt-independent
        self._qt_bridge = None

    @property
    def settings(self) -> Settings:
        return self._settings

    @property
    def active_provider(self) -> Optional[SipProvider]:
        idx = self._settings.active_provider_index
        return self._providers.get(idx)

    @property
    def engine(self) -> Optional[SipEngine]:
        return self._engine

    @property
    def registration_state(self) -> RegistrationState:
        if self._engine:
            return self._engine.registration_state
        return RegistrationState.DISCONNECTED

    @property
    def is_provisioning(self) -> bool:
        return self._provisioning_provider is not None

    def _get_qt_bridge(self):
        """Lazily import and return the Qt event bridge."""
        if self._qt_bridge is None:
            from app.gui.qt_bridge import QtEventBridge
            self._qt_bridge = QtEventBridge.instance()
        return self._qt_bridge

    def initialize_engine(self) -> bool:
        """Initialize SIP engine with active provider."""
        provider = self.active_provider
        if not provider:
            return False

        if self._engine:
            self._engine.cleanup()

        self._engine = SipEngine(provider.get_config())

        # Register internal callbacks that emit Qt signals for thread-safe GUI updates
        bridge = self._get_qt_bridge()

        def on_reg_state(state: RegistrationState, reason: str):
            bridge.registration_state_changed.emit(state, reason)

        def on_call_state(call_id: int, state: CallState, reason: str):
            bridge.call_state_changed.emit(call_id, state, reason)

        def on_incoming_call(call_id: int, remote_uri: str):
            bridge.incoming_call.emit(call_id, remote_uri)

        self._engine.add_state_callback(on_reg_state)
        self._engine.add_call_state_callback(on_call_state)
        self._engine.add_incoming_call_callback(on_incoming_call)

        success = self._engine.initialize()
        if success:
            self._engine.register()
        return success

    def start_registration(self) -> bool:
        """Start SIP registration."""
        if not self._engine:
            return self.initialize_engine()
        return self._engine.register()

    def stop(self) -> None:
        """Stop SIP engine."""
        if self._engine:
            self._engine.cleanup()
            self._engine = None

    # Call handling methods
    def make_call(self, destination: str) -> bool:
        """Make an outgoing call."""
        if self._engine:
            return self._engine.make_call(destination)
        return False

    def hangup_call(self, call_id: int) -> bool:
        """Hang up an active call."""
        if self._engine:
            return self._engine.hangup_call(call_id)
        return False

    def answer_call(self, call_id: int) -> bool:
        """Answer an incoming call."""
        if self._engine:
            return self._engine.answer_call(call_id)
        return False

    def reject_call(self, call_id: int) -> bool:
        """Reject an incoming call."""
        if self._engine:
            return self._engine.reject_call(call_id)
        return False

    def add_provider(self, provider_id: str, config: Optional[SipProviderConfig] = None) -> int:
        """Add a new SIP provider (for already configured providers like generic SIP)."""
        provider = ProviderRegistry.create_provider(provider_id, config)
        index = len(self._settings.providers)
        self._settings.add_provider(provider.get_config())
        self._providers[index] = provider
        return index

    def start_jio_provisioning(self) -> tuple[int, ProvisioningResult]:
        """Start Jio Fiber provisioning without adding to settings yet.
        
        Returns:
            Tuple of (provisioning_index, initial_result)
        """
        # Create a Jio Fiber provider for provisioning
        provider = ProviderRegistry.create_provider("jio_fiber")
        index = len(self._settings.providers)  # temporary index
        
        self._provisioning_provider = provider
        self._provisioning_index = index
        
        # Start provisioning
        result = provider.provision()
        
        return index, result

    def submit_jio_otp(self, otp: str) -> None:
        """Submit OTP for Jio Fiber provisioning."""
        if self._provisioning_provider and hasattr(self._provisioning_provider, 'submit_otp'):
            self._provisioning_provider.submit_otp(otp)

    def cancel_jio_provisioning(self) -> None:
        """Cancel ongoing Jio Fiber provisioning."""
        if self._provisioning_provider and hasattr(self._provisioning_provider, 'cancel_provisioning'):
            self._provisioning_provider.cancel_provisioning()
        self._provisioning_provider = None
        self._provisioning_index = -1

    def commit_jio_provisioning(self, index: int, result: ProvisioningResult) -> bool:
        """Commit successful Jio Fiber provisioning to settings."""
        if not result.success or not result.config:
            return False
        
        # Add the provider to settings now
        provider = self._provisioning_provider
        if provider is None:
            return False
        
        provider.update_config(result.config)
        self._settings.add_provider(result.config)
        self._providers[index] = provider
        
        # Clear provisioning state
        self._provisioning_provider = None
        self._provisioning_index = -1
        
        # Reinitialize engine if this is the active provider
        if index == self._settings.active_provider_index:
            self.initialize_engine()
        
        return True

    def get_jio_provisioning_status(self) -> Optional[ProvisioningResult]:
        """Get the current Jio Fiber provisioning status."""
        if self._provisioning_provider and hasattr(self._provisioning_provider, '_provisioning_result'):
            return self._provisioning_provider._provisioning_result
        return None

    def remove_provider(self, index: int) -> bool:
        """Remove a SIP provider."""
        if index in self._providers:
            # If removing active provider, stop engine first
            if index == self._settings.active_provider_index:
                self.stop()

            del self._providers[index]
            self._settings.remove_provider(index)

            # Reindex providers
            new_providers = {}
            for i, (old_idx, provider) in enumerate(sorted(self._providers.items())):
                new_providers[i] = provider
            self._providers = new_providers

            return True
        return False

    def set_active_provider(self, index: int) -> bool:
        """Set the active provider."""
        if index in self._providers:
            self._settings.set_active_provider(index)
            # Reinitialize engine with new provider
            self.initialize_engine()
            return True
        return False

    def provision_provider(self, index: int, otp: Optional[str] = None) -> ProvisioningResult:
        """Provision a provider (Jio Fiber) - for re-provisioning existing configured accounts."""
        provider = self._providers.get(index)
        if not provider:
            return ProvisioningResult(success=False, error="Provider not found")

        if not provider.supports_provisioning:
            return ProvisioningResult(success=False, error="Provider does not support provisioning")

        result = provider.provision(otp)

        if result.success and result.config:
            # Update provider config and settings
            provider.update_config(result.config)
            self._settings.providers[index] = result.config

            # Reinitialize engine if this is the active provider
            if index == self._settings.active_provider_index:
                self.initialize_engine()

        return result

    def submit_otp(self, index: int, otp: str) -> None:
        """Submit OTP for provisioning."""
        provider = self._providers.get(index)
        if provider and hasattr(provider, 'submit_otp'):
            provider.submit_otp(otp)

    def cancel_provisioning(self, index: int) -> None:
        """Cancel ongoing provisioning."""
        provider = self._providers.get(index)
        if provider and hasattr(provider, 'cancel_provisioning'):
            provider.cancel_provisioning()

    def remove_account(self, index: int) -> ProvisioningResult:
        """Remove a provisioned account."""
        provider = self._providers.get(index)
        if not provider:
            return ProvisioningResult(success=False, error="Provider not found")

        # Stop engine if this is the active provider
        if index == self._settings.active_provider_index:
            self.stop()

        result = provider.remove_account()

        if result.success:
            # Remove provider from settings
            self.remove_provider(index)

        return result

    def get_provisioning_status(self, index: int) -> Optional[ProvisioningResult]:
        """Get the current provisioning status for a provider."""
        provider = self._providers.get(index)
        if provider and hasattr(provider, '_provisioning_result'):
            return provider._provisioning_result
        return None


# Global service instance
_service_instance: Optional[SipApplicationService] = None


def get_service() -> SipApplicationService:
    """Get the global SIP application service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = SipApplicationService()
    return _service_instance