from setuptools import setup, find_packages

setup(
    name="a2a-escrow-cli",
    version="1.0.0",
    description="Escrow-in-a-box for AI agents. Trustless settlement in 5 commands.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Brandon (OpenClaw)",
    author_email="brandon@openclaw.ai",
    url="https://github.com/widrss/a2a-escrow-cli",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "requests>=2.28.0",
        "click>=8.1.0",
        "rich>=13.0.0",
    ],
    entry_points={
        "console_scripts": [
            "a2a-escrow=a2a_escrow.cli:cli",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries",
    ],
)
