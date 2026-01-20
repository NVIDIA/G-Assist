"""
Plugin Emulator CLI

Command-line interface for the G-Assist Plugin Emulator.
"""

import argparse
import json
import os
import sys
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from colorama import Fore, Style, init

from .engine import PluginEngine, EngineConfig, EngineMode, ExecutionResult


# Initialize colorama
init(autoreset=True)


def setup_logging(verbose: bool):
    """Configure logging - WARNING by default for cleaner output"""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def print_header():
    """Print CLI header"""
    print(f"\n{Fore.CYAN}{'=' * 70}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}G-Assist Plugin Emulator{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'=' * 70}{Style.RESET_ALL}\n")


def print_plugins(engine: PluginEngine):
    """Print list of plugins"""
    plugins = engine.list_plugins()
    
    print(f"\n{Fore.GREEN}Loaded Plugins ({len(plugins)}):{Style.RESET_ALL}")
    print("-" * 60)
    
    for p in plugins:
        state_icon = f"{Fore.GREEN}*{Style.RESET_ALL}" if p.state.name == "READY" else f"{Fore.WHITE}o{Style.RESET_ALL}"
        mode_tag = f"{Fore.YELLOW}[passthrough]{Style.RESET_ALL}" if p.passthrough else ""
        persistent_tag = f"{Fore.BLUE}[persistent]{Style.RESET_ALL}" if p.persistent else ""
        
        print(f"  {state_icon} {Fore.WHITE}{p.name:<25}{Style.RESET_ALL} "
              f"{p.function_count} function(s) {mode_tag} {persistent_tag}")
        print(f"     {Fore.LIGHTBLACK_EX}{p.description[:55]}...{Style.RESET_ALL}")
    
    print()


def print_functions(engine: PluginEngine, plugin_name: Optional[str] = None):
    """Print list of functions"""
    functions = engine.list_functions(plugin_name)
    
    title = f"Functions for '{plugin_name}'" if plugin_name else "All Functions"
    print(f"\n{Fore.GREEN}{title} ({len(functions)}):{Style.RESET_ALL}")
    print("-" * 70)
    
    for f in functions:
        name = f.get('name', 'unknown')
        desc = f.get('description', '')[:50]
        plugin = engine.manager.get_plugin_for_function(name) or 'unknown'
        
        params = f.get('parameters', {}).get('properties', {})
        param_names = list(params.keys())
        param_str = f"({', '.join(param_names)})" if param_names else "()"
        
        print(f"  {Fore.WHITE}{name}{Style.RESET_ALL}{param_str}")
        print(f"     {Fore.LIGHTBLACK_EX}[{plugin}] {desc}...{Style.RESET_ALL}")
    
    print()


def print_result(result: ExecutionResult):
    """Print execution result"""
    if result.success:
        print(f"\n{Fore.GREEN}[OK] Success{Style.RESET_ALL} "
              f"({result.execution_time_ms:.1f}ms)")
    else:
        print(f"\n{Fore.RED}[FAIL] Failed{Style.RESET_ALL} "
              f"({result.execution_time_ms:.1f}ms)")
    
    if result.response:
        print(f"\n{result.response}")
    
    if result.error:
        print(f"\n{Fore.RED}Error: {result.error}{Style.RESET_ALL}")
    
    if result.awaiting_input:
        print(f"\n{Fore.YELLOW}Plugin is awaiting input. "
              f"Use --input to send data or --exit to quit passthrough mode.{Style.RESET_ALL}")


def cmd_list(args, engine: PluginEngine):
    """List plugins or functions"""
    if args.what == 'plugins':
        print_plugins(engine)
    elif args.what == 'functions':
        print_functions(engine, args.plugin)
    elif args.what == 'catalog':
        catalog = engine.get_tool_catalog()
        print(json.dumps(catalog, indent=2))


def cmd_exec(args, engine: PluginEngine):
    """Execute a function"""
    function_name = args.function
    
    # Parse arguments
    arguments = {}
    if args.args:
        try:
            arguments = json.loads(args.args)
        except json.JSONDecodeError:
            # Try to parse as key=value pairs
            for pair in args.args.split(','):
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    arguments[key.strip()] = value.strip()
                else:
                    print(f"{Fore.RED}Invalid argument format: {pair}{Style.RESET_ALL}")
                    return 1
    
    print(f"\n{Fore.CYAN}Executing: {function_name}({json.dumps(arguments)}){Style.RESET_ALL}")
    
    result = engine.execute(function_name, arguments)
    print_result(result)
    
    return 0 if result.success else 1


