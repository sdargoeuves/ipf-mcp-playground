import json
from collections.abc import Sequence
from typing import Any, Dict, List, Optional

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

    def _format_response(self, data: Any, success: bool = True, message: str = "") -> List[TextContent]:
        """Helper method to format responses consistently."""
        if success:
            response = {
                "success": True,
                "data": data,
                "current_snapshot": self.ipf.snapshot_id,
            }
        else:
            response = {
                "success": False,
                "error": str(data),
                "current_snapshot": self.ipf.snapshot_id,
            }
        if message:
            response["message"] = message
        return [TextContent(type="text", text=json.dumps(response, indent=2, default=str))]

    def _handle_exception(self, e: Exception, operation: str) -> List[TextContent]:
        """Helper method to handle exceptions consistently."""
        return self._format_response(
            data=str(e),
            success=False,
            message=f"Failed to {operation}"
        )


class GetFilterHelpToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_filter_help", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="Get comprehensive help on IP Fabric filter syntax and operators. Essential for constructing filters for all query functions.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            },
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
            description="Retrieve all available snapshots from IP Fabric. Use this to find snapshot IDs before setting one, or changing snapshots if you don't know the existing snapshots.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            },
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
            description="""Set or change the active snapshot for all subsequent IP Fabric queries.
            
            This function changes the global snapshot context that will be used by all other 
            IP Fabric data retrieval functions. Once set, all queries (devices, interfaces, 
            routing tables, VLANs, etc.) will operate against the specified snapshot until 
            this function is called again with a different snapshot_id.
            
            Usage Requirements:
            - MUST be called before any data retrieval functions when a specific snapshot is required
            - Should be called whenever switching between different snapshots
            - Is required when the user specifies a particular snapshot by name or ID
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "snapshot_id": {
                        "type": "string",
                        "description": "The unique ID of the snapshot to activate. Use ipf_get_snapshots() to see available snapshot IDs."
                    }
                },
                "required": ["snapshot_id"],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        snapshot_id = args.get("snapshot_id")
        if not snapshot_id:
            return self._format_response(
                "snapshot_id argument is required",
                success=False,
                message="Missing required parameter"
            )
        
        try:
            old_snapshot = self.ipf.snapshot_id
            self.ipf.snapshot_id = snapshot_id
            result = {
                "old_snapshot": old_snapshot,
                "new_snapshot": self.ipf.snapshot_id,
            }
            return self._format_response(
                result,
                message=f"Successfully changed snapshot from {old_snapshot} to {self.ipf.snapshot_id}"
            )
        except Exception as e:
            return self._handle_exception(e, f"set snapshot to {snapshot_id}")


class GetDevicesToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_devices", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Get devices from IP Fabric inventory
            
            Args:
                filters: Optional dict of filters to apply (e.g. {"hostname": ["eq", "router1"]})
                columns: Optional list of specific columns to return
            
            Returns:
                Device inventory data
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "object",
                        "description": "Filter criteria using IP Fabric filter syntax. Use ipf_get_filter_help for syntax help."
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific columns to return, or to use with the filters. If not specified, all columns will be returned.",
                        "available_columns": {
                            "id": "string",
                            "configReg": "string",
                            "devType": "string",
                            "family": "string",
                            "hostname": "string",
                            "hostnameOriginal": "string",
                            "hostnameProcessed": "string",
                            "domain": "string",
                            "fqdn": "string",
                            "stack": "boolean",
                            "icon": "string",
                            "image": "string",
                            "objectId": "string",
                            "taskKey": "string",
                            "loginIp": "string",
                            "loginIpv4": "string",
                            "loginIpv6": "string",
                            "loginType": "string",
                            "loginPort": "integer",
                            "memoryTotalBytes": "integer",
                            "memoryUsedBytes": "integer",
                            "memoryUtilization": "integer",
                            "model": "string",
                            "platform": "string",
                            "processor": "string",
                            "rd": "string",
                            "reload": "string",
                            "siteName": "string",
                            "sn": "string",
                            "snHw": "string",
                            "stpDomain": "string",
                            "uptime": "integer",
                            "vendor": "string",
                            "version": "string",
                            "slug": "string",
                            "tsDiscoveryStart": "integer",
                            "tsDiscoveryEnd": "integer",
                            "secDiscoveryDuration": "integer",
                            "credentialsNotes": "string"
                        }
                    },
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            filters = args.get("filters", {})
            columns = args.get("columns")
            
            result = self.ipf.inventory.devices.all(filters=filters, columns=columns)
            
            return self._format_response(
                result,
                message=f"Retrieved {len(result) if result else 0} devices"
            )
        except Exception as e:
            return self._handle_exception(e, "retrieve devices")


class GetInterfacesToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_interfaces", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Get interfaces from IP Fabric inventory
            
            Args:
                filters: Optional dict of filters to apply (e.g. {"hostname": ["eq", "router1"]})
                columns: Optional list of specific columns to return
            
            Returns:
                Interface inventory data
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "object",
                        "description": "Filter criteria using IP Fabric filter syntax. Use ipf_get_filter_help for syntax help."
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific columns to return, or to use with the filters. If not specified, all columns will be returned.",
                        "available_columns": {
                            "id": "string",
                            "dscr": "string",
                            "duplex": "string",
                            "bandwidth": "integer",
                            "errDisabled": "string",
                            "hasTransceiver": "boolean",
                            "hostname": "string",
                            "intName": "string",
                            "intNameAlias": "string",
                            "lastStatusChange": "integer",
                            "l1": "string",
                            "l2": "string",
                            "loginIp": "string",
                            "loginType": "string",
                            "mac": "string",
                            "media": "string",
                            "mtu": "integer",
                            "nameOriginal": "string",
                            "primaryIp": "string",
                            "reason": "string",
                            "rel": "integer",
                            "siteName": "string",
                            "sn": "string",
                            "speed": "string",
                            "speedValue": "integer",
                            "speedType": "string",
                            "transceiverPn": "string",
                            "transceiverSn": "string",
                            "transceiverType": "string",
                            "slug": "string",
                            "clearingType": "string",
                            "clearingValue": "integer",
                            "lastInputType": "string",
                            "lastInputValue": "integer",
                            "lastOutputType": "string",
                            "lastOutputValue": "integer"
                        }
                    },
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            filters = args.get("filters", {})
            columns = args.get("columns")
            
            result = self.ipf.inventory.interfaces.all(filters=filters, columns=columns)
            
            return self._format_response(
                result,
                message=f"Retrieved {len(result) if result else 0} interfaces"
            )
        except Exception as e:
            return self._handle_exception(e, "retrieve interfaces")


class GetSitesToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_sites", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Get sites from IP Fabric inventory
            
            Args:
                filters: Optional dict of filters to apply
                columns: Optional list of specific columns to return
            
            Returns:
                Sites inventory data
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "object",
                        "description": "Filter criteria using IP Fabric filter syntax."
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific columns to return, or to use with the filters. If not specified, all columns will be returned.",
                        "available_columns": {
                            "id": "string",
                            "devicesCount": "integer",
                            "networksCount": "integer",
                            "rDCount": "integer",
                            "rDomains": ["string"],
                            "routersCount": "integer",
                            "siteName": "string",
                            "stpDCount": "integer",
                            "stpDomains": ["string"],
                            "switchesCount": "integer",
                            "usersCount": "integer",
                            "vlanCount": "integer"
                        }
                    },
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            filters = args.get("filters", {})
            columns = args.get("columns")
            
            result = self.ipf.inventory.sites.all(filters=filters, columns=columns)
            
            return self._format_response(
                result,
                message=f"Retrieved {len(result) if result else 0} sites"
            )
        except Exception as e:
            return self._handle_exception(e, "retrieve sites")


class GetVendorsToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_vendors", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Get vendors from IP Fabric inventory
            
            Args:
                filters: Optional dict of filters to apply
                columns: Optional list of specific columns to return
            
            Returns:
                Vendors inventory data
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "object",
                        "description": "Filter criteria using IP Fabric filter syntax."
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific columns to return, or to use with the filters. If not specified, all columns will be returned.",
                        "available_columns": {
                            "id": "string",
                            "devicesCount": "integer",
                            "familiesCount": "integer",
                            "modelsCount": "integer",
                            "platformsCount": "integer",
                            "vendor": "string"
                        }
                    },
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            filters = args.get("filters", {})
            columns = args.get("columns")
            
            result = self.ipf.inventory.vendors.all(filters=filters, columns=columns)
            
            return self._format_response(
                result,
                message=f"Retrieved {len(result) if result else 0} vendors"
            )
        except Exception as e:
            return self._handle_exception(e, "retrieve vendors")


class GetRoutingTableToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_routing_table", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Get routing table data from IP Fabric
            
            Args:
                filters: Optional dict of filters to apply
                columns: Optional list of specific columns to return
            
            Returns:
                Routing table data
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "object",
                        "description": "Filter criteria using IP Fabric filter syntax."
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific columns to return, or to use with the filters. If not specified, all columns will be returned.",
                        "available_columns": {
                            {
                                "id": "string",
                                "hostname": "string",
                                "network": "string",
                                "nexthop": [
                                    {
                                        "ad": "integer",
                                        "age": "integer",
                                        "intName": "string",
                                        "ip": "string",
                                        "labels": "string",
                                        "metric": "integer",
                                        "oid": "string",
                                        "vni": "integer",
                                        "vrfLeak": "string",
                                        "vtepIp": "string"
                                    }
                                ],
                                "nhCount": "integer",
                                "nhLowestAge": "integer",
                                "nhLowestMetric": "integer",
                                "prefix": "integer",
                                "protocol": "string",
                                "siteName": "string",
                                "sn": "string",
                                "vrf": "string"
                            }
                        }
                    },
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            filters = args.get("filters", {})
            columns = args.get("columns")
            
            result = self.ipf.technology.routing.routes_ipv4.all(filters=filters, columns=columns)
            
            return self._format_response(
                result,
                message=f"Retrieved {len(result) if result else 0} routing entries"
            )
        except Exception as e:
            return self._handle_exception(e, "retrieve routing table")


class GetVlansToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_vlans", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Get VLAN data from IP Fabric
            
            Args:
                filters: Optional dict of filters to apply
                columns: Optional list of specific columns to return
            
            Returns:
                VLAN data
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "object",
                        "description": "Filter criteria using IP Fabric filter syntax."
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific columns to return, or to use with the filters. If not specified, all columns will be returned.",
                        "available_columns": {
                            "id": "string",
                            "hostname": "string",
                            "siteName": "string",
                            "sn": "string",
                            "status": "string",
                            "stdStatus": "string",
                            "stpDomain": "string",
                            "vlanId": "integer",
                            "vlanName": "string"
                        },
                    },
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            filters = args.get("filters", {})
            columns = args.get("columns")
            
            result = self.ipf.technology.vlans.device_detail.all(filters=filters, columns=columns)
            
            return self._format_response(
                result,
                message=f"Retrieved {len(result) if result else 0} VLAN entries"
            )
        except Exception as e:
            return self._handle_exception(e, "retrieve VLANs")


class GetNeighborsToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_neighbors", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Get neighbor discovery data from IP Fabric. Use filter on prtocol like `cdp`, `stp`, or `cef`
            
            Args:
                filters: Optional dict of filters to apply
                columns: Optional list of specific columns to return
            
            Returns:
                Neighbor discovery data
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "object",
                        "description": "Filter criteria using IP Fabric filter syntax."
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific columns to return, or to use with the filters. If not specified, all columns will be returned.",
                        "available_columns": {
                            "id": "string",
                            "devType": "string",
                            "hostname": "string",
                            "intName": "string",
                            "localAddress": "string",
                            "localAddressV6": "string",
                            "neiIp": "string",
                            "neiIpV6": "string",
                            "protocol": "string",
                            "siteName": "string",
                            "sn": "string",
                            "source": "string",
                            "subnet": "string"
                        },
                    },
                    "required": [],
                }
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            filters = args.get("filters", {})
            columns = args.get("columns")
            
            result = self.ipf.technology.neighbors.neighbors_all.all(filters=filters, columns=columns)
            
            return self._format_response(
                result,
                message=f"Retrieved {len(result) if result else 0} neighbor entries"
            )
        except Exception as e:
            return self._handle_exception(e, "retrieve neighbors")


class GetAvailableColumnsToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_available_columns", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Get available columns for a specific table type
            
            Args:
                table_type: Type of table (e.g., "devices", "interfaces", "routing", "vlans")
            
            Returns:
                List of available columns for the specified table
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "table_type": {
                        "type": "string",
                        "description": "The table type to inspect. Valid options: devices, interfaces, sites, vendors, platforms, routing, vlans, neighbors",
                        "enum": ["devices", "interfaces", "sites", "vendors", "platforms", "routing", "vlans", "neighbors"]
                    }
                },
                "required": ["table_type"],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        table_type = args.get("table_type")
        
        if not table_type:
            return self._format_response(
                "table_type argument is required",
                success=False,
                message="Missing required parameter"
            )

        # Map table types to their API paths
        table_map = {
            "devices": "tables/inventory/devices",
            "interfaces": "tables/inventory/interfaces",
            "sites": "tables/inventory/sites",
            "vendors": "tables/inventory/summary/vendors",
            "platforms": "tables/inventory/summary/platforms",
            "routing": "tables/networks/routes",
            "vlans": "tables/vlan/device",
            "neighbors": "tables/neighbors/all",
        }

        if table_type not in table_map:
            return self._format_response(
                f"Unknown table type: {table_type}",
                success=False,
                message=f"Available table types: {', '.join(table_map.keys())}"
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
                result,
                message=f"Retrieved {len(columns) if columns else 0} columns for {table_type} table"
            )
        except Exception as e:
            return self._handle_exception(e, f"get columns for {table_type}")


class GetConnectionInfoToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_connection_info", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Get IP Fabric connection information and status
            
            Returns:
                Connection details and current snapshot info
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
                "base_url": getattr(self.ipf, 'base_url', 'Unknown'),
                "current_snapshot": self.ipf.snapshot_id,
                "api_version": getattr(self.ipf, 'api_version', 'Unknown'),
                "connected": True,  # If we can create this response, we're connected
            }
            
            # Try to get additional info if available
            try:
                snapshots = self.ipf.get_snapshots()
                if snapshots:
                    result["total_snapshots"] = len(snapshots)
                    result["latest_snapshot"] = snapshots[0] if snapshots else None
            except Exception:
                # Don't fail if we can't get snapshots
                pass
            
            return self._format_response(
                result,
                message="Connection information retrieved successfully"
            )
        except Exception as e:
            return self._handle_exception(e, "get connection information")


# Registry of all tool handlers for easy access
TOOL_HANDLERS = {
    "ipf_get_filter_help": GetFilterHelpToolHandler,
    "ipf_get_snapshots": GetSnapshotsToolHandler,
    "ipf_set_snapshot": SetSnapshotToolHandler,
    "ipf_get_devices": GetDevicesToolHandler,
    "ipf_get_interfaces": GetInterfacesToolHandler,
    # "ipf_get_hosts": GetHostsToolHandler,  # TODO: Assuming this is for host data
    "ipf_get_sites": GetSitesToolHandler,
    "ipf_get_vendors": GetVendorsToolHandler,
    "ipf_get_routing_table": GetRoutingTableToolHandler,
    # "ipf_get_managed_ipv4": GetManagedIPv4ToolHandler,  # TODO: Assuming this is for managed IPs
    "ipf_get_vlans": GetVlansToolHandler,
    "ipf_get_neighbors": GetNeighborsToolHandler,
    "ipf_get_available_columns": GetAvailableColumnsToolHandler,
    "ipf_get_connection_info": GetConnectionInfoToolHandler,
}