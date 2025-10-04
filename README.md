# Storage Tools

A Python application to help manage and analyze files and folders on your system.

## Features

- **Folder Analysis**: Show disk usage and statistics for folders
- **Duplicate Files Search**: Find duplicate files based on content
- **Duplicate Folders Search**: Identify folders with similar content
- **Large Files Search**: Locate the largest files on your system
- More features coming soon!

## Installation

### For Development

1. Clone the repository:
```bash
git clone <your-repo-url>
cd storage-tools
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On macOS/Linux
```

3. Install the package in development mode with dev dependencies:
```bash
pip install -e ".[dev]"
```

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

Format code with Black:
```bash
black storage_tools tests
```

Sort imports with isort:
```bash
isort storage_tools tests
```

### Linting

Run flake8 for linting:
```bash
flake8 storage_tools tests
```

Run mypy for type checking:
```bash
mypy storage_tools
```

### Run All Quality Checks

```bash
# Format code
black storage_tools tests
isort storage_tools tests

# Run linters
flake8 storage_tools tests
mypy storage_tools

# Run tests
pytest
```

## Usage

Once installed, you can run the tool using:

```bash
storage-tools --help
```

## Project Structure

```
storage-tools/
├── storage_tools/          # Main package directory
│   ├── __init__.py
│   ├── cli.py             # CLI interface
│   ├── analyzer.py        # Folder analysis module
│   ├── duplicates.py      # Duplicate detection module
│   └── utils.py           # Utility functions
├── tests/                 # Test directory
│   ├── __init__.py
│   └── test_*.py         # Test files
├── pyproject.toml        # Project configuration
├── setup.cfg             # Additional tool configuration
├── .gitignore            # Git ignore rules
└── README.md             # This file
```

## License

MIT License
