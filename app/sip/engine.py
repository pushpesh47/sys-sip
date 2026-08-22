"""SIP Engine - PJSUA2 integration layer."""

import queue
import threading
from enum import Enum
from typing import Any, Callable, Optional

import pjsua2

from app.config.settings import SipProviderConfig


class RegistrationState(Enum):
    """SIP registration states."""

    INITIALIZING = "initializing"
    CONNECTING = "connecting"
    REGISTERING = "registering"
    REGISTERED = "registered"
    REGISTRATION_FAILED = "registration_failed"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class CallState(Enum):
    """SIP call states."""

    IDLE = "idle"
    CALLING = "calling"
    RINGING = "ringing"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    FAILED = "failed"


class SipEngine:
    """
    SIP Engine managing PJSUA2 endpoint, transport, and account.

    This engine is provider-agnostic and uses generic SIP configuration.
    """

    def __init__(self, config: SipProviderConfig):
        self.config = config
        self._endpoint: Optional[pjsua2.Endpoint] = None
        self._account: Optional[pjsua2.Account] = None
        self._transport_id: int = -1
        self._registration_state = RegistrationState.INITIALIZING
        self._state_callbacks: list[Callable[[RegistrationState, str], None]] = []
        self._call_state_callbacks: list[Callable[[int, CallState, str], None]] = []
        self._incoming_call_callbacks: list[Callable[[int, str], None]] = []
        self._running = False
        self._event_thread: Optional[threading.Thread] = None
        self._account_lock = threading.Lock()
        self._calls: dict[int, pjsua2.Call] = {}
        self._call_media_connected: dict[int, bool] = {}  # Track media connection state
        self._calls_disconnecting: set[int] = set()  # Track calls pending termination
        self._pending_commands: queue.Queue[tuple[str, tuple, dict]] = queue.Queue()

    @property
    def registration_state(self) -> RegistrationState:
        return self._registration_state

    @property
    def is_registered(self) -> bool:
        return self._registration_state == RegistrationState.REGISTERED

    @property
    def is_running(self) -> bool:
        return self._running

    def add_state_callback(self, callback: Callable[[RegistrationState, str], None]) -> None:
        """Add a callback for registration state changes."""
        self._state_callbacks.append(callback)

    def remove_state_callback(self, callback: Callable[[RegistrationState, str], None]) -> None:
        """Remove a state callback."""
        if callback in self._state_callbacks:
            self._state_callbacks.remove(callback)

    def add_call_state_callback(self, callback: Callable[[int, CallState, str], None]) -> None:
        """Add a callback for call state changes."""
        self._call_state_callbacks.append(callback)

    def remove_call_state_callback(self, callback: Callable[[int, CallState, str], None]) -> None:
        """Remove a call state callback."""
        if callback in self._call_state_callbacks:
            self._call_state_callbacks.remove(callback)

    def add_incoming_call_callback(self, callback: Callable[[int, str], None]) -> None:
        """Add a callback for incoming calls."""
        self._incoming_call_callbacks.append(callback)

    def remove_incoming_call_callback(self, callback: Callable[[int, str], None]) -> None:
        """Remove an incoming call callback."""
        if callback in self._incoming_call_callbacks:
            self._incoming_call_callbacks.remove(callback)

    def _set_state(self, state: RegistrationState, reason: str = "") -> None:
        """Set registration state and notify callbacks."""
        if self._registration_state != state:
            self._registration_state = state
            for callback in self._state_callbacks:
                try:
                    callback(state, reason)
                except Exception:
                    pass  # Ignore callback errors

    def _notify_call_state(self, call_id: int, state: CallState, reason: str = "") -> None:
        """Notify call state change callbacks."""
        for callback in self._call_state_callbacks:
            try:
                callback(call_id, state, reason)
            except Exception:
                pass

    def _notify_incoming_call(self, call_id: int, remote_uri: str) -> None:
        """Notify incoming call callbacks."""
        for callback in self._incoming_call_callbacks:
            try:
                callback(call_id, remote_uri)
            except Exception:
                pass

    def initialize(self) -> bool:
        """
        Initialize PJSUA2 endpoint and create SIP transport.

        Returns:
            True if initialization succeeded, False otherwise.
        """
        try:
            self._set_state(RegistrationState.INITIALIZING, "Creating PJSUA2 endpoint")

            # Create endpoint
            self._endpoint = pjsua2.Endpoint()
            self._endpoint.libCreate()

            # Configure endpoint
            ep_config = pjsua2.EpConfig()
            ep_config.uaConfig.userAgent = self.config.user_agent
            ep_config.logConfig.level = 5
            ep_config.logConfig.consoleLevel = 5
            ep_config.medConfig.ptime = 20
            ep_config.medConfig.ecOptions = 1
            ep_config.medConfig.ecTailLen = 200
            ep_config.medConfig.audioFramePtime = 20

            self._set_state(RegistrationState.INITIALIZING, "Initializing PJSUA2 library")
            self._endpoint.libInit(ep_config)

            # Configure codecs - disable unwanted, prioritize AMR/AMR-WB
            self._configure_codecs()

            # Create TLS transport
            self._set_state(RegistrationState.CONNECTING, "Creating TLS transport")
            transport_config = pjsua2.TransportConfig()
            transport_config.port = self.config.local_port
            transport_config.tlsConfig.verifyServer = False

            self._transport_id = self._endpoint.transportCreate(
                pjsua2.PJSIP_TRANSPORT_TLS,
                transport_config
            )

            # Start the library
            self._endpoint.libStart()
            self._running = True

            # Start event handling thread
            self._event_thread = threading.Thread(target=self._event_loop, daemon=True)
            self._event_thread.start()

            return True

        except Exception as e:
            self._set_state(RegistrationState.ERROR, f"Initialization failed: {e}")
            self.cleanup()
            return False

    def _configure_codecs(self) -> None:
        """Configure audio codecs per Jio requirements."""
        if not self._endpoint:
            return

        # Disable unwanted codecs
        unwanted = [
            "speex/16000", "speex/8000", "speex/32000",
            "iLBC/8000", "GSM/8000",
            "PCMU/8000", "PCMA/8000", "G722/16000",
            "L16/44100/1", "L16/44100/2"
        ]
        for codec_id in unwanted:
            try:
                self._endpoint.codecSetPriority(codec_id, 0)
            except Exception:
                pass

        # Set AMR and AMR-WB to highest priority
        try:
            self._endpoint.codecSetPriority("AMR-WB/16000", 255)
            self._endpoint.codecSetPriority("AMR/8000", 254)
        except Exception:
            pass

        # Configure AMR-WB fmtp parameters
        try:
            codec_param = self._endpoint.codecGetParam("AMR-WB/16000")
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
            self._endpoint.codecSetParam("AMR-WB/16000", codec_param)
        except Exception:
            pass

        # Configure AMR fmtp parameters
        try:
            codec_param = self._endpoint.codecGetParam("AMR/8000")
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
            self._endpoint.codecSetParam("AMR/8000", codec_param)
        except Exception:
            pass

    def register(self) -> bool:
        """
        Create SIP account and register.

        Returns:
            True if registration was initiated, False on error.
        """
        if not self._endpoint or not self._running:
            self._set_state(RegistrationState.ERROR, "Engine not initialized")
            return False

        try:
            self._set_state(RegistrationState.REGISTERING, "Creating SIP account")

            # Build account configuration
            account_config = pjsua2.AccountConfig()
            account_config.natConfig.sipOutboundUse = False

            # Public identity
            sip_number = f"+{self.config.username}" if not self.config.username.startswith("+") else self.config.username
            account_config.idUri = f"sip:{sip_number}@{self.config.domain}"

            # Registrar and proxy
            account_config.regConfig.registrarUri = f"sip:{self.config.registrar_host}:{self.config.registrar_port}"
            account_config.sipConfig.proxies.append(
                f"sip:{self.config.proxy_host}:{self.config.proxy_port};transport=tls"
            )

            # Registration headers
            account_config.regConfig.headers = pjsua2.SipHeaderVector()
            header = pjsua2.SipHeader()
            header.hName = "P-Access-Network-Info"
            header.hValue = self.config.p_access_network_info
            account_config.regConfig.headers.append(header)

            # Contact parameters for REGISTER
            contact_parts = [
                f'+sip.instance="<{self.config.instance_id}>"',
                f"reg-id={self.config.reg_id}",
            ]
            if self.config.contact_video:
                contact_parts.append("video")
            account_config.regConfig.contactParams = ";" + ";".join(contact_parts)

            # Contact parameters for all SIP messages
            account_config.sipConfig.contactParams = account_config.regConfig.contactParams

            # Transport
            account_config.sipConfig.transportId = self._transport_id

            # Authentication credentials
            cred = pjsua2.AuthCredInfo()
            cred.scheme = "Digest"
            cred.realm = self.config.realm
            cred.username = f"{self.config.username}@{self.config.domain}"
            cred.data = self.config.password
            cred.dataType = 0

            account_config.sipConfig.authCreds = pjsua2.AuthCredInfoVector()
            account_config.sipConfig.authCreds.append(cred)

            # Create account with callback
            self._account = _SipAccountCallback(self, self.config)
            self._account.create(account_config)

            self._set_state(RegistrationState.REGISTERING, "Waiting for registration...")
            return True

        except Exception as e:
            self._set_state(RegistrationState.REGISTRATION_FAILED, f"Registration failed: {e}")
            return False

    def unregister(self) -> None:
        """Unregister and cleanup account."""
        with self._account_lock:
            if self._account:
                try:
                    self._account.shutdown()
                except Exception:
                    pass
                self._account = None

    def make_call(self, destination: str) -> bool:
        """
        Make an outgoing SIP call.

        Args:
            destination: Destination phone number or SIP URI.

        Returns:
            True if call was initiated, False on error.
        """
        if not self._account or not self._endpoint or not self._running:
            self._notify_call_state(-1, CallState.FAILED, "Engine not ready")
            return False

        try:
            call = _SipCallCallback(self, self.config)

            call_parameters = pjsua2.CallOpParam(True)
            
            # Build callee URI
            callee_uri = self._build_callee_uri(destination)
            call_parameters.txOption.targetUri = callee_uri

            # Add P-Preferred-Identity header
            preferred_identity = pjsua2.SipHeader()
            preferred_identity.hName = "P-Preferred-Identity"
            preferred_identity.hValue = self.config.build_p_preferred_identity()
            call_parameters.txOption.headers.append(preferred_identity)

            # Add P-Access-Network-Info header
            access_network_info = pjsua2.SipHeader()
            access_network_info.hName = "P-Access-Network-Info"
            access_network_info.hValue = self.config.p_access_network_info
            call_parameters.txOption.headers.append(access_network_info)

            # Add Supported header
            supported = pjsua2.SipHeader()
            supported.hName = "Supported"
            supported.hValue = "outbound, path, gruu, replaces, timer, norefersub, 100rel"
            call_parameters.txOption.headers.append(supported)

            # Add Allow header
            allow = pjsua2.SipHeader()
            allow.hName = "Allow"
            allow.hValue = "INVITE, ACK, CANCEL, OPTIONS, BYE, REFER, NOTIFY, UPDATE, PRACK, INFO"
            call_parameters.txOption.headers.append(allow)

            # Make the call - this creates the actual PJSUA2 call and assigns call ID
            call.makeCall(callee_uri, call_parameters)

            # Get call ID AFTER makeCall() - the call object now has a valid call ID
            call_id = call.getId()

            # Store call reference
            with self._account_lock:
                self._calls[call_id] = call

            self._notify_call_state(call_id, CallState.CALLING, destination)
            return True

        except Exception as e:
            self._notify_call_state(-1, CallState.FAILED, f"Failed to make call: {e}")
            return False

    def hangup_call(self, call_id: int) -> bool:
        """
        Hang up an active call.

        Args:
            call_id: Call ID to hang up.

        Returns:
            True if hangup was queued, False on error.
        """
        with self._account_lock:
            call = self._calls.get(call_id)
            if not call:
                return False

        # Queue the hangup command for execution on the PJSUA2 event thread.
        # This avoids cross-thread access to the SWIG Call proxy object,
        # which causes native crashes when the Qt thread calls hangup()
        # while the event thread processes the DISCONNECTED callback.
        self._pending_commands.put(("hangup", (call_id,), {}))
        return True

    def answer_call(self, call_id: int) -> bool:
        """
        Answer an incoming call.

        Args:
            call_id: Call ID to answer.

        Returns:
            True if answer was queued, False on error.
        """
        with self._account_lock:
            call = self._calls.get(call_id)
            if not call:
                return False

        # Queue the answer command for execution on the PJSUA2 event thread.
        # This avoids cross-thread access to the SWIG Call proxy object.
        self._pending_commands.put(("answer", (call_id,), {}))
        return True

    def reject_call(self, call_id: int) -> bool:
        """
        Reject an incoming call.

        Args:
            call_id: Call ID to reject.

        Returns:
            True if reject was queued, False on error.
        """
        with self._account_lock:
            call = self._calls.get(call_id)
            if not call:
                return False

        # Queue the reject command for execution on the PJSUA2 event thread.
        # This avoids cross-thread access to the SWIG Call proxy object.
        self._pending_commands.put(("reject", (call_id,), {}))
        return True

    def _remove_call(self, call_id: int) -> None:
        """Remove call from active calls dict and clean up media."""
        with self._account_lock:
            # Clean up media connections if they were established
            if self._call_media_connected.pop(call_id, False):
                self._cleanup_call_media(call_id)
            self._calls.pop(call_id, None)
            self._calls_disconnecting.discard(call_id)

    def _cleanup_call_media(self, call_id: int) -> None:
        """Clean up audio media connections for a call."""
        if not self._endpoint:
            return
        try:
            # Get the call object if still available
            call = self._calls.get(call_id)
            if call:
                try:
                    call_media = call.getMedia(0)
                    if call_media:
                        call_media = pjsua2.AudioMedia.typecastFromMedia(call_media)
                        # Stop call media transmission
                        call_media.stopTransmit()
                except Exception:
                    pass
            
            # Stop audio device media
            aud_dev_mgr = self._endpoint.audDevManager()
            aud_dev_mgr.getCaptureDevMedia().stopTransmit()
            aud_dev_mgr.getPlaybackDevMedia().stopTransmit()
        except Exception:
            pass

    def _build_callee_uri(self, destination: str) -> str:
        """Build callee SIP URI from destination number."""
        # For Jio Fiber, use phone-context parameter
        if self.config.name == "Jio Fiber":
            return f"sip:{destination}@{self.config.domain}?phone-context={self.config.domain}&user=phone"
        else:
            # Generic SIP URI
            if "@" in destination:
                return f"sip:{destination}"
            else:
                return f"sip:{destination}@{self.config.domain}"

    def _event_loop(self) -> None:
        """Main event loop for PJSUA2."""
        # Register this thread with pjsua2 endpoint
        try:
            if self._endpoint:
                self._endpoint.libRegisterThread("pjsua2_event_loop")
        except Exception:
            pass

        while self._running and self._endpoint:
            try:
                # Drain pending commands before handling events
                self._process_pending_commands()
                
                self._endpoint.libHandleEvents(100)
                
                # Drain pending commands after handling events
                self._process_pending_commands()
            except Exception:
                if self._running:
                    # Small delay to prevent busy loop on error
                    threading.Event().wait(0.1)

        # Unregister thread on exit
        try:
            if self._endpoint:
                # Note: libUnregisterThread doesn't exist, thread auto-unregisters on exit
                pass
        except Exception:
            pass

    def _process_pending_commands(self) -> None:
        """Process all pending SIP commands on the event thread."""
        while True:
            try:
                cmd, args, kwargs = self._pending_commands.get_nowait()
            except queue.Empty:
                break
            
            try:
                if cmd == "hangup":
                    self._execute_hangup(*args, **kwargs)
                elif cmd == "reject":
                    self._execute_reject(*args, **kwargs)
                elif cmd == "answer":
                    self._execute_answer(*args, **kwargs)
                else:
                    pass  # Unknown command - ignore
            except Exception:
                pass  # Ignore command execution errors

    def _execute_answer(self, call_id: int) -> None:
        """Execute incoming call answer on the event thread."""
        with self._account_lock:
            call = self._calls.get(call_id)
            if not call:
                return

            try:
                call.answer(pjsua2.CallOpParam(True))
            except Exception:
                pass

    def _execute_reject(self, call_id: int) -> None:
        """Execute incoming call rejection on the event thread."""
        with self._account_lock:
            call = self._calls.get(call_id)
            if not call:
                return

            # Mark call as disconnecting BEFORE calling PJSUA2 hangup()
            # to prevent race condition where callback fires before tracking set is updated
            self._calls_disconnecting.add(call_id)
            self._notify_call_state(call_id, CallState.DISCONNECTING, "Call rejected")

            try:
                # Use CallOpParam(True) with status code for rejection (e.g., 603 Decline)
                call.hangup(pjsua2.CallOpParam(True))
            except Exception:
                pass

    def _execute_hangup(self, call_id: int) -> None:
        """Execute hangup on the event thread."""
        with self._account_lock:
            call = self._calls.get(call_id)
            account = self._account
            if not call or not account:
                return

            self._calls_disconnecting.add(call_id)

        self._notify_call_state(call_id, CallState.DISCONNECTED, "Hangup completed")

        try:
            # Use a plain PJSUA2 Call wrapper for hangup.
            # The working PJSUA2 reference implementation performs hangup
            # through pjsua2.Call(account, call_id), not a Python Call subclass.
            hangup_call = pjsua2.Call(account, call_id)
            hangup_call.hangup(pjsua2.CallOpParam())
        except Exception as e:
            # If the call was already dead/disconnected in PJSUA2, 
            # log it or ignore, but the UI and internal state are already cleaned up.
            pass
        finally:
            self._remove_call(call_id)
            self._calls_disconnecting.discard(call_id)

    def cleanup(self) -> None:
        """Clean up PJSUA2 resources."""
        self._running = False

        with self._account_lock:
            # Clean up all active calls' media
            for call_id in list(self._call_media_connected.keys()):
                self._cleanup_call_media(call_id)
            self._call_media_connected.clear()
            
            if self._account:
                try:
                    self._account.shutdown()
                except Exception:
                    pass
                self._account = None
            self._calls.clear()
            self._calls_disconnecting.clear()

        if self._endpoint:
            try:
                self._endpoint.libDestroy()
            except Exception:
                pass
            self._endpoint = None

        self._transport_id = -1
        self._set_state(RegistrationState.DISCONNECTED, "Engine stopped")


