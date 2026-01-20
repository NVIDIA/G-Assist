"""
Plugin Directory Watcher

Monitors the plugins directory for changes and triggers auto-discovery.
Watches for:
- New plugins added
- Plugins removed
- Manifest changes
- Executable changes
"""

import os
import time
import logging
import threading
from typing import Callable, Dict, Set, Optional, List
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PluginChange:
    """Represents a change to a plugin"""
    plugin_name: str
    change_type: str  # 'added', 'removed', 'modified', 'manifest_updated'
    file_path: Optional[str] = None


class PluginWatcher:
    """
    Watches the plugins directory for changes.
    
    Uses polling-based approach for cross-platform compatibility.
    Checks for:
    - New plugin directories with manifest.json
    - Removed plugin directories
    - Modified manifest.json files
    - Modified executable files
    """
    
    def __init__(
        self,
        plugins_dir: str,
        on_change: Optional[Callable[[List[PluginChange]], None]] = None,
        poll_interval: float = 2.0,
    ):
        """
        Initialize the watcher.
        
        Args:
            plugins_dir: Path to plugins directory
            on_change: Callback when changes detected
            poll_interval: Seconds between directory scans
        """
        self.plugins_dir = Path(plugins_dir)
        self.on_change = on_change
        self.poll_interval = poll_interval
        
        # State tracking
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._known_plugins: Dict[str, Dict] = {}  # plugin_name -> {manifest_mtime, exe_mtime}
        
        # Initialize known plugins
        self._scan_plugins()
    
    def start(self):
        """Start watching for changes"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(
            target=self._watch_loop,
            name="PluginWatcher",
            daemon=True
        )
        self._thread.start()
        logger.info(f"Plugin watcher started (polling every {self.poll_interval}s)")
    
    def stop(self):
        """Stop watching"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self.poll_interval + 1)
        self._thread = None
        logger.info("Plugin watcher stopped")
    
    @property
    def is_running(self) -> bool:
        """Check if watcher is running"""
        return self._running
    
    def _watch_loop(self):
        """Main watch loop"""
        while self._running:
            try:
                changes = self._check_for_changes()
                if changes and self.on_change:
                    self.on_change(changes)
            except Exception as e:
                logger.error(f"Watcher error: {e}")
            
            time.sleep(self.poll_interval)
    
    def _scan_plugins(self) -> Dict[str, Dict]:
        """Scan plugins directory and return plugin info"""
        plugins = {}
        
        if not self.plugins_dir.exists():
            return plugins
        
        for item in self.plugins_dir.iterdir():
            if not item.is_dir():
                continue
            
            manifest_path = item / "manifest.json"
            if not manifest_path.exists():
                continue
            
            plugin_name = item.name
            
            # Get modification times
            manifest_mtime = manifest_path.stat().st_mtime
            
            # Try to find executable
            exe_mtime = None
            try:
                import json
                with open(manifest_path) as f:
                    manifest = json.load(f)
                exe_name = manifest.get("executable", "")
                exe_path = item / exe_name
                if exe_path.exists():
                    exe_mtime = exe_path.stat().st_mtime
            except:
                pass
            
            plugins[plugin_name] = {
                "manifest_mtime": manifest_mtime,
                "exe_mtime": exe_mtime,
                "path": str(item)
            }
        
        return plugins
    
    def _check_for_changes(self) -> List[PluginChange]:
        """Check for changes since last scan"""
        changes = []
        current_plugins = self._scan_plugins()
        
        # Check for new plugins
        for name in current_plugins:
            if name not in self._known_plugins:
                changes.append(PluginChange(
                    plugin_name=name,
                    change_type="added",
                    file_path=current_plugins[name]["path"]
                ))
                logger.info(f"New plugin detected: {name}")
        
        # Check for removed plugins
        for name in self._known_plugins:
            if name not in current_plugins:
                changes.append(PluginChange(
                    plugin_name=name,
                    change_type="removed",
                    file_path=self._known_plugins[name]["path"]
                ))
                logger.info(f"Plugin removed: {name}")
        
        # Check for modified plugins
        for name in current_plugins:
            if name in self._known_plugins:
                old_info = self._known_plugins[name]
                new_info = current_plugins[name]
                
                # Check manifest change
                if new_info["manifest_mtime"] != old_info["manifest_mtime"]:
                    changes.append(PluginChange(
                        plugin_name=name,
                        change_type="manifest_updated",
                        file_path=str(Path(new_info["path"]) / "manifest.json")
                    ))
                    logger.info(f"Plugin manifest updated: {name}")
                
                # Check executable change
                elif new_info["exe_mtime"] and old_info["exe_mtime"]:
                    if new_info["exe_mtime"] != old_info["exe_mtime"]:
                        changes.append(PluginChange(
                            plugin_name=name,
                            change_type="modified",
                            file_path=new_info["path"]
                        ))
                        logger.info(f"Plugin executable updated: {name}")
        
        # Update known plugins
        self._known_plugins = current_plugins
        
        return changes
    
    def get_known_plugins(self) -> List[str]:
        """Get list of currently known plugin names"""
        return list(self._known_plugins.keys())
    
    def force_rescan(self) -> List[PluginChange]:
        """Force a rescan and return any changes"""
        return self._check_for_changes()


class PluginWatcherManager:
    """
    Manages the plugin watcher and integrates with PluginManager.
    
    Provides callbacks for:
    - Plugin added
    - Plugin removed  
    - Plugin updated
    """
    
    def __init__(
        self,
        plugins_dir: str,
        on_plugins_changed: Optional[Callable[[List[PluginChange]], None]] = None,
        auto_reload: bool = True,
        poll_interval: float = 2.0,
    ):
        """
        Initialize the watcher manager.
        
        Args:
            plugins_dir: Path to plugins directory
            on_plugins_changed: Callback when plugins change
            auto_reload: If True, automatically trigger reload
            poll_interval: Seconds between scans
        """
        self.plugins_dir = plugins_dir
        self.on_plugins_changed = on_plugins_changed
        self.auto_reload = auto_reload
        
        self._watcher = PluginWatcher(
            plugins_dir=plugins_dir,
            on_change=self._handle_changes,
            poll_interval=poll_interval
        )
        
        # Pending changes (batched)
        self._pending_changes: List[PluginChange] = []
        self._change_lock = threading.Lock()
        self._debounce_timer: Optional[threading.Timer] = None
        self._debounce_delay = 1.0  # Wait 1 second to batch changes
    
    def start(self):
        """Start watching"""
        self._watcher.start()
    
    def stop(self):
        """Stop watching"""
        if self._debounce_timer:
            self._debounce_timer.cancel()
        self._watcher.stop()
    
    @property
    def is_running(self) -> bool:
        """Check if watcher is running"""
        return self._watcher.is_running
    
    def _handle_changes(self, changes: List[PluginChange]):
        """Handle detected changes with debouncing"""
        with self._change_lock:
            self._pending_changes.extend(changes)
            
            # Cancel existing timer
            if self._debounce_timer:
                self._debounce_timer.cancel()
            
            # Set new timer to batch changes
            self._debounce_timer = threading.Timer(
                self._debounce_delay,
                self._process_pending_changes
            )
            self._debounce_timer.start()
    
    def _process_pending_changes(self):
        """Process all pending changes"""
        with self._change_lock:
            if not self._pending_changes:
                return
            
            changes = self._pending_changes.copy()
            self._pending_changes.clear()
        
        # Notify callback
        if self.on_plugins_changed:
            self.on_plugins_changed(changes)
    
    def force_rescan(self) -> List[PluginChange]:
        """Force an immediate rescan"""
        return self._watcher.force_rescan()

