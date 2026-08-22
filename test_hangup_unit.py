#!/usr/bin/env python3
"""
Simple unit test for hangup fix - tests the engine logic without full SIP stack.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from unittest.mock import MagicMock, patch, PropertyMock
from app.sip.engine import SipEngine, CallState
from app.config.settings import SipProviderConfig


def test_remove_call_double_cleanup():
    """Test that _remove_call handles double cleanup gracefully."""
    print("Testing _remove_call double cleanup...")
    
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
    
    # Mock the endpoint
    engine._endpoint = MagicMock()
    engine._account = MagicMock()
    
    # Add a fake call
    fake_call = MagicMock()
    fake_call.getId.return_value = 123
    fake_call.getMedia.return_value = None
    
    with engine._account_lock:
        engine._calls[123] = fake_call
        engine._call_media_connected[123] = True
    
    print("  Added fake call to engine")
    
    # Call _remove_call first time
    engine._remove_call(123)
    print("  First _remove_call() OK")
    
    # Call _remove_call second time - should not crash
    engine._remove_call(123)
    print("  Second _remove_call() OK (no crash)")
    
    # Verify call is removed
    with engine._account_lock:
        assert 123 not in engine._calls, "Call should be removed from _calls"
        assert 123 not in engine._call_media_connected, "Call should be removed from _call_media_connected"
    
    print("  Call properly removed from dicts")
    print("  PASSED")


def test_remove_call_media_cleanup():
    """Test that _remove_call cleans up media when connected."""
    print("\nTesting _remove_call media cleanup...")
    
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
    
    # Mock the endpoint and audio device manager
    mock_endpoint = MagicMock()
    mock_aud_dev_mgr = MagicMock()
    mock_capture_media = MagicMock()
    mock_playback_media = MagicMock()
    mock_call_media = MagicMock()
    
    mock_aud_dev_mgr.getCaptureDevMedia.return_value = mock_capture_media
    mock_aud_dev_mgr.getPlaybackDevMedia.return_value = mock_playback_media
    mock_endpoint.audDevManager.return_value = mock_aud_dev_mgr
    
    engine._endpoint = mock_endpoint
    engine._account = MagicMock()
    
    # Add a fake call with media connected
    fake_call = MagicMock()
    fake_call.getId.return_value = 456
    fake_call.getMedia.return_value = mock_call_media
    
    with engine._account_lock:
        engine._calls[456] = fake_call
        engine._call_media_connected[456] = True
    
    # Call _remove_call
    engine._remove_call(456)
    
    # Verify media cleanup was called
    mock_capture_media.stopTransmit.assert_called()
    mock_playback_media.stopTransmit.assert_called()
    mock_call_media.stopTransmit.assert_called()
    
    # Verify call is removed
    with engine._account_lock:
        assert 456 not in engine._calls
        assert 456 not in engine._call_media_connected
    
    print("  Media cleanup called correctly")
    print("  Call properly removed from dicts")
    print("  PASSED")


def test_remove_call_no_media():
    """Test that _remove_call works when media was not connected."""
    print("\nTesting _remove_call without media...")
    
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
    
    # Mock the endpoint
    engine._endpoint = MagicMock()
    engine._account = MagicMock()
    
    # Add a fake call WITHOUT media connected
    fake_call = MagicMock()
    fake_call.getId.return_value = 789
    
    with engine._account_lock:
        engine._calls[789] = fake_call
        # NOT adding to _call_media_connected
    
    # Call _remove_call - should not crash
    engine._remove_call(789)
    
    # Verify call is removed
    with engine._account_lock:
        assert 789 not in engine._calls
        assert 789 not in engine._call_media_connected
    
    print("  Call removed without media cleanup")
    print("  PASSED")


def test_hangup_call_not_in_dict():
    """Test that hangup_call returns False when call not in dict."""
    print("\nTesting hangup_call with missing call...")
    
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
    engine._account = MagicMock()
    
    # Try to hangup a call that doesn't exist
    result = engine.hangup_call(999)
    
    assert result == False, "hangup_call should return False for missing call"
    print("  hangup_call returned False as expected")
    print("  PASSED")


def test_call_state_mapping():
    """Test CallState enum values."""
    print("\nTesting CallState enum...")
    
    assert CallState.IDLE.value == "idle"
    assert CallState.CALLING.value == "calling"
    assert CallState.RINGING.value == "ringing"
    assert CallState.CONNECTING.value == "connecting"
    assert CallState.CONNECTED.value == "connected"
    assert CallState.DISCONNECTING.value == "disconnecting"
    assert CallState.DISCONNECTED.value == "disconnected"
    assert CallState.FAILED.value == "failed"
    
    print("  All CallState values correct")
    print("  PASSED")


if __name__ == "__main__":
    print("Running unit tests for hangup fix...")
    print("=" * 60)
    
    try:
        test_remove_call_double_cleanup()
        test_remove_call_media_cleanup()
        test_remove_call_no_media()
        test_hangup_call_not_in_dict()
        test_call_state_mapping()
        
        print("\n" + "=" * 60)
        print("ALL UNIT TESTS PASSED!")
        print("=" * 60)
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)