class _SipAccountCallback(pjsua2.Account):
    """PJSUA2 Account callback handler."""

    def __init__(self, engine: SipEngine, config: SipProviderConfig):
        super().__init__()
        self._engine = engine
        self._config = config

    def onRegState(self, prm: pjsua2.OnRegStateParam) -> None:
        """Handle registration state changes."""
        info = self.getInfo()

        if prm.code == 200 and info.regIsActive:
            self._engine._set_state(RegistrationState.REGISTERED, "Registration successful")
        elif prm.code == 401:
            self._engine._set_state(RegistrationState.REGISTERING, "Authenticating...")
        elif prm.code >= 300:
            self._engine._set_state(RegistrationState.REGISTRATION_FAILED, f"Registration failed: {prm.reason}")
        else:
            self._engine._set_state(RegistrationState.REGISTERING, f"Registration: {prm.reason}")

    def onIncomingCall(self, prm: pjsua2.OnIncomingCallParam) -> None:
        """Handle incoming call."""
        # Create call callback object
        call = _SipCallCallback(self._engine, self._config, prm.callId)
        
        # Store call reference
        with self._engine._account_lock:
            self._engine._calls[prm.callId] = call
        
        # Get remote URI
        call_info = call.getInfo()
        remote_uri = call_info.remoteUri
        
        # Notify incoming call
        self._engine._notify_incoming_call(prm.callId, remote_uri)

    def onCallState(self, prm: pjsua2.OnCallStateParam) -> None:
        """Handle call state changes."""
        # Call state is handled exclusively by _SipCallCallback.
        # Do not create a temporary pjsua2.Call wrapper or notify the engine here.
        pass

    def onCallMediaState(self, prm: pjsua2.OnCallMediaStateParam) -> None:
        """Handle call media state changes."""
        # Media handling is owned by _SipCallCallback.
        # Do not configure call media from the account callback.
        pass

