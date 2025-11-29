"""Tests for Proxmox client."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# We'll test the client logic without actually connecting to Proxmox


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    with patch("proxmox_mcp.proxmox_client.settings") as mock:
        mock.proxmox_host = "test-proxmox"
        mock.proxmox_port = 8006
        mock.proxmox_verify_ssl = False
        mock.proxmox_base_url = "https://test-proxmox:8006/api2/json"
        mock.use_api_token = True
        mock.proxmox_api_token_id = "test@pve!test"
        mock.proxmox_api_token_secret = "test-secret"
        yield mock


@pytest.mark.asyncio
async def test_client_creates_auth_header(mock_settings):
    """Test that the client creates proper auth headers for API token."""
    from proxmox_mcp.proxmox_client import ProxmoxClient

    client = ProxmoxClient()
    headers = client._get_headers()

    assert "Authorization" in headers
    assert headers["Authorization"] == "PVEAPIToken=test@pve!test=test-secret"


@pytest.mark.asyncio
async def test_get_all_vms_aggregates_from_nodes(mock_settings):
    """Test that get_all_vms fetches VMs from all nodes."""
    from proxmox_mcp.proxmox_client import ProxmoxClient

    client = ProxmoxClient()

    # Mock the get method
    async def mock_get(path, **kwargs):
        if path == "/nodes":
            return [{"node": "pve1"}, {"node": "pve2"}]
        elif "/qemu" in path:
            if "pve1" in path:
                return [{"vmid": 100, "name": "vm1", "status": "running"}]
            else:
                return [{"vmid": 200, "name": "vm2", "status": "stopped"}]
        return []

    client.get = AsyncMock(side_effect=mock_get)

    vms = await client.get_all_vms()

    assert len(vms) == 2
    assert vms[0]["vmid"] == 100
    assert vms[0]["node"] == "pve1"
    assert vms[1]["vmid"] == 200
    assert vms[1]["node"] == "pve2"
