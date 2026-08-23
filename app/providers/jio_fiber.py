"""Jio Fiber SIP provider integration."""

import threading
import time
from typing import Any, Optional

from app.config.settings import SipProviderConfig
from app.providers.base import ProvisioningResult, ProvisioningState, SipProvider


class JioFiberProvider(SipProvider):
    """Jio Fiber SIP provider with provisioning support."""

    @property
    def provider_name(self) -> str:
        return "Jio Fiber"

    @property
    def supports_provisioning(self) -> bool:
        return True

    def __init__(self, config: Optional[SipProviderConfig] = None):
        if config is None:
            config = SipProviderConfig(name="Jio Fiber")
        super().__init__(config)
        self._provisioner = None
        self._provisioning_thread: Optional[threading.Thread] = None
        self._otp_event = threading.Event()
        self._otp_code: Optional[str] = None
        self._provisioning_result: Optional[ProvisioningResult] = None
        self._cancel_provisioning = False
        self._msisdn: Optional[str] = None

    def _get_provisioner(self):
        """Lazy import and return the provisioner module."""
        if self._provisioner is None:
            import sys
            from pathlib import Path

            project_root = Path(__file__).resolve().parent.parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))

            import jio_fiber_sip_provisioner as provisioner_module
            self._provisioner = provisioner_module
        return self._provisioner

    def provision(self, otp: Optional[str] = None) -> ProvisioningResult:
        """
        Provision Jio Fiber SIP credentials.

        If otp is provided, use it to verify. Otherwise, start the provisioning
        process and wait for OTP via the GUI callback.
        """
        if otp is not None:
            return self._verify_otp(otp)

        # Start provisioning in background thread
        self._cancel_provisioning = False
        self._provisioning_result = None
        self._otp_event.clear()
        self._otp_code = None

        self._provisioning_thread = threading.Thread(target=self._run_provisioning, daemon=True)
        self._provisioning_thread.start()

        # Return a result indicating OTP is required - set state to WAITING_OTP
        return ProvisioningResult(
            success=False,
            requires_otp=True,
            error="Waiting for OTP...",
            state=ProvisioningState.WAITING_OTP,
        )

    def _run_provisioning(self):
        """Run the provisioning flow in a background thread."""
        try:
            provisioner = self._get_provisioner()

            # Step 1: Ensure endpoint is ready
            host, acc = provisioner.ensure_endpoint_ready(None)
            msisdn = acc.get("msisdn")
            if not msisdn:
                self._provisioning_result = ProvisioningResult(
                    success=False,
                    error="Could not determine MSISDN from router",
                )
                return

            # Store msisdn for use in _verify_otp
            self._msisdn = msisdn

            # Step 2: Request device add (triggers OTP)
            mac = provisioner.mac_from_hostname(provisioner.HARD_HOSTNAME)
            sess = provisioner.requests.Session()
            sess.verify = False

            add_resp = provisioner.ims_request(host, provisioner.HARD_HOSTNAME, mac, operation="add", session=sess)
            content_type = add_resp.headers.get("content-type", "").lower()

            if add_resp.status_code == 200 and "application/xml" in content_type:
                self._provisioning_result = ProvisioningResult(
                    success=False,
                    error=f"SIP account already exists for device. Remove it first.",
                )
                return

            if add_resp.status_code != 200:
                self._provisioning_result = ProvisioningResult(
                    success=False,
                    error=f"Registration request failed: HTTP {add_resp.status_code}",
                )
                return

            target_msisdn = add_resp.headers.get("x-amn", "<unknown>")

            # Handle cookies
            set_cookie_raw = add_resp.headers.get("set-cookie", "")
            from http.cookies import SimpleCookie
            sc = SimpleCookie()
            try:
                sc.load(set_cookie_raw)
            except Exception:
                sc = SimpleCookie()
            for key, morsel in sc.items():
                sess.cookies.set(key, morsel.value)

            # Signal that OTP was sent and wait for it
            self._provisioning_result = ProvisioningResult(
                success=False,
                requires_otp=True,
                otp_sent_to=target_msisdn,
                error="Waiting for OTP...",
                state=ProvisioningState.WAITING_OTP,
            )

            # Wait for OTP from GUI (with timeout)
            otp_received = self._otp_event.wait(timeout=300)  # 5 minute timeout
            if not otp_received or self._cancel_provisioning:
                self._provisioning_result = ProvisioningResult(
                    success=False,
                    error="Provisioning cancelled or timed out",
                )
                return

            # Verify OTP
            result = self._verify_otp(self._otp_code, sess, host, provisioner.HARD_HOSTNAME, mac)
            self._provisioning_result = result

        except Exception as e:
            self._provisioning_result = ProvisioningResult(
                success=False,
                error=f"Provisioning error: {str(e)}",
            )

    def _verify_otp(
        self,
        otp: str,
        session=None,
        host=None,
        hostname=None,
        mac=None,
    ) -> ProvisioningResult:
        """Verify OTP and fetch SIP config."""
        try:
            provisioner = self._get_provisioner()

            if session is None:
                sess = provisioner.requests.Session()
                sess.verify = False
            else:
                sess = session

            if host is None:
                host, _ = provisioner.ensure_endpoint_ready(None)

            if hostname is None:
                hostname = provisioner.HARD_HOSTNAME

            if mac is None:
                mac = provisioner.mac_from_hostname(provisioner.HARD_HOSTNAME)

            otp_int = int(otp)
            verify = provisioner.otp_verify(host, otp_int, session=sess)

            if verify.status_code != 200:
                # Try fallback cookies
                from http.cookies import SimpleCookie
                set_cookie_raw = ""
                if hasattr(self, '_last_add_resp'):
                    set_cookie_raw = self._last_add_resp.headers.get("set-cookie", "")
                sc = SimpleCookie()
                try:
                    sc.load(set_cookie_raw)
                except Exception:
                    sc = SimpleCookie()
                fallback_cookie_jar = provisioner.requests.cookies.cookiejar_from_dict(
                    {k: m.value for k, m in sc.items()}
                )
                verify2 = provisioner.requests.get(
                    f"https://{host}:{provisioner.IMS_PORT}/",
                    params={"OTP": otp_int},
                    cookies=fallback_cookie_jar,
                    verify=False,
                    timeout=8,
                )
                if verify2.status_code != 200:
                    return ProvisioningResult(
                        success=False,
                        requires_otp=True,
                        error=f"Invalid OTP. Please try again.",
                        otp_sent_to=self._provisioning_result.otp_sent_to if self._provisioning_result else None,
                        state=ProvisioningState.WAITING_OTP,
                    )

            # Step 3: Fetch SIP config
            root = provisioner.fetch_sip_config(host, hostname, mac, session=sess)
            sip = provisioner.parse_sip_values(root)

            realm = sip.get("realm", "ue.wln.ims.jio.com")
            # Use stored msisdn (from request_account) for SIP_NUMBER, not username from SIP config
            msisdn = self._msisdn or sip.get("username") or ""
            userpwd = sip.get("userpwd")

            if not userpwd:
                return ProvisioningResult(
                    success=False,
                    error="Could not obtain SIP password from router config",
                    state=ProvisioningState.FAILED,
                )

            # Build config
            local_ip = provisioner.get_local_ipv4()
            # SIP_NUMBER should be just the phone number with +91 prefix, no domain
            sip_number = f"+91{msisdn}" if msisdn and not msisdn.startswith("+") else (msisdn or "")

            config = SipProviderConfig(
                name="Jio Fiber",
                username=sip_number.lstrip("+"),
                password=userpwd,
                domain=sip.get("home_network_domain_name", "br.wln.ims.jio.com"),
                registrar_host=host,
                registrar_port=5068,
                proxy_host=sip.get("address", "").split(":")[0] if sip.get("address") else host,
                proxy_port=5068,
                transport="TLS",
                realm=realm,
                user_agent="ParikaProxy/1.0",
                local_port=5061,
                rtp_port=52000,
                ipv4_address=local_ip,
                instance_id=sip.get("uuid_value", ""),
                reg_id="1",
                contact_video=True,
                q_value="0.5",
                p_access_network_info="GPON;PSAPId=" + sip.get("psoltid", ""),
                icsi_ref="urn:urn-7:3gpp-service.ims.icsi.mmtel",
                iari_ref="urn:urn-7:3gpp-application.ims.iari.rcs.jio.eucr",
                gsma_rcs_telephony="none",
            )

            return ProvisioningResult(
                success=True,
                config=config,
                error=None,
                state=ProvisioningState.SUCCESS,
            )

        except ValueError:
            return ProvisioningResult(
                success=False,
                requires_otp=True,
                error="Invalid OTP format. Use digits only.",
                otp_sent_to=self._provisioning_result.otp_sent_to if self._provisioning_result else None,
                state=ProvisioningState.WAITING_OTP,
            )
        except Exception as e:
            return ProvisioningResult(
                success=False,
                error=f"OTP verification failed: {str(e)}",
                state=ProvisioningState.FAILED,
            )

    def submit_otp(self, otp: str) -> None:
        """Submit OTP from GUI."""
        self._otp_code = otp
        # Update state to indicate OTP is being verified
        if self._provisioning_result:
            self._provisioning_result.state = ProvisioningState.VERIFYING_OTP
        self._otp_event.set()

    def cancel_provisioning(self) -> None:
        """Cancel ongoing provisioning."""
        self._cancel_provisioning = True
        self._otp_event.set()

    def remove_account(self) -> ProvisioningResult:
        """Remove the Jio Fiber SIP account."""
        try:
            provisioner = self._get_provisioner()
            host, _ = provisioner.ensure_endpoint_ready(None)
            mac = provisioner.mac_from_hostname(provisioner.HARD_HOSTNAME)

            response = provisioner.remove_device(host, provisioner.HARD_HOSTNAME, mac)

            if response.status_code == 200:
                return ProvisioningResult(success=True, config=None, state=ProvisioningState.SUCCESS)
            else:
                return ProvisioningResult(
                    success=False,
                    error=f"Device removal failed: HTTP {response.status_code}",
                    state=ProvisioningState.FAILED,
                )

        except Exception as e:
            return ProvisioningResult(
                success=False,
                error=f"Account removal failed: {str(e)}",
                state=ProvisioningState.FAILED,
            )


def find_project_root() -> Path:
    """Find project root by looking for .env file."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / ".env").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent.parent.parent


# Import Path for the helper
from pathlib import Path