class _SipCallCallback(pjsua2.Call):
    """PJSUA2 Call callback handler."""

    def __init__(self, engine: SipEngine, config: SipProviderConfig, call_id: int = -1):
        if call_id >= 0:
            # For incoming calls, use the existing call ID
            super().__init__(engine._account, call_id)
        else:
            super().__init__(engine._account)
        self._engine = engine
        self._config = config

    def onCallState(self, prm: pjsua2.OnCallStateParam) -> None:
        """Handle call state changes."""
        info = self.getInfo()

        print(f"SIP CALLBACK: call_id={self.getId()} state={info.stateText} status={info.lastStatusCode} reason={info.lastReason}", flush=True)
        # Map PJSUA2 call state to our CallState enum
        state_map = {
            pjsua2.PJSIP_INV_STATE_NULL: CallState.IDLE,
            pjsua2.PJSIP_INV_STATE_CALLING: CallState.CALLING,
            pjsua2.PJSIP_INV_STATE_INCOMING: CallState.RINGING,
            pjsua2.PJSIP_INV_STATE_EARLY: CallState.CONNECTING,
            pjsua2.PJSIP_INV_STATE_CONNECTING: CallState.CONNECTING,
            pjsua2.PJSIP_INV_STATE_CONFIRMED: CallState.CONNECTED,
            pjsua2.PJSIP_INV_STATE_DISCONNECTED: CallState.DISCONNECTED,
        }
        
        call_state = state_map.get(info.state, CallState.IDLE)
        reason = f"{info.lastStatusCode} {info.lastReason}" if info.lastStatusCode else ""
        
        # Use self.getId() which returns the PJSUA-LIB call ID
        call_id = self.getId()
        
        # Handle DISCONNECTED state - this is the authoritative termination signal
        if info.state == pjsua2.PJSIP_INV_STATE_DISCONNECTED:
            if info.lastStatusCode >= 300:
                call_state = CallState.FAILED
            else:
                call_state = CallState.DISCONNECTED
            
            # Remove from disconnecting set since call has actually terminated
            self._engine._calls_disconnecting.discard(call_id)
            
            self._engine._notify_call_state(call_id, call_state, reason)
            
            # Clean up disconnected calls - this is the single place where call removal happens
            if call_state in (CallState.DISCONNECTED, CallState.FAILED):
                self._engine._remove_call(call_id)
            return
        
        # If call is in disconnecting phase but not yet DISCONNECTED, report DISCONNECTING
        if call_id in self._engine._calls_disconnecting:
            call_state = CallState.DISCONNECTING
        
        self._engine._notify_call_state(call_id, call_state, reason)

    def onCallMediaState(self, prm: pjsua2.OnCallMediaStateParam) -> None:
        """Handle call media state changes."""
        try:
            call_info = self.getInfo()
            endpoint = self._engine._endpoint

            if not endpoint:
                return

            for media_index, media in enumerate(call_info.media):
                if media.type != pjsua2.PJMEDIA_TYPE_AUDIO:
                    continue

                if media.status != pjsua2.PJSUA_CALL_MEDIA_ACTIVE:
                    continue

                audio_media = self.getAudioMedia(media_index)

                capture_device = endpoint.audDevManager().getCaptureDevMedia()
                playback_device = endpoint.audDevManager().getPlaybackDevMedia()

                audio_media.startTransmit(playback_device)
                capture_device.startTransmit(audio_media)

                self._engine._call_media_connected[self.getId()] = True

                print(f"[CALL] Audio media connected for call {self.getId()}.", flush=True)

        except Exception as e:
            print(f"[CALL] Audio media setup failed: {e}", flush=True)

    def onCallSdpCreated(self, prm: pjsua2.OnCallSdpCreatedParam) -> None:
        """Modify SDP for outgoing calls - match the working test implementation."""
        sdp = prm.sdp.wholeSdp
        lines = sdp.splitlines()
        new_lines = []
        
        for line in lines:
            # Fix origin line: o=- -> o=Juice with fixed session id
            if line.startswith("o="):
                line = f"o=Juice 1737281838294729 1737281838294729 IN IP4 {self._config.ipv4_address}"
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
                final_sdp_lines.append(f"c=IN IP4 {self._config.ipv4_address}")
        
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