from setuptools import setup, find_packages

setup(
    name="rise",            # Name of the package
    version="0.0.1",             # Version of your package
    description="Python interfaces into RISE module",  # Short description
    author="RISE Team",          # Your name
    author_email="risaac@nvidia.com",  # Your email
    # URL to the project (e.g., GitHub)
    url="https://gitlab-master.nvidia.com/rise/rise-bindings",
    packages=find_packages(),    # Automatically find the package(s) in the project
    # List your dependencies here (from requirements.txt)
   	install_requires=[
        'tqdm',  # Add the module you want to include
    ]
)
