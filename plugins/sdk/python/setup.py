"""
G-Assist Plugin SDK Setup

Install with:
    pip install .

Or for development:
    pip install -e .
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="gassist-sdk",
    version="2.0.0",
    author="NVIDIA Corporation",
    author_email="",
    description="SDK for building G-Assist plugins",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/NVIDIA/g-assist",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: Other/Proprietary License",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=[
        # No external dependencies - uses only standard library!
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "mypy>=1.0",
            "black>=23.0",
        ],
    },
)

