# MCP server for IP Fabric

MCP server to interact with IP Fabric via the python SDK.

<a href="https://ipfabric.io"><img width="380" height="200" src="https://ipfabric.io/wp-content/uploads/2024/06/IP_Fabric_Logo_Color-1.svg" alt="server for IP Fabric MCP server" /></a>

## Components

### Tools

The server implements multiple tools to interact with IP Fabric:

- list_devices: Lists all devices in the IP Fabric inventory
- get_device_details: Returns detailed information about a specific device
- search: Search for devices matching a specified text query across all devices in the inventory
- TODO: complete the list

### Example prompts

Its good to first instruct Claude to use IP Fabric. Then it will always call the tool.

The use prompts like this:

- Get the details of the last device added to the inventory
- Search for all devices with the tag "production" and quickly explain to me their role in the network
- TODO: complete the list

## Configuration

### IP Fabric API Key

There are two ways to configure the environment with the IP Fabric API Key.

1. Add to server config (preferred)

    ```json
    {
      "mcp-ipf": {
        "command": "uvx",
        "args": [
          "mcp-ipf"
        ],
        "env": {
          "IP_TOKEN": "<your_api_key_here>",
          "IPF_URL": "<your_ip_fabric_host>",
          "IPF_VERIFY": "True|False"
        }
      }
    }
    ```

    Sometimes Claude has issues detecting the location of uv / uvx. You can use `which uvx` to find and paste the full path in above config in such cases.

2. Create a `.env` file in the working directory with the following required variables:

    ```bash
    IPF_TOKEN=your_api_key_here
    IPF_URL=your_ip_fabric_host
    IPF_VERIFY=True|False
    ```

## Quickstart

### Install

#### IP Fabric SDK

You need the IP Fabric SDK installed: https://github.com/ipfabric/ipfabric-sdk

Install and enable it in the settings and copy the api key.

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
          "IPF_VERIFY": "True|False"
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
          "IPF_TOKEN": "<YOUR_IPF_TOKEN>",
          "IPF_URL": "<your_ip_fabric_host>",
          "IPF_VERIFY": "True|False"
        }
      }
    }
  }
  ```

</details>

## Development

### Building

To prepare the package for distribution:

1. Sync dependencies and update lockfile:

```bash
uv sync
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
