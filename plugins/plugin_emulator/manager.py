"""
Plugin Manager

Manages discovery, loading, and lifecycle of plugins.
Provides a unified interface for executing plugin functions.

This mirrors the G-Assist engine's PluginManager class implementation.
"""

import os
import logging
import threading
from typing import Dict, List, Optional, Set, Callable, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, field

from .manifest import (
    ManifestParser,
    PluginManifest,
    FunctionDefinition,
    ManifestError,
    discover_plugins,
    validate_plugin_name,
)
from .plugin import Plugin, PluginState, PluginResponse, PluginError


logger = logging.getLogger(__name__)


@dataclass
class PluginInfo:
    """Basic plugin information"""
    name: str
    description: str
    state: PluginState
    persistent: bool
    passthrough: bool
    function_count: int


@dataclass
class FailedPluginInfo:
    """Information about a plugin that failed to load"""
    name: str
    reason: str


class PluginManager:
    """
    Manages the lifecycle of G-Assist plugins.
    
    Features:
    - Plugin directory scanning
    - Manifest parsing and validation
    - Plugin process management
    - Function routing and execution
    - Tag-based function filtering
    
    This mirrors the G-Assist engine's PluginManager class implementation.
    """
    
    def __init__(
        self,
        plugins_dir: Optional[str] = None,
        on_stream: Optional[Callable[[str, str], None]] = None,
        on_complete: Optional[Callable[[str, bool, str], None]] = None,
    ):
        """
        Initialize the plugin manager.
        
        Args:
            plugins_dir: Path to plugins directory
            on_stream: Callback for streaming data (plugin_name, data)
            on_complete: Callback for completion (plugin_name, success, data)
        """
        self._plugins_dir = plugins_dir
        self._on_stream = on_stream
        self._on_complete = on_complete
        
        # Plugin storage
        self._plugins: Dict[str, Plugin] = {}
        self._manifests: Dict[str, PluginManifest] = {}
        
        # Function routing
        self._functions: Dict[str, str] = {}  # function_name -> plugin_name
        
        # Tag lookup
        self._tag_lookup: Dict[str, Set[str]] = {}  # tag -> set of function names
        
        # ICL function definitions (for AI inference)
        self._icl_definitions: Dict[str, List[Dict[str, Any]]] = {}
        
        # Failed plugins
        self._failed_plugins: List[FailedPluginInfo] = []
        
        # Threading
        self._lock = threading.RLock()
        
        # Initialization state
        self._initialized = False
    
    @property
    def plugins_dir(self) -> Optional[str]:
        """Get plugins directory path"""
        return self._plugins_dir
    
    @plugins_dir.setter
    def plugins_dir(self, path: str):
        """Set plugins directory path"""
        self._plugins_dir = path
    
    def initialize(self, plugins_dir: Optional[str] = None, verbose: bool = True) -> bool:
        """
        Initialize the plugin manager by scanning and loading plugins.

        Args:
            plugins_dir: Optional plugins directory override
            verbose: Print progress to stdout
            
        Returns:
            True if initialization succeeded
        """
        if plugins_dir:
            self._plugins_dir = plugins_dir

        if not self._plugins_dir:
            logger.error("No plugins directory specified")
            return False

        plugins_path = Path(self._plugins_dir)
        if not plugins_path.exists():
            logger.warning(f"Plugins directory does not exist: {plugins_path}")
            return False

        logger.info(f"Initializing PluginManager with directory: {plugins_path}")
        if verbose:
            print(f"\nScanning plugins directory: {plugins_path}")

        # Discover and load plugins
        plugin_names = discover_plugins(str(plugins_path))
        logger.info(f"Discovered {len(plugin_names)} plugin(s): {plugin_names}")
        if verbose:
            print(f"Discovered {len(plugin_names)} plugin(s): {', '.join(plugin_names)}")
        
        # Clear existing data
        with self._lock:
            self._plugins.clear()
            self._manifests.clear()
            self._functions.clear()
            self._tag_lookup.clear()
            self._icl_definitions.clear()
            self._failed_plugins.clear()
        
        # Load each plugin
        if verbose:
            print("\nLoading plugins...")
        for i, plugin_name in enumerate(plugin_names, 1):
            try:
                if verbose:
                    print(f"  [{i}/{len(plugin_names)}] Loading {plugin_name}...", end=" ", flush=True)
                self._load_plugin(plugin_name)
                if verbose:
                    manifest = self._manifests.get(plugin_name)
                    func_count = len(manifest.functions) if manifest else 0
                    mcp_tag = " (MCP)" if manifest and manifest.mcp_enabled else ""
                    print(f"OK ({func_count} functions){mcp_tag}")
            except Exception as e:
                logger.error(f"Failed to load plugin '{plugin_name}': {e}")
                self._failed_plugins.append(FailedPluginInfo(plugin_name, str(e)))
                if verbose:
                    print(f"FAILED: {e}")

        # Start persistent plugins
        self._start_persistent_plugins(verbose)
        
        self._initialized = True
        logger.info(f"PluginManager initialized: {len(self._plugins)} plugin(s) loaded")
        
        if verbose:
            total_functions = sum(len(m.functions) for m in self._manifests.values())
            print(f"\nInitialization complete: {len(self._plugins)} plugins, {total_functions} functions")

        return True
    
    def shutdown(self):
        """Shutdown all plugins and cleanup"""
        logger.info("Shutting down PluginManager")
        
        with self._lock:
            for name, plugin in self._plugins.items():
                try:
                    if plugin.is_running:
                        logger.info(f"Stopping plugin '{name}'")
                        plugin.shutdown()
                except Exception as e:
                    logger.error(f"Error stopping plugin '{name}': {e}")
            
            self._plugins.clear()
            self._initialized = False
    
    def _load_plugin(self, plugin_name: str) -> bool:
        """Load a single plugin"""
        
        if not validate_plugin_name(plugin_name):
            raise ManifestError(f"Invalid plugin name: {plugin_name}")
        
        plugin_dir = os.path.join(self._plugins_dir, plugin_name)
        
        # Parse manifest
        manifest = ManifestParser.parse_directory(plugin_dir)
        
        # Create plugin instance
        plugin = Plugin(
            manifest=manifest,
            on_stream=lambda data, name=plugin_name: self._handle_stream(name, data),
            on_complete=lambda s, d, name=plugin_name: self._handle_complete(name, s, d),
        )
        
        # Register plugin
        with self._lock:
            self._plugins[plugin_name] = plugin
            self._manifests[plugin_name] = manifest
            
            # Register functions
            icl_defs = []
            for func in manifest.functions:
                self._functions[func.name] = plugin_name
                icl_defs.append(func.to_dict())
                
                # Register tags
                for tag in func.tags:
                    tag_lower = tag.lower()
                    if tag_lower not in self._tag_lookup:
                        self._tag_lookup[tag_lower] = set()
                    self._tag_lookup[tag_lower].add(func.name)
                
                # Also register manifest-level tags
                for tag in manifest.tags:
                    tag_lower = tag.lower()
                    if tag_lower not in self._tag_lookup:
                        self._tag_lookup[tag_lower] = set()
                    self._tag_lookup[tag_lower].add(func.name)
            
            self._icl_definitions[plugin_name] = icl_defs
        
        logger.info(f"Loaded plugin '{plugin_name}' with {len(manifest.functions)} function(s)")
        return True
    
    def _start_persistent_plugins(self, verbose: bool = True):
        """Start plugins marked as persistent, with extra time for MCP plugins"""
        import time
        
        persistent_plugins = [(name, plugin) for name, plugin in self._plugins.items() if plugin.persistent]
        
        if not persistent_plugins:
            return
        
        if verbose:
            print(f"\nStarting {len(persistent_plugins)} persistent plugin(s)...")
        
        mcp_plugins = []
        
        for i, (name, plugin) in enumerate(persistent_plugins, 1):
            logger.info(f"Starting persistent plugin '{name}'")
            if verbose:
                print(f"  [{i}/{len(persistent_plugins)}] Starting {name}...", end=" ", flush=True)
            try:
                response = plugin.initialize()
                if not response.success:
                    logger.error(f"Failed to initialize persistent plugin '{name}': {response.message}")
                    if verbose:
                        print(f"FAILED: {response.message}")
                else:
                    if verbose:
                        print("OK")
                    # Track MCP plugins that need extra time
                    manifest = self._manifests.get(name)
                    if manifest and manifest.mcp_enabled:
                        mcp_plugins.append(name)
            except Exception as e:
                logger.error(f"Error starting persistent plugin '{name}': {e}")
                if verbose:
                    print(f"ERROR: {e}")
        
        # Give MCP plugins time to connect and discover functions
        if mcp_plugins:
            if verbose:
                print(f"\nWaiting for MCP plugins to discover functions: {', '.join(mcp_plugins)}")
                print("  ", end="", flush=True)
                for i in range(5):
                    print(".", end="", flush=True)
                    time.sleep(1)
                print(" done")
            else:
                logger.info(f"Waiting for MCP plugins to discover functions: {mcp_plugins}")
                time.sleep(5)
            
            # Re-read manifests for MCP plugins (they may have updated on disk)
            if verbose:
                print("Refreshing MCP plugin manifests...")
            for name in mcp_plugins:
                try:
                    manifest = self._manifests.get(name)
                    if manifest:
                        old_count = len(manifest.functions)
                        self._refresh_mcp_manifest(name, manifest.directory)
                        new_manifest = self._manifests.get(name)
                        new_count = len(new_manifest.functions) if new_manifest else 0
                        if verbose and new_count != old_count:
                            print(f"  {name}: {old_count} -> {new_count} functions")
                except Exception as e:
                    logger.warning(f"Could not refresh manifest for MCP plugin '{name}': {e}")
    
    def _refresh_mcp_manifest(self, plugin_name: str, plugin_dir: str):
        """Re-read manifest for an MCP plugin after it has discovered functions"""
        try:
            # Re-parse the manifest
            new_manifest = ManifestParser.parse_directory(plugin_dir)
            old_manifest = self._manifests.get(plugin_name)
            
            # Check if functions have changed
            old_func_count = len(old_manifest.functions) if old_manifest else 0
            new_func_count = len(new_manifest.functions)
            
            if new_func_count != old_func_count:
                logger.info(f"MCP plugin '{plugin_name}' refreshed: {old_func_count} -> {new_func_count} functions")
                
                # Update stored manifest
                self._manifests[plugin_name] = new_manifest
                
                # Re-register functions
                with self._lock:
                    # Remove old function registrations
                    funcs_to_remove = [f for f, p in self._functions.items() if p == plugin_name]
                    for f in funcs_to_remove:
                        del self._functions[f]
                    
                    # Add new functions
                    icl_defs = []
                    for func in new_manifest.functions:
                        self._functions[func.name] = plugin_name
                        icl_defs.append(func.to_dict())
                        
                        # Register tags
                        for tag in func.tags:
                            tag_lower = tag.lower()
                            if tag_lower not in self._tag_lookup:
                                self._tag_lookup[tag_lower] = set()
                            self._tag_lookup[tag_lower].add(func.name)
                    
                    self._icl_definitions[plugin_name] = icl_defs
                    
                    # Update plugin's manifest reference
                    plugin = self._plugins.get(plugin_name)
                    if plugin:
                        plugin.manifest = new_manifest
            else:
                logger.debug(f"MCP plugin '{plugin_name}' manifest unchanged ({new_func_count} functions)")
                
        except Exception as e:
            logger.warning(f"Failed to refresh manifest for '{plugin_name}': {e}")

    def _handle_stream(self, plugin_name: str, data: str):
        """Handle streaming data from a plugin"""
        if self._on_stream:
            self._on_stream(plugin_name, data)
    
    def _handle_complete(self, plugin_name: str, success: bool, data: str):
        """Handle completion from a plugin"""
        if self._on_complete:
            self._on_complete(plugin_name, success, data)
    
    # ========================================================================
    # Public API
    # ========================================================================
    
    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get a plugin by name"""
        with self._lock:
            return self._plugins.get(name)
    
    def get_plugin_names(self) -> List[str]:
        """Get list of all plugin names"""
        with self._lock:
            return list(self._plugins.keys())
    
    def get_plugins_info(self) -> List[PluginInfo]:
        """Get information about all plugins"""
        with self._lock:
            return [
                PluginInfo(
                    name=name,
                    description=plugin.description,
                    state=plugin.state,
                    persistent=plugin.persistent,
                    passthrough=plugin.passthrough,
                    function_count=len(plugin.get_function_names())
                )
                for name, plugin in self._plugins.items()
            ]
    
    def get_failed_plugins(self) -> List[FailedPluginInfo]:
        """Get list of plugins that failed to load"""
        with self._lock:
            return list(self._failed_plugins)
    
    def plugin_exists(self, name: str) -> bool:
        """Check if a plugin exists"""
        with self._lock:
            return name in self._plugins
    
    def function_exists(self, function_name: str) -> bool:
        """Check if a function exists in any plugin"""
        with self._lock:
            return function_name in self._functions
    
    def get_plugin_for_function(self, function_name: str) -> Optional[str]:
        """Get the plugin name that implements a function"""
        with self._lock:
            return self._functions.get(function_name)
    
    def is_passthrough(self, plugin_name: str) -> bool:
        """Check if a plugin is in passthrough mode"""
        with self._lock:
            plugin = self._plugins.get(plugin_name)
            return plugin.passthrough if plugin else False
    
    def get_icl_definitions(self, plugin_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get ICL function definitions.
        
        Args:
            plugin_name: Optional filter by plugin name
            
        Returns:
            List of function definitions in ICL format
        """
        with self._lock:
            if plugin_name:
                return list(self._icl_definitions.get(plugin_name, []))
            else:
                # Return all definitions
                result = []
                for defs in self._icl_definitions.values():
                    result.extend(defs)
                return result
    
    def get_function_definition(self, function_name: str) -> Optional[Dict[str, Any]]:
        """Get ICL definition for a specific function"""
        plugin_name = self.get_plugin_for_function(function_name)
        if not plugin_name:
            return None
        
        defs = self._icl_definitions.get(plugin_name, [])
        for d in defs:
            if d.get("name") == function_name:
                return d
        return None
    
    def get_all_functions(self) -> List[str]:
        """Get list of all function names"""
        with self._lock:
            return list(self._functions.keys())
    
    def get_functions_by_tag(self, tag: str) -> List[str]:
        """Get functions that have a specific tag"""
        with self._lock:
            return list(self._tag_lookup.get(tag.lower(), set()))
    
    def get_functions_by_tags(self, tags: List[str]) -> List[str]:
        """Get functions that have all specified tags"""
        if not tags:
            return self.get_all_functions()
        
        with self._lock:
            # Start with functions that have the first tag
            result = self._tag_lookup.get(tags[0].lower(), set())
            
            # Intersect with functions that have remaining tags
            for tag in tags[1:]:
                tag_funcs = self._tag_lookup.get(tag.lower(), set())
                result = result.intersection(tag_funcs)
            
            return list(result)
    
    # ========================================================================
    # Execution API
    # ========================================================================
    
    def execute(
        self,
        function_name: str,
        arguments: Dict[str, Any],
        context: Optional[List[Dict[str, str]]] = None,
        system_info: Optional[str] = None,
        timeout_ms: int = 30000
    ) -> PluginResponse:
        """
        Execute a plugin function.
        
        Args:
            function_name: Name of the function to execute
            arguments: Function arguments
            context: Optional conversation context
            system_info: Optional system information
            timeout_ms: Execution timeout
            
        Returns:
            PluginResponse with result
        """
        # Find the plugin that implements this function
        plugin_name = self.get_plugin_for_function(function_name)
        if not plugin_name:
            return PluginResponse(
                success=False,
                message=f"Unknown function: {function_name}"
            )
        
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            return PluginResponse(
                success=False,
                message=f"Plugin not found: {plugin_name}"
            )
        
        logger.info(f"Executing {function_name}({arguments}) via plugin '{plugin_name}'")
        
        return plugin.execute(
            function=function_name,
            arguments=arguments,
            context=context,
            system_info=system_info,
            timeout_ms=timeout_ms
        )
    
    def execute_direct(
        self,
        plugin_name: str,
        function_name: str,
        arguments: Dict[str, Any],
        context: Optional[List[Dict[str, str]]] = None,
        system_info: Optional[str] = None,
        timeout_ms: int = 30000
    ) -> PluginResponse:
        """
        Execute a function on a specific plugin directly.
        
        Args:
            plugin_name: Name of the plugin
            function_name: Name of the function
            arguments: Function arguments
            context: Optional conversation context
            system_info: Optional system information
            timeout_ms: Execution timeout
            
        Returns:
            PluginResponse with result
        """
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            return PluginResponse(
                success=False,
                message=f"Plugin not found: {plugin_name}"
            )
        
        logger.info(f"Executing {plugin_name}.{function_name}({arguments})")
        
        return plugin.execute(
            function=function_name,
            arguments=arguments,
            context=context,
            system_info=system_info,
            timeout_ms=timeout_ms
        )
    
    def start_plugin(self, plugin_name: str) -> bool:
        """Start a specific plugin"""
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            logger.error(f"Plugin not found: {plugin_name}")
            return False
        
        response = plugin.initialize()
        return response.success
    
    def stop_plugin(self, plugin_name: str) -> bool:
        """Stop a specific plugin"""
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            logger.error(f"Plugin not found: {plugin_name}")
            return False
        
        response = plugin.shutdown()
        return response.success
    
    def get_awaiting_input_plugin(self) -> Optional[Plugin]:
        """Get the plugin currently awaiting user input"""
        with self._lock:
            for plugin in self._plugins.values():
                if plugin.is_awaiting_input:
                    return plugin
        return None
    
    def send_user_input(self, plugin_name: str, content: str) -> PluginResponse:
        """Send user input to a plugin in passthrough mode"""
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            return PluginResponse(
                success=False,
                message=f"Plugin not found: {plugin_name}"
            )
        
        return plugin.send_user_input(content)
    
    # ========================================================================
    # Tool Catalog (for LLM inference)
    # ========================================================================
    
    def refresh_mcp_plugins(self) -> Dict[str, int]:
        """
        Refresh manifests for all MCP plugins.
        
        Returns:
            Dict mapping plugin name to new function count
        """
        results = {}
        
        for name, manifest in self._manifests.items():
            if manifest.mcp_enabled:
                old_count = len(manifest.functions)
                self._refresh_mcp_manifest(name, manifest.directory)
                new_manifest = self._manifests.get(name)
                new_count = len(new_manifest.functions) if new_manifest else 0
                results[name] = new_count
                
                if new_count != old_count:
                    logger.info(f"Refreshed '{name}': {old_count} -> {new_count} functions")
        
        return results
    
    def get_mcp_plugins(self) -> List[str]:
        """Get list of MCP-enabled plugin names"""
        return [name for name, manifest in self._manifests.items() if manifest.mcp_enabled]

    def build_tool_catalog(self) -> List[Dict[str, Any]]:
        """
        Build unified tool catalog for LLM inference.
        
        Returns:
            List of tool definitions in OpenAI function calling format
        """
        tools = []
        
        for plugin_name, defs in self._icl_definitions.items():
            for func_def in defs:
                tool = {
                    "type": "function",
                    "function": {
                        "name": func_def["name"],
                        "description": f"[Plugin: {plugin_name}] {func_def.get('description', '')}",
                        "parameters": func_def.get("parameters", {"type": "object", "properties": {}})
                    }
                }
                tools.append(tool)
        
        return tools