def cmd_passthrough(args, engine: PluginEngine):
    """Run in passthrough mode"""
    plugin_name = args.plugin
    function_name = args.function or ""
    
    # Get plugin
    plugin = engine.get_plugin(plugin_name)
    if not plugin:
        print(f"{Fore.RED}Plugin not found: {plugin_name}{Style.RESET_ALL}")
        return 1
    
    # Find a function if not specified
    if not function_name:
        functions = plugin.get_function_names()
        if functions:
            function_name = functions[0]
        else:
            print(f"{Fore.RED}Plugin has no functions{Style.RESET_ALL}")
            return 1
    
    print(f"\n{Fore.CYAN}Entering passthrough mode with {plugin_name}.{function_name}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Type 'exit', 'quit', or 'done' to leave.{Style.RESET_ALL}\n")
    
    # Execute initial function
    result = engine.execute_passthrough(plugin_name, function_name)
    if result.response:
        print(result.response)
    
    if result.error and not result.awaiting_input:
        print(f"{Fore.RED}Error: {result.error}{Style.RESET_ALL}")
        return 1
    
    # Interactive passthrough loop
    while engine.is_in_passthrough:
        try:
            user_input = input(f"{Fore.GREEN}[{plugin_name}]> {Style.RESET_ALL}").strip()
            
            if user_input.lower() in ('exit', 'quit', 'done'):
                engine.exit_passthrough()
                print(f"\n{Fore.YELLOW}Exited passthrough mode.{Style.RESET_ALL}")
                break
            
            result = engine.send_input(user_input)
            if result.response:
                print(result.response)
            
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Interrupted. Exiting passthrough mode.{Style.RESET_ALL}")
            engine.exit_passthrough()
            break
        except EOFError:
            break
    
    return 0


def cmd_test(args, engine: PluginEngine):
    """Run autonomous tests"""
    # Load test configuration
    if args.test_file:
        with open(args.test_file) as f:
            test_config = json.load(f)
    else:
        # Build test from command line args
        test_config = {
            'tests': [{
                'function': args.function,
                'prompt': args.prompt or f"Execute {args.function}",
                'expectation': args.expectation or "Function should execute successfully",
                'arguments': json.loads(args.args) if args.args else {}
            }]
        }
    
    tests = test_config.get('tests', [])
    
    print(f"\n{Fore.CYAN}Running {len(tests)} autonomous test(s){Style.RESET_ALL}\n")
    print("=" * 80)
    
    passed = 0
    failed = 0
    
    for i, test in enumerate(tests, 1):
        function_name = test.get('function')
        prompt = test.get('prompt', '')
        expectation = test.get('expectation', '')
        arguments = test.get('arguments', {})
        
        print(f"\n{Fore.WHITE}Test {i}/{len(tests)}: {function_name}{Style.RESET_ALL}")
        print(f"  Prompt: {prompt[:60]}...")
        print(f"  Expectation: {expectation[:60]}...")
        
        try:
            result = engine.test_function_autonomous(
                function_name=function_name,
                test_prompt=prompt,
                expected_behavior=expectation,
                arguments=arguments,
                max_turns=args.max_turns
            )
            
            if result.passed:
                print(f"  {Fore.GREEN}[PASS]{Style.RESET_ALL} "
                      f"({result.turns_used} turn(s), {result.execution_time_ms:.1f}ms)")
                passed += 1
            else:
                print(f"  {Fore.RED}[FAIL]{Style.RESET_ALL} "
                      f"({result.turns_used} turn(s), {result.execution_time_ms:.1f}ms)")
                print(f"    Reason: {result.reasoning[:80]}...")
                failed += 1
                
        except Exception as e:
            print(f"  {Fore.RED}[ERROR] {e}{Style.RESET_ALL}")
            failed += 1
    
    print("\n" + "=" * 80)
    print(f"\n{Fore.WHITE}Results:{Style.RESET_ALL}")
    print(f"  {Fore.GREEN}Passed: {passed}{Style.RESET_ALL}")
    print(f"  {Fore.RED}Failed: {failed}{Style.RESET_ALL}")
    print(f"  Total: {passed + failed}")
    
    return 0 if failed == 0 else 1


