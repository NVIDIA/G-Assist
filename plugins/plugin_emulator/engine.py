"""
Plugin Emulator Engine

Main orchestrator for plugin testing and validation.
Supports both user-driven (interactive) and autonomous (LLM judge) modes.
"""

import os
import sys
import json
import time
import logging
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from colorama import Fore, Style

from .manager import PluginManager, PluginInfo
from .plugin import Plugin, PluginState, PluginResponse
from .watcher import PluginWatcher, PluginChange


logger = logging.getLogger(__name__)


class EngineMode(Enum):
    """Engine operation modes"""
    INTERACTIVE = auto()      # User-driven, manual interaction
    ONE_SHOT = auto()         # Execute single command and exit
    PASSTHROUGH = auto()      # Direct plugin passthrough mode
    AUTONOMOUS = auto()       # LLM judge-driven autonomous testing
    BATCH = auto()            # Batch execution of multiple commands


@dataclass
class ExecutionResult:
    """Result of a plugin execution"""
    success: bool
    plugin_name: str
    function_name: str
    arguments: Dict[str, Any]
    response: str
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    awaiting_input: bool = False


@dataclass
class AutonomousTestResult:
    """Result of autonomous testing"""
    plugin_name: str
    function_name: str
    test_prompt: str
    expected_behavior: str
    actual_response: str
    passed: bool
    reasoning: str
    confidence: float
    turns_used: int
    execution_time_ms: float


@dataclass
class EngineConfig:
    """Engine configuration"""
    plugins_dir: str
    mode: EngineMode = EngineMode.INTERACTIVE
    verbose: bool = False
    timeout_ms: int = 30000
    # Watcher settings
    watch_plugins: bool = True  # Auto-detect plugin changes
    watch_interval: float = 2.0  # Seconds between scans
    # LLM judge settings (for autonomous mode)
    llm_api_key: Optional[str] = None
    llm_model: str = "nvdev/meta/llama-3.1-70b-instruct"
    llm_temperature: float = 0.1
    max_turns: int = 3


class PluginEngine:
    """
    Plugin Emulator Engine
    
    Acts as an engine emulator for plugin development, supporting:
    - Interactive mode: Manual command execution
    - One-shot mode: Single command execution
    - Passthrough mode: Direct plugin communication
    - Autonomous mode: LLM judge-driven validation
    - Batch mode: Multiple command execution
    
    This emulates the G-Assist engine's plugin communication capabilities
    while providing additional testing and validation features.
    """
    
    def __init__(
        self,
        config: Optional[EngineConfig] = None,
        plugins_dir: Optional[str] = None,
    ):
        """
        Initialize the plugin emulator engine.
        
        Args:
            config: Engine configuration
            plugins_dir: Plugins directory (alternative to config)
        """
        if config:
            self.config = config
        elif plugins_dir:
            self.config = EngineConfig(plugins_dir=plugins_dir)
        else:
            raise ValueError("Either config or plugins_dir must be provided")
        
        # Setup logging - WARNING by default, DEBUG if verbose
        log_level = logging.DEBUG if self.config.verbose else logging.WARNING
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Initialize plugin manager
        self.manager = PluginManager(
            plugins_dir=self.config.plugins_dir,
            on_stream=self._on_stream,
            on_complete=self._on_complete,
        )
        
        # Streaming output callback
        self._stream_callback: Optional[Callable[[str, str], None]] = None
        
        # Current passthrough plugin
        self._passthrough_plugin: Optional[str] = None
        
        # LLM judge (loaded on demand for autonomous mode)
        self._llm_judge = None
        
        # Execution history
        self._history: List[ExecutionResult] = []
        
        # Plugin watcher
        self._watcher: Optional[PluginWatcher] = None
        self._pending_plugin_changes: List[PluginChange] = []
    
    def initialize(self) -> bool:
        """
        Initialize the engine and load plugins.
        
        Returns:
            True if initialization succeeded
        """
        logger.info(f"Initializing PluginEngine (mode: {self.config.mode.name})")
        success = self.manager.initialize()
        
        if success:
            # Start plugin watcher if enabled
            if self.config.watch_plugins:
                self._start_watcher()
        
        return success
    
    def _start_watcher(self):
        """Start the plugin directory watcher"""
        if self._watcher:
            self._watcher.stop()
        
        self._watcher = PluginWatcher(
            plugins_dir=self.config.plugins_dir,
            on_change=self._on_plugins_changed,
            poll_interval=self.config.watch_interval
        )
        self._watcher.start()
        logger.info("Plugin watcher started")
    
    def _on_plugins_changed(self, changes: List[PluginChange]):
        """Handle plugin directory changes"""
        if not changes:
            return
        
        # Store pending changes for display in interactive mode
        self._pending_plugin_changes.extend(changes)
        
        # Log changes
        for change in changes:
            if change.change_type == "added":
                logger.info(f"[Watcher] New plugin detected: {change.plugin_name}")
            elif change.change_type == "removed":
                logger.info(f"[Watcher] Plugin removed: {change.plugin_name}")
            elif change.change_type == "manifest_updated":
                logger.info(f"[Watcher] Plugin manifest updated: {change.plugin_name}")
            elif change.change_type == "modified":
                logger.info(f"[Watcher] Plugin executable updated: {change.plugin_name}")
    
    def shutdown(self):
        """Shutdown the engine and all plugins"""
        logger.info("Shutting down PluginEngine")
        
        # Stop watcher first
        if self._watcher:
            self._watcher.stop()
            self._watcher = None
        
        self.manager.shutdown()
    
    def _on_stream(self, plugin_name: str, data: str):
        """Handle streaming data from plugins"""
        if self._stream_callback:
            self._stream_callback(plugin_name, data)
        else:
            # Default: print to stdout
            print(data, end='', flush=True)
    
    def _on_complete(self, plugin_name: str, success: bool, data: str):
        """Handle completion from plugins"""
        pass  # Handled by execute() return value
    
    def set_stream_callback(self, callback: Callable[[str, str], None]):
        """Set callback for streaming output"""
        self._stream_callback = callback
    
    # ========================================================================
    # Plugin Information API
    # ========================================================================
    
    def list_plugins(self) -> List[PluginInfo]:
        """Get list of all loaded plugins"""
        return self.manager.get_plugins_info()
    
    def list_functions(self, plugin_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get list of available functions.
        
        Args:
            plugin_name: Optional filter by plugin
            
        Returns:
            List of function definitions
        """
        return self.manager.get_icl_definitions(plugin_name)
    
    def get_tool_catalog(self) -> List[Dict[str, Any]]:
        """Get tool catalog for LLM inference"""
        return self.manager.build_tool_catalog()
    
    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get a specific plugin"""
        return self.manager.get_plugin(name)
    
    # ========================================================================
    # Execution API
    # ========================================================================
    
    def execute(
        self,
        function_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        context: Optional[List[Dict[str, str]]] = None,
    ) -> ExecutionResult:
        """
        Execute a plugin function.
        
        Args:
            function_name: Name of the function to execute
            arguments: Function arguments (default: empty dict)
            context: Optional conversation context
            
        Returns:
            ExecutionResult with response
        """
        arguments = arguments or {}
        
        start_time = time.time()
        
        response = self.manager.execute(
            function_name=function_name,
            arguments=arguments,
            context=context,
            timeout_ms=self.config.timeout_ms
        )
        
        execution_time = (time.time() - start_time) * 1000
        
        plugin_name = self.manager.get_plugin_for_function(function_name) or "unknown"
        
        result = ExecutionResult(
            success=response.success,
            plugin_name=plugin_name,
            function_name=function_name,
            arguments=arguments,
            response=response.message,
            error=None if response.success else response.message,
            execution_time_ms=execution_time,
            awaiting_input=response.awaiting_input
        )
        
        # Track in history
        self._history.append(result)
        
        # Handle passthrough mode
        if response.awaiting_input:
            self._passthrough_plugin = plugin_name
        else:
            self._passthrough_plugin = None
        
        return result
    
    def execute_passthrough(
        self,
        plugin_name: str,
        function_name: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        Execute a function in passthrough mode.
        
        The plugin will stay in passthrough mode, accepting user input
        until the session ends.
        
        Args:
            plugin_name: Plugin name
            function_name: Function to execute
            arguments: Function arguments
            
        Returns:
            ExecutionResult with initial response
        """
        plugin = self.manager.get_plugin(plugin_name)
        if not plugin:
            return ExecutionResult(
                success=False,
                plugin_name=plugin_name,
                function_name=function_name,
                arguments=arguments or {},
                response="",
                error=f"Plugin not found: {plugin_name}"
            )
        
        result = self.execute(function_name, arguments)
        
        if result.awaiting_input:
            self._passthrough_plugin = plugin_name
            logger.info(f"Entered passthrough mode with plugin '{plugin_name}'")
        
        return result
    
    def send_input(self, content: str) -> ExecutionResult:
        """
        Send user input to the current passthrough plugin.
        
        Args:
            content: User input text
            
        Returns:
            ExecutionResult with response
        """
        if not self._passthrough_plugin:
            return ExecutionResult(
                success=False,
                plugin_name="",
                function_name="input",
                arguments={"content": content},
                response="",
                error="No plugin in passthrough mode"
            )
        
        plugin = self.manager.get_plugin(self._passthrough_plugin)
        if not plugin:
            return ExecutionResult(
                success=False,
                plugin_name=self._passthrough_plugin,
                function_name="input",
                arguments={"content": content},
                response="",
                error=f"Plugin not found: {self._passthrough_plugin}"
            )
        
        start_time = time.time()
        response = plugin.send_user_input(content)
        execution_time = (time.time() - start_time) * 1000
        
        result = ExecutionResult(
            success=response.success,
            plugin_name=self._passthrough_plugin,
            function_name="input",
            arguments={"content": content},
            response=response.message,
            error=None if response.success else response.message,
            execution_time_ms=execution_time,
            awaiting_input=response.awaiting_input
        )
        
        self._history.append(result)
        
        if not response.awaiting_input:
            self._passthrough_plugin = None
            logger.info("Exited passthrough mode")
        
        return result
    
    def exit_passthrough(self) -> bool:
        """
        Exit passthrough mode.
        
        Returns:
            True if exited successfully
        """
        if not self._passthrough_plugin:
            return True
        
        # Send exit command
        result = self.send_input("exit")
        
        if not result.awaiting_input:
            self._passthrough_plugin = None
            return True
        
        # Force exit
        plugin = self.manager.get_plugin(self._passthrough_plugin)
        if plugin:
            plugin.stop()
        
        self._passthrough_plugin = None
        return True
    
    @property
    def is_in_passthrough(self) -> bool:
        """Check if engine is in passthrough mode"""
        return self._passthrough_plugin is not None
    
    @property
    def passthrough_plugin(self) -> Optional[str]:
        """Get the current passthrough plugin name"""
        return self._passthrough_plugin
    
    # ========================================================================
    # Batch Execution API
    # ========================================================================
    
    def execute_batch(
        self,
        commands: List[Dict[str, Any]]
    ) -> List[ExecutionResult]:
        """
        Execute multiple commands in sequence.
        
        Args:
            commands: List of command dicts with 'function' and 'arguments'
            
        Returns:
            List of ExecutionResults
        """
        results = []
        
        for cmd in commands:
            function_name = cmd.get('function', cmd.get('name', ''))
            arguments = cmd.get('arguments', cmd.get('params', {}))
            
            if not function_name:
                results.append(ExecutionResult(
                    success=False,
                    plugin_name="",
                    function_name="",
                    arguments=arguments,
                    response="",
                    error="Missing function name"
                ))
                continue
            
            result = self.execute(function_name, arguments)
            results.append(result)
            
            # Stop on error if desired
            if not result.success:
                logger.warning(f"Batch execution stopped at {function_name}: {result.error}")
                break
        
        return results
    
    # ========================================================================
    # Autonomous Testing API (LLM Judge Integration)
    # ========================================================================
    
    def _get_llm_judge(self):
        """Get or create LLM judge instance"""
        if self._llm_judge is None:
            # Import here to avoid circular dependencies
            try:
                # Try to import from parent directory
                sys.path.insert(0, str(Path(__file__).parent.parent))
                from llm_judge import LLMJudge
                
                api_key = self.config.llm_api_key or os.environ.get('LLM_API_KEY')
                if not api_key:
                    raise ValueError("LLM_API_KEY required for autonomous mode")
                
                self._llm_judge = LLMJudge(
                    api_key=api_key,
                    model=self.config.llm_model,
                    temperature=self.config.llm_temperature
                )
            except ImportError:
                raise ImportError(
                    "LLMJudge not available. Make sure llm_judge.py is in the parent directory."
                )
        
        return self._llm_judge
    
    def test_function_autonomous(
        self,
        function_name: str,
        test_prompt: str,
        expected_behavior: str,
        arguments: Optional[Dict[str, Any]] = None,
        max_turns: Optional[int] = None,
    ) -> AutonomousTestResult:
        """
        Test a plugin function using LLM judge.
        
        The LLM judge will:
        1. Execute the function with given arguments
        2. Evaluate the response against expected behavior
        3. Issue follow-up queries if needed
        4. Return pass/fail with reasoning
        
        Args:
            function_name: Function to test
            test_prompt: User prompt that would trigger this function
            expected_behavior: Description of expected behavior
            arguments: Function arguments
            max_turns: Maximum turns for follow-up (default: config value)
            
        Returns:
            AutonomousTestResult with detailed results
        """
        judge = self._get_llm_judge()
        max_turns = max_turns or self.config.max_turns
        
        start_time = time.time()
        turns_used = 0
        conversation_history = []
        
        # Execute initial function call
        result = self.execute(function_name, arguments)
        turns_used += 1
        
        current_response = result.response
        conversation_history.append({
            'user': test_prompt,
            'assistant': current_response
        })
        
        # Get initial judgment
        from llm_judge import JudgmentResult
        
        judgment = judge.assess_response(
            user_prompt=test_prompt,
            assistant_response=current_response,
            expectation=expected_behavior,
            conversation_history=[],
            remaining_turns=max_turns - turns_used
        )
        
        # Handle follow-up turns
        while judgment.result == JudgmentResult.FOLLOW_UP and turns_used < max_turns:
            follow_up_prompt = judgment.follow_up_prompt or "Can you provide more details?"
            
            # If in passthrough mode, send input
            if self.is_in_passthrough:
                follow_result = self.send_input(follow_up_prompt)
                current_response = follow_result.response
            else:
                # Re-execute the function (might not make sense for all functions)
                break
            
            turns_used += 1
            conversation_history.append({
                'user': follow_up_prompt,
                'assistant': current_response
            })
            
            # Get next judgment
            judgment = judge.assess_response(
                user_prompt=follow_up_prompt,
                assistant_response=current_response,
                expectation=expected_behavior,
                conversation_history=conversation_history[:-1],
                remaining_turns=max_turns - turns_used
            )
        
        execution_time = (time.time() - start_time) * 1000
        
        # Determine pass/fail
        passed = judgment.result in (JudgmentResult.SUCCESS, JudgmentResult.ACCEPTABLE)
        
        return AutonomousTestResult(
            plugin_name=result.plugin_name,
            function_name=function_name,
            test_prompt=test_prompt,
            expected_behavior=expected_behavior,
            actual_response=current_response,
            passed=passed,
            reasoning=judgment.reasoning,
            confidence=judgment.confidence,
            turns_used=turns_used,
            execution_time_ms=execution_time
        )
    
    def test_plugin_autonomous(
        self,
        plugin_name: str,
        test_cases: List[Dict[str, Any]],
    ) -> List[AutonomousTestResult]:
        """
        Run autonomous tests on all functions of a plugin.
        
        Args:
            plugin_name: Plugin to test
            test_cases: List of test case dicts with:
                - function: Function name
                - prompt: Test prompt
                - expectation: Expected behavior
                - arguments: Optional arguments
                
        Returns:
            List of AutonomousTestResults
        """
        results = []
        
        for test in test_cases:
            function_name = test.get('function')
            test_prompt = test.get('prompt', '')
            expected_behavior = test.get('expectation', '')
            arguments = test.get('arguments', {})
            
            if not function_name:
                continue
            
            logger.info(f"Running autonomous test: {plugin_name}.{function_name}")
            
            result = self.test_function_autonomous(
                function_name=function_name,
                test_prompt=test_prompt,
                expected_behavior=expected_behavior,
                arguments=arguments
            )
            
            results.append(result)
            
            status = "PASS" if result.passed else "FAIL"
            logger.info(f"  {status}: {result.reasoning[:80]}...")
        
        return results
    
    # ========================================================================
    # Interactive Mode API
    # ========================================================================
    
    def run_interactive(self):
        """
        Run engine in interactive mode with menu-driven interface.
        
        Provides a user-friendly menu for:
        - Listing plugins and their functions
        - Executing functions with prompted arguments
        - Entering passthrough mode
        """
        self._print_banner()
        self._print_startup_summary()
        
        while True:
            try:
                # Handle passthrough mode separately
                if self.is_in_passthrough:
                    self._handle_passthrough_input()
                    continue
                
                # Show main menu
                choice = self._show_main_menu()
                
                if choice == '1':
                    self._menu_list_plugins()
                elif choice == '2':
                    self._menu_select_plugin()
                elif choice == '3':
                    self._menu_execute_function()
                elif choice == '4':
                    self._menu_validate_plugin()
                elif choice == '5':
                    self._menu_reload_plugins()
                elif choice == '0' or choice.lower() in ('q', 'quit', 'exit'):
                    print("\nShutting down...")
                    break
                else:
                    print("\nInvalid choice. Please try again.")
                    
            except KeyboardInterrupt:
                print("\n")
                if self.is_in_passthrough:
                    self.exit_passthrough()
                    print("Exited passthrough mode.")
                else:
                    print("\nShutting down...")
                    break
            except EOFError:
                # Non-interactive mode, exit gracefully
                print("\nNon-interactive mode detected. Exiting...")
                break
            except Exception as e:
                logger.exception(f"Error: {e}")
                print(f"\nError: {e}")
        
        self.shutdown()
    
    def _print_banner(self):
        """Print startup banner"""
        print("\n" + "=" * 70)
        print("  G-Assist Plugin Emulator")
        print("  Emulates G-Assist engine plugin communication for development & testing")
        print("=" * 70)
    
    def _print_startup_summary(self):
        """Print summary of discovered plugins"""
        plugins = self.list_plugins()
        failed = self.manager.get_failed_plugins()
        mcp_plugins = self.manager.get_mcp_plugins()
        
        print(f"\nDiscovered {len(plugins)} plugin(s)")
        
        if mcp_plugins:
            print(f"MCP-enabled plugins: {', '.join(mcp_plugins)}")
        
        if plugins:
            print("\nLoaded plugins:")
            for i, p in enumerate(plugins, 1):
                status = "RUNNING" if p.state == PluginState.READY else "STOPPED"
                flags = []
                if p.persistent:
                    flags.append("persistent")
                if p.passthrough:
                    flags.append("passthrough")
                if p.name in mcp_plugins:
                    flags.append("MCP")
                flag_str = f" ({', '.join(flags)})" if flags else ""
                print(f"  {i}. {p.name} - {p.function_count} function(s) [{status}]{flag_str}")
        
        if failed:
            print("\nFailed to load:")
            for fp in failed:
                print(f"  - {fp.name}: {fp.reason}")
        
        print()
    
    def _show_main_menu(self) -> str:
        """Show main menu and get user choice"""
        # Check for pending plugin changes from watcher
        if self._pending_plugin_changes:
            self._show_plugin_changes()
        
        print("\n" + "-" * 40)
        print("MAIN MENU")
        print("-" * 40)
        print("  1. List all plugins")
        print("  2. Select a plugin (view functions)")
        print("  3. Execute a function")
        print("  4. Validate a plugin")
        print("  5. Reload plugins")
        print("  0. Exit")
        print("-" * 40)
        
        return input("Enter choice: ").strip()
    
    def _show_plugin_changes(self):
        """Display pending plugin changes detected by watcher"""
        print(f"\n{Fore.YELLOW}{'=' * 50}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}  PLUGIN CHANGES DETECTED{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}{'=' * 50}{Style.RESET_ALL}")
        
        added = []
        removed = []
        updated = []
        
        for change in self._pending_plugin_changes:
            if change.change_type == "added":
                added.append(change.plugin_name)
            elif change.change_type == "removed":
                removed.append(change.plugin_name)
            else:
                updated.append(change.plugin_name)
        
        if added:
            print(f"\n  {Fore.GREEN}+ New plugins:{Style.RESET_ALL}")
            for name in set(added):
                print(f"      {name}")
        
        if removed:
            print(f"\n  {Fore.RED}- Removed plugins:{Style.RESET_ALL}")
            for name in set(removed):
                print(f"      {name}")
        
        if updated:
            print(f"\n  {Fore.CYAN}~ Updated plugins:{Style.RESET_ALL}")
            for name in set(updated):
                print(f"      {name}")
        
        print(f"\n{Fore.YELLOW}  Press 5 to reload or continue with current state{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}{'=' * 50}{Style.RESET_ALL}")
        
        # Clear pending changes after showing
        self._pending_plugin_changes.clear()
    
    def _menu_list_plugins(self):
        """List all plugins with details"""
        plugins = self.list_plugins()
        
        print(f"\n{'=' * 70}")
        print(f"LOADED PLUGINS ({len(plugins)})")
        print("=" * 70)
        
        if not plugins:
            print("No plugins loaded.")
            return
        
        for i, p in enumerate(plugins, 1):
            status = "RUNNING" if p.state == PluginState.READY else "STOPPED"
            print(f"\n[{i}] {p.name}")
            print(f"    Description: {p.description}")
            print(f"    Status: {status}")
            print(f"    Functions: {p.function_count}")
            print(f"    Persistent: {'Yes' if p.persistent else 'No'}")
            print(f"    Passthrough: {'Yes' if p.passthrough else 'No'}")
        
        print()
        input("Press Enter to continue...")
    
    def _menu_select_plugin(self):
        """Select a plugin and view its functions"""
        plugins = self.list_plugins()
        
        if not plugins:
            print("\nNo plugins loaded.")
            return
        
        print(f"\n{'=' * 70}")
        print("SELECT A PLUGIN")
        print("=" * 70)
        
        for i, p in enumerate(plugins, 1):
            print(f"  {i}. {p.name} ({p.function_count} functions)")
        print("  0. Back to main menu")
        
        choice = input("\nEnter plugin number: ").strip()
        
        if choice == '0':
            return
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(plugins):
                self._show_plugin_functions(plugins[idx].name)
            else:
                print("Invalid selection.")
        except ValueError:
            # Try by name
            for p in plugins:
                if p.name.lower() == choice.lower():
                    self._show_plugin_functions(p.name)
                    return
            print("Invalid selection.")
    
    def _show_plugin_functions(self, plugin_name: str):
        """Show functions for a specific plugin"""
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            print(f"Plugin '{plugin_name}' not found.")
            return
        
        functions = self.manager.get_icl_definitions(plugin_name)
        
        print(f"\n{'=' * 70}")
        print(f"PLUGIN: {plugin_name}")
        print(f"Description: {plugin.description}")
        print("=" * 70)
        
        print(f"\nFunctions ({len(functions)}):")
        print("-" * 50)
        
        for i, func in enumerate(functions, 1):
            name = func.get('name', 'unknown')
            desc = func.get('description', 'No description')
            params = func.get('parameters', {}).get('properties', {})
            required = func.get('parameters', {}).get('required', [])
            
            print(f"\n  [{i}] {name}")
            print(f"      {desc}")
            
            if params:
                print("      Parameters:")
                for pname, pdef in params.items():
                    req_mark = "*" if pname in required else " "
                    ptype = pdef.get('type', 'any')
                    pdesc = pdef.get('description', '')
                    enum_vals = pdef.get('enum', [])
                    
                    if enum_vals:
                        print(f"        {req_mark} {pname} ({ptype}): {pdesc}")
                        print(f"          Options: {', '.join(str(v) for v in enum_vals)}")
                    else:
                        print(f"        {req_mark} {pname} ({ptype}): {pdesc}")
        
        print("\n  (* = required parameter)")
        print()
        
        # Offer to execute a function
        exec_choice = input("Enter function number to execute (or 0 to go back): ").strip()
        
        if exec_choice == '0':
            return
        
        try:
            idx = int(exec_choice) - 1
            if 0 <= idx < len(functions):
                self._execute_function_interactive(functions[idx])
        except ValueError:
            pass
    
    def _menu_execute_function(self):
        """Execute a function with prompted arguments"""
        all_functions = self.list_functions()
        
        if not all_functions:
            print("\nNo functions available.")
            return
        
        print(f"\n{'=' * 70}")
        print("EXECUTE FUNCTION")
        print("=" * 70)
        
        for i, func in enumerate(all_functions, 1):
            name = func.get('name', 'unknown')
            plugin = self.manager.get_plugin_for_function(name) or 'unknown'
            print(f"  {i}. {name} [{plugin}]")
        print("  0. Back to main menu")
        
        choice = input("\nEnter function number or name: ").strip()
        
        if choice == '0':
            return
        
        # Find the function
        selected_func = None
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(all_functions):
                selected_func = all_functions[idx]
        except ValueError:
            # Search by name
            for func in all_functions:
                if func.get('name', '').lower() == choice.lower():
                    selected_func = func
                    break
        
        if selected_func:
            self._execute_function_interactive(selected_func)
        else:
            print("Function not found.")
    
    def _execute_function_interactive(self, func_def: Dict[str, Any]):
        """Execute a function with interactive argument prompts"""
        func_name = func_def.get('name', '')
        params = func_def.get('parameters', {}).get('properties', {})
        required = func_def.get('parameters', {}).get('required', [])
        
        print(f"\n{'=' * 70}")
        print(f"EXECUTE: {func_name}")
        print("=" * 70)
        print(f"Description: {func_def.get('description', 'No description')}")
        
        arguments = {}
        
        if params:
            print("\nEnter arguments (press Enter for default/skip optional):")
            print("-" * 50)
            
            for pname, pdef in params.items():
                ptype = pdef.get('type', 'string')
                pdesc = pdef.get('description', '')
                default = pdef.get('default')
                enum_vals = pdef.get('enum', [])
                is_required = pname in required
                
                # Build prompt
                req_str = " (required)" if is_required else " (optional)"
                default_str = f" [default: {default}]" if default is not None else ""
                
                print(f"\n  {pname}{req_str}:")
                print(f"    Type: {ptype}")
                if pdesc:
                    print(f"    Description: {pdesc}")
                if enum_vals:
                    print(f"    Options: {', '.join(str(v) for v in enum_vals)}")
                
                prompt = f"    Enter value{default_str}: "
                value = input(prompt).strip()
                
                if value:
                    # Convert to appropriate type
                    try:
                        if ptype == 'number' or ptype == 'integer':
                            value = float(value) if '.' in value else int(value)
                        elif ptype == 'boolean':
                            value = value.lower() in ('true', 'yes', '1')
                        elif ptype == 'array':
                            value = json.loads(value) if value.startswith('[') else value.split(',')
                        elif ptype == 'object':
                            value = json.loads(value)
                    except (ValueError, json.JSONDecodeError):
                        pass  # Keep as string
                    
                    arguments[pname] = value
                elif default is not None:
                    arguments[pname] = default
                elif is_required:
                    print(f"    Warning: Required parameter '{pname}' was not provided.")
        
        # Confirm execution
        print(f"\n{'=' * 70}")
        print("CONFIRM EXECUTION")
        print("=" * 70)
        print(f"Function: {func_name}")
        print(f"Arguments: {json.dumps(arguments, indent=2)}")
        
        confirm = input("\nExecute? (Y/n): ").strip().lower()
        
        if confirm in ('', 'y', 'yes'):
            print("\nExecuting...")
            print("-" * 50)
            
            result = self.execute(func_name, arguments)
            
            print(f"\n{'=' * 70}")
            print("RESULT")
            print("=" * 70)
            print(f"Success: {result.success}")
            print(f"Execution time: {result.execution_time_ms:.1f}ms")
            
            if result.response:
                print(f"\nResponse:\n{result.response}")
            
            if result.error:
                print(f"\nError: {result.error}")
            
            # If plugin wants passthrough mode, enter it automatically
            if result.awaiting_input:
                print(f"\nPlugin entered passthrough mode. Type 'exit' to leave.")
                print("-" * 50)
                self._passthrough_plugin = result.plugin_name
                self._handle_passthrough_input()
                return  # Don't show "Press Enter" after passthrough
        else:
            print("Cancelled.")
        
        print()
        input("Press Enter to continue...")
    
    def _menu_validate_plugin(self):
        """Validate a plugin's compliance"""
        plugins = self.list_plugins()
        
        if not plugins:
            print("\nNo plugins loaded.")
            input("Press Enter to continue...")
            return
        
        print(f"\n{'=' * 70}")
        print("VALIDATE PLUGIN")
        print("=" * 70)
        print("Select a plugin to validate:")
        
        for i, p in enumerate(plugins, 1):
            status = "RUNNING" if p.state == PluginState.READY else "STOPPED"
            print(f"  {i}. {p.name} [{status}]")
        print("  0. Back to main menu")
        
        choice = input("\nEnter plugin number: ").strip()
        
        if choice == '0':
            return
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(plugins):
                plugin_name = plugins[idx].name
                self._run_validation(plugin_name)
        except ValueError:
            # Try by name
            for p in plugins:
                if p.name.lower() == choice.lower():
                    self._run_validation(p.name)
                    return
            print("Invalid selection.")
    
    def _run_validation(self, plugin_name: str):
        """Run validation on a specific plugin"""
        from .validator import PluginValidator
        
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            print(f"Plugin '{plugin_name}' not found.")
            return
        
        manifest = self.manager._manifests.get(plugin_name)
        if not manifest:
            print(f"Manifest not found for '{plugin_name}'.")
            return
        
        print(f"\n{'=' * 70}")
        print(f"VALIDATING: {plugin_name}")
        print("=" * 70)
        print("\nThis will run a comprehensive validation suite including:")
        print("  - Manifest compliance")
        print("  - Startup behavior")
        print("  - Protocol compliance (JSON-RPC 2.0)")
        print("  - Heartbeat/ping response")
        print("  - Function execution")
        print("  - Error handling")
        print("  - Shutdown behavior")
        print()
        
        confirm = input("Start validation? (Y/n): ").strip().lower()
        if confirm not in ('', 'y', 'yes'):
            print("Validation cancelled.")
            return
        
        print("\nRunning validation (this may take a minute)...")
        print("-" * 70)
        
        validator = PluginValidator(plugin, manifest)
        report = validator.validate(verbose=True)
        
        # Print the report
        validator.print_report(report)
        
        # Offer to export
        export = input("Export report to JSON? (y/N): ").strip().lower()
        if export in ('y', 'yes'):
            from datetime import datetime
            filename = f"validation_{plugin_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            validator.export_report(filename)
        
        input("\nPress Enter to continue...")
    
    def _menu_reload_plugins(self):
        """Reload all plugins"""
        print("\nReloading plugins...")
        self.manager.shutdown()
        if self.manager.initialize():
            print("Plugins reloaded successfully.")
            self._print_startup_summary()
        else:
            print("Failed to reload plugins.")
        input("Press Enter to continue...")
    
    def _handle_passthrough_input(self):
        """Handle input while in passthrough mode"""
        print(f"\n[Passthrough mode with '{self._passthrough_plugin}']")
        print("Type 'exit', 'quit', or 'done' to leave passthrough mode.\n")
        
        while self.is_in_passthrough:
            try:
                user_input = input(f"[{self._passthrough_plugin}]> ").strip()
                
                if user_input.lower() in ('exit', 'quit', 'done'):
                    self.exit_passthrough()
                    print("Exited passthrough mode.\n")
                    break
                
                if not user_input:
                    continue
                
                result = self.send_input(user_input)
                
                if result.response:
                    print(result.response)
                
                if result.error:
                    print(f"Error: {result.error}")
                
            except KeyboardInterrupt:
                print("\nExiting passthrough mode...")
                self.exit_passthrough()
                break
    
    def _print_plugins(self):
        """Print list of plugins (legacy method)"""
        plugins = self.list_plugins()
        print(f"\nLoaded Plugins ({len(plugins)}):")
        print("-" * 60)
        for p in plugins:
            state = "[READY]" if p.state == PluginState.READY else "[    ]"
            mode = "[passthrough]" if p.passthrough else ""
            print(f"  {state} {p.name:<20} {p.function_count} function(s) {mode}")
            print(f"     {p.description[:55]}...")
        print()
    
    def _print_functions(self):
        """Print list of functions (legacy method)"""
        functions = self.list_functions()
        print(f"\nAvailable Functions ({len(functions)}):")
        print("-" * 60)
        for f in functions:
            name = f.get('name', 'unknown')
            desc = f.get('description', '')[:50]
            plugin = self.manager.get_plugin_for_function(name) or 'unknown'
            print(f"  {name:<30} [{plugin}]")
            print(f"     {desc}...")
        print()
    
    # ========================================================================
    # History and Debugging
    # ========================================================================
    
    def get_history(self) -> List[ExecutionResult]:
        """Get execution history"""
        return list(self._history)
    
    def clear_history(self):
        """Clear execution history"""
        self._history.clear()
    
    def export_history(self, path: str):
        """Export execution history to JSON file"""
        data = []
        for result in self._history:
            data.append({
                'success': result.success,
                'plugin_name': result.plugin_name,
                'function_name': result.function_name,
                'arguments': result.arguments,
                'response': result.response,
                'error': result.error,
                'execution_time_ms': result.execution_time_ms
            })
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Exported {len(data)} history entries to {path}")

