import pytest
from unittest.mock import patch, MagicMock
from plugin import execute_set_keyboard_color_command

@patch('plugins.access-stock-tonic.plugin.OpenRGBClient')
def test_set_keyboard_color_valid(mock_openrgb):
    mock_client = MagicMock()
    mock_device = MagicMock()
    mock_client.devices = [mock_device]
    mock_openrgb.return_value = mock_client
    params = {'color': 'red'}
    result = execute_set_keyboard_color_command(params)
    assert result['success']
    mock_device.set_color.assert_called()

@patch('plugins.access-stock-tonic.plugin.OpenRGBClient')
def test_set_keyboard_color_invalid_color(mock_openrgb):
    params = {'color': 'notacolor'}
    result = execute_set_keyboard_color_command(params)
    assert not result['success']
    assert 'Unknown color' in result['message']

@patch('plugins.access-stock-tonic.plugin.OpenRGBClient')
def test_set_keyboard_color_missing_color(mock_openrgb):
    params = {}
    result = execute_set_keyboard_color_command(params)
    assert not result['success']
    assert 'Missing color' in result['message']

@patch('plugins.access-stock-tonic.plugin.OpenRGBClient')
def test_set_keyboard_color_no_devices(mock_openrgb):
    mock_client = MagicMock()
    mock_client.devices = []
    mock_openrgb.return_value = mock_client
    params = {'color': 'blue'}
    result = execute_set_keyboard_color_command(params)
    assert not result['success']
    assert 'No RGB devices found' in result['message'] 