def cmd_interactive(args, engine: PluginEngine):
    """Run in interactive mode - uses engine's built-in menu"""
    # Skip the CLI header and plugin list - engine.run_interactive() does this
    engine.run_interactive()
    return 0


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='G-Assist Plugin Emulator - Emulates G-Assist engine for plugin testing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start interactive mode (default - just specify plugins directory)
  python -m plugin_emulator -d ./plugins

  # List all plugins (scripting mode)
  python -m plugin_emulator -d ./plugins list plugins

  # Execute a function directly
  python -m plugin_emulator -d ./plugins exec my_function --args '{"param": "value"}'

  # Run autonomous tests
  python -m plugin_emulator -d ./plugins test --test-file tests.json
"""
    )
    
    # Global arguments
    parser.add_argument(
        '--plugins-dir', '-d',
        required=True,
        help='Path to plugins directory'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=30000,
        help='Execution timeout in milliseconds (default: 30000)'
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # list command
    list_parser = subparsers.add_parser('list', help='List plugins or functions')
    list_parser.add_argument(
        'what',
        choices=['plugins', 'functions', 'catalog'],
        help='What to list'
    )
    list_parser.add_argument(
        '--plugin', '-p',
        help='Filter by plugin name (for functions)'
    )
    
    # exec command
    exec_parser = subparsers.add_parser('exec', help='Execute a function')
    exec_parser.add_argument(
        'function',
        help='Function name to execute'
    )
    exec_parser.add_argument(
        '--args', '-a',
        help='Function arguments as JSON or key=value pairs'
    )
    
    # passthrough command
    passthrough_parser = subparsers.add_parser('passthrough', help='Run in passthrough mode')
    passthrough_parser.add_argument(
        'plugin',
        help='Plugin name'
    )
    passthrough_parser.add_argument(
        '--function', '-f',
        help='Initial function to call (optional)'
    )
    
    # test command
    test_parser = subparsers.add_parser('test', help='Run autonomous tests')
    test_parser.add_argument(
        '--test-file', '-t',
        help='Test configuration JSON file'
    )
    test_parser.add_argument(
        '--function', '-f',
        help='Single function to test'
    )
    test_parser.add_argument(
        '--prompt',
        help='Test prompt'
    )
    test_parser.add_argument(
        '--expectation',
        help='Expected behavior description'
    )
    test_parser.add_argument(
        '--args', '-a',
        help='Function arguments as JSON'
    )
    test_parser.add_argument(
        '--max-turns',
        type=int,
        default=3,
        help='Maximum turns for follow-up (default: 3)'
    )
    test_parser.add_argument(
        '--api-key',
        help='LLM API key (or set LLM_API_KEY env var)'
    )
    
    # interactive command
    interactive_parser = subparsers.add_parser('interactive', help='Run in interactive mode')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Default to interactive mode if no command specified
    if not args.command:
        args.command = 'interactive'
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Print header (skip for interactive mode - it has its own banner)
    if args.command != 'interactive':
        print_header()
    
    # Build config
    config = EngineConfig(
        plugins_dir=args.plugins_dir,
        verbose=args.verbose,
        timeout_ms=args.timeout,
    )
    
    # Add LLM settings for test command
    if args.command == 'test':
        config.llm_api_key = getattr(args, 'api_key', None) or os.environ.get('LLM_API_KEY')
        config.max_turns = getattr(args, 'max_turns', 3)
    
    # Create engine
    try:
        engine = PluginEngine(config=config)
        
        if not engine.initialize():
            print(f"{Fore.RED}Failed to initialize engine{Style.RESET_ALL}")
            return 1
        
        # For interactive mode, don't print here - the engine does it
        if args.command != 'interactive':
            print(f"{Fore.GREEN}Engine initialized successfully{Style.RESET_ALL}")
            print_plugins(engine)
        
    except Exception as e:
        print(f"{Fore.RED}Error initializing engine: {e}{Style.RESET_ALL}")
        return 1
    
    # Execute command
    try:
        if args.command == 'list':
            return cmd_list(args, engine)
        elif args.command == 'exec':
            return cmd_exec(args, engine)
        elif args.command == 'passthrough':
            return cmd_passthrough(args, engine)
        elif args.command == 'test':
            return cmd_test(args, engine)
        elif args.command == 'interactive':
            return cmd_interactive(args, engine)
        else:
            parser.print_help()
            return 1
    finally:
        engine.shutdown()


if __name__ == '__main__':
    sys.exit(main())

