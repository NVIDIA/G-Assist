from setuptools import setup, find_packages

setup(
    name="gassist",                      # Name of the package
    version="0.0.1",                  # Version of your package
    description="Python interfaces into G-Assist module",  # Short description
    url="",                           # URL to the project (e.g., GitHub)
    packages=find_packages(),         # Automatically find the package(s) in the project
    install_requires=[
        'tqdm',      # For progress bars
        'flask',     # Lightweight web framework
        'flask-cors',# For handling Cross-Origin Resource Sharing
        'colorama'   # For colored terminal text
    ],
    include_package_data=True,        # Include files specified by MANIFEST.in (if any)
    package_data={
        # Include the precompiled DLL file in the g-assist package.
        "gassist": ["python_binding.dll"]
    },
    zip_safe=False  # Disables zip-safe mode; needed for binaries in some cases.
)
