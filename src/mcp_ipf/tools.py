import json
from collections.abc import Sequence
from typing import Any, List

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
    """Base class for all IP Fabric tool handlers.

    This class provides the foundation for implementing IP Fabric API tool handlers
    in an MCP (Model Context Protocol) server environment. Each handler wraps specific
    IP Fabric functionality and provides consistent error handling and response formatting.

    Attributes:
        name (str): The unique name identifier for this tool handler
        ipf (IPFClient): The IP Fabric client instance used for API communication

    Methods:
        get_tool_description(): Returns the MCP Tool definition for this handler
        run_tool(): Executes the tool with provided arguments
        _format_response(): Helper for consistent response formatting
        _handle_exception(): Helper for consistent exception handling
    """

    def __init__(self, tool_name: str, ipf_client: IPFClient):
        self.name = tool_name
        self.ipf = ipf_client

    def get_tool_description(self) -> Tool:
        raise NotImplementedError()

    def run_tool(self, args: dict) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        raise NotImplementedError()

    def _format_response(self, data: Any, success: bool = True, message: str = "", snapshot_id: str | None = None) -> List[TextContent]:
        """Helper method to format responses consistently."""
        if success:
            response = {
                "success": True,
                "data": data,
                "current_snapshot": snapshot_id or self.ipf.snapshot_id,
            }
        else:
            response = {
                "success": False,
                "error": str(data),
                "current_snapshot": snapshot_id or self.ipf.snapshot_id,
            }
        if message:
            response["message"] = message
        return [TextContent(type="text", text=json.dumps(response, indent=2, default=str))]

    def _handle_exception(self, e: Exception, operation: str) -> List[TextContent]:
        """Helper method to handle exceptions consistently."""
        return self._format_response(data=str(e), success=False, message=f"Failed to {operation}")


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
                    "cidr": {
                        "description": "CIDR network match (IP tables only)",
                        "example": "{'loginIpv4': ['cidr', '10.194.0.0/16']}",
                    },
                    "neq": {
                        "description": "Not equal (case-sensitive)",
                        "example": "{'vendor': ['neq', 'cisco']}",
                    },
                    "empty": {
                        "description": "Field is empty or null",
                        "example": "{'description': ['empty']}",
                    },
                    "nempty": {
                        "description": "Field is not empty",
                        "example": "{'description': ['nempty']}",
                    },
                },
            },
            "logical_operators": {
                "and": "Combine multiple conditions with AND logic (default)",
                "or": "Combine multiple conditions with OR logic",
            },
            "examples": {
                "simple_filter": "{'vendor': ['eq', 'cisco']}",
                "multiple_and": "{'vendor': ['eq', 'cisco'], 'siteName': ['like', 'core']}",
                "or_condition": "{'or': [{'vendor': ['eq', 'cisco']}, {'vendor': ['eq', 'arista']}]}",
                "complex_nested": "{'and': [{'loginIpv4': ['cidr', '10.194.0.0/16']}, {'or': [{'vendor': ['like', 'forti']}, {'vendor': ['eq', 'hpe']}]}]}",
                "regex_ip": "{'loginIpv4': ['reg', '10\\.194\\.5[6-7]']}",
            },
            "tips": [
                "Use 'like' for substring matching (case-insensitive)",
                "Use 'reg' for complex pattern matching (case-sensitive)",
                "Use 'cidr' for IP network matching where supported",
                "Combine filters with 'and' (default) or 'or' logic",
                "Test filters with small datasets first",
                "Use get_available_columns to see what columns are available",
            ],
        }
        return self._format_response(help_data, message="Filter help information retrieved successfully")


class GetSnapshotsToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_snapshots", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Get all available snapshots from IP Fabric. Snapshots represent point-in-time captures of your network topology, configuration and state.""",
            inputSchema={"type": "object", "properties": {}, "required": []},
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            snapshots = self.ipf.get_snapshots()
            result = {
                "snapshots": snapshots,
                "current_snapshot": self.ipf.snapshot_id,
                "snapshot_count": len(snapshots) if snapshots else 0,
            }
            return self._format_response(result, message="Snapshots retrieved successfully")
        except Exception as e:
            return self._handle_exception(e, "retrieve snapshots")


class SetSnapshotToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_set_snapshot", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Set the active snapshot for all subsequent IP Fabric queries. All subsequent queries will operate against the specified snapshot.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "snapshot_id": {
                        "type": "string",
                        "description": "The unique ID of the snapshot to activate. Use ipf_get_snapshots to see available snapshot IDs.",
                    }
                },
                "required": ["snapshot_id"],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        snapshot_id = args.get("snapshot_id")
        if not snapshot_id:
            return self._format_response(
                "snapshot_id argument is required", success=False, message="Missing required parameter"
            )

        try:
            old_snapshot = self.ipf.snapshot_id
            self.ipf.snapshot_id = snapshot_id
            result = {
                "old_snapshot": old_snapshot,
                "new_snapshot": self.ipf.snapshot_id,
            }
            return self._format_response(
                result, message=f"Successfully changed snapshot from {old_snapshot} to {self.ipf.snapshot_id}"
            )
        except Exception as e:
            return self._handle_exception(e, f"set snapshot to {snapshot_id}")


class GetTableToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_table", ipf_client)
        self.table_map = {
            "devices": self.ipf.inventory.devices,
            "interfaces": self.ipf.inventory.interfaces,
            "hosts": self.ipf.inventory.hosts,
            "sites": self.ipf.inventory.sites,
            "vendors": self.ipf.inventory.vendors,
            "routing_ipv4": self.ipf.technology.routing.routes_ipv4,
            "managed_ipv4": self.ipf.technology.addressing.managed_ip_ipv4,
            "arp": self.ipf.technology.addressing.arp_table,
            "mac": self.ipf.technology.addressing.mac_table,
            "vlans": self.ipf.technology.vlans.device_detail,
            "neighbors": self.ipf.technology.neighbors.neighbors_all,
        }

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Get data from a specified IP Fabric table. This is the primary tool for retrieving network state information.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "The name of the table to query.",
                        "enum": list(self.table_map.keys()),
                    },
                    "filters": {
                        "type": "object",
                        "description": "Filter criteria using IP Fabric filter syntax. Use ipf_get_filter_help for syntax.",
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific columns to return. If not specified, default columns will be returned.",
                    },
                    "snapshot_id": {
                        "type": "string",
                        "description": "The ID of the snapshot to query against. If not specified, the current snapshot will be used.",
                    },
                },
                "required": ["table_name"],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        table_name = args.get("table_name")
        if not table_name:
            return self._format_response(
                "table_name argument is required", success=False, message="Missing required parameter"
            )

        if table_name not in self.table_map:
            return self._format_response(
                f"Unknown table name: {table_name}",
                success=False,
                message=f"Available tables: {', '.join(self.table_map.keys())}",
            )

        try:
            return self._query_ipf_data(table_name, args)
        except Exception as e:
            return self._handle_exception(e, f"retrieve data from table '{table_name}'")

    
    def _query_ipf_data(self, table_name, args):
        table_obj = self.table_map[table_name]
        filters = args.get("filters", {})
        columns = args.get("columns")
        snapshot_id = args.get("snapshot_id", self.ipf.snapshot_id)

        result = table_obj.all(filters=filters, columns=columns, snapshot_id=snapshot_id)

        return self._format_response(result, message=f"Retrieved {len(result) if result else 0} entries from '{table_name}'")

class GetConnectionInfoToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_connection_info", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Get IP Fabric connection status and information. Useful for verifying connectivity.""",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            # Get basic connection info
            result = {
                "base_url": getattr(self.ipf, "base_url", "Unknown"),
                "current_snapshot": self.ipf.snapshot_id,
                "api_version": getattr(self.ipf, "api_version", "Unknown"),
                "connected": True,
            }

            # Try to get additional info if available
            try:
                snapshots = self.ipf.get_snapshots()
                loaded_snapshots = [v for k, v in snapshots.items() if (v.status == "done" and "$" not in k)]
                if loaded_snapshots:
                    result["total_loaded_snapshots"] = len(loaded_snapshots)
                    result["latest_snapshot"] = snapshots["$last"].snapshot_id
            except Exception:
                pass

            return self._format_response(result, message="Connection information retrieved successfully")
        except Exception as e:
            return self._handle_exception(e, "get connection information")


class GetAvailableColumnsToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_available_columns", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Get available columns for IP Fabric table name
            
            Discovers the schema and available fields for different data tables.
            Use this to understand what data is available before constructing
            queries or filters.
            
            Args:
                table_type: Table to inspect (devices, interfaces, routing, vlans, etc.)
            
            Returns:
                List of available columns with their namess for the specified table
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "table_type": {
                        "type": "string",
                        "description": "The table type to inspect. Valid options: devices, interfaces, sites, vendors, platforms, routing, vlans, neighbors",
                        "enum": [
                            "devices", "interfaces", "sites", "vendors",
                            "managed_ipv4", "arp", "mac",
                            "routing", "vlans", "neighbors"
                        ],
                    }
                },
                "required": ["table_type"],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        table_type = args.get("table_type")

        if not table_type:
            return self._format_response(
                "table_type argument is required", success=False, message="Missing required parameter"
            )

        # Map table types to their API paths
        table_map = {
            "devices": "tables/inventory/devices",
            "interfaces": "tables/inventory/interfaces",
            "hosts": "tables/inventory/hosts",
            "sites": "tables/inventory/sites",
            "vendors": "tables/inventory/summary/vendors",
            "routing": "tables/networks/routes",
            "managed_ipv4": "tables/addressing/managed-devs",
            "vlans": "tables/vlan/device",
            "neighbors": "tables/neighbors/all",
        }

        if table_type not in table_map:
            return self._format_response(
                f"Unknown table type: {table_type}",
                success=False,
                message=f"Available table types: {', '.join(table_map.keys())}",
            )

        try:
            columns = self.ipf.get_columns(table_map[table_type])

            result = {
                "table_type": table_type,
                "table_path": table_map[table_type],
                "columns": columns,
                "column_count": len(columns) if columns else 0,
            }

            return self._format_response(
                result, message=f"Retrieved {len(columns) if columns else 0} columns for {table_type} table"
            )
        except Exception as e:
            return self._handle_exception(e, f"get columns for {table_type}")


class GetConnectionInfoToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_connection_info", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Get IP Fabric connection status and information
            
            Retrieves current connection details including active snapshot,
            API version, and availability status. Useful for verifying connectivity.
            
            Returns:
                Connection details with base URL, current snapshot, API version,
                and snapshot statistics
            """,
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            # Get basic connection info
            result = {
                "base_url": getattr(self.ipf, "base_url", "Unknown"),
                "current_snapshot": self.ipf.snapshot_id,
                "api_version": getattr(self.ipf, "api_version", "Unknown"),
                "connected": True,  # If we can create this response, we're connected
            }

            # Try to get additional info if available
            try:
                snapshots = self.ipf.get_snapshots()
                loaded_snapshots = [v for k, v in snapshots.items() if (v.status == "done" and "$" not in k)]
                if loaded_snapshots:
                    result["total_loaded_snapshots"] = len(loaded_snapshots)
                    result["latest_snapshot"] = snapshots["$last"].snapshot_id
            except Exception:
                # Don't fail if we can't get snapshots
                pass

            return self._format_response(result, message="Connection information retrieved successfully")
        except Exception as e:
            return self._handle_exception(e, "get connection information")


class CompareTableToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_compare_table", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Compare the same table between two IP Fabric snapshots
            
            Compares a specific table from the current active snapshot to the same
            table in another snapshot, identifying added, removed, and changed records.
            This is essential for tracking network changes over time, compliance 
            monitoring, and change impact analysis.
            
            By default, compares against $prev (previous snapshot), but if $prev
            is the same as current snapshot, it will use $last instead. You can
            also specify a specific snapshot_id to compare against.

            Here is an example to perform a diff of the IPv4 routing table
            between the current snapshot and the previous one:
            ipf.technology.routing.routes_ipv4.compare(
                snapshot_id="$",
                columns=["hostname", "network", "nexthop"],
                nested_columns_ignore=["age", "vtepIp", "label", "oid", "vni", "vrfLeak", "label"]
            )

            Here is an example to compare devices based on hostname only:            
            In [32]: ipf.inventory.devices.compare(snapshot_id="$prev", columns=['hostname'])
            Out[32]:
            
            {
                'added': [{'hostname': 'fw2'}, {'hostname': 'fw3'}, {'hostname': 'fw1'}],
                'removed': [
                    {'hostname': 'fw2/netlab'},
                    {'hostname': 'fw3/netlab'},
                    {'hostname': 'fw1/root'},
                    {'hostname': 'fw3/root'},
                    {'hostname': 'fw1/netlab'},
                    {'hostname': 'fw2/root'}
                ]
            }

            Args:
                table_path: Path to the table to compare (e.g., "technology.vlans.device_detail")
                snapshot_id: Optional snapshot ID to compare against (defaults to smart $prev/$last selection)
                columns: Optional list of columns to include in comparison
                columns_ignore: Optional list of columns to ignore in comparison
                unique_keys: Optional list of columns to use as unique identifiers
                nested_columns_ignore: Optional list of nested columns to ignore
                table_filters: Optional filters to apply before comparison
            
            Returns:
                Dictionary with 'added', 'removed', and 'changed' keys containing
                the differences between snapshots
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "table_path": {
                        "type": "string",
                        "description": """
                            Dot-notation path to the table to compare, like those tables:
                            inventory.devices
                            inventory.interfaces
                            inventory.hosts
                            inventory.sites
                            technology.routing.routes_ipv4
                            technology.neighbors.neighbors_all
                            technology.addressing.managed_ip_ipv4
                            technology.addressing.arp_table
                            technology.addressing.mac_table
                            technology.vlans.device_detail
                        """,
                        "examples": [
                            "ipf.inventory.devices.compare(snapshot_id='$prev', columns=['hostname']) # to compare devices purely based on hostname, it will ignore all other columns",
                            "ipf.inventory.devices.compare(snapshot_id='$prev', columns=['hostname', 'sn', 'loginIpv4'])",
                            "ipf.inventory.interfaces.compare()",
                            "ipf.inventory.hosts.compare()",
                            "ipf.inventory.sites.compare()",
                            "ipf.technology.routing.routes_ipv4.compare()",
                            "ipf.technology.neighbors.neighbors_all.compare()",
                            "ipf.technology.addressing.managed_ip_ipv4.compare()",
                            "ipf.technology.vlans.device_detail.compare()",
                        ],
                    },
                    "snapshot_id": {
                        "type": "string",
                        "description": """
                            The ID of the snapshot to query against (e.g., 'cf2d7763-85b3-4d97-afdb-e66eb6e4125e')
                            If not provided, will use $prev, or $last if $prev is the same as current snapshot
                            Use ipf_get_snapshots() to see available snapshot IDs if needed.
                        """
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of columns to include in the comparison. If not specified, all columns will be compared.",
                    },
                    "columns_ignore": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of columns to ignore during comparison. By default, 'id' column is ignored.",
                    },
                    "unique_keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of columns to use as unique identifiers for matching records. If not specified, all columns will be used as primary key.",
                    },
                    "nested_columns_ignore": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of nested columns to ignore during comparison.",
                    },
                    "table_filters": {
                        "type": "object",
                        "description": "Optional filters to apply to the table before comparison using IP Fabric filter syntax.",
                    },
                },
                "required": ["table_path"],
            },
        )

    def run_tool(self, args: dict):
        try:
            table_path = args["table_path"]
            snapshot_id = args.get("snapshot_id")
            columns = args.get("columns")
            columns_ignore = args.get("columns_ignore")
            unique_keys = args.get("unique_keys")
            nested_columns_ignore = args.get("nested_columns_ignore")
            table_filters = args.get("table_filters", {})

            # Smart snapshot selection if not provided
            if not snapshot_id:
                prev_snapshot_id = self.ipf.snapshots["$prev"].snapshot_id

                if self.ipf.snapshot_id == prev_snapshot_id:
                    # If $prev is the same as current, use $last instead
                    snapshot_id = self.ipf.snapshots["$last"].snapshot_id
                    selected_snapshot = "$last"
                else:
                    # Use $prev as default
                    snapshot_id = prev_snapshot_id
                    selected_snapshot = "$prev"
            elif snapshot_id == self.ipf.snapshot_id:
                return (None, "Cannot compare against the current snapshot")
            else:
                selected_snapshot = snapshot_id

            # Navigate to the specified table using dot notation
            table_obj = self.ipf
            for part in table_path.split("."):
                table_obj = getattr(table_obj, part)

            # Call the compare method with the provided parameters
            result = table_obj.compare(
                snapshot_id=snapshot_id,
                columns=columns,
                columns_ignore=columns_ignore,
                unique_keys=unique_keys,
                nested_columns_ignore=nested_columns_ignore,
                filters=table_filters,
            )

            # Format the response with summary statistics
            summary_parts = []
            if result:
                if "added" in result:
                    summary_parts.append(f"{len(result['added'])} added")
                if "removed" in result:
                    summary_parts.append(f"{len(result['removed'])} removed")
                if "changed" in result:
                    summary_parts.append(f"{len(result['changed'])} changed")

            summary = f"Comparison completed for table '{table_path}' against snapshot '{selected_snapshot}': {', '.join(summary_parts) if summary_parts else 'No differences found'}"

            return self._format_response(data=result, success=True, message=summary)

        except AttributeError as e:
            return self._handle_exception(e, f"access table '{table_path}' - verify the table path is correct")
        except Exception as e:
            return self._handle_exception(e, f"compare snapshots for table '{table_path}'")

class DiffRoutesToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_diff_routes", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Compare IPv4 routing tables between two IP Fabric snapshots
            
            Compares IPv4 routes between two specified snapshots and returns a structured 
            summary of changes. This tool provides detailed analysis of route additions, 
            removals, and modifications between snapshots, making it ideal for network 
            change tracking and troubleshooting.
            
            The comparison uses a composite key of hostname|vrf|network to identify 
            unique routes and compares protocol, nexthop IP, interface name, and metric 
            for changes.
            
            Example usage:
            - Compare current snapshot with previous: diff_routes("current_id", "$prev")
            - Compare two specific snapshots: diff_routes("2024-01-15", "2024-01-16")
            
            Args:
                snapshot_a: The ID of the first snapshot
                snapshot_b: The ID of the second snapshot to compare against snapshot_a
            
            Returns:
                Dictionary containing:
                - snapshot_a_id/snapshot_b_id: The snapshot IDs used
                - added: List of route keys added in snapshot_b
                - removed: List of route keys removed in snapshot_b  
                - changed: List of modified routes with detailed change information
                - summary_counts: Count of added, removed, and modified routes
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "snapshot_a": {
                        "type": "string",
                        "description": "The ID of the first snapshot (e.g., 'cf2d7763-85b3-4d97-afdb-e66eb6e4125e' or use '$prev', '$last')",
                        "examples": ["cf2d7763-85b3-4d97-afdb-e66eb6e4125e", "$prev", "$last"]
                    },
                    "snapshot_b": {
                        "type": "string", 
                        "description": "The ID of the second snapshot to compare against snapshot_a",
                        "examples": ["92feb80a-c473-4812-a0a4-32ebe79f05e9", "$prev", "$last"]
                    }
                },
                "required": ["snapshot_a", "snapshot_b"]
            }
        )

    def run_tool(self, args: dict):
        try:
            snapshot_a = args["snapshot_a"]
            snapshot_b = args["snapshot_b"]
            
            # Validate that we're not comparing the same snapshot
            if snapshot_a == snapshot_b:
                return self._format_response(
                    data=None,
                    success=False,
                    message="Cannot compare the same snapshot against itself"
                )
            
            # Fetch route data from both snapshots
            routes_a = self.ipf.technology.routing.routes_ipv4.all(snapshot_id=snapshot_a)
            routes_b = self.ipf.technology.routing.routes_ipv4.all(snapshot_id=snapshot_b)
            
            # Process the comparison
            result = self._compare_routes(routes_a, routes_b, snapshot_a, snapshot_b)
            
            return self._format_response(
                data=result,
                success=True,
                message=result["message"]
            )
            
        except Exception as e:
            return self._handle_exception(e, f"compare routes between snapshots '{snapshot_a}' and '{snapshot_b}'")

    def _compare_routes(self, routes_a: list, routes_b: list, snapshot_a: str, snapshot_b: str) -> dict:
        """
        Internal method to perform the actual route comparison logic.
        
        Args:
            routes_a: List of routes from snapshot A
            routes_b: List of routes from snapshot B
            snapshot_a: ID of snapshot A
            snapshot_b: ID of snapshot B
            
        Returns:
            Dictionary with comparison results
        """
        def make_key(route):
            """Create a unique key for a route using hostname|vrf|network"""
            return f"{route.get('hostname')}|{route.get('vrf')}|{route.get('network')}"

        def simplify(route):
            """Simplify route data to essential fields for comparison"""
            nexthop_ip = None
            int_name = None
            
            # Safely access nested nexthop data
            nexthop = route.get("nexthop")
            if nexthop and len(nexthop) > 0 and nexthop[0]:
                nexthop_ip = nexthop[0].get("ip")
                int_name = nexthop[0].get("intName")
            
            return {
                "protocol": route.get("protocol"),
                "nexthop_ip": nexthop_ip,
                "intName": int_name,
                "metric": route.get("nhLowestMetric"),
            }

        # Create dictionaries for comparison
        dict_a = {make_key(r): simplify(r) for r in routes_a}
        dict_b = {make_key(r): simplify(r) for r in routes_b}

        added = []
        removed = []
        changed = []

        # Find removed and changed routes
        for key in dict_a:
            if key not in dict_b:
                removed.append(key)
            elif dict_a[key] != dict_b[key]:
                changes = {
                    field: {"from": dict_a[key].get(field), "to": dict_b[key].get(field)}
                    for field in dict_a[key]
                    if dict_a[key].get(field) != dict_b[key].get(field)
                }
                if changes:
                    changed.append({"route": key, "changes": changes})

        # Find added routes
        for key in dict_b:
            if key not in dict_a:
                added.append(key)

        summary_counts = {
            "added": len(added),
            "removed": len(removed),
            "modified": len(changed),
        }

        return {
            "snapshot_a_id": snapshot_a,
            "snapshot_b_id": snapshot_b,
            "added": added,
            "removed": removed,
            "changed": changed,
            "summary_counts": summary_counts,
            "message": f"Route table comparison complete. Found {summary_counts['added']} added, {summary_counts['removed']} removed, and {summary_counts['modified']} modified routes."
        }
