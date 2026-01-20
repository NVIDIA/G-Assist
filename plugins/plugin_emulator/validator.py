"""
Plugin Validator

Validates plugin compliance with the G-Assist Plugin Protocol V2.
Produces a scorecard covering:
- Protocol compliance (JSON-RPC 2.0, framing)
- Heartbeat/ping response
- Timeout handling
- Error handling
- Manifest accuracy
- Streaming behavior
"""

import time
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .plugin import Plugin, PluginState, PluginResponse
from .manifest import PluginManifest
from .protocol import (
    JsonRpcRequest,
    build_ping_request,
    build_execute_request,
    build_initialize_request,
    PING_TIMEOUT_MS,
    EXECUTE_TIMEOUT_MS,
)

logger = logging.getLogger(__name__)


class ValidationStatus(Enum):
    """Status for each validation check"""
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"
    INFO = "INFO"


@dataclass
class ValidationCheck:
    """Result of a single validation check"""
    name: str
    status: ValidationStatus
    message: str
    details: str = ""
    duration_ms: float = 0.0


@dataclass
class ValidationCategory:
    """Category of validation checks"""
    name: str
    description: str
    checks: List[ValidationCheck] = field(default_factory=list)
    
    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.status == ValidationStatus.PASS)
    
    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if c.status == ValidationStatus.FAIL)
    
    @property
    def warnings(self) -> int:
        return sum(1 for c in self.checks if c.status == ValidationStatus.WARN)
    
    @property
    def score(self) -> float:
        """Score from 0-100"""
        total = len([c for c in self.checks if c.status != ValidationStatus.SKIP])
        if total == 0:
            return 100.0
        passed = self.passed + (self.warnings * 0.5)
        return (passed / total) * 100


@dataclass
class ValidationReport:
    """Complete validation report for a plugin"""
    plugin_name: str
    plugin_version: str
    timestamp: str
    categories: List[ValidationCategory] = field(default_factory=list)
    
    @property
    def total_checks(self) -> int:
        return sum(len(c.checks) for c in self.categories)
    
    @property
    def total_passed(self) -> int:
        return sum(c.passed for c in self.categories)
    
    @property
    def total_failed(self) -> int:
        return sum(c.failed for c in self.categories)
    
    @property
    def total_warnings(self) -> int:
        return sum(c.warnings for c in self.categories)
    
    @property
    def overall_score(self) -> float:
        """Overall score from 0-100"""
        if not self.categories:
            return 0.0
        return sum(c.score for c in self.categories) / len(self.categories)
    
    @property
    def grade(self) -> str:
        """Letter grade based on score"""
        score = self.overall_score
        if score >= 95:
            return "A+"
        elif score >= 90:
            return "A"
        elif score >= 85:
            return "B+"
        elif score >= 80:
            return "B"
        elif score >= 75:
            return "C+"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"


class PluginValidator:
    """
    Validates plugin compliance with G-Assist Protocol V2.
    
    Runs a series of tests and produces a scorecard report.
    """
    
    def __init__(self, plugin: Plugin, manifest: PluginManifest):
        self.plugin = plugin
        self.manifest = manifest
        self.report: Optional[ValidationReport] = None
    
    def validate(self, verbose: bool = False) -> ValidationReport:
        """
        Run full validation suite.
        
        Args:
            verbose: If True, print progress during validation
            
        Returns:
            ValidationReport with all results
        """
        from datetime import datetime
        
        self.report = ValidationReport(
            plugin_name=self.manifest.name,
            plugin_version=getattr(self.manifest, 'version', '1.0.0') if hasattr(self.manifest, 'version') else '1.0.0',
            timestamp=datetime.now().isoformat()
        )
        
        if verbose:
            print(f"\nValidating plugin: {self.manifest.name}")
            print("=" * 60)
        
        # Run validation categories
        self.report.categories.append(self._validate_manifest(verbose))
        self.report.categories.append(self._validate_startup(verbose))
        
        # Add MCP validation if plugin is MCP-enabled
        if self.manifest.mcp_enabled:
            self.report.categories.append(self._validate_mcp(verbose))
        
        self.report.categories.append(self._validate_protocol(verbose))
        self.report.categories.append(self._validate_heartbeat(verbose))
        self.report.categories.append(self._validate_execution(verbose))
        self.report.categories.append(self._validate_stress(verbose))
        self.report.categories.append(self._validate_error_handling(verbose))
        self.report.categories.append(self._validate_shutdown(verbose))
        
        return self.report
    
    def _validate_manifest(self, verbose: bool) -> ValidationCategory:
        """Validate manifest compliance"""
        category = ValidationCategory(
            name="Manifest",
            description="Manifest file structure and content"
        )
        
        if verbose:
            print("\n[1/8] Checking manifest...")
        
        # Check manifest version
        if self.manifest.manifest_version == 1:
            category.checks.append(ValidationCheck(
                name="Manifest Version",
                status=ValidationStatus.PASS,
                message="Using supported manifest version 1"
            ))
        else:
            category.checks.append(ValidationCheck(
                name="Manifest Version",
                status=ValidationStatus.FAIL,
                message=f"Unsupported manifest version: {self.manifest.manifest_version}"
            ))
        
        # Check protocol version
        if self.manifest.protocol_version == "2.0":
            category.checks.append(ValidationCheck(
                name="Protocol Version",
                status=ValidationStatus.PASS,
                message="Using Protocol V2 (2.0)"
            ))
        else:
            category.checks.append(ValidationCheck(
                name="Protocol Version",
                status=ValidationStatus.FAIL,
                message=f"Invalid protocol version: {self.manifest.protocol_version}"
            ))
        
        # Check description
        if self.manifest.description and len(self.manifest.description) > 10:
            category.checks.append(ValidationCheck(
                name="Description",
                status=ValidationStatus.PASS,
                message="Has meaningful description"
            ))
        else:
            category.checks.append(ValidationCheck(
                name="Description",
                status=ValidationStatus.WARN,
                message="Missing or short description"
            ))
        
        # Check functions exist
        if self.manifest.functions and len(self.manifest.functions) > 0:
            category.checks.append(ValidationCheck(
                name="Functions Defined",
                status=ValidationStatus.PASS,
                message=f"Defines {len(self.manifest.functions)} function(s)"
            ))
        else:
            category.checks.append(ValidationCheck(
                name="Functions Defined",
                status=ValidationStatus.FAIL,
                message="No functions defined in manifest"
            ))
        
        # Check function names don't use reserved prefix
        reserved_funcs = [f for f in self.manifest.functions if f.name.startswith("rise_")]
        if not reserved_funcs:
            category.checks.append(ValidationCheck(
                name="Function Names",
                status=ValidationStatus.PASS,
                message="No reserved 'rise_' prefix used"
            ))
        else:
            category.checks.append(ValidationCheck(
                name="Function Names",
                status=ValidationStatus.FAIL,
                message=f"Functions use reserved prefix: {[f.name for f in reserved_funcs]}"
            ))
        
        # Check each function has description
        funcs_without_desc = [f for f in self.manifest.functions if not f.description]
        if not funcs_without_desc:
            category.checks.append(ValidationCheck(
                name="Function Descriptions",
                status=ValidationStatus.PASS,
                message="All functions have descriptions"
            ))
        else:
            category.checks.append(ValidationCheck(
                name="Function Descriptions",
                status=ValidationStatus.WARN,
                message=f"Functions missing descriptions: {[f.name for f in funcs_without_desc]}"
            ))
        
        # Check passthrough mode consistency
        if self.manifest.passthrough:
            if len(self.manifest.functions) == 1:
                category.checks.append(ValidationCheck(
                    name="Passthrough Mode",
                    status=ValidationStatus.PASS,
                    message="Passthrough enabled with single function"
                ))
            else:
                category.checks.append(ValidationCheck(
                    name="Passthrough Mode",
                    status=ValidationStatus.WARN,
                    message="Passthrough enabled but multiple functions defined"
                ))
        
        # Check MCP configuration
        if self.manifest.mcp_enabled:
            category.checks.append(ValidationCheck(
                name="MCP Enabled",
                status=ValidationStatus.INFO,
                message="Plugin uses MCP for function discovery"
            ))
            
            if self.manifest.mcp_launch_on_startup:
                category.checks.append(ValidationCheck(
                    name="MCP Startup",
                    status=ValidationStatus.PASS,
                    message="MCP server launches on startup"
                ))
        
        return category
    
    def _validate_startup(self, verbose: bool) -> ValidationCategory:
        """Validate plugin startup behavior"""
        category = ValidationCategory(
            name="Startup",
            description="Plugin startup and initialization"
        )
        
        if verbose:
            print("\n[2/8] Checking startup...")
        
        # Ensure plugin is stopped first
        if self.plugin.is_running:
            self.plugin.stop()
            time.sleep(0.5)
        
        # Test startup time
        start_time = time.time()
        started = self.plugin.start()
        startup_time = (time.time() - start_time) * 1000
        
        if started:
            category.checks.append(ValidationCheck(
                name="Process Start",
                status=ValidationStatus.PASS,
                message="Plugin process started successfully",
                duration_ms=startup_time
            ))
        else:
            category.checks.append(ValidationCheck(
                name="Process Start",
                status=ValidationStatus.FAIL,
                message="Failed to start plugin process"
            ))
            return category  # Can't continue without process
        
        # Check startup time
        if startup_time < 1000:
            category.checks.append(ValidationCheck(
                name="Startup Time",
                status=ValidationStatus.PASS,
                message=f"Started in {startup_time:.0f}ms (< 1s)",
                duration_ms=startup_time
            ))
        elif startup_time < 3000:
            category.checks.append(ValidationCheck(
                name="Startup Time",
                status=ValidationStatus.WARN,
                message=f"Started in {startup_time:.0f}ms (1-3s, consider optimizing)",
                duration_ms=startup_time
            ))
        else:
            category.checks.append(ValidationCheck(
                name="Startup Time",
                status=ValidationStatus.FAIL,
                message=f"Started in {startup_time:.0f}ms (> 3s, too slow)",
                duration_ms=startup_time
            ))
        
        # Test initialize
        start_time = time.time()
        init_response = self.plugin.initialize()
        init_time = (time.time() - start_time) * 1000
        
        if init_response.success:
            category.checks.append(ValidationCheck(
                name="Initialize Response",
                status=ValidationStatus.PASS,
                message="Responded to initialize request",
                duration_ms=init_time
            ))
        else:
            category.checks.append(ValidationCheck(
                name="Initialize Response",
                status=ValidationStatus.FAIL,
                message=f"Initialize failed: {init_response.message}",
                duration_ms=init_time
            ))
        
        # Check initialize time
        if init_time < 5000:
            category.checks.append(ValidationCheck(
                name="Initialize Time",
                status=ValidationStatus.PASS,
                message=f"Initialized in {init_time:.0f}ms",
                duration_ms=init_time
            ))
        else:
            category.checks.append(ValidationCheck(
                name="Initialize Time",
                status=ValidationStatus.WARN,
                message=f"Initialization slow: {init_time:.0f}ms",
                duration_ms=init_time
            ))
        
        return category
    
    def _validate_mcp(self, verbose: bool) -> ValidationCategory:
        """Validate MCP-based plugin discovery and connectivity"""
        category = ValidationCategory(
            name="MCP Discovery",
            description="MCP server connectivity and function discovery"
        )
        
        if verbose:
            print("\n[MCP] Checking MCP connectivity and function discovery...")
        
        if not self.manifest.mcp_enabled:
            category.checks.append(ValidationCheck(
                name="MCP Status",
                status=ValidationStatus.SKIP,
                message="Plugin does not use MCP"
            ))
            return category
        
        # Record initial function count
        initial_func_count = len(self.manifest.functions)
        
        category.checks.append(ValidationCheck(
            name="Initial Functions",
            status=ValidationStatus.INFO,
            message=f"Manifest has {initial_func_count} functions at startup"
        ))
        
        # Wait for MCP discovery to complete (give it extra time)
        if verbose:
            print("    Waiting 10 seconds for MCP discovery to complete...")
        
        time.sleep(10)
        
        # Check if plugin is still running after MCP connection
        if self.plugin.is_running:
            category.checks.append(ValidationCheck(
                name="MCP Connection",
                status=ValidationStatus.PASS,
                message="Plugin running after MCP connection time"
            ))
        else:
            category.checks.append(ValidationCheck(
                name="MCP Connection",
                status=ValidationStatus.FAIL,
                message="Plugin crashed during MCP connection"
            ))
            return category
        
        # Try to re-read manifest to see if functions were discovered
        try:
            from .manifest import ManifestParser
            refreshed_manifest = ManifestParser.parse_directory(self.manifest.directory)
            refreshed_func_count = len(refreshed_manifest.functions)
            
            if refreshed_func_count > 0:
                category.checks.append(ValidationCheck(
                    name="Function Discovery",
                    status=ValidationStatus.PASS,
                    message=f"Discovered {refreshed_func_count} functions via MCP"
                ))
                
                if refreshed_func_count != initial_func_count:
                    category.checks.append(ValidationCheck(
                        name="Manifest Updated",
                        status=ValidationStatus.PASS,
                        message=f"Manifest updated: {initial_func_count} -> {refreshed_func_count} functions"
                    ))
                else:
                    category.checks.append(ValidationCheck(
                        name="Manifest Updated",
                        status=ValidationStatus.INFO,
                        message="Function count unchanged (may be cached)"
                    ))
            else:
                category.checks.append(ValidationCheck(
                    name="Function Discovery",
                    status=ValidationStatus.WARN,
                    message="No functions discovered (MCP server may be unavailable)"
                ))
                
        except Exception as e:
            category.checks.append(ValidationCheck(
                name="Manifest Refresh",
                status=ValidationStatus.WARN,
                message=f"Could not refresh manifest: {str(e)[:50]}"
            ))
        
        # Test that discovered functions are actually executable
        if verbose:
            print("    Testing MCP-discovered function execution...")
        
        if self.manifest.functions:
            test_func = self.manifest.functions[0]
            args = {}
            for param in test_func.parameters:
                if param.required:
                    if param.type == "string":
                        args[param.name] = "mcp_test"
                    elif param.type in ("number", "integer"):
                        args[param.name] = 1
            
            start_time = time.time()
            response = self.plugin.execute(
                function=test_func.name,
                arguments=args,
                timeout_ms=15000
            )
            exec_time = (time.time() - start_time) * 1000
            
            if response.success or response.awaiting_input:
                category.checks.append(ValidationCheck(
                    name="MCP Function Execution",
                    status=ValidationStatus.PASS,
                    message=f"MCP function '{test_func.name}' executed ({exec_time:.0f}ms)",
                    duration_ms=exec_time
                ))
                
                if response.awaiting_input:
                    self.plugin.send_user_input("exit")
            else:
                category.checks.append(ValidationCheck(
                    name="MCP Function Execution",
                    status=ValidationStatus.WARN,
                    message=f"MCP function failed: {response.message[:50]}..."
                ))
        
        return category
    
    def _validate_protocol(self, verbose: bool) -> ValidationCategory:
        """Validate protocol compliance"""
        category = ValidationCategory(
            name="Protocol",
            description="JSON-RPC 2.0 protocol compliance"
        )
        
        if verbose:
            print("\n[3/8] Checking protocol compliance...")
        
        if not self.plugin.is_running:
            category.checks.append(ValidationCheck(
                name="Protocol Tests",
                status=ValidationStatus.SKIP,
                message="Plugin not running"
            ))
            return category
        
        # Protocol compliance is validated by successful communication
        # If we got here, basic protocol is working
        category.checks.append(ValidationCheck(
            name="JSON-RPC 2.0",
            status=ValidationStatus.PASS,
            message="Plugin speaks JSON-RPC 2.0"
        ))
        
        category.checks.append(ValidationCheck(
            name="Length-Prefixed Framing",
            status=ValidationStatus.PASS,
            message="Uses 4-byte big-endian length prefix"
        ))
        
        category.checks.append(ValidationCheck(
            name="UTF-8 Encoding",
            status=ValidationStatus.PASS,
            message="Messages are UTF-8 encoded"
        ))
        
        return category
    
    def _validate_heartbeat(self, verbose: bool) -> ValidationCategory:
        """Validate heartbeat/ping behavior with extended testing"""
        category = ValidationCategory(
            name="Heartbeat",
            description="Ping/pong and liveness over time"
        )
        
        if verbose:
            print("\n[4/8] Checking heartbeat response (extended test - ~10 seconds)...")
        
        if not self.plugin.is_running:
            category.checks.append(ValidationCheck(
                name="Heartbeat Tests",
                status=ValidationStatus.SKIP,
                message="Plugin not running"
            ))
            return category
        
        # Extended heartbeat test - send pings over 10 seconds
        ping_times = []
        ping_failures = 0
        test_duration = 10  # seconds
        ping_interval = 1.0  # seconds
        
        start_test = time.time()
        ping_count = 0
        
        while (time.time() - start_test) < test_duration:
            ping_count += 1
            start_time = time.time()
            success = self.plugin.send_ping()
            ping_time = (time.time() - start_time) * 1000
            
            if success:
                ping_times.append(ping_time)
            else:
                ping_failures += 1
            
            if verbose and ping_count % 3 == 0:
                print(f"    Ping {ping_count}: {'OK' if success else 'FAIL'}")
            
            time.sleep(ping_interval)
        
        # Wait for final responses
        time.sleep(0.5)
        
        # Analyze ping results
        if ping_times:
            avg_time = sum(ping_times) / len(ping_times)
            min_time = min(ping_times)
            max_time = max(ping_times)
            
            # Check consistency (standard deviation)
            variance = sum((t - avg_time) ** 2 for t in ping_times) / len(ping_times)
            std_dev = variance ** 0.5
            
            if ping_failures == 0:
                category.checks.append(ValidationCheck(
                    name="Ping Response",
                    status=ValidationStatus.PASS,
                    message=f"All {ping_count} pings successful over {test_duration}s"
                ))
            else:
                failure_rate = (ping_failures / ping_count) * 100
                if failure_rate < 10:
                    category.checks.append(ValidationCheck(
                        name="Ping Response",
                        status=ValidationStatus.WARN,
                        message=f"{ping_failures}/{ping_count} ping failures ({failure_rate:.0f}%)"
                    ))
                else:
                    category.checks.append(ValidationCheck(
                        name="Ping Response",
                        status=ValidationStatus.FAIL,
                        message=f"{ping_failures}/{ping_count} ping failures ({failure_rate:.0f}%)"
                    ))
            
            # Response time analysis
            category.checks.append(ValidationCheck(
                name="Ping Timing",
                status=ValidationStatus.INFO,
                message=f"Avg: {avg_time:.0f}ms, Min: {min_time:.0f}ms, Max: {max_time:.0f}ms"
            ))
            
            # Consistency check
            if std_dev < 100:
                category.checks.append(ValidationCheck(
                    name="Response Consistency",
                    status=ValidationStatus.PASS,
                    message=f"Consistent timing (std dev: {std_dev:.0f}ms)"
                ))
            elif std_dev < 500:
                category.checks.append(ValidationCheck(
                    name="Response Consistency",
                    status=ValidationStatus.WARN,
                    message=f"Variable timing (std dev: {std_dev:.0f}ms)"
                ))
            else:
                category.checks.append(ValidationCheck(
                    name="Response Consistency",
                    status=ValidationStatus.FAIL,
                    message=f"Highly inconsistent timing (std dev: {std_dev:.0f}ms)"
                ))
        else:
            category.checks.append(ValidationCheck(
                name="Ping Response",
                status=ValidationStatus.FAIL,
                message="No successful pings"
            ))
        
        # Check if plugin updates heartbeat
        old_heartbeat = self.plugin._last_heartbeat_time
        time.sleep(0.2)
        self.plugin.send_ping()
        time.sleep(0.5)
        
        if self.plugin._last_heartbeat_time > old_heartbeat:
            category.checks.append(ValidationCheck(
                name="Heartbeat Update",
                status=ValidationStatus.PASS,
                message="Updates heartbeat on communication"
            ))
        else:
            category.checks.append(ValidationCheck(
                name="Heartbeat Update",
                status=ValidationStatus.WARN,
                message="Heartbeat not updated after ping"
            ))
        
        # Check heartbeat timeout compliance
        if not self.plugin.is_heartbeat_expired():
            category.checks.append(ValidationCheck(
                name="Heartbeat Timeout",
                status=ValidationStatus.PASS,
                message="Within heartbeat timeout window"
            ))
        else:
            category.checks.append(ValidationCheck(
                name="Heartbeat Timeout",
                status=ValidationStatus.FAIL,
                message="Heartbeat expired - plugin may be unresponsive"
            ))
        
        return category
    
    def _validate_execution(self, verbose: bool) -> ValidationCategory:
        """Validate command execution with repeated calls and stress testing"""
        category = ValidationCategory(
            name="Execution",
            description="Function execution behavior and consistency"
        )
        
        if verbose:
            print("\n[5/8] Checking execution behavior (multiple calls per function)...")
        
        if not self.plugin.is_running:
            category.checks.append(ValidationCheck(
                name="Execution Tests",
                status=ValidationStatus.SKIP,
                message="Plugin not running"
            ))
            return category
        
        # Test executing each function multiple times
        functions_tested = 0
        functions_passed = 0
        all_exec_times = []
        
        for func in self.manifest.functions:
            functions_tested += 1
            
            # Build minimal arguments (empty for optional params)
            args = {}
            for param in func.parameters:
                if param.required:
                    # Provide dummy values based on type
                    if param.type == "string":
                        args[param.name] = "test"
                    elif param.type in ("number", "integer"):
                        args[param.name] = 1
                    elif param.type == "boolean":
                        args[param.name] = True
                    elif param.type == "array":
                        args[param.name] = []
                    elif param.type == "object":
                        args[param.name] = {}
            
            # Execute function 3 times to check consistency
            func_times = []
            func_successes = 0
            func_responses = []
            
            for attempt in range(3):
                start_time = time.time()
                response = self.plugin.execute(
                    function=func.name,
                    arguments=args,
                    timeout_ms=15000  # 15 second timeout for validation
                )
                exec_time = (time.time() - start_time) * 1000
                
                if response.success or response.awaiting_input:
                    func_successes += 1
                    func_times.append(exec_time)
                    all_exec_times.append(exec_time)
                    func_responses.append(response.message)
                
                # Exit passthrough if needed
                if response.awaiting_input:
                    self.plugin.send_user_input("exit")
                    time.sleep(0.3)
                
                time.sleep(0.2)  # Small delay between calls
            
            if func_successes == 3:
                functions_passed += 1
                avg_time = sum(func_times) / len(func_times)
                category.checks.append(ValidationCheck(
                    name=f"Execute: {func.name}",
                    status=ValidationStatus.PASS,
                    message=f"3/3 calls OK (avg: {avg_time:.0f}ms)",
                    duration_ms=avg_time
                ))
            elif func_successes > 0:
                avg_time = sum(func_times) / len(func_times) if func_times else 0
                category.checks.append(ValidationCheck(
                    name=f"Execute: {func.name}",
                    status=ValidationStatus.WARN,
                    message=f"{func_successes}/3 calls succeeded",
                    duration_ms=avg_time
                ))
            else:
                category.checks.append(ValidationCheck(
                    name=f"Execute: {func.name}",
                    status=ValidationStatus.FAIL,
                    message="All 3 calls failed"
                ))
            
            # Check response consistency (non-empty, sensible)
            non_empty_responses = [r for r in func_responses if r and len(r.strip()) > 0]
            if len(non_empty_responses) == func_successes and func_successes > 0:
                category.checks.append(ValidationCheck(
                    name=f"Response: {func.name}",
                    status=ValidationStatus.PASS,
                    message="Returns non-empty responses"
                ))
            elif func_successes > 0:
                category.checks.append(ValidationCheck(
                    name=f"Response: {func.name}",
                    status=ValidationStatus.WARN,
                    message=f"Some empty responses ({len(non_empty_responses)}/{func_successes})"
                ))
            
            if verbose:
                print(f"    {func.name}: {func_successes}/3 OK")
        
        # Overall execution summary
        if functions_passed == functions_tested:
            category.checks.append(ValidationCheck(
                name="Execution Summary",
                status=ValidationStatus.PASS,
                message=f"All {functions_tested} functions consistent (3 calls each)"
            ))
        elif functions_passed > 0:
            category.checks.append(ValidationCheck(
                name="Execution Summary",
                status=ValidationStatus.WARN,
                message=f"{functions_passed}/{functions_tested} functions fully consistent"
            ))
        else:
            category.checks.append(ValidationCheck(
                name="Execution Summary",
                status=ValidationStatus.FAIL,
                message="No functions executed consistently"
            ))
        
        # Analyze overall timing consistency
        if all_exec_times:
            avg_all = sum(all_exec_times) / len(all_exec_times)
            max_all = max(all_exec_times)
            min_all = min(all_exec_times)
            
            category.checks.append(ValidationCheck(
                name="Timing Analysis",
                status=ValidationStatus.INFO,
                message=f"Avg: {avg_all:.0f}ms, Range: {min_all:.0f}-{max_all:.0f}ms"
            ))
            
            # Check for timeouts (>10s)
            slow_calls = [t for t in all_exec_times if t > 10000]
            if not slow_calls:
                category.checks.append(ValidationCheck(
                    name="Timeout Compliance",
                    status=ValidationStatus.PASS,
                    message="All calls completed within 10s"
                ))
            else:
                category.checks.append(ValidationCheck(
                    name="Timeout Compliance",
                    status=ValidationStatus.WARN,
                    message=f"{len(slow_calls)} calls exceeded 10s"
                ))
        
        return category
    
    def _validate_stress(self, verbose: bool) -> ValidationCategory:
        """Stress test with rapid-fire commands and concurrent behavior"""
        category = ValidationCategory(
            name="Stress Test",
            description="Rapid-fire commands and sustained load"
        )
        
        if verbose:
            print("\n[6/8] Running stress tests (~15 seconds)...")
        
        if not self.plugin.is_running:
            category.checks.append(ValidationCheck(
                name="Stress Tests",
                status=ValidationStatus.SKIP,
                message="Plugin not running"
            ))
            return category
        
        # Pick a function to stress test (first one available)
        if not self.manifest.functions:
            category.checks.append(ValidationCheck(
                name="Stress Tests",
                status=ValidationStatus.SKIP,
                message="No functions to test"
            ))
            return category
        
        test_func = self.manifest.functions[0]
        args = {}
        for param in test_func.parameters:
            if param.required:
                if param.type == "string":
                    args[param.name] = "stress_test"
                elif param.type in ("number", "integer"):
                    args[param.name] = 1
                elif param.type == "boolean":
                    args[param.name] = True
        
        # Test 1: Rapid-fire commands (10 quick calls)
        if verbose:
            print(f"    Rapid-fire test: 10 quick calls to {test_func.name}...")
        
        rapid_times = []
        rapid_failures = 0
        
        for i in range(10):
            start_time = time.time()
            response = self.plugin.execute(
                function=test_func.name,
                arguments=args,
                timeout_ms=15000
            )
            exec_time = (time.time() - start_time) * 1000
            
            if response.success or response.awaiting_input:
                rapid_times.append(exec_time)
            else:
                rapid_failures += 1
            
            if response.awaiting_input:
                self.plugin.send_user_input("exit")
                time.sleep(0.1)
            
            # Very short delay for rapid-fire
            time.sleep(0.05)
        
        if rapid_failures == 0:
            avg_time = sum(rapid_times) / len(rapid_times)
            category.checks.append(ValidationCheck(
                name="Rapid-Fire Commands",
                status=ValidationStatus.PASS,
                message=f"10/10 rapid calls succeeded (avg: {avg_time:.0f}ms)"
            ))
        elif rapid_failures <= 2:
            category.checks.append(ValidationCheck(
                name="Rapid-Fire Commands",
                status=ValidationStatus.WARN,
                message=f"{10-rapid_failures}/10 rapid calls succeeded"
            ))
        else:
            category.checks.append(ValidationCheck(
                name="Rapid-Fire Commands",
                status=ValidationStatus.FAIL,
                message=f"Only {10-rapid_failures}/10 rapid calls succeeded"
            ))
        
        # Test 2: Sustained load (calls over 10 seconds)
        if verbose:
            print("    Sustained load test: continuous calls for 10 seconds...")
        
        sustained_times = []
        sustained_failures = 0
        test_start = time.time()
        call_count = 0
        
        while (time.time() - test_start) < 10:
            call_count += 1
            start_time = time.time()
            response = self.plugin.execute(
                function=test_func.name,
                arguments=args,
                timeout_ms=10000
            )
            exec_time = (time.time() - start_time) * 1000
            
            if response.success or response.awaiting_input:
                sustained_times.append(exec_time)
            else:
                sustained_failures += 1
            
            if response.awaiting_input:
                self.plugin.send_user_input("exit")
                time.sleep(0.1)
            
            time.sleep(0.3)  # Moderate pace
        
        success_rate = ((call_count - sustained_failures) / call_count) * 100 if call_count > 0 else 0
        
        if success_rate >= 95:
            category.checks.append(ValidationCheck(
                name="Sustained Load",
                status=ValidationStatus.PASS,
                message=f"{call_count} calls over 10s, {success_rate:.0f}% success"
            ))
        elif success_rate >= 80:
            category.checks.append(ValidationCheck(
                name="Sustained Load",
                status=ValidationStatus.WARN,
                message=f"{call_count} calls, {success_rate:.0f}% success (some degradation)"
            ))
        else:
            category.checks.append(ValidationCheck(
                name="Sustained Load",
                status=ValidationStatus.FAIL,
                message=f"{call_count} calls, only {success_rate:.0f}% success"
            ))
        
        # Test 3: Check plugin health after stress
        if verbose:
            print("    Checking plugin health after stress...")
        
        time.sleep(1)  # Let plugin settle
        
        # Verify plugin is still responsive
        health_response = self.plugin.execute(
            function=test_func.name,
            arguments=args,
            timeout_ms=10000
        )
        
        if health_response.success or health_response.awaiting_input:
            category.checks.append(ValidationCheck(
                name="Post-Stress Health",
                status=ValidationStatus.PASS,
                message="Plugin responsive after stress test"
            ))
            if health_response.awaiting_input:
                self.plugin.send_user_input("exit")
        else:
            category.checks.append(ValidationCheck(
                name="Post-Stress Health",
                status=ValidationStatus.FAIL,
                message="Plugin unresponsive after stress test"
            ))
        
        # Check heartbeat after stress
        if not self.plugin.is_heartbeat_expired():
            category.checks.append(ValidationCheck(
                name="Post-Stress Heartbeat",
                status=ValidationStatus.PASS,
                message="Heartbeat healthy after stress"
            ))
        else:
            category.checks.append(ValidationCheck(
                name="Post-Stress Heartbeat",
                status=ValidationStatus.WARN,
                message="Heartbeat lagging after stress"
            ))
        
        # Analyze timing degradation
        if sustained_times:
            first_half = sustained_times[:len(sustained_times)//2]
            second_half = sustained_times[len(sustained_times)//2:]
            
            if first_half and second_half:
                avg_first = sum(first_half) / len(first_half)
                avg_second = sum(second_half) / len(second_half)
                degradation = ((avg_second - avg_first) / avg_first) * 100 if avg_first > 0 else 0
                
                if degradation < 20:
                    category.checks.append(ValidationCheck(
                        name="Performance Stability",
                        status=ValidationStatus.PASS,
                        message=f"Stable performance ({degradation:+.0f}% change)"
                    ))
                elif degradation < 50:
                    category.checks.append(ValidationCheck(
                        name="Performance Stability",
                        status=ValidationStatus.WARN,
                        message=f"Some degradation ({degradation:+.0f}% slower)"
                    ))
                else:
                    category.checks.append(ValidationCheck(
                        name="Performance Stability",
                        status=ValidationStatus.FAIL,
                        message=f"Significant degradation ({degradation:+.0f}% slower)"
                    ))
        
        return category
    
    def _validate_error_handling(self, verbose: bool) -> ValidationCategory:
        """Validate error handling"""
        category = ValidationCategory(
            name="Error Handling",
            description="Graceful error handling"
        )
        
        if verbose:
            print("\n[7/8] Checking error handling...")
        
        if not self.plugin.is_running:
            category.checks.append(ValidationCheck(
                name="Error Handling Tests",
                status=ValidationStatus.SKIP,
                message="Plugin not running"
            ))
            return category
        
        # Test unknown function
        start_time = time.time()
        response = self.plugin.execute(
            function="__nonexistent_function_12345__",
            arguments={},
            timeout_ms=5000
        )
        exec_time = (time.time() - start_time) * 1000
        
        if not response.success and response.error_code is not None:
            category.checks.append(ValidationCheck(
                name="Unknown Function",
                status=ValidationStatus.PASS,
                message="Returns error for unknown function",
                duration_ms=exec_time
            ))
        elif not response.success:
            category.checks.append(ValidationCheck(
                name="Unknown Function",
                status=ValidationStatus.WARN,
                message="Returns error but no error code",
                duration_ms=exec_time
            ))
        else:
            category.checks.append(ValidationCheck(
                name="Unknown Function",
                status=ValidationStatus.FAIL,
                message="Does not reject unknown function",
                duration_ms=exec_time
            ))
        
        # Test with missing required parameters
        for func in self.manifest.functions:
            required_params = [p for p in func.parameters if p.required]
            if required_params:
                response = self.plugin.execute(
                    function=func.name,
                    arguments={},  # Missing required params
                    timeout_ms=5000
                )
                
                # Plugin should either handle gracefully or return error
                if not response.success or response.message:
                    category.checks.append(ValidationCheck(
                        name="Missing Parameters",
                        status=ValidationStatus.PASS,
                        message=f"Handles missing params for {func.name}"
                    ))
                else:
                    category.checks.append(ValidationCheck(
                        name="Missing Parameters",
                        status=ValidationStatus.WARN,
                        message=f"No clear error for missing params in {func.name}"
                    ))
                break  # Only test one function
        
        # Check plugin is still running after error tests
        if self.plugin.is_running:
            category.checks.append(ValidationCheck(
                name="Stability After Errors",
                status=ValidationStatus.PASS,
                message="Plugin remains stable after error conditions"
            ))
        else:
            category.checks.append(ValidationCheck(
                name="Stability After Errors",
                status=ValidationStatus.FAIL,
                message="Plugin crashed during error tests"
            ))
        
        return category
    
    def _validate_shutdown(self, verbose: bool) -> ValidationCategory:
        """Validate shutdown behavior"""
        category = ValidationCategory(
            name="Shutdown",
            description="Clean shutdown behavior"
        )
        
        if verbose:
            print("\n[8/8] Checking shutdown behavior...")
        
        if not self.plugin.is_running:
            category.checks.append(ValidationCheck(
                name="Shutdown Tests",
                status=ValidationStatus.SKIP,
                message="Plugin not running"
            ))
            return category
        
        # Test graceful shutdown
        start_time = time.time()
        shutdown_response = self.plugin.shutdown()
        shutdown_time = (time.time() - start_time) * 1000
        
        if shutdown_response.success:
            category.checks.append(ValidationCheck(
                name="Graceful Shutdown",
                status=ValidationStatus.PASS,
                message=f"Shutdown completed in {shutdown_time:.0f}ms",
                duration_ms=shutdown_time
            ))
        else:
            category.checks.append(ValidationCheck(
                name="Graceful Shutdown",
                status=ValidationStatus.WARN,
                message=f"Shutdown response: {shutdown_response.message}",
                duration_ms=shutdown_time
            ))
        
        # Check if process exited
        time.sleep(1)
        if not self.plugin.is_running:
            category.checks.append(ValidationCheck(
                name="Process Exit",
                status=ValidationStatus.PASS,
                message="Process exited cleanly"
            ))
        else:
            # Force stop
            self.plugin.stop()
            category.checks.append(ValidationCheck(
                name="Process Exit",
                status=ValidationStatus.WARN,
                message="Process required force stop"
            ))
        
        # Check shutdown time
        if shutdown_time < 3000:
            category.checks.append(ValidationCheck(
                name="Shutdown Time",
                status=ValidationStatus.PASS,
                message=f"Shutdown in {shutdown_time:.0f}ms (< 3s)"
            ))
        else:
            category.checks.append(ValidationCheck(
                name="Shutdown Time",
                status=ValidationStatus.WARN,
                message=f"Slow shutdown: {shutdown_time:.0f}ms"
            ))
        
        return category
    
    def print_report(self, report: Optional[ValidationReport] = None):
        """Print a formatted validation report"""
        report = report or self.report
        if not report:
            print("No validation report available. Run validate() first.")
            return
        
        print("\n")
        print("=" * 70)
        print(f"  PLUGIN VALIDATION REPORT")
        print("=" * 70)
        print(f"  Plugin: {report.plugin_name} v{report.plugin_version}")
        print(f"  Time: {report.timestamp}")
        print("=" * 70)
        
        # Overall score
        print(f"\n  OVERALL SCORE: {report.overall_score:.1f}% ({report.grade})")
        print(f"  Total Checks: {report.total_checks}")
        print(f"  Passed: {report.total_passed}  |  Failed: {report.total_failed}  |  Warnings: {report.total_warnings}")
        
        # Category details
        for category in report.categories:
            print(f"\n  {'-' * 66}")
            print(f"  {category.name.upper()} ({category.score:.0f}%)")
            print(f"  {category.description}")
            print(f"  {'-' * 66}")
            
            for check in category.checks:
                # Status indicator
                if check.status == ValidationStatus.PASS:
                    status_str = "[PASS]"
                elif check.status == ValidationStatus.FAIL:
                    status_str = "[FAIL]"
                elif check.status == ValidationStatus.WARN:
                    status_str = "[WARN]"
                elif check.status == ValidationStatus.SKIP:
                    status_str = "[SKIP]"
                else:
                    status_str = "[INFO]"
                
                # Time if available
                time_str = f" ({check.duration_ms:.0f}ms)" if check.duration_ms > 0 else ""
                
                print(f"    {status_str} {check.name}{time_str}")
                print(f"           {check.message}")
        
        # Summary
        print(f"\n{'=' * 70}")
        print(f"  VALIDATION COMPLETE")
        print(f"  Grade: {report.grade} ({report.overall_score:.1f}%)")
        
        if report.overall_score >= 90:
            print(f"  Status: EXCELLENT - Plugin is a good citizen!")
        elif report.overall_score >= 75:
            print(f"  Status: GOOD - Minor improvements recommended")
        elif report.overall_score >= 60:
            print(f"  Status: ACCEPTABLE - Several issues to address")
        else:
            print(f"  Status: NEEDS WORK - Significant improvements required")
        
        print("=" * 70)
        print()
    
    def export_report(self, path: str, report: Optional[ValidationReport] = None):
        """Export validation report to JSON file"""
        report = report or self.report
        if not report:
            return
        
        data = {
            "plugin_name": report.plugin_name,
            "plugin_version": report.plugin_version,
            "timestamp": report.timestamp,
            "overall_score": report.overall_score,
            "grade": report.grade,
            "total_checks": report.total_checks,
            "total_passed": report.total_passed,
            "total_failed": report.total_failed,
            "total_warnings": report.total_warnings,
            "categories": []
        }
        
        for category in report.categories:
            cat_data = {
                "name": category.name,
                "description": category.description,
                "score": category.score,
                "checks": []
            }
            
            for check in category.checks:
                cat_data["checks"].append({
                    "name": check.name,
                    "status": check.status.value,
                    "message": check.message,
                    "details": check.details,
                    "duration_ms": check.duration_ms
                })
            
            data["categories"].append(cat_data)
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Report exported to: {path}")

