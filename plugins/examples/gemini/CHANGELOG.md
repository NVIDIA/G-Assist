# Changelog

## [Unreleased] - 2025-07-12

### Fixed
- Fixed a `SyntaxError` in `gemini.py` that crashed the plugin on startup. The error was caused by an improper use of a raw string inside an f-string when defining file paths. The original error was:
  ```
  File "C:\Users\Sasha\Documents\GitHub\RTX-assist\G-Assist\plugins\examples\gemini\gemini.py", line 35
    API_KEY_FILE = os.path.join(f'{os.environ.get("PROGRAMDATA", ".")}{r'\NVIDIA Corporation\nvtopps\rise\plugins\google'}', 'google.key')
                                                                         ^
  SyntaxError: unexpected character after line continuation character
  ```
- The `build.bat` script now checks for the Python executable by running `python --version` instead of using the `where` command. This provides a more reliable detection method, as `where` is not available on all Windows systems.
- The `README.md` has been updated to reflect the correct build output directory, which is `Release`, not `dist\google`.
- Corrected the `git clone` and directory navigation instructions in `README.md` to provide a clear and accurate setup path.
- Simplified the API key setup by instructing users to create `google.key` directly. The build script now also includes a backward-compatibility feature to automatically rename `gemini.key` if it exists, making the process more robust.

### Added
- The `build.bat` script will now automatically rename `gemini.key` to `google.key` if `google.key` is not already present, simplifying the setup process for users.
