"""
Plugin Manifest Parser

Parses plugin manifest.json files to extract:
- Plugin metadata (name, description, executable)
- Function definitions (name, description, parameters)
- Tags and configuration

This mirrors the C++ PluginManager::parsePluginManifest() implementation.
"""

import json
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path


# Supported manifest version (matching C++ PLUGIN_VERSION_SUPPORTED)
PLUGIN_VERSION_SUPPORTED = 1


class ManifestError(Exception):
    """Manifest parsing errors"""
    pass


@dataclass
class ParameterDefinition:
    """Definition of a function parameter"""
    name: str
    type: str
    description: str = ""
    required: bool = True
    enum: Optional[List[str]] = None
    default: Optional[Any] = None
    
    @classmethod
    def from_dict(cls, name: str, schema: Dict[str, Any]) -> 'ParameterDefinition':
        """Parse from JSON Schema property"""
        return cls(
            name=name,
            type=schema.get("type", "string"),
            description=schema.get("description", ""),
            required=True,  # Set by parent based on required array
            enum=schema.get("enum"),
            default=schema.get("default")
        )


@dataclass
class FunctionDefinition:
    """Definition of a plugin function"""
    name: str
    description: str
    parameters: List[ParameterDefinition] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, func_dict: Dict[str, Any]) -> 'FunctionDefinition':
        """Parse from manifest function object"""
        name = func_dict.get("name", "")
        description = func_dict.get("description", "")
        tags = func_dict.get("tags", [])
        
        # Parse parameters from JSON Schema format
        parameters = []
        params_schema = func_dict.get("parameters", {})
        
        if isinstance(params_schema, dict):
            properties = params_schema.get("properties", {})
            required = params_schema.get("required", [])
            
            for param_name, param_schema in properties.items():
                param = ParameterDefinition.from_dict(param_name, param_schema)
                param.required = param_name in required
                parameters.append(param)
        
        return cls(
            name=name,
            description=description,
            parameters=parameters,
            tags=tags
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to ICL function definition format"""
        properties = {}
        required = []
        
        for param in self.parameters:
            prop = {"type": param.type, "description": param.description}
            if param.enum:
                prop["enum"] = param.enum
            if param.default is not None:
                prop["default"] = param.default
            properties[param.name] = prop
            
            if param.required:
                required.append(param.name)
        
        result = {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
        
        if self.tags:
            result["tags"] = self.tags
        
        return result


@dataclass
class PluginManifest:
    """Parsed plugin manifest"""
    name: str
    description: str
    directory: str
    executable: str
    executable_path: str
    manifest_version: int
    protocol_version: str
    persistent: bool = False
    passthrough: bool = False
    functions: List[FunctionDefinition] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    mcp_enabled: bool = False
    mcp_launch_on_startup: bool = False
    
    def get_function(self, name: str) -> Optional[FunctionDefinition]:
        """Get a function definition by name"""
        for func in self.functions:
            if func.name == name:
                return func
        return None
    
    def get_function_names(self) -> List[str]:
        """Get list of all function names"""
        return [f.name for f in self.functions]
    
    def to_icl_definitions(self) -> List[Dict[str, Any]]:
        """Convert to ICL function definitions format"""
        return [f.to_dict() for f in self.functions]


class ManifestParser:
    """
    Plugin manifest parser
    
    Mirrors the C++ parsePluginManifest() implementation.
    """
    
    @staticmethod
    def parse(manifest_path: str) -> PluginManifest:
        """
        Parse a plugin manifest.json file.
        
        Args:
            manifest_path: Path to manifest.json
            
        Returns:
            Parsed PluginManifest
            
        Raises:
            ManifestError: If manifest is invalid or missing required fields
        """
        manifest_path = Path(manifest_path)
        
        if not manifest_path.exists():
            raise ManifestError(f"Manifest not found: {manifest_path}")
        
        # Read and parse JSON
        try:
            content = manifest_path.read_text(encoding='utf-8')
            
            # Skip UTF-8 BOM if present
            if content.startswith('\ufeff'):
                content = content[1:]
            
            manifest_dict = json.loads(content)
        except json.JSONDecodeError as e:
            raise ManifestError(f"JSON parse error: {e}")
        except Exception as e:
            raise ManifestError(f"Failed to read manifest: {e}")
        
        return ManifestParser._parse_dict(manifest_dict, manifest_path)
    
    @staticmethod
    def parse_directory(plugin_dir: str) -> PluginManifest:
        """
        Parse a plugin directory (looks for manifest.json inside).
        
        Args:
            plugin_dir: Path to plugin directory
            
        Returns:
            Parsed PluginManifest
        """
        plugin_dir = Path(plugin_dir)
        manifest_path = plugin_dir / "manifest.json"
        return ManifestParser.parse(str(manifest_path))
    
    @staticmethod
    def _parse_dict(manifest: Dict[str, Any], manifest_path: Path) -> PluginManifest:
        """Parse manifest from dictionary"""
        
        plugin_dir = manifest_path.parent
        plugin_name = plugin_dir.name
        
        # Validate required fields
        required_fields = ["manifestVersion", "executable", "persistent"]
        for field_name in required_fields:
            if field_name not in manifest:
                raise ManifestError(f"Missing required field: {field_name}")
        
        # Validate protocol version
        if "protocol_version" not in manifest:
            raise ManifestError("Missing required 'protocol_version' field")
        
        protocol_version = manifest["protocol_version"]
        if protocol_version != "2.0":
            raise ManifestError(f"Unsupported protocol_version '{protocol_version}' (expected '2.0')")
        
        # Validate manifest version
        manifest_version = manifest["manifestVersion"]
        if manifest_version != PLUGIN_VERSION_SUPPORTED:
            raise ManifestError(
                f"Unsupported manifest version {manifest_version} "
                f"(expected {PLUGIN_VERSION_SUPPORTED})"
            )
        
        # Extract basic fields
        description = manifest.get("description", "No description provided.")
        executable = manifest["executable"]
        persistent = manifest["persistent"]
        
        # Build full executable path
        executable_path = str(plugin_dir / executable)
        
        # Parse functions
        functions = ManifestParser._parse_functions(manifest, plugin_name)
        
        # Check passthrough mode (only valid for single-function plugins)
        passthrough = manifest.get("passthrough", False)
        if passthrough and len(functions) != 1:
            passthrough = False
        
        # Parse tags
        tags = []
        if "tags" in manifest and isinstance(manifest["tags"], list):
            tags = [str(t) for t in manifest["tags"] if isinstance(t, str)]
        
        # Parse MCP configuration
        mcp_enabled = False
        mcp_launch_on_startup = False
        if "mcp" in manifest and isinstance(manifest["mcp"], dict):
            mcp_config = manifest["mcp"]
            mcp_enabled = mcp_config.get("enabled", False)
            mcp_launch_on_startup = mcp_config.get("launch_on_startup", False)
        
        # Validate function names (must not use reserved prefix)
        for func in functions:
            if func.name.startswith("rise_"):
                raise ManifestError(
                    f"Function '{func.name}' uses reserved 'rise_' prefix"
                )
        
        return PluginManifest(
            name=plugin_name,
            description=description,
            directory=str(plugin_dir),
            executable=executable,
            executable_path=executable_path,
            manifest_version=manifest_version,
            protocol_version=protocol_version,
            persistent=persistent,
            passthrough=passthrough,
            functions=functions,
            tags=tags,
            mcp_enabled=mcp_enabled,
            mcp_launch_on_startup=mcp_launch_on_startup
        )
    
    @staticmethod
    def _parse_functions(manifest: Dict[str, Any], plugin_name: str) -> List[FunctionDefinition]:
        """Parse function definitions from manifest"""
        
        functions = []
        
        # Check for unified JSON Schema format
        if "schema" in manifest and isinstance(manifest["schema"], dict):
            functions = ManifestParser._extract_functions_from_schema(
                manifest["schema"], plugin_name
            )
        # Check for simple functions array format
        elif "functions" in manifest and isinstance(manifest["functions"], list):
            for func_dict in manifest["functions"]:
                if isinstance(func_dict, dict):
                    func = FunctionDefinition.from_dict(func_dict)
                    functions.append(func)
        else:
            raise ManifestError("Manifest missing both 'schema' and 'functions'")
        
        # Validate each function has required fields
        for func in functions:
            if not func.name:
                raise ManifestError("Function entry missing 'name'")
            if not func.description:
                raise ManifestError(f"Function '{func.name}' missing 'description'")
        
        return functions
    
    @staticmethod
    def _extract_functions_from_schema(schema: Dict[str, Any], plugin_name: str) -> List[FunctionDefinition]:
        """
        Extract function definitions from unified JSON Schema format.
        
        The schema format is a JSON Schema object where each function is defined
        as a property with type, description, and parameters.
        """
        functions = []
        
        # Handle anyOf/oneOf structure (multiple functions)
        if "anyOf" in schema:
            for item in schema["anyOf"]:
                func = ManifestParser._parse_schema_function(item)
                if func:
                    functions.append(func)
        elif "oneOf" in schema:
            for item in schema["oneOf"]:
                func = ManifestParser._parse_schema_function(item)
                if func:
                    functions.append(func)
        # Handle single function schema
        elif "properties" in schema:
            func = ManifestParser._parse_schema_function(schema)
            if func:
                functions.append(func)
        # Handle functions as object properties
        elif isinstance(schema, dict):
            for name, definition in schema.items():
                if isinstance(definition, dict) and "description" in definition:
                    func = FunctionDefinition.from_dict({
                        "name": name,
                        **definition
                    })
                    functions.append(func)
        
        return functions
    
    @staticmethod
    def _parse_schema_function(schema_item: Dict[str, Any]) -> Optional[FunctionDefinition]:
        """Parse a single function from JSON Schema item"""
        
        if not isinstance(schema_item, dict):
            return None
        
        # Try to find the function name
        name = schema_item.get("name", schema_item.get("title", ""))
        description = schema_item.get("description", "")
        
        # If this is a wrapper with "function" property
        if "function" in schema_item:
            func_def = schema_item["function"]
            name = func_def.get("name", name)
            description = func_def.get("description", description)
            schema_item = func_def
        
        if not name:
            return None
        
        return FunctionDefinition.from_dict({
            "name": name,
            "description": description,
            "parameters": schema_item.get("parameters", {}),
            "tags": schema_item.get("tags", [])
        })


def discover_plugins(plugins_dir: str) -> List[str]:
    """
    Discover plugin directories in a plugins folder.
    
    Args:
        plugins_dir: Path to plugins directory
        
    Returns:
        List of plugin directory names
    """
    plugins_dir = Path(plugins_dir)
    
    if not plugins_dir.exists():
        return []
    
    plugins = []
    for item in plugins_dir.iterdir():
        if item.is_dir():
            manifest_path = item / "manifest.json"
            if manifest_path.exists():
                plugins.append(item.name)
    
    return sorted(plugins)


def validate_plugin_name(name: str) -> bool:
    """
    Validate that a plugin name is safe and valid.
    
    Args:
        name: Plugin name to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not name:
        return False
    
    # Check for path traversal
    if ".." in name or "/" in name or "\\" in name:
        return False
    
    # Check for reserved names
    reserved = {"con", "prn", "aux", "nul", "com1", "com2", "lpt1", "lpt2"}
    if name.lower() in reserved:
        return False
    
    # Check for valid characters (alphanumeric, underscore, hyphen)
    import re
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', name):
        return False
    
    return True

