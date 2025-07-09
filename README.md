# MCP server for IP Fabric

MCP server to interact with IP Fabric via the python SDK.

<a href="https://ipfabric.io"><img width="380" height="200" src="https://ipfabric.io/wp-content/uploads/2024/06/IP_Fabric_Logo_Color-1.svg" alt="server for IP Fabric MCP server" /></a>

## Components

### Tools

The server implements multiple tools to interact with IP Fabric:

- **ipf_get_snapshots**: Lists all available snapshots in IP Fabric
- **ipf_set_snapshot**: Sets the active snapshot for subsequent queries
- **ipf_get_devices**: Gets device inventory data with optional filters
- **ipf_get_interfaces**: Gets interface inventory data with optional filters
- **ipf_get_routing_table_ipv4**: Gets IPv4 routing table data with optional filters
- **ipf_get_managed_ipv4**: Gets managed IP data with optional filters
- **ipf_get_hosts**: Gets host data with optional filters
- **ipf_get_sites**: Gets site inventory data (planned)
- **ipf_get_vendors**: Gets vendor inventory data (planned)
- **ipf_get_platforms**: Gets platform inventory data (planned)
- **ipf_get_vlans**: Gets VLAN data (planned)
- **ipf_get_neighbors**: Gets neighbor discovery data (planned)
- **ipf_get_available_columns**: Gets available columns for specific table types (planned)
- **ipf_get_connection_info**: Gets IP Fabric connection information (planned)

### Example prompts

It's good to first instruct Claude to use IP Fabric. Then it will always call the tools.

Use prompts like this:

- "Show me all available snapshots in IP Fabric"
- "Set the snapshot to the latest one and show me all devices"
- "Get all Cisco devices from the inventory"
- "Show me all interfaces on router 'core-01'"
- "Find all routes to 192.168.1.0/24"
- "Get devices with hostname containing 'switch' and show their platforms"
- "Show me the routing table for devices in site 'headquarters'"

## Configuration

### IP Fabric API Configuration

Configure the environment with the IP Fabric connection details:

#### Required Environment Variables

```bash
IPF_TOKEN=your_api_key_here
IPF_URL=your_ip_fabric_host
IPF_VERIFY=True|False  # SSL certificate verification
```

#### Optional Environment Variables

```bash
IPF_SNAPSHOT_ID=snapshot_id_here  # Set default snapshot
```

### Configuration Methods

1. **Add to server config (preferred)**

    ```json
    {
      "mcp-ipf": {
        "command": "uvx",
        "args": [
          "mcp-ipf"
        ],
        "env": {
          "IPF_TOKEN": "<your_api_key_here>",
          "IPF_URL": "<your_ip_fabric_host>",
          "IPF_VERIFY": "True"
        }
      }
    }
    ```

    Sometimes Claude has issues detecting the location of uv / uvx. You can use `which uvx` to find and paste the full path in above config in such cases.

2. **Create a `.env` file** in the working directory with the required variables:

    ```bash
    IPF_TOKEN=your_api_key_here
    IPF_URL=your_ip_fabric_host
    IPF_VERIFY=True
    IPF_SNAPSHOT_ID=optional_default_snapshot_id
    ```

## Quickstart

### Prerequisites

#### IP Fabric API Access

You need IP Fabric API access with a valid API token. Get this from your IP Fabric instance:

1. Log into your IP Fabric instance
2. Go to Settings → API tokens
3. Create a new API token
4. Copy the token for use in configuration

#### Claude Desktop

On MacOS: `~/Library/Application\ Support/Claude/claude_desktop_config.json`

<details>
  <summary>Development/Unpublished Servers Configuration</summary>
  
  ```json
  {
    "mcpServers": {
      "mcp-ipf": {
        "command": "uv",
        "args": [
          "--directory",
          "<dir_to>/mcp-ipf",
          "run",
          "mcp-ipf"
        ],
        "env": {
          "IPF_TOKEN": "<your_api_key_here>",
          "IPF_URL": "<your_ip_fabric_host>",
          "IPF_VERIFY": "True"
        }
      }
    }
  }
  ```

</details>

<details>
  <summary>Published Servers Configuration</summary>

  ```json
  {
    "mcpServers": {
      "mcp-ipf": {
        "command": "uvx",
        "args": [
          "mcp-ipf"
        ],
        "env": {
          "IPF_TOKEN": "<your_api_key_here>",
          "IPF_URL": "<your_ip_fabric_host>",
          "IPF_VERIFY": "True"
        }
      }
    }
  }
  ```

</details>

## Development

### Project Structure

```tree
mcp-ipf/
├── src/
│   └── mcp_ipf/
│       ├── __init__.py      # Package entry point
│       ├── server.py        # MCP server implementation
│       ├── tools.py         # Tool handlers
│       └── ipf.py          # IP Fabric integration
├── pyproject.toml
└── README.md
```

### Building

To prepare the package for distribution:

1. Sync dependencies and update lockfile:

    ```bash
    uv sync
    ```

2. Build the package:

    ```bash
    uv build
    ```

### Running

Run the server directly during development:

```bash
uv run mcp-ipf
```

Or run the server module directly:

```bash
uv run python -m mcp_ipf
```

### Debugging

Since MCP servers run over stdio, debugging can be challenging. For the best debugging
experience, we strongly recommend using the [MCP Inspector](https://github.com/modelcontextprotocol/inspector).

You can launch the MCP Inspector via [`npm`](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm) with this command:

```bash
npx @modelcontextprotocol/inspector uv --directory /path/to/mcp-ipf run mcp-ipf
```

Upon launching, the Inspector will display a URL that you can access in your browser to begin debugging.

You can also watch the server logs with this command:

```bash
tail -n 20 -f ~/Library/Logs/Claude/mcp-server-mcp-ipf.log
```

### Adding New Tools

To add new IP Fabric tools:

1. Create a new tool handler class in `tools.py`
2. Add the tool class to the `tool_classes` list in `server.py`
3. The tool will be automatically registered and available

## Troubleshooting

### Common Issues

1. **Connection errors**: Verify your `IPF_URL` and `IPF_TOKEN` are correct
2. **SSL certificate issues**: Set `IPF_VERIFY=False` if using self-signed certificates
3. **Permission errors**: Ensure your API token has sufficient permissions in IP Fabric
4. **Snapshot issues**: Use `ipf_get_snapshots` to see available snapshots, then `ipf_set_snapshot` to select one
