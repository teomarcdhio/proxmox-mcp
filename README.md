# Proxmox MCP Server

A read-only MCP (Model Context Protocol) server that allows LLM agents to interact with your Proxmox homelab VMs.

## Features

- 📋 **List all VMs and containers** across your Proxmox cluster
- 🔍 **Get detailed VM information** including hardware specs, network config, and disks
- 📊 **Monitor VM status** with real-time CPU, memory, and I/O metrics
- 📈 **Historical metrics** with hourly, daily, weekly, monthly, or yearly data
- 📸 **List VM snapshots** to see backup points
- 🖥️ **Cluster overview** with node status and aggregate resources

All operations are **read-only** - your VMs are safe!

## Quick Start

### 1. Install UV (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Configure Proxmox credentials

```bash
cp .env.example .env
# Edit .env with your Proxmox details
```

### 3. Create a read-only API token in Proxmox

1. Go to **Datacenter** → **Permissions** → **API Tokens**
2. Click **Add**
3. Select a user (or create a new one with `PVEAuditor` role)
4. Set Token ID (e.g., `homelab-mcp`)
5. **Uncheck** "Privilege Separation" if using an auditor user
6. Copy the token secret (shown only once!)

#### Recommended: Create a dedicated auditor user

```bash
# SSH to your Proxmox server
pveum user add mcp-reader@pve
pveum acl modify / -user mcp-reader@pve -role PVEAuditor
pveum user token add mcp-reader@pve proxmox-mcp
```

### 4. Run the server

```bash
cd proxmox-mcp

# SSE mode (recommended for remote access)
uv run proxmox-mcp --transport sse

# Or stdio mode (for local VS Code/CLI usage)
uv run proxmox-mcp --transport stdio
```

### Alternative: Install globally with pip

```bash
pip install -e .
proxmox-mcp --transport sse
```

## Available Tools

| Tool | Description |
|------|-------------|
| `list_vms` | List all VMs and containers with basic info |
| `get_vm_info` | Get detailed VM configuration and specs |
| `get_vm_status` | Get current runtime status and metrics |
| `get_vm_metrics` | Get historical performance data |
| `get_vm_filesystem_info` | Get disk space from inside a VM (requires guest agent) |
| `list_nodes` | List all Proxmox nodes |
| `list_vm_snapshots` | List snapshots for a VM |
| `get_cluster_status` | Get cluster health and totals |

## Configuration

All settings can be configured via environment variables or a `.env` file:

| Variable | Description | Default |
|----------|-------------|---------|
| `PROXMOX_HOST` | Proxmox server hostname/IP | `localhost` |
| `PROXMOX_PORT` | Proxmox API port | `8006` |
| `PROXMOX_VERIFY_SSL` | Verify SSL certificates | `false` |
| `PROXMOX_API_TOKEN_ID` | API token ID (user@realm!tokenid) | - |
| `PROXMOX_API_TOKEN_SECRET` | API token secret | - |
| `MCP_SERVER_HOST` | SSE server bind address | `0.0.0.0` |
| `MCP_SERVER_PORT` | SSE server port | `8080` |

## Using with LLM Clients

### VS Code with GitHub Copilot

Add to your VS Code `settings.json` or user `mcp.json`:

```json
{
  "servers": {
    "proxmox": {
      "url": "http://your-server:8080/sse"
    }
  }
}
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "proxmox": {
      "url": "http://your-server:8080/sse"
    }
  }
}
```

### Local stdio mode

For local usage, you can run with stdio transport:

```json
{
  "mcpServers": {
    "proxmox": {
      "command": "uv",
      "args": [
        "run",
        "--directory", "/path/to/proxmox-mcp",
        "proxmox-mcp",
        "--transport", "stdio"
      ]
    }
  }
}
```

## Example Queries

Once connected, you can ask your LLM:

- "List all my VMs"
- "What's the status of VM 100?"
- "Show me the CPU usage history for my plex server"
- "Which VMs are currently stopped?"
- "How much memory is my cluster using?"

## Security Notes

1. **Use API tokens** instead of username/password
2. **Use the PVEAuditor role** for true read-only access
3. **Run behind a reverse proxy** with HTTPS in production
4. **Firewall the MCP port** to trusted networks only

## Development

```bash
cd proxmox-mcp

# Install dev dependencies
uv sync --extra dev

# Run tests
uv run pytest

# Lint
uv run ruff check src/
```

## License

MIT
