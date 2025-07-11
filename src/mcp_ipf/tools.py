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
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            filters = args.get("filters", {})
            columns = args.get("columns")

            result = self.ipf.inventory.devices.all(filters=filters, columns=columns)

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
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            filters = args.get("filters", {})
            columns = args.get("columns")

            result = self.ipf.inventory.interfaces.all(filters=filters, columns=columns)

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
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            filters = args.get("filters", {})
            columns = args.get("columns")

            result = self.ipf.inventory.hosts.all(filters=filters, columns=columns)

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
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            filters = args.get("filters", {})
            columns = args.get("columns")

            result = self.ipf.inventory.sites.all(filters=filters, columns=columns)

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
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            filters = args.get("filters", {})
            columns = args.get("columns")

            result = self.ipf.inventory.vendors.all(filters=filters, columns=columns)

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
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            filters = args.get("filters", {})
            columns = args.get("columns")

            result = self.ipf.technology.routing.routes_ipv4.all(filters=filters, columns=columns)

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
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            filters = args.get("filters", {})
            columns = args.get("columns")

            result = self.ipf.technology.addressing.managed_ip_ipv4.all(filters=filters, columns=columns)

            return self._format_response(result, message=f"Retrieved {len(result) if result else 0} managed IPv4 entries")
        except Exception as e:
            return self._handle_exception(e, "retrieve managed IPv4 entries")


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
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            filters = args.get("filters", {})
            columns = args.get("columns")

            result = self.ipf.technology.vlans.device_detail.all(filters=filters, columns=columns)

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
                },
                "required": [],
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent]:
        try:
            filters = args.get("filters", {})
            columns = args.get("columns")

            result = self.ipf.technology.neighbors.neighbors_all.all(filters=filters, columns=columns)

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
                        "enum": ["devices", "interfaces", "sites", "vendors", "platforms", "routing", "vlans", "neighbors"],
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
                loaded_snapshots = [snapshots[k] for k, v in snapshots.items() if (v.status == "done" and "$" not in k)]
                if loaded_snapshots:
                    result["total_loaded_snapshots"] = len(loaded_snapshots)
                    result["latest_snapshot"] = snapshots["$last"].snapshot_id
            except Exception:
                # Don't fail if we can't get snapshots
                pass

            return self._format_response(result, message="Connection information retrieved successfully")
        except Exception as e:
            return self._handle_exception(e, "get connection information")


# Registry of all tool handlers for easy access
TOOL_HANDLERS = {
    "ipf_get_filter_help": GetFilterHelpToolHandler,
    "ipf_get_snapshots": GetSnapshotsToolHandler,
    "ipf_set_snapshot": SetSnapshotToolHandler,
    "ipf_get_devices": GetDevicesToolHandler,
    "ipf_get_interfaces": GetInterfacesToolHandler,
    "ipf_get_hosts": GetHostsToolHandler,
    "ipf_get_sites": GetSitesToolHandler,
    "ipf_get_vendors": GetVendorsToolHandler,
    "ipf_get_routing_table": GetRoutingTableToolHandler,
    "ipf_get_managed_ipv4": GetManagedIPv4ToolHandler,
    "ipf_get_vlans": GetVlansToolHandler,
    "ipf_get_neighbors": GetNeighborsToolHandler,
    "ipf_get_available_columns": GetAvailableColumnsToolHandler,
    "ipf_get_connection_info": GetConnectionInfoToolHandler,
}
