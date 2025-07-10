import logging
import os
from collections.abc import Sequence
from typing import Any

from dotenv import load_dotenv
from ipfabric import IPFClient
from mcp.server import Server
from mcp.types import (
    EmbeddedResource,
    ImageContent,
    TextContent,
    Tool,
)

load_dotenv(override=True)

# from . import tools

import sys
import os

# Get the current directory of the script
current_dir = os.path.dirname(os.path.abspath(__file__))

# Add the parent directory of 'src' to the system path
sys.path.append(os.path.abspath(os.path.join(current_dir, '..')))

# Now you can import tools
from mcp_ipf import tools




# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-ipf")

app = Server("mcp-ipf")
tool_handlers = {}

# Global variable to hold the IPFClient instance
ipf_client = None


def initialize_ipf_client():
    """Initialize the IPFClient with environment variables."""
    global ipf_client
    
    ipf_token = os.getenv("IPF_TOKEN", None)
    ipf_url = os.getenv("IPF_URL", None)
    ipf_verify = os.getenv("IPF_VERIFY", "true").lower() in ("true", "1", "yes")
    ipf_timeout = int(os.getenv("IPF_TIMEOUT", 60))  # Default to 60 seconds if not set

    if not ipf_token:
        raise ValueError(f"IPF_TOKEN environment variable required. Working directory: {os.getcwd()}")
    if not ipf_url:
        raise ValueError(f"IPF_URL environment variable required. Working directory: {os.getcwd()}")

    # Create IPFClient instance
    ipf_client = IPFClient(base_url=ipf_url, auth=ipf_token, verify=ipf_verify, timeout=ipf_timeout)
    logger.info(f"IPFClient initialized for URL: {ipf_url}")


def register_tool_handlers():
    """Register all IP Fabric tool handlers."""
    if ipf_client is None:
        raise RuntimeError("IPFClient not initialized. Call initialize_ipf_client() first.")
    
    # Create and register IP Fabric tool handlers with individual error handling
    tool_classes = [
        ("GetFilterHelpToolHandler", tools.GetFilterHelpToolHandler),
        ("GetSnapshotsToolHandler", tools.GetSnapshotsToolHandler),
        ("SetSnapshotToolHandler", tools.SetSnapshotToolHandler),
        ("GetDevicesToolHandler", tools.GetDevicesToolHandler),
        ("GetInterfacesToolHandler", tools.GetInterfacesToolHandler),
        ("GetHostsToolHandler", tools.GetHostsToolHandler),
        ("GetSitesToolHandler", tools.GetSitesToolHandler),
        ("GetVendorsToolHandler", tools.GetVendorsToolHandler),
        ("GetVlansToolHandler", tools.GetVlansToolHandler),
        ("GetRoutingTableToolHandler", tools.GetRoutingTableToolHandler),
        ("GetManagedIPv4ToolHandler", tools.GetManagedIPv4ToolHandler),
        ("GetNeighborsToolHandler", tools.GetNeighborsToolHandler),
        ("GetAvailableColumnsToolHandler", tools.GetAvailableColumnsToolHandler),
        ("GetConnectionInfoToolHandler", tools.GetConnectionInfoToolHandler),
    ]
    
    for tool_name, tool_class in tool_classes:
        try:
            logger.info(f"Registering tool: {tool_name}")
            tool_handler = tool_class(ipf_client)
            
            # Test the tool description to catch schema issues early
            tool_description = tool_handler.get_tool_description()
            logger.info(f"Tool {tool_name} description: {tool_description}")
            
            add_tool_handler(tool_handler)
            logger.info(f"Successfully registered: {tool_name}")
            
        except Exception as e:
            logger.error(f"Failed to register {tool_name}: {e}")
            logger.error(f"Error type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Continue with other tools
            continue

    logger.info(f"Registered {len(tool_handlers)} tool handlers")


def add_tool_handler(tool_class: tools.ToolHandler):
    global tool_handlers
    tool_handlers[tool_class.name] = tool_class


def get_tool_handler(name: str) -> tools.ToolHandler | None:
    if name not in tool_handlers:
        return None
    return tool_handlers[name]


# @app.list_tools()
# async def list_tools() -> list[Tool]:
#     """List available tools."""
#     return [th.get_tool_description() for th in tool_handlers.values()]

# Also add this debug version of list_tools
@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    tools_list = []
    for name, handler in tool_handlers.items():
        try:
            tool_desc = handler.get_tool_description()
            logger.info(f"Adding tool to list: {name}")
            tools_list.append(tool_desc)
        except Exception as e:
            logger.error(f"Error getting tool description for {name}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    return tools_list


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
    """Handle tool calls for command line run."""
    if not isinstance(arguments, dict):
        raise RuntimeError("arguments must be dictionary")

    tool_handler = get_tool_handler(name)
    if not tool_handler:
        raise ValueError(f"Unknown tool: {name}")

    try:
        return tool_handler.run_tool(arguments)
    except Exception as e:
        logger.error(str(e))
        raise RuntimeError(f"Caught Exception. Error: {str(e)}")


async def main():
    """Main entry point for the MCP server."""
    try:
        # Initialize IPFClient and register tools
        initialize_ipf_client()
        register_tool_handlers()
        
        # Import here to avoid issues with event loops
        from mcp.server.stdio import stdio_server

        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

