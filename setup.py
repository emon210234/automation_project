"""Setup configuration for the Invoice Automation Platform."""

from setuptools import find_packages, setup

setup(
    name="automation_platform",
    version="1.0.0",
    description="Production-grade Invoice Automation Platform with UiPath Integration",
    author="Automation Team",
    python_requires=">=3.9",
    packages=find_packages(),
    include_package_data=True,
    package_data={"automation_platform": ["config/*.yaml", "database/*.sql"]},
    install_requires=[
        "pyyaml>=6.0",
        "pdfplumber>=0.10.0",
        "pandas>=2.0.0",
        "requests>=2.31.0",
        "beautifulsoup4>=4.12.0",
    ],
    extras_require={
        "dev": ["pytest>=7.4.0", "pytest-cov>=4.1.0"],
    },
    entry_points={
        "console_scripts": [
            "automation-init-db=automation_platform.scripts.init_db:main",
            "automation-create-jobs=automation_platform.scripts.create_jobs:main",
            "automation-worker=automation_platform.scripts.start_worker:main",
        ],
    },
)
