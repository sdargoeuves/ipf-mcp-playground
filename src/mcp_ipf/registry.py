"""Tool registration and discovery module."""

import inspect
import logging
from typing import List, Type, Callable, Any

logger = logging.getLogger(__name__)

def discover_tool_handlers(tools_module) -> List[Type]:
    """
    Discover all ToolHandler subclasses in the given tools module.
    
    Args:
        tools_module: The module to inspect for tool classes
        
    Returns:
        List of ToolHandler subclass types
    """
    tool_classes = []
    
    for name, obj in inspect.getmembers(tools_module, inspect.isclass):
        # Check if it's a subclass of ToolHandler but not ToolHandler itself
        if (hasattr(tools_module, 'ToolHandler') and 
            issubclass(obj, tools_module.ToolHandler) and 
            obj is not tools_module.ToolHandler):
            tool_classes.append(obj)
            logger.debug(f"Discovered tool class: {obj.__name__}")
    
    return tool_classes

def register_discovered_tools(
    tools_module, 
    ipf_client, 
    add_handler_func: Callable[[Any], None]
) -> tuple[int, int]:
    """
    Register all discovered tool handlers.
    
    Args:
        tools_module: The module containing tool classes
        ipf_client: The IPFClient instance
        add_handler_func: Function to add handlers to the registry
        
    Returns:
        Tuple of (registered_count, failed_count)
    """
    tool_classes = discover_tool_handlers(tools_module)
    registered_count = 0
    failed_count = 0
    
    for tool_class in tool_classes:
        try:
            tool_handler = tool_class(ipf_client)
            
            # Validate tool description during registration
            tool_handler.get_tool_description()
            
            add_handler_func(tool_handler)
            registered_count += 1
            logger.info(f"Registered tool: {tool_class.__name__}")

        except Exception as e:
            failed_count += 1
            logger.error(f"Failed to register {tool_class.__name__}: {e}")
            # Could add traceback logging here if needed
            continue
    
    total_discovered = registered_count + failed_count
    logger.info(f"Successfully registered {registered_count}/{total_discovered} tools")
    
    if failed_count > 0:
        logger.warning(f"{failed_count} tools failed to register")
    
    return registered_count, failed_count

def get_tool_info(tools_module) -> dict:
    """
    Get information about available tools without registering them.
    
    Returns:
        Dictionary with tool discovery information
    """
    tool_classes = discover_tool_handlers(tools_module)
    return {
        'discovered_count': len(tool_classes),
        'tool_names': [cls.__name__ for cls in tool_classes],
        'tool_classes': tool_classes
    }
