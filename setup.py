"""Setup script for claude-adapter-py"""
from setuptools import setup, find_packages

setup(
    package_dir={"": "src"},
    packages=find_packages(where="src"),
)
