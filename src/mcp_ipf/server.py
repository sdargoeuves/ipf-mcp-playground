import logging
import os
import sys
import traceback
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

# Get the current directory of the script
current_dir = os.path.dirname(os.path.abspath(__file__))
# Add the parent directory of 'src' to the system path
sys.path.append(os.path.abspath(os.path.join(current_dir, "..")))

# Now you can import tools
from mcp_ipf import tools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-ipf")

# Silence verbose third-party loggers
logging.getLogger("ipfabric").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("mcp.server.lowlevel.server").setLevel(logging.WARNING)

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

    # Define tool classes to register
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
        ("GetArpToolHandler", tools.GetArpToolHandler),
        ("GetMacToolHandler", tools.GetMacToolHandler),
        ("GetNeighborsToolHandler", tools.GetNeighborsToolHandler),
        ("GetAvailableColumnsToolHandler", tools.GetAvailableColumnsToolHandler),
        ("GetConnectionInfoToolHandler", tools.GetConnectionInfoToolHandler),
        ("CompareTableToolHandler", tools.CompareTableToolHandler),
    ]

    registered_count = 0
    for tool_name, tool_class in tool_classes:
        try:
            tool_handler = tool_class(ipf_client)
            
            # Validate tool description during registration
            tool_handler.get_tool_description()
            
            add_tool_handler(tool_handler)
            registered_count += 1
            logger.debug(f"Registered tool: {tool_name}")

        except Exception as e:
            logger.error(f"Failed to register {tool_name}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            continue

    logger.info(f"Successfully registered {registered_count}/{len(tool_classes)} tools")


def add_tool_handler(tool_class: tools.ToolHandler):
    """Add a tool handler to the global registry."""
    global tool_handlers
    tool_handlers[tool_class.name] = tool_class


def get_tool_handler(name: str) -> tools.ToolHandler | None:
    """Get a tool handler by name."""
    return tool_handlers.get(name)


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    tools_list = []
    for name, handler in tool_handlers.items():
        try:
            tools_list.append(handler.get_tool_description())
        except Exception as e:
            logger.error(f"Error getting tool description for {name}: {e}")
            # Continue with other tools instead of failing completely
            continue
    
    logger.debug(f"Returning {len(tools_list)} available tools")
    return tools_list


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
    """Handle tool calls."""
    if not isinstance(arguments, dict):
        raise RuntimeError("arguments must be dictionary")

    tool_handler = get_tool_handler(name)
    if not tool_handler:
        raise ValueError(f"Unknown tool: {name}")

    try:
        return tool_handler.run_tool(arguments)
    except Exception as e:
        logger.error(f"Tool {name} failed: {e}")
        raise RuntimeError(f"Tool execution failed: {e}")


async def main():
    """Main entry point for the MCP server."""
    try:
        logger.info("Starting IP Fabric MCP server...")
        
        # Initialize IPFClient and register tools
        initialize_ipf_client()
        register_tool_handlers()
        
        logger.info("Server ready, starting stdio server...")

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
