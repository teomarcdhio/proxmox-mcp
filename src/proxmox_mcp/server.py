"""MCP Server with SSE transport for Proxmox VM management."""

import asyncio
import logging

from mcp.server.fastmcp import FastMCP

from .config import settings
from .proxmox_client import proxmox
from .tools.vms import register_vm_tools

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_mcp_server() -> FastMCP:
    """Create and configure the MCP server."""
    mcp = FastMCP(
        name="proxmox-mcp",
        instructions="""
        This MCP server provides read-only access to a Proxmox homelab environment.
        
        Available capabilities:
        - List all VMs and containers across the cluster
        - Get detailed information about specific VMs
        - View current VM status and resource usage
        - Get historical performance metrics
        - List VM snapshots
        - View cluster and node status
        
        All operations are read-only and safe to use.
        VM IDs (vmid) are numeric identifiers like 100, 101, etc.
        Node names are the hostnames of your Proxmox servers.
        """,
    )

    # Register tools
    register_vm_tools(mcp)

    logger.info("MCP server created with VM tools registered")
    return mcp


# Create the server instance
mcp = create_mcp_server()


async def run_sse_server():
    """Run the MCP server with SSE transport using FastMCP's sse_app."""
    import uvicorn
    
    logger.info(f"Starting SSE server on http://{settings.mcp_server_host}:{settings.mcp_server_port}")
    logger.info(f"MCP SSE endpoint: http://{settings.mcp_server_host}:{settings.mcp_server_port}/sse")
    
    # Get the Starlette app from FastMCP
    app = mcp.sse_app()
    
    config = uvicorn.Config(
        app,
        host=settings.mcp_server_host,
        port=settings.mcp_server_port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def cleanup():
    """Cleanup resources on shutdown."""
    await proxmox.close()
    logger.info("Proxmox client closed")


def main():
    """Main entry point for the MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Proxmox MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="sse",
        help="Transport method: stdio for local, sse for remote (default: sse)",
    )
    parser.add_argument(
        "--host",
        default=None,
        help=f"Host to bind to (default: {settings.mcp_server_host})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=f"Port to bind to (default: {settings.mcp_server_port})",
    )
    args = parser.parse_args()

    # Override settings if provided
    if args.host:
        settings.mcp_server_host = args.host
    if args.port:
        settings.mcp_server_port = args.port

    try:
        if args.transport == "stdio":
            logger.info("Starting MCP server with stdio transport")
            mcp.run(transport="stdio")
        else:
            logger.info("Starting MCP server with SSE transport")
            asyncio.run(run_sse_server())
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    finally:
        asyncio.run(cleanup())


if __name__ == "__main__":
    main()
