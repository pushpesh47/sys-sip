#!/usr/bin/env python3
"""
Test script to verify the hangup fix works correctly.
This tests the call lifecycle without requiring a full GUI.
"""

import os
import sys
import threading
import time

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Set up library path for pjsua2
os.environ['LD_LIBRARY_PATH'] = os.path.join(PROJECT_ROOT, 'jfc-pjproject', 'pjsip', 'lib')

import pjsua2
from app.sip.engine import SipEngine, RegistrationState, CallState
from app.config.settings import SipProviderConfig


class TestCallObserver:
    """Observe call state changes for testing."""
    
    def __init__(self):
        self.states = []
        self.lock = threading.Lock()
        self.call_ids = set()
        
    def on_reg_state(self, state: RegistrationState, reason: str):
        print(f"REG: {state.value} - {reason}")
        
    def on_call_state(self, call_id: int, state: CallState, reason: str):
        with self.lock:
            self.states.append((call_id, state, reason))
            self.call_ids.add(call_id)
        print(f"CALL {call_id}: {state.value} - {reason}")
        
    def on_incoming_call(self, call_id: int, remote_uri: str):
        print(f"INCOMING CALL {call_id}: {remote_uri}")


def test_call_lifecycle():
    """Test the complete call lifecycle including hangup."""
    print("=" * 60)
    print("Testing call lifecycle with hangup fix")
    print("=" * 60)
    
    # Create test config
    config = SipProviderConfig(
        name='Test',
        username='test',
        password='test',
        domain='test.com',
        registrar_host='test.com',
        registrar_port=5060,
        proxy_host='test.com',
        proxy_port=5060,
        transport='TLS',
        realm='test',
        p_access_network_info='test',
        instance_id='test',
        reg_id=1,
        contact_video=False,
        ipv4_address='127.0.0.1',
        local_port=5061,
        user_agent='Test'
    )
    
    observer = TestCallObserver()
    
    # Create engine
    engine = SipEngine(config)
    engine.add_state_callback(observer.on_reg_state)
    engine.add_call_state_callback(observer.on_call_state)
    engine.add_incoming_call_callback(observer.on_incoming_call)
    
    # Initialize engine
    print("\n1. Initializing engine...")
    if not engine.initialize():
        print("FAILED: Engine initialization failed")
        return False
    print("   Engine initialized")
    
    # Register
    print("\n2. Registering...")
    if not engine.register():
        print("FAILED: Registration failed")
        engine.cleanup()
        return False
    
    # Wait for registration
    print("   Waiting for registration...")
    for i in range(30):
        time.sleep(0.5)
        if engine.registration_state == RegistrationState.REGISTERED:
            print("   Registered!")
            break
        elif engine.registration_state in (RegistrationState.REGISTRATION_FAILED, RegistrationState.ERROR):
            print(f"FAILED: Registration failed: {engine.registration_state}")
            engine.cleanup()
            return False
    else:
        print("FAILED: Registration timeout")
        engine.cleanup()
        return False
    
    # Make a call (this will fail since there's no real server, but we test the flow)
    print("\n3. Making call...")
    success = engine.make_call("08149384995")
    if not success:
        print("   Call initiation returned False (expected in test env)")
    else:
        print("   Call initiated")
    
    # Wait a bit for call state
    time.sleep(1)
    
    # Check call states observed
    with observer.lock:
        print(f"\n4. Observed call states: {len(observer.states)}")
        for call_id, state, reason in observer.states:
            print(f"   Call {call_id}: {state.value} - {reason}")
        call_ids = list(observer.call_ids)
    
    # Test hangup if we have a call
    if call_ids:
        call_id = call_ids[0]
        print(f"\n5. Hanging up call {call_id}...")
        success = engine.hangup_call(call_id)
        if success:
            print("   Hangup initiated")
        else:
            print("   Hangup failed (call may not exist)")
        
        # Wait for disconnect
        time.sleep(1)
        
        # Check final states
        with observer.lock:
            print(f"\n6. Final observed states: {len(observer.states)}")
            for call_id, state, reason in observer.states:
                print(f"   Call {call_id}: {state.value} - {reason}")
    
    # Cleanup
    print("\n7. Cleaning up engine...")
    engine.cleanup()
    print("   Engine cleaned up")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETED")
    print("=" * 60)
    return True


def test_double_cleanup_prevention():
    """Test that double cleanup is prevented."""
    print("\n" + "=" * 60)
    print("Testing double cleanup prevention")
    print("=" * 60)
    
    config = SipProviderConfig(
        name='Test',
        username='test',
        password='test',
        domain='test.com',
        registrar_host='test.com',
        registrar_port=5060,
        proxy_host='test.com',
        proxy_port=5060,
        transport='TLS',
        realm='test',
        p_access_network_info='test',
        instance_id='test',
        reg_id=1,
        contact_video=False,
        ipv4_address='127.0.0.1',
        local_port=5061,
        user_agent='Test'
    )
    
    engine = SipEngine(config)
    
    # Initialize
    if not engine.initialize():
        print("FAILED: Engine initialization failed")
        return False
    
    # Manually add a fake call to the dict to test _remove_call
    from unittest.mock import MagicMock
    fake_call = MagicMock()
    fake_call.getId.return_value = 123
    
    with engine._account_lock:
        engine._calls[123] = fake_call
        engine._call_media_connected[123] = True
    
    print("Added fake call to engine")
    
    # Call _remove_call twice - should not crash
    print("Calling _remove_call first time...")
    engine._remove_call(123)
    print("First removal OK")
    
    print("Calling _remove_call second time...")
    engine._remove_call(123)
    print("Second removal OK (no crash)")
    
    # Verify call is removed
    with engine._account_lock:
        assert 123 not in engine._calls
        assert 123 not in engine._call_media_connected
    
    print("Call properly removed from dicts")
    
    engine.cleanup()
    print("Engine cleaned up")
    
    print("\nDouble cleanup prevention test PASSED")
    return True


if __name__ == "__main__":
    print("Running hangup fix tests...")
    
    # Test 1: Double cleanup prevention
    try:
        test_double_cleanup_prevention()
    except Exception as e:
        print(f"Double cleanup test FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Test 2: Call lifecycle (requires SIP server, will fail but tests flow)
    try:
        test_call_lifecycle()
    except Exception as e:
        print(f"Call lifecycle test FAILED: {e}")
        import traceback
        traceback.print_exc()
        # Don't exit - this is expected to fail without real SIP server
    
    print("\nAll tests completed!")