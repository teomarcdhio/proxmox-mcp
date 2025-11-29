"""VM-related MCP tools for Proxmox."""

import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..proxmox_client import proxmox

logger = logging.getLogger(__name__)


def register_vm_tools(mcp: FastMCP) -> None:
    """Register all VM-related tools with the MCP server."""

    @mcp.tool()
    async def list_vms() -> list[dict[str, Any]]:
        """List all VMs and containers across all Proxmox nodes.

        Returns a list of all virtual machines and LXC containers with their
        basic information including:
        - vmid: The VM/container ID
        - name: The VM/container name
        - status: Current status (running, stopped, etc.)
        - node: The Proxmox node hosting this VM
        - type: 'qemu' for VMs or 'lxc' for containers
        - cpu: Number of CPUs
        - maxmem: Maximum memory in bytes
        - maxdisk: Maximum disk size in bytes
        """
        logger.info("Listing all VMs and containers")

        # Get both VMs and containers
        vms = await proxmox.get_all_vms()
        containers = await proxmox.get_all_containers()

        # Mark VMs with type
        for vm in vms:
            vm["type"] = "qemu"

        all_guests = vms + containers

        # Return simplified, consistent format
        result = []
        for guest in all_guests:
            result.append(
                {
                    "vmid": guest.get("vmid"),
                    "name": guest.get("name", f"VM-{guest.get('vmid')}"),
                    "status": guest.get("status"),
                    "node": guest.get("node"),
                    "type": guest.get("type"),
                    "cpus": guest.get("cpus", guest.get("maxcpu", 0)),
                    "memory_bytes": guest.get("maxmem", 0),
                    "disk_bytes": guest.get("maxdisk", 0),
                    "uptime_seconds": guest.get("uptime", 0),
                }
            )

        logger.info(f"Found {len(result)} VMs/containers")
        return result

    @mcp.tool()
    async def get_vm_info(vmid: int, node: str | None = None) -> dict[str, Any]:
        """Get detailed information about a specific VM or container.

        Args:
            vmid: The VM or container ID (e.g., 100, 101)
            node: The Proxmox node name. If not provided, will search all nodes.

        Returns detailed configuration including:
        - Hardware: CPU, memory, disks, network interfaces
        - Settings: Boot order, OS type, description
        - Status: Current state, uptime, resource usage
        """
        logger.info(f"Getting info for VM {vmid} on node {node or 'auto-detect'}")

        # If node not provided, find the VM
        if node is None:
            all_vms = await proxmox.get_all_vms()
            all_containers = await proxmox.get_all_containers()

            for vm in all_vms + all_containers:
                if vm.get("vmid") == vmid:
                    node = vm.get("node")
                    break

            if node is None:
                return {"error": f"VM {vmid} not found on any node"}

        # Try QEMU first, then LXC
        try:
            config = await proxmox.get_vm_config(node, vmid)
            status = await proxmox.get_vm_status(node, vmid)
            vm_type = "qemu"
        except Exception:
            try:
                config = await proxmox.get_container_config(node, vmid)
                status = await proxmox.get_container_status(node, vmid)
                vm_type = "lxc"
            except Exception as e:
                return {"error": f"Failed to get VM/container info: {e}"}

        # Parse network interfaces
        networks = []
        for key, value in config.items():
            if key.startswith("net") and value:
                networks.append({"interface": key, "config": value})

        # Parse disks
        disks = []
        disk_prefixes = ("scsi", "virtio", "ide", "sata", "rootfs", "mp")
        for key, value in config.items():
            if any(key.startswith(p) for p in disk_prefixes) and value:
                if isinstance(value, str) and (":" in value or "volume" in value.lower()):
                    disks.append({"device": key, "config": value})

        return {
            "vmid": vmid,
            "node": node,
            "type": vm_type,
            "name": config.get("name", status.get("name", f"VM-{vmid}")),
            "description": config.get("description", ""),
            "status": status.get("status"),
            "uptime_seconds": status.get("uptime", 0),
            "hardware": {
                "cpus": config.get("cores", config.get("cpulimit", 1)),
                "sockets": config.get("sockets", 1),
                "memory_mb": config.get("memory", 0),
                "balloon": config.get("balloon", None),
            },
            "cpu_usage_percent": round(status.get("cpu", 0) * 100, 2),
            "memory_usage_bytes": status.get("mem", 0),
            "memory_total_bytes": status.get("maxmem", 0),
            "disk_read_bytes": status.get("diskread", 0),
            "disk_write_bytes": status.get("diskwrite", 0),
            "network_in_bytes": status.get("netin", 0),
            "network_out_bytes": status.get("netout", 0),
            "networks": networks,
            "disks": disks,
            "boot_order": config.get("boot", ""),
            "os_type": config.get("ostype", ""),
            "machine_type": config.get("machine", ""),
        }

    @mcp.tool()
    async def get_vm_status(vmid: int, node: str | None = None) -> dict[str, Any]:
        """Get the current runtime status of a VM or container.

        Args:
            vmid: The VM or container ID
            node: The Proxmox node name (optional, will auto-detect)

        Returns:
        - status: running, stopped, paused, etc.
        - uptime: How long the VM has been running
        - cpu: Current CPU usage percentage
        - memory: Current memory usage
        - network I/O stats
        - disk I/O stats
        """
        logger.info(f"Getting status for VM {vmid}")

        # Find node if not provided
        if node is None:
            all_vms = await proxmox.get_all_vms()
            all_containers = await proxmox.get_all_containers()

            for vm in all_vms + all_containers:
                if vm.get("vmid") == vmid:
                    node = vm.get("node")
                    break

            if node is None:
                return {"error": f"VM {vmid} not found"}

        # Try QEMU first, then LXC
        try:
            status = await proxmox.get_vm_status(node, vmid)
            vm_type = "qemu"
        except Exception:
            try:
                status = await proxmox.get_container_status(node, vmid)
                vm_type = "lxc"
            except Exception as e:
                return {"error": f"Failed to get status: {e}"}

        return {
            "vmid": vmid,
            "node": node,
            "type": vm_type,
            "name": status.get("name", f"VM-{vmid}"),
            "status": status.get("status"),
            "uptime_seconds": status.get("uptime", 0),
            "cpu_usage_percent": round(status.get("cpu", 0) * 100, 2),
            "memory_used_bytes": status.get("mem", 0),
            "memory_total_bytes": status.get("maxmem", 0),
            "memory_usage_percent": round(
                (status.get("mem", 0) / max(status.get("maxmem", 1), 1)) * 100, 2
            ),
            "disk_read_bytes": status.get("diskread", 0),
            "disk_write_bytes": status.get("diskwrite", 0),
            "network_in_bytes": status.get("netin", 0),
            "network_out_bytes": status.get("netout", 0),
            "pid": status.get("pid"),
            "qmpstatus": status.get("qmpstatus"),  # QEMU Machine Protocol status
        }

    @mcp.tool()
    async def get_vm_metrics(
        vmid: int, node: str | None = None, timeframe: str = "hour"
    ) -> dict[str, Any]:
        """Get historical metrics/performance data for a VM.

        Args:
            vmid: The VM or container ID
            node: The Proxmox node name (optional)
            timeframe: Time range for metrics - one of:
                - 'hour': Last hour (default)
                - 'day': Last 24 hours
                - 'week': Last 7 days
                - 'month': Last 30 days
                - 'year': Last year

        Returns time-series data including:
        - CPU usage over time
        - Memory usage over time
        - Network I/O over time
        - Disk I/O over time
        """
        logger.info(f"Getting metrics for VM {vmid} over {timeframe}")

        if timeframe not in ("hour", "day", "week", "month", "year"):
            return {"error": f"Invalid timeframe: {timeframe}. Use hour/day/week/month/year"}

        # Find node if not provided
        if node is None:
            all_vms = await proxmox.get_all_vms()
            for vm in all_vms:
                if vm.get("vmid") == vmid:
                    node = vm.get("node")
                    break

            if node is None:
                return {"error": f"VM {vmid} not found"}

        try:
            rrd_data = await proxmox.get_vm_rrddata(node, vmid, timeframe)
        except Exception as e:
            return {"error": f"Failed to get metrics: {e}"}

        if not rrd_data:
            return {
                "vmid": vmid,
                "node": node,
                "timeframe": timeframe,
                "message": "No metrics data available",
                "data_points": [],
            }

        # Process and return the metrics
        data_points = []
        for point in rrd_data:
            data_points.append(
                {
                    "timestamp": point.get("time"),
                    "cpu_percent": round((point.get("cpu", 0) or 0) * 100, 2),
                    "memory_bytes": point.get("mem", 0),
                    "memory_max_bytes": point.get("maxmem", 0),
                    "disk_read_bytes": point.get("diskread", 0),
                    "disk_write_bytes": point.get("diskwrite", 0),
                    "network_in_bytes": point.get("netin", 0),
                    "network_out_bytes": point.get("netout", 0),
                }
            )

        return {
            "vmid": vmid,
            "node": node,
            "timeframe": timeframe,
            "data_points_count": len(data_points),
            "data_points": data_points,
        }

    @mcp.tool()
    async def list_nodes() -> list[dict[str, Any]]:
        """List all Proxmox nodes in the cluster.

        Returns information about each node including:
        - Node name and status
        - CPU and memory resources
        - Running VMs count
        - Uptime
        """
        logger.info("Listing all Proxmox nodes")

        nodes = await proxmox.get_nodes()

        result = []
        for node in nodes:
            result.append(
                {
                    "node": node.get("node"),
                    "status": node.get("status"),
                    "cpu_usage_percent": round((node.get("cpu", 0) or 0) * 100, 2),
                    "memory_used_bytes": node.get("mem", 0),
                    "memory_total_bytes": node.get("maxmem", 0),
                    "memory_usage_percent": round(
                        (node.get("mem", 0) / max(node.get("maxmem", 1), 1)) * 100, 2
                    ),
                    "disk_used_bytes": node.get("disk", 0),
                    "disk_total_bytes": node.get("maxdisk", 0),
                    "uptime_seconds": node.get("uptime", 0),
                }
            )

        return result

    @mcp.tool()
    async def list_vm_snapshots(vmid: int, node: str | None = None) -> list[dict[str, Any]]:
        """List all snapshots for a VM.

        Args:
            vmid: The VM ID
            node: The Proxmox node name (optional, will auto-detect)

        Returns list of snapshots with:
        - Snapshot name and description
        - Creation time
        - Whether it includes RAM state
        """
        logger.info(f"Listing snapshots for VM {vmid}")

        # Find node if not provided
        if node is None:
            all_vms = await proxmox.get_all_vms()
            for vm in all_vms:
                if vm.get("vmid") == vmid:
                    node = vm.get("node")
                    break

            if node is None:
                return [{"error": f"VM {vmid} not found"}]

        try:
            snapshots = await proxmox.get_vm_snapshots(node, vmid)
        except Exception as e:
            return [{"error": f"Failed to get snapshots: {e}"}]

        result = []
        for snap in snapshots or []:
            if snap.get("name") == "current":
                continue  # Skip the 'current' pseudo-snapshot

            result.append(
                {
                    "name": snap.get("name"),
                    "description": snap.get("description", ""),
                    "snaptime": snap.get("snaptime"),
                    "vmstate": snap.get("vmstate", False),  # True if RAM included
                    "parent": snap.get("parent"),
                }
            )

        return result

    @mcp.tool()
    async def get_cluster_status() -> dict[str, Any]:
        """Get overall Proxmox cluster status and health.

        Returns:
        - Cluster name and quorum status
        - List of all nodes with their status
        - Total resources (CPU, memory, storage)
        """
        logger.info("Getting cluster status")

        try:
            cluster_status = await proxmox.get_cluster_status()
        except Exception as e:
            return {"error": f"Failed to get cluster status: {e}"}

        nodes = []
        cluster_info = {}

        for item in cluster_status or []:
            if item.get("type") == "cluster":
                cluster_info = {
                    "name": item.get("name"),
                    "nodes_count": item.get("nodes", 0),
                    "quorate": item.get("quorate", 0) == 1,
                    "version": item.get("version"),
                }
            elif item.get("type") == "node":
                nodes.append(
                    {
                        "name": item.get("name"),
                        "id": item.get("id"),
                        "online": item.get("online", 0) == 1,
                        "local": item.get("local", 0) == 1,
                        "ip": item.get("ip"),
                    }
                )

        # Get aggregate stats
        node_details = await proxmox.get_nodes()
        total_cpu = 0
        total_mem = 0
        total_disk = 0
        used_mem = 0
        used_disk = 0

        for n in node_details:
            total_mem += n.get("maxmem", 0)
            total_disk += n.get("maxdisk", 0)
            used_mem += n.get("mem", 0)
            used_disk += n.get("disk", 0)
            total_cpu += n.get("maxcpu", 0)

        return {
            "cluster": cluster_info,
            "nodes": nodes,
            "totals": {
                "cpu_cores": total_cpu,
                "memory_total_bytes": total_mem,
                "memory_used_bytes": used_mem,
                "memory_usage_percent": round((used_mem / max(total_mem, 1)) * 100, 2),
                "disk_total_bytes": total_disk,
                "disk_used_bytes": used_disk,
                "disk_usage_percent": round((used_disk / max(total_disk, 1)) * 100, 2),
            },
        }

    @mcp.tool()
    async def get_vm_filesystem_info(vmid: int, node: str | None = None) -> dict[str, Any]:
        """Get filesystem/disk space information from inside a VM using the QEMU guest agent.

        This requires the qemu-guest-agent to be installed and running inside the VM.
        Install it with: apt install qemu-guest-agent (Debian/Ubuntu) or
        yum install qemu-guest-agent (RHEL/CentOS)

        Args:
            vmid: The VM ID
            node: The Proxmox node name (optional, will auto-detect)

        Returns filesystem information including:
        - Mount points
        - Total size
        - Used space
        - Free space
        - Filesystem type
        """
        logger.info(f"Getting filesystem info for VM {vmid}")

        # Find node if not provided
        if node is None:
            all_vms = await proxmox.get_all_vms()
            for vm in all_vms:
                if vm.get("vmid") == vmid:
                    node = vm.get("node")
                    break

            if node is None:
                return {"error": f"VM {vmid} not found"}

        try:
            fsinfo = await proxmox.get_vm_agent_fsinfo(node, vmid)
        except Exception as e:
            error_msg = str(e)
            if "500" in error_msg or "QEMU guest agent" in error_msg.lower():
                return {
                    "error": "QEMU guest agent not available",
                    "hint": "Install qemu-guest-agent inside the VM: apt install qemu-guest-agent",
                    "vmid": vmid,
                    "node": node,
                }
            return {"error": f"Failed to get filesystem info: {e}"}

        if not fsinfo:
            return {
                "error": "No filesystem info returned",
                "hint": "QEMU guest agent may not be running or properly configured",
                "vmid": vmid,
                "node": node,
            }

        # Format the filesystem info
        filesystems = []
        for fs in fsinfo.get("result", fsinfo) if isinstance(fsinfo, dict) else fsinfo:
            total_bytes = fs.get("total-bytes", 0)
            used_bytes = fs.get("used-bytes", 0)
            free_bytes = total_bytes - used_bytes if total_bytes else 0

            filesystems.append({
                "mountpoint": fs.get("mountpoint"),
                "filesystem_type": fs.get("type"),
                "device": fs.get("name"),
                "total_bytes": total_bytes,
                "used_bytes": used_bytes,
                "free_bytes": free_bytes,
                "total_gb": round(total_bytes / (1024**3), 2) if total_bytes else 0,
                "used_gb": round(used_bytes / (1024**3), 2) if used_bytes else 0,
                "free_gb": round(free_bytes / (1024**3), 2) if free_bytes else 0,
                "usage_percent": round((used_bytes / total_bytes) * 100, 2) if total_bytes else 0,
            })

        return {
            "vmid": vmid,
            "node": node,
            "filesystems": filesystems,
        }
