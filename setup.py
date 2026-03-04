from setuptools import setup, find_packages

setup(
    name="ep1-flasher",
    version="1.0.0",
    description="CLI Flasher for Everything Presence One",
    author="Everything Smart Home Community",
    py_modules=["ep1-flasher"],
    python_requires=">=3.7",
    install_requires=[
        "requests>=2.25.0",
        "pyserial>=3.5",
        "esptool>=4.0",
    ],
    entry_points={
        "console_scripts": [
            "ep1-flasher=ep1_flasher:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Home Automation",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)
