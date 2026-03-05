from setuptools import setup, find_packages

with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="jaka_logger",
    version="1.1.0",
    author="Lars",
    description="Thread-safe Python logger with file, console, and callback support",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/llienke/jaka_logger",
    packages=find_packages(exclude=["tests", "tests.*"]),
    install_requires=[],
    python_requires=">=3.5",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: System :: Logging",
        "Intended Audience :: Developers",
    ],
    keywords="logging thread-safe callbacks robotics jaka",
)