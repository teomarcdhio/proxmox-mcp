"""Async Proxmox API client for read-only operations."""

import logging
from typing import Any

import httpx

from .config import settings

logger = logging.getLogger(__name__)


class ProxmoxClientError(Exception):
    """Base exception for Proxmox client errors."""

    pass


class ProxmoxAuthError(ProxmoxClientError):
    """Authentication failed."""

    pass


class ProxmoxClient:
    """Async HTTP client for Proxmox VE API (read-only operations)."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._auth_ticket: str | None = None
        self._csrf_token: str | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=settings.proxmox_base_url,
                verify=settings.proxmox_verify_ssl,
                timeout=30.0,
            )
            await self._authenticate()
        return self._client

    async def _authenticate(self) -> None:
        """Authenticate with Proxmox API."""
        if settings.use_api_token:
            # API token auth - no ticket needed, just set header
            logger.info("Using API token authentication")
            return

        # Username/password authentication
        if not settings.proxmox_username or not settings.proxmox_password:
            raise ProxmoxAuthError(
                "No authentication configured. Set PROXMOX_API_TOKEN_ID and "
                "PROXMOX_API_TOKEN_SECRET, or PROXMOX_USERNAME and PROXMOX_PASSWORD."
            )

        logger.info(f"Authenticating as {settings.proxmox_username}@{settings.proxmox_realm}")

        try:
            response = await self._client.post(
                "/access/ticket",
                data={
                    "username": f"{settings.proxmox_username}@{settings.proxmox_realm}",
                    "password": settings.proxmox_password,
                },
            )
            response.raise_for_status()
            data = response.json()["data"]
            self._auth_ticket = data["ticket"]
            self._csrf_token = data["CSRFPreventionToken"]
            logger.info("Authentication successful")
        except httpx.HTTPStatusError as e:
            raise ProxmoxAuthError(f"Authentication failed: {e.response.text}") from e
        except Exception as e:
            raise ProxmoxAuthError(f"Authentication failed: {e}") from e

    def _get_headers(self) -> dict[str, str]:
        """Get authentication headers for API requests."""
        headers = {}

        if settings.use_api_token:
            # API token format: PVEAPIToken=user@realm!tokenid=secret
            headers["Authorization"] = (
                f"PVEAPIToken={settings.proxmox_api_token_id}={settings.proxmox_api_token_secret}"
            )
        elif self._auth_ticket:
            headers["Cookie"] = f"PVEAuthCookie={self._auth_ticket}"
            if self._csrf_token:
                headers["CSRFPreventionToken"] = self._csrf_token

        return headers

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        """Make an authenticated API request."""
        client = await self._get_client()
        headers = self._get_headers()

        try:
            response = await client.request(method, path, headers=headers, **kwargs)
            response.raise_for_status()
            return response.json().get("data")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                # Try re-authenticating once
                await self._authenticate()
                headers = self._get_headers()
                response = await client.request(method, path, headers=headers, **kwargs)
                response.raise_for_status()
                return response.json().get("data")
            raise ProxmoxClientError(f"API request failed: {e.response.text}") from e
        except Exception as e:
            raise ProxmoxClientError(f"API request failed: {e}") from e

    async def get(self, path: str, **kwargs) -> Any:
        """Make a GET request."""
        return await self._request("GET", path, **kwargs)

    # =========================================================================
    # Cluster & Node Operations
    # =========================================================================

    async def get_cluster_status(self) -> list[dict[str, Any]]:
        """Get cluster status including all nodes."""
        return await self.get("/cluster/status")

    async def get_nodes(self) -> list[dict[str, Any]]:
        """Get list of all nodes in the cluster."""
        return await self.get("/nodes")

    async def get_node_status(self, node: str) -> dict[str, Any]:
        """Get detailed status for a specific node."""
        return await self.get(f"/nodes/{node}/status")

    # =========================================================================
    # VM Operations (QEMU)
    # =========================================================================

    async def get_all_vms(self) -> list[dict[str, Any]]:
        """Get all VMs across all nodes."""
        nodes = await self.get_nodes()
        all_vms = []

        for node_info in nodes:
            node = node_info["node"]
            try:
                vms = await self.get("/nodes/{}/qemu".format(node))
                for vm in vms or []:
                    vm["node"] = node
                    all_vms.append(vm)
            except ProxmoxClientError as e:
                logger.warning(f"Failed to get VMs from node {node}: {e}")

        return all_vms

    async def get_vm_status(self, node: str, vmid: int) -> dict[str, Any]:
        """Get current status of a VM."""
        return await self.get(f"/nodes/{node}/qemu/{vmid}/status/current")

    async def get_vm_config(self, node: str, vmid: int) -> dict[str, Any]:
        """Get VM configuration."""
        return await self.get(f"/nodes/{node}/qemu/{vmid}/config")

    async def get_vm_rrddata(
        self, node: str, vmid: int, timeframe: str = "hour"
    ) -> list[dict[str, Any]]:
        """Get VM metrics/RRD data.

        Args:
            node: Node name
            vmid: VM ID
            timeframe: One of 'hour', 'day', 'week', 'month', 'year'
        """
        return await self.get(
            f"/nodes/{node}/qemu/{vmid}/rrddata", params={"timeframe": timeframe}
        )

    async def get_vm_snapshots(self, node: str, vmid: int) -> list[dict[str, Any]]:
        """Get list of VM snapshots."""
        return await self.get(f"/nodes/{node}/qemu/{vmid}/snapshot")

    # =========================================================================
    # Container Operations (LXC)
    # =========================================================================

    async def get_all_containers(self) -> list[dict[str, Any]]:
        """Get all LXC containers across all nodes."""
        nodes = await self.get_nodes()
        all_containers = []

        for node_info in nodes:
            node = node_info["node"]
            try:
                containers = await self.get(f"/nodes/{node}/lxc")
                for ct in containers or []:
                    ct["node"] = node
                    ct["type"] = "lxc"
                    all_containers.append(ct)
            except ProxmoxClientError as e:
                logger.warning(f"Failed to get containers from node {node}: {e}")

        return all_containers

    async def get_container_status(self, node: str, vmid: int) -> dict[str, Any]:
        """Get current status of a container."""
        return await self.get(f"/nodes/{node}/lxc/{vmid}/status/current")

    async def get_container_config(self, node: str, vmid: int) -> dict[str, Any]:
        """Get container configuration."""
        return await self.get(f"/nodes/{node}/lxc/{vmid}/config")

    # =========================================================================
    # Storage Operations
    # =========================================================================

    async def get_storage(self) -> list[dict[str, Any]]:
        """Get list of all storage pools."""
        return await self.get("/storage")

    async def get_node_storage(self, node: str) -> list[dict[str, Any]]:
        """Get storage status for a specific node."""
        return await self.get(f"/nodes/{node}/storage")

    # =========================================================================
    # Network Operations
    # =========================================================================

    async def get_node_networks(self, node: str) -> list[dict[str, Any]]:
        """Get network configuration for a node."""
        return await self.get(f"/nodes/{node}/network")

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Global client instance
proxmox = ProxmoxClient()
