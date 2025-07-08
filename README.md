# Hypha Artifact

A Python library for interacting with [Hypha](https://github.com/amun-ai/hypha) artifacts, providing both synchronous and asynchronous APIs for file operations in Hypha workspaces.

This python package provide a convenient way to interact with [hypha artifacts api](https://docs.amun.ai/#/artifact-manager). Allows you to perform file operations on remote artifacts as if you are working with local files.

## What are Hypha Artifacts?

An **artifact** is a folder-like container that represents a project, application, dataset, or any organized collection of files with associated metadata. Think of it as a smart directory that can be shared, versioned, and searched across different environments.

### Key Characteristics

- **Folder-like Structure**: Contains an arbitrary number of files and subdirectories, just like a regular filesystem folder
- **Rich Metadata**: Each artifact has searchable metadata (name, description, tags, etc.) stored in a SQL database for efficient discovery
- **Cloud Storage**: Files are stored in S3-compatible storage with organized prefixes for scalability and performance
- **Cross-Platform Access**: Can be accessed from anywhere with proper credentials, enabling seamless collaboration

### Common Use Cases

**🤖 Machine Learning & AI**
- Store model weights, configurations, and training checkpoints
- Version datasets and preprocessing pipelines
- Share experiment results and analysis notebooks

**📊 Data Science & Research**
- Organize research datasets with rich metadata
- Share reproducible analysis workflows
- Store and version data processing scripts

**🚀 Application Development**
- Store application assets (images, configs, static files)
- Version control for application builds and releases
- Share resources across development teams

**📚 Documentation & Collaboration**
- Centralized project documentation and resources
- Shared workspace for team collaboration
- Educational materials and tutorials

**🔬 Scientific Computing**
- Store simulation results and parameters
- Share computational workflows and environments
- Archive experimental data with metadata

### Example Artifact Structure

```
my-ml-project/                 # Artifact name
├── metadata                   # Stored in SQL database
│   ├── name: "my-ml-project"
│   ├── description: "Image classification model"
│   ├── tags: ["ml", "vision", "pytorch"]
│   └── created_by: "researcher@lab.edu"
└── files/                     # Stored in S3 with prefix
    ├── model.pth              # Trained model weights
    ├── config.yaml            # Model configuration
    ├── dataset/               # Training data
    │   ├── train/
    │   └── test/
    ├── notebooks/             # Analysis notebooks
    │   └── training.ipynb
    └── README.md              # Documentation
```

With this library, you can interact with artifacts using familiar file operations, making it easy to integrate cloud storage into your existing workflows.

## Installation

```bash
pip install hypha-artifact
```

## Quick Start

### Basic Setup

```python
from hypha_artifact import HyphaArtifact

# Initialize with your credentials
artifact = HyphaArtifact(
    artifact_name="my-artifact",
    workspace="your-workspace-id", 
    token="your-personal-token"
)
```

### Basic File Operations

```python
# Create and write to a file
with artifact.open("hello.txt", "w") as f:
    f.write("Hello, Hypha!")

# Read file content
content = artifact.cat("hello.txt")
print(content)  # Output: Hello, Hypha!

# List files in the artifact
files = artifact.ls("/")
print([f["name"] for f in files])

# Check if file exists
if artifact.exists("hello.txt"):
    print("File exists!")

# Copy a file
artifact.copy("hello.txt", "hello_copy.txt")

# Remove a file
artifact.rm("hello_copy.txt")
```

## API Reference

### Synchronous API

The `HyphaArtifact` class provides synchronous file operations:

#### Initialization

```python
HyphaArtifact(artifact_name: str, workspace: str, token: str)
```

#### File Operations

- **`open(path: str, mode: str)`** - Open a file for reading/writing
- **`cat(path: str) -> str`** - Read entire file content
- **`ls(path: str, detail: bool = True) -> list`** - List files and directories
- **`exists(path: str) -> bool`** - Check if file exists
- **`copy(source: str, destination: str)`** - Copy a file
- **`rm(path: str)`** - Remove a file

#### Example Usage

```python
from hypha_artifact import HyphaArtifact

# Initialize artifact
artifact = HyphaArtifact("my-data", "workspace-123", "token-456")

# Create a new file
with artifact.open("data.txt", "w") as f:
    f.write("Important data\nLine 2\nLine 3")

# Read partial content
with artifact.open("data.txt", "r") as f:
    first_10_chars = f.read(10)
    print(first_10_chars)  # "Important "

# List all files with details
files = artifact.ls("/", detail=True)
for file_info in files:
    print(f"Name: {file_info['name']}, Size: {file_info.get('size', 'N/A')}")

# List just file names
file_names = artifact.ls("/", detail=False)
print("Files:", file_names)

# Complete workflow
source_file = "source.txt"
backup_file = "backup.txt"

# Create source file
with artifact.open(source_file, "w") as f:
    f.write("This is my source content")

# Verify and backup
if artifact.exists(source_file):
    artifact.copy(source_file, backup_file)
    print("Backup created successfully")

# Clean up
artifact.rm(backup_file)
```

### Asynchronous API

The `AsyncHyphaArtifact` class provides asynchronous file operations for better performance in async applications:

#### Initialization

```python
from hypha_artifact import AsyncHyphaArtifact

async_artifact = AsyncHyphaArtifact(
    artifact_name="my-artifact",
    workspace="workspace-id",
    token="your-token"
)
```

#### Async File Operations

All methods are async versions of the synchronous API:

- **`await open(path: str, mode: str)`** - Open a file asynchronously
- **`await cat(path: str) -> str`** - Read entire file content
- **`await ls(path: str, detail: bool = True) -> list`** - List files and directories  
- **`await exists(path: str) -> bool`** - Check if file exists
- **`await copy(source: str, destination: str)`** - Copy a file
- **`await rm(path: str)`** - Remove a file

#### Context Manager Support

```python
import asyncio
from hypha_artifact import AsyncHyphaArtifact

async def main():
    # Method 1: Manual connection management
    artifact = AsyncHyphaArtifact("my-artifact", "workspace", "token")
    
    async with artifact:
        async with artifact.open("async_file.txt", "w") as f:
            await f.write("Async content")
        
        content = await artifact.cat("async_file.txt")
        print(content)
    
    # Method 2: Context manager for the entire artifact
    async with AsyncHyphaArtifact("my-artifact", "workspace", "token") as artifact:
        # Create file
        async with artifact.open("test.txt", "w") as f:
            await f.write("Test content")
        
        # List files
        files = await artifact.ls("/")
        print("Files:", [f["name"] for f in files])
        
        # Check existence
        exists = await artifact.exists("test.txt")
        print(f"File exists: {exists}")
        
        # Copy and remove
        await artifact.copy("test.txt", "test_copy.txt") 
        await artifact.rm("test_copy.txt")

# Run the async function
asyncio.run(main())
```

#### Async Workflow Example

```python
import asyncio
from hypha_artifact import AsyncHyphaArtifact

async def process_files():
    async with AsyncHyphaArtifact("data-processing", "workspace", "token") as artifact:
        
        # Create multiple files concurrently
        tasks = []
        for i in range(5):
            async def create_file(index):
                async with artifact.open(f"file_{index}.txt", "w") as f:
                    await f.write(f"Content for file {index}")
            
            tasks.append(create_file(i))
        
        await asyncio.gather(*tasks)
        
        # List all created files
        files = await artifact.ls("/", detail=False)
        print("Created files:", files)
        
        # Read and process files
        for filename in files:
            if filename.startswith("file_"):
                content = await artifact.cat(filename)
                print(f"{filename}: {content}")

asyncio.run(process_files())
```

## Advanced Usage

### Partial File Reading

Both APIs support reading specific amounts of data:

```python
# Synchronous
with artifact.open("large_file.txt", "r") as f:
    chunk = f.read(1024)  # Read first 1KB

# Asynchronous  
async with artifact.open("large_file.txt", "r") as f:
    chunk = await f.read(1024)  # Read first 1KB
```

### Error Handling

```python
from hypha_artifact import HyphaArtifact

artifact = HyphaArtifact("my-artifact", "workspace", "token")

try:
    # Try to read a non-existent file
    content = artifact.cat("non_existent.txt")
except Exception as e:
    print(f"Error reading file: {e}")

# Always check existence first
if artifact.exists("my_file.txt"):
    content = artifact.cat("my_file.txt")
else:
    print("File not found")
```

## Integration with Hypha

This library is designed to work seamlessly with [Hypha](https://github.com/amun-ai/hypha), a platform for building and deploying AI services. Artifacts provide persistent storage for your Hypha applications.

For comprehensive information about Hypha's artifact management system, including:
- Advanced configuration options
- Authentication methods  
- Workspace management
- API endpoints and specifications
- Security considerations

Please refer to the official [Hypha Artifact Manager Documentation](https://docs.amun.ai/#/artifact-manager).

## Requirements

- Python 3.7+
- Valid Hypha workspace credentials
- Network access to Hypha services

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
