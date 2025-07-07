import json
from collections.abc import Sequence

from ipfabric import IPFClient
from mcp.types import (
    EmbeddedResource,
    ImageContent,
    TextContent,
    Tool,
)

# Note: The main server script will be responsible for creating the IPFClient
# and passing it to the ToolHandler constructors.


class ToolHandler:
    """Base class for all IP Fabric tool handlers."""

    def __init__(self, tool_name: str, ipf_client: IPFClient):
        self.name = tool_name
        self.ipf = ipf_client

    def get_tool_description(self) -> Tool:
        raise NotImplementedError()

    def run_tool(self, args: dict) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        raise NotImplementedError()


class GetFilterHelpToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_filter_help", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="Get comprehensive help on IP Fabric filter syntax and operators. Essential for constructing filters for all query functions.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        help_data = {
            "filter_syntax": {
                "format": "Each filter uses the format: {'column_name': ['operator', 'value']}",
                "operators": {
                    "eq": {"description": "Exact match (case-sensitive)", "example": "{'vendor': ['eq', 'cisco']}"},
                    "like": {
                        "description": "Contains match (case-insensitive)",
                        "example": "{'hostname': ['like', 'core']}",
                    },
                    "reg": {
                        "description": "Regular expression (case-sensitive)",
                        "example": "{'vendor': ['reg', '(cisco|arista)']}",
                    },
                    "ireg": {
                        "description": "Case-insensitive regular expression",
                        "example": "{'vendor': ['ireg', '(cisco|ARISTA)']}",
                    },
                },
            },
            "tips": [
                "Combine multiple filters with AND logic: {'filter1': [...], 'filter2': [...]}",
                "For IP addresses, use escaped dots in regex: '192\\.168\\.'",
            ],
        }
        return [TextContent(type="text", text=json.dumps(help_data, indent=2))]


class GetSnapshotsToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_snapshots", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="Retrieve all available snapshots from IP Fabric. Use this to find snapshot IDs before setting one.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            snapshots = self.ipf.get_snapshots()
            result = {"snapshots": snapshots, "current_snapshot": self.ipf.snapshot_id}
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]


class SetSnapshotToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_set_snapshot", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="Set the active snapshot for all subsequent IP Fabric queries.",
            inputSchema={
                "type": "object",
                "properties": {
                    "snapshot_id": {"type": "string", "description": "The unique ID of the snapshot to activate."}
                },
                "required": ["snapshot_id"],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        if "snapshot_id" not in args:
            raise RuntimeError("snapshot_id argument is required.")
        try:
            old_snapshot = self.ipf.snapshot_id
            snapshot_id = args["snapshot_id"]
            self.ipf.snapshot_id = snapshot_id
            result = {
                "success": True,
                "old_snapshot": old_snapshot,
                "new_snapshot": self.ipf.snapshot_id,
                "message": f"Successfully changed snapshot from {old_snapshot} to {snapshot_id}",
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except Exception as e:
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {"error": str(e), "message": f"Failed to set snapshot to {args['snapshot_id']}"}, indent=2
                    ),
                )
            ]


class GetDevicesToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_devices", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="Retrieve network devices from the IP Fabric inventory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filters": {"type": "object", "description": "Filter criteria. e.g. {'vendor': ['eq', 'Cisco']}"},
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific columns to return, e.g., ['hostname', 'siteName']",
                    },
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            result = self.ipf.inventory.devices.all(filters=args.get("filters", {}), columns=args.get("columns"))
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except Exception as e:
            return [
                TextContent(
                    type="text", text=json.dumps({"error": str(e), "message": "Failed to retrieve devices"}, indent=2)
                )
            ]


class GetInterfacesToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_interfaces", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="Retrieve network interface information from IP Fabric.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filters": {"type": "object", "description": "Filter criteria. e.g. {'l1': ['eq', 'down']}"},
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific columns to return, e.g., ['hostname', 'intName', 'l1']",
                    },
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            result = self.ipf.inventory.interfaces.all(filters=args.get("filters", {}), columns=args.get("columns"))
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except Exception as e:
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"error": str(e), "message": "Failed to retrieve interfaces"}, indent=2),
                )
            ]


# ... You would continue this pattern for all other tools ...
# (ipf_get_sites, ipf_get_vendors, ipf_get_routing_table, etc.)


# Example for one more tool:
class GetRoutingTableToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_routing_table", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="Retrieve routing table entries from IP Fabric.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filters": {"type": "object", "description": "Filter criteria. e.g. {'protocol': ['eq', 'ospf']}"},
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific columns to return, e.g., ['hostname', 'network', 'protocol']",
                    },
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            result = self.ipf.technology.routing.routes.all(
                filters=args.get("filters", {}), columns=args.get("columns")
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except Exception as e:
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"error": str(e), "message": "Failed to retrieve routing table"}, indent=2),
                )
            ]
