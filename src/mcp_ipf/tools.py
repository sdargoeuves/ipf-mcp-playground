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
            description="""Get all available snapshots from IP Fabric
            
            Snapshots represent point-in-time captures of your network topology, configuration and state.
            Use this to discover available snapshots before switching contexts or to understand
            the timeline of network discoveries.
            
            Returns:
                List of snapshots with metadata including ID, name, creation time, status,
                number of devices (total and licensed), siteName, and more.
            """,
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
            description="""Set the active snapshot for all subsequent IP Fabric queries
        
            Changes the global snapshot context used by all data retrieval functions.
            All subsequent queries (devices, interfaces, routing, VLANs, etc.) will operate
            against the specified snapshot until changed again.
            
            Args:
                snapshot_id: The unique identifier of the snapshot to activate
            
            Returns:
                Confirmation with old and new snapshot IDs
            
            Usage:
                - Call before any data queries when targeting a specific snapshot, if different from the current one
                - Required when user specifies a particular snapshot by name/ID, if different from the current one
                - Use ipf_get_snapshots() first to see available options
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "snapshot_id": {
                        "type": "string",
                        "description": "The unique ID of the snapshot to activate. Use ipf_get_snapshots() to see available snapshot IDs.",
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


class GetDevicesToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_devices", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Get network devices from IP Fabric inventory
            
            Retrieves comprehensive device information including hostname, loginIP, uptime,
            serial number (unique -- generated by IP Fabric based on device context, called `sn`, and the one provided by the device called `snHw`),
            vendor, model, platform, software version, operational status. Essential for
            network inventory analysis and device management tasks.
            
            Args:
                filters: Optional filtering using IP Fabric syntax (e.g., {"vendor": ["eq", "cisco"]})
                columns: Optional list to limit returned columns for performance
                snapshot_id: snapshot ID to query against, use if you want to query against a specific snapshot instead of the current one.

            Returns:
                Device inventory with hostname, IP, vendor, model, version, site, and status data
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "object",
                        "description": "Filter criteria using IP Fabric filter syntax. Use ipf_get_filter_help for syntax help, based on available_columns.",
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
                            "credentialsNotes": "string",
                        },
                    },
                    "snapshot_id": {
                        "type": "string",
                        "description": """
                            The ID of the snapshot to query against (e.g., 'cf2d7763-85b3-4d97-afdb-e66eb6e4125e')
                            If not specified, the current snapshot (ipf.snapshot_id) will be used
                            Use ipf_get_snapshots() to see available snapshot IDs if needed.
                        """
                    },
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            filters = args.get("filters", {})
            columns = args.get("columns")
            snapshot_id = args.get("snapshot_id", self.ipf.snapshot_id)

            result = self.ipf.inventory.devices.all(filters=filters, columns=columns, snapshot_id=snapshot_id)

            return self._format_response(result, message=f"Retrieved {len(result) if result else 0} devices")
        except Exception as e:
            return self._handle_exception(e, "retrieve devices")


class GetInterfacesToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_interfaces", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Get network interfaces from IP Fabric inventory
            
            Retrieves detailed interface information including operational status on l1 and l2 layers,
            configuration, speeds, MTU, last Input/Output and clearing, and physical properties. Critical for network
            connectivity analysis and troubleshooting.
            
            Args:
                filters: Optional filtering (e.g., {"hostname": ["eq", "router1"]})
                columns: Optional list to limit returned columns
            
            Returns:
                Interface data with status, speed, VLAN, IP addressing, and physical details
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "object",
                        "description": "Filter criteria using IP Fabric filter syntax. Use ipf_get_filter_help for syntax help, based on available_columns.",
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
                            "lastOutputValue": "integer",
                        },
                    },
                    "snapshot_id": {
                        "type": "string",
                        "description": """
                            The ID of the snapshot to query against (e.g., 'cf2d7763-85b3-4d97-afdb-e66eb6e4125e')
                            If not specified, the current snapshot (ipf.snapshot_id) will be used
                            Use ipf_get_snapshots() to see available snapshot IDs if needed.
                        """
                    },
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            filters = args.get("filters", {})
            columns = args.get("columns")
            snapshot_id = args.get("snapshot_id", self.ipf.snapshot_id)

            result = self.ipf.inventory.interfaces.all(filters=filters, columns=columns, snapshot_id=snapshot_id)

            return self._format_response(result, message=f"Retrieved {len(result) if result else 0} interfaces")
        except Exception as e:
            return self._handle_exception(e, "retrieve interfaces")


class GetHostsToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_hosts", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Get end hosts from IP Fabric inventory
            This tool provides a comprehensive overview of host details, including the IP address, MAC address, and DNS name (if available).
            Additionally, it offers insights into the physical connections of each host, including the associated device
            and interface (Edge) as well as the gateway device. If applicable, VLAN and VRF information for each host is also included.
            
            Args:
                filters: Optional filtering (e.g., {"siteName": ["eq", "headquarters"]})
                columns: Optional list to limit returned columns
            
            Returns:
                Host data with IP/MAC addresses, connected switches/interfaces, 
                gateways, VLAN/VRF info, and access point details
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "object",
                        "description": "Filter criteria using IP Fabric filter syntax. Use ipf_get_filter_help for syntax help, based on available_columns.",
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific columns to return, or to use with the filters. If not specified, all columns will be returned.",
                        "available_columns": {
                            "id": "string",
                            "accessPoints": [{"hostname": "string", "sn": "string", "ssid": "string"}],
                            "dnsName": "string",
                            "edges": [
                                {
                                    "hostname": "string",
                                    "sn": "string",
                                    "intName": "string",
                                    "intDscr": "string",
                                    "poe": "string",
                                }
                            ],
                            "gateways": [{"hostname": "string", "sn": "string", "intName": "string"}],
                            "ip": "string",
                            "mac": "string",
                            "siteName": "string",
                            "type": ["string"],
                            "uniqId": "string",
                            "vendor": "string",
                            "vlan": "integer",
                            "vrf": "string",
                        },
                    },
                    "snapshot_id": {
                        "type": "string",
                        "description": """
                            The ID of the snapshot to query against (e.g., 'cf2d7763-85b3-4d97-afdb-e66eb6e4125e')
                            If not specified, the current snapshot (ipf.snapshot_id) will be used
                            Use ipf_get_snapshots() to see available snapshot IDs if needed.
                        """
                    },
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            filters = args.get("filters", {})
            columns = args.get("columns")
            snapshot_id = args.get("snapshot_id", self.ipf.snapshot_id)

            result = self.ipf.inventory.hosts.all(filters=filters, columns=columns, snapshot_id=snapshot_id)

            return self._format_response(result, message=f"Retrieved {len(result) if result else 0} hosts")
        except Exception as e:
            return self._handle_exception(e, "retrieve hosts")


class GetSitesToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_sites", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Get sites from IP Fabric inventory

            Retrieves site-level network summary information including device counts,
            routing domains, and VLAN statistics. Useful for network planning and
            site-based analysis.
            
            Args:
                filters: Optional filtering (e.g., {"devicesCount": ["gt", 10]})
                columns: Optional list to limit returned columns
            
            Returns:
                Site data with device/router/switch counts, routing domains, STP domains,
                VLAN counts, and user statistics        
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "object",
                        "description": "Filter criteria using IP Fabric filter syntax. Use ipf_get_filter_help for syntax help, based on available_columns.",
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
                            "vlanCount": "integer",
                        },
                    },
                    "snapshot_id": {
                        "type": "string",
                        "description": """
                            The ID of the snapshot to query against (e.g., 'cf2d7763-85b3-4d97-afdb-e66eb6e4125e')
                            If not specified, the current snapshot (ipf.snapshot_id) will be used
                            Use ipf_get_snapshots() to see available snapshot IDs if needed.
                        """
                    },
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            filters = args.get("filters", {})
            columns = args.get("columns")
            snapshot_id = args.get("snapshot_id", self.ipf.snapshot_id)

            result = self.ipf.inventory.sites.all(filters=filters, columns=columns, snapshot_id=snapshot_id)

            return self._format_response(result, message=f"Retrieved {len(result) if result else 0} sites")
        except Exception as e:
            return self._handle_exception(e, "retrieve sites")


class GetVendorsToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_vendors", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Get vendor summary from IP Fabric inventory
            
            Provides vendor-based network statistics including device counts and
            platform diversity. Useful for vendor analysis and compliance reporting.
            
            Args:
                filters: Optional filtering (e.g., {"vendor": ["like", "cisco"]})
                columns: Optional list to limit returned columns
            
            Returns:
                Vendor statistics with device counts, platform/model/family diversity
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "object",
                        "description": "Filter criteria using IP Fabric filter syntax. Use ipf_get_filter_help for syntax help, based on available_columns.",
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
                            "vendor": "string",
                        },
                    },
                    "snapshot_id": {
                        "type": "string",
                        "description": """
                            The ID of the snapshot to query against (e.g., 'cf2d7763-85b3-4d97-afdb-e66eb6e4125e')
                            If not specified, the current snapshot (ipf.snapshot_id) will be used
                            Use ipf_get_snapshots() to see available snapshot IDs if needed.
                        """
                    },
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            filters = args.get("filters", {})
            columns = args.get("columns")
            snapshot_id = args.get("snapshot_id", self.ipf.snapshot_id)

            result = self.ipf.inventory.vendors.all(filters=filters, columns=columns, snapshot_id=snapshot_id)

            return self._format_response(result, message=f"Retrieved {len(result) if result else 0} vendors")
        except Exception as e:
            return self._handle_exception(e, "retrieve vendors")


class GetRoutingTableToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_routing_table", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Get IPv4 routing table entries from IP Fabric
            
            Retrieves detailed routing information including next-hops, metrics,
            and protocols. Essential for routing analysis, and network troubleshooting.
            
            Args:
                filters: Optional filtering (e.g., {"protocol": ["eq", "ospf"]})
                columns: Optional list to limit returned columns
            
            Returns:
                Routing entries with networks, next-hops, metrics, protocols, VRFs,
                and administrative distances
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "object",
                        "description": "Filter criteria using IP Fabric filter syntax. Use ipf_get_filter_help for syntax help, based on available_columns.",
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific columns to return, or to use with the filters. If not specified, all columns will be returned.",
                        "available_columns": {
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
                                    "vtepIp": "string",
                                }
                            ],
                            "nhCount": "integer",
                            "nhLowestAge": "integer",
                            "nhLowestMetric": "integer",
                            "prefix": "integer",
                            "protocol": "string",
                            "siteName": "string",
                            "sn": "string",
                            "vrf": "string",
                        },
                    },
                    "snapshot_id": {
                        "type": "string",
                        "description": """
                            The ID of the snapshot to query against (e.g., 'cf2d7763-85b3-4d97-afdb-e66eb6e4125e')
                            If not specified, the current snapshot (ipf.snapshot_id) will be used
                            Use ipf_get_snapshots() to see available snapshot IDs if needed.
                        """
                    },
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            filters = args.get("filters", {})
            columns = args.get("columns")
            snapshot_id = args.get("snapshot_id", self.ipf.snapshot_id)

            result = self.ipf.technology.routing.routes_ipv4.all(filters=filters, columns=columns, snapshot_id=snapshot_id)

            return self._format_response(result, message=f"Retrieved {len(result) if result else 0} routing entries")
        except Exception as e:
            return self._handle_exception(e, "retrieve routing table")


class GetManagedIPv4ToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_managed_ipv4", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Get managed IPv4 addresses from IP Fabric
            
            Retrieves all configured IPv4 addresses and subnets across the network,
            including interface assignments and DNS resolution. Critical for IP
            address management and subnet planning.
            
            Args:
                filters: Optional filtering (e.g., {"net": ["cidr", "10.0.0.0/8"]})
                columns: Optional list to limit returned columns
            
            Returns:
                IPv4 data with addresses, subnets, interface assignments, DNS names,
                VLANs, VRFs, and operational status
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "object",
                        "description": "Filter criteria using IP Fabric filter syntax. Use ipf_get_filter_help for syntax help, based on available_columns.",
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific columns to return, or to use with the filters. If not specified, all columns will be returned.",
                        "available_columns": {
                            "id": "string",
                            "dnsHostnameMatch": "integer",
                            "dnsName": "string",
                            "dnsReverseMatch": "integer",
                            "hostname": "string",
                            "intName": "string",
                            "ip": "string",
                            "mac": "string",
                            "net": "string",
                            "siteName": "string",
                            "sn": "string",
                            "stateL1": "string",
                            "stateL2": "string",
                            "type": "string",
                            "vlanId": "integer",
                            "vrf": "string",
                        },
                    },
                    "snapshot_id": {
                        "type": "string",
                        "description": """
                            The ID of the snapshot to query against (e.g., 'cf2d7763-85b3-4d97-afdb-e66eb6e4125e')
                            If not specified, the current snapshot (ipf.snapshot_id) will be used
                            Use ipf_get_snapshots() to see available snapshot IDs if needed.
                        """
                    },
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            filters = args.get("filters", {})
            columns = args.get("columns")
            snapshot_id = args.get("snapshot_id", self.ipf.snapshot_id)

            result = self.ipf.technology.addressing.managed_ip_ipv4.all(filters=filters, columns=columns, snapshot_id=snapshot_id)

            return self._format_response(result, message=f"Retrieved {len(result) if result else 0} managed IPv4 entries")
        except Exception as e:
            return self._handle_exception(e, "retrieve managed IPv4 entries")


class GetArpToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_arp", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Get ARP entries from IP Fabric

            Retrieves all configured ARP entries across the network,
            including IP-MAC bindings and interface assignments. Critical for IP
            address management and troubleshooting.

            Args:
                filters: Optional filtering (e.g., {"ip": ["eq", "10.0.0.1"]})
                columns: Optional list to limit returned columns

            Returns:
                ARP table data with Device, IP address, MAC address, VRF, Vlan and interface assignments
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "object",
                        "description": "Filter criteria using IP Fabric filter syntax. Use ipf_get_filter_help for syntax help, based on available_columns.",
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific columns to return, or to use with the filters. If not specified, all columns will be returned.",
                        "available_columns": {
                            "id": "string",
                            "hostname": "string",
                            "intName": "string",
                            "ip": "string",
                            "mac": "string",
                            "proxy": "boolean",
                            "siteName": "string",
                            "sn": "string",
                            "vendor": "string",
                            "vlanId": "integer",
                            "vrf": "string",
                        },
                    },
                    "snapshot_id": {
                        "type": "string",
                        "description": """
                            The ID of the snapshot to query against (e.g., 'cf2d7763-85b3-4d97-afdb-e66eb6e4125e')
                            If not specified, the current snapshot (ipf.snapshot_id) will be used
                            Use ipf_get_snapshots() to see available snapshot IDs if needed.
                        """
                    },
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            filters = args.get("filters", {})
            columns = args.get("columns")
            snapshot_id = args.get("snapshot_id", self.ipf.snapshot_id)

            result = self.ipf.technology.addressing.arp_table.all(filters=filters, columns=columns, snapshot_id=snapshot_id)

            return self._format_response(result, message=f"Retrieved {len(result) if result else 0} ARP table entries")
        except Exception as e:
            return self._handle_exception(e, "retrieve ARP table entries")


class GetMacToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_mac", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Get MAC entries from IP Fabric

            Retrieves all configured MAC entries across the network,
            including MAC, vendor based on OUI, and interface assignments.

            Args:
                filters: Optional filtering (e.g., {"mac": ["eq", "0011.2233.4455"]})
                columns: Optional list to limit returned columns

            Returns:
                MAC table data with Device, IP address, MAC address, VRF, Vlan and interface assignments
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "object",
                        "description": "Filter criteria using IP Fabric filter syntax. Use ipf_get_filter_help for syntax help, based on available_columns.",
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific columns to return, or to use with the filters. If not specified, all columns will be returned.",
                        "available_columns": {
                            "id": "string",
                            "edge": "boolean",
                            "hostname": "string",
                            "intName": "string",
                            "mac": "string",
                            "siteName": "string",
                            "sn": "string",
                            "source": "string",
                            "type": "string",
                            "user": "boolean",
                            "vendor": "string",
                            "vlan": "integer",
                            "vni": "integer",
                            "vxlans": [{"intName": "string", "vtepIp": "string"}],
                            "fabricPath": {"localId": "integer", "subswitchId": "integer", "switchId": "integer"},
                            "virtualBridge": "string",
                        },
                    },
                    "snapshot_id": {
                        "type": "string",
                        "description": """
                            The ID of the snapshot to query against (e.g., 'cf2d7763-85b3-4d97-afdb-e66eb6e4125e')
                            If not specified, the current snapshot (ipf.snapshot_id) will be used
                            Use ipf_get_snapshots() to see available snapshot IDs if needed.
                        """
                    },
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            filters = args.get("filters", {})
            columns = args.get("columns")
            snapshot_id = args.get("snapshot_id", self.ipf.snapshot_id)

            result = self.ipf.technology.addressing.mac_table.all(filters=filters, columns=columns, snapshot_id=snapshot_id)

            return self._format_response(result, message=f"Retrieved {len(result) if result else 0} MAC table entries")
        except Exception as e:
            return self._handle_exception(e, "retrieve MAC table entries")


class GetVlansToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_vlans", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Get VLAN information from IP Fabric
            
            Retrieves VLAN information including names, IDs, and operational status
            per device. Essential for VLAN troubleshooting and network segmentation
            analysis.
            
            Args:
                filters: Optional filtering (e.g., {"vlanId": ["eq", 100]})
                columns: Optional list to limit returned columns
            
            Returns:
                VLAN data with IDs, names, status, STP domains, and device assignments
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "object",
                        "description": "Filter criteria using IP Fabric filter syntax. Use ipf_get_filter_help for syntax help, based on available_columns.",
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
                            "vlanName": "string",
                        },
                    },
                    "snapshot_id": {
                        "type": "string",
                        "description": """
                            The ID of the snapshot to query against (e.g., 'cf2d7763-85b3-4d97-afdb-e66eb6e4125e')
                            If not specified, the current snapshot (ipf.snapshot_id) will be used
                            Use ipf_get_snapshots() to see available snapshot IDs if needed.
                        """
                    },
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            filters = args.get("filters", {})
            columns = args.get("columns")
            snapshot_id = args.get("snapshot_id", self.ipf.snapshot_id)

            result = self.ipf.technology.vlans.device_detail.all(filters=filters, columns=columns, snapshot_id=snapshot_id)

            return self._format_response(result, message=f"Retrieved {len(result) if result else 0} VLAN entries")
        except Exception as e:
            return self._handle_exception(e, "retrieve VLANs")


class GetNeighborsToolHandler(ToolHandler):
    def __init__(self, ipf_client: IPFClient):
        super().__init__("ipf_get_neighbors", ipf_client)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Get neighbor discovery data from IP Fabric
            
            Retrieves network neighbor relationships discovered through various protocols
            (CDP, STP, CEF). Critical for topology verification and building mapping between assets.
            Use filter on protocol like `cdp`, `stp`, or `cef`.
            
            Args:
                filters: Optional filtering (e.g., {"protocol": ["eq", "cdp"]})
                columns: Optional list to limit returned columns
            
            Returns:
                Neighbor data with local/remote devices, interfaces, protocols,
                and IP addresses
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "object",
                        "description": "Filter criteria using IP Fabric filter syntax. Use ipf_get_filter_help for syntax help, based on available_columns.",
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
                            "subnet": "string",
                        },
                    },
                    "snapshot_id": {
                        "type": "string",
                        "description": """
                            The ID of the snapshot to query against (e.g., 'cf2d7763-85b3-4d97-afdb-e66eb6e4125e')
                            If not specified, the current snapshot (ipf.snapshot_id) will be used
                            Use ipf_get_snapshots() to see available snapshot IDs if needed.
                        """
                    },
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            filters = args.get("filters", {})
            columns = args.get("columns")
            snapshot_id = args.get("snapshot_id", self.ipf.snapshot_id)

            result = self.ipf.technology.neighbors.neighbors_all.all(filters=filters, columns=columns, snapshot_id=snapshot_id)

            return self._format_response(result, message=f"Retrieved {len(result) if result else 0} neighbor entries")
        except Exception as e:
            return self._handle_exception(e, "retrieve neighbors")


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
