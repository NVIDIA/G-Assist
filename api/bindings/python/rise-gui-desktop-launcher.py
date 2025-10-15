"""
Desktop launcher for G-Assist - automatically starts in desktop mode
"""
import sys
import os

# Force desktop mode by adding --desktop argument
sys.argv = [sys.argv[0], '--desktop']

# When frozen by PyInstaller, get the path to bundled files
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    bundle_dir = sys._MEIPASS
else:
    # Running as script
    bundle_dir = os.path.dirname(os.path.abspath(__file__))

# Add bundle directory to path
sys.path.insert(0, bundle_dir)

# Import rise-gui as a module
import importlib.util
rise_gui_path = os.path.join(bundle_dir, "rise-gui.py")
spec = importlib.util.spec_from_file_location("rise_gui", rise_gui_path)
rise_gui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rise_gui)

if __name__ == "__main__":
    rise_gui.main()

