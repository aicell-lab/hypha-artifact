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

### Performance Features

**🚀 Multipart Upload Support**
- Automatic multipart upload for files over 100MB
- Parallel chunk upload in async mode for faster transfers
- Configurable chunk sizes and thresholds
- Efficient handling of very large files (GB+)

**⚡ Concurrent Operations**
- Async version supports parallel file operations
- Batch folder uploads with concurrent file transfers
- Optimized for high-throughput data workflows

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

### Synchronous Version

```python
from hypha_artifact import HyphaArtifact

# Initialize with your credentials
artifact = HyphaArtifact(
    artifact_id="my-artifact",
    workspace="your-workspace-id", 
    token="your-workspace-token"
)

# Stage changes to the artifact
artifact.edit(stage=True)

# Create and write to a file
with artifact.open("hello.txt", "w") as f:
    f.write("Hello, Hypha!")

# Commit the changes with a comment
artifact.commit(comment="Added hello.txt")

# Read file content
content = artifact.cat("hello.txt")
print(content)  # Output: Hello, Hypha!

# List files in the artifact
files = artifact.ls("/")
print([f["name"] for f in files])

# Check if file exists
if artifact.exists("hello.txt"):
    print("File exists!")

# Stage changes for copying a file
artifact.edit(stage=True)
artifact.copy("hello.txt", "hello_copy.txt")
artifact.commit(comment="Copied hello.txt")

# Stage changes for removing a file
artifact.edit(stage=True)
artifact.rm("hello_copy.txt")
artifact.commit(comment="Removed hello_copy.txt")
```

### Asynchronous Version (Recommended)

```python
import asyncio
from hypha_artifact import AsyncHyphaArtifact

async def main():
    # Initialize and use as context manager
    async with AsyncHyphaArtifact(
        artifact_id="my-artifact",
        workspace="your-workspace-id", 
        token="your-workspace-token"
    ) as artifact:
        
        # Stage changes to the artifact
        await artifact.edit(stage=True)
        
        # Create and write to a file
        async with artifact.open("hello.txt", "w") as f:
            await f.write("Hello, Hypha!")
            
        # Commit the changes with a comment
        await artifact.commit(comment="Added hello.txt")
        
        # Read file content
        content = await artifact.cat("hello.txt")
        print(content)  # Output: Hello, Hypha!
        
        # List files in the artifact
        files = await artifact.ls("/")
        print([f["name"] for f in files])
        
        # Check if file exists
        if await artifact.exists("hello.txt"):
            print("File exists!")
        
        # Stage, copy, and commit
        await artifact.edit(stage=True)
        await artifact.copy("hello.txt", "hello_copy.txt")
        await artifact.commit(comment="Copied hello.txt")
        
        # Stage, remove, and commit
        await artifact.edit(stage=True)
        await artifact.rm("hello_copy.txt")
        await artifact.commit(comment="Removed hello_copy.txt")

# Run the async function
asyncio.run(main())
```

## API Reference

### Synchronous API

The `HyphaArtifact` class provides synchronous file operations:

#### Initialization

```python
HyphaArtifact(artifact_id: str, workspace: str, token: str)
```

#### File Operations

- **`open(path: str, mode: str)`** - Open a file for reading/writing
- **`cat(path: str) -> str`** - Read entire file content
- **`ls(path: str, detail: bool = True) -> list`** - List files and directories
- **`exists(path: str) -> bool`** - Check if file exists
- **`copy(source: str, destination: str)`** - Copy a file
- **`rm(path: str)`** - Remove a file

#### Upload Operations

- **`upload(local_path, remote_path="", recursive=True, enable_multipart=False, ...)`** - Upload files or folders with multipart support

#### Example Usage

```python
from hypha_artifact import HyphaArtifact

# Initialize artifact
artifact = HyphaArtifact("my-data", "workspace-123", "token-456")

# Stage changes before writing
artifact.edit(stage=True)

# Create a new file
with artifact.open("data.txt", "w") as f:
    f.write("Important data\nLine 2\nLine 3")

# Commit the changes
artifact.commit(comment="Added data.txt")

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

# Stage, create, and commit the source file
artifact.edit(stage=True)
with artifact.open(source_file, "w") as f:
    f.write("This is my source content")
artifact.commit(comment="Created source file")

# Verify and backup
if artifact.exists(source_file):
    artifact.edit(stage=True)
    artifact.copy(source_file, backup_file)
    artifact.commit(comment="Created backup")
    print("Backup created successfully")

# Clean up
artifact.edit(stage=True)
artifact.rm(backup_file)
artifact.commit(comment="Removed backup")

# Upload Operations Examples

# Upload a large file with multipart support
artifact.upload(
    "large_dataset.zip",
    "/datasets/large_dataset.zip",
    enable_multipart=True,
    chunk_size=10*1024*1024  # 10MB chunks
)

# Upload an entire project folder
artifact.upload(
    "./my-project",
    "/projects/my-project",
    recursive=True,
    enable_multipart=True,  # For large files in the folder
    multipart_threshold=50*1024*1024  # 50MB threshold
)
```

### Asynchronous API

The `AsyncHyphaArtifact` class provides asynchronous file operations for better performance in async applications:

#### Initialization

```python
from hypha_artifact import AsyncHyphaArtifact

async_artifact = AsyncHyphaArtifact(
    artifact_id="my-artifact",
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
    artifact = AsyncHyphaArtifact("my-workspace/my-artifact", token="token")
    
    await artifact.edit(stage=True)
    async with artifact.open("async_file.txt", "w") as f:
        await f.write("Async content")
    await artifact.commit(comment="Added async_file.txt")
    
    content = await artifact.cat("async_file.txt")
    print(content)
    
    # Method 2: Context manager for the entire artifact
    async with AsyncHyphaArtifact("my-artifact", "workspace", "token") as artifact:
        # Stage, create, and commit
        await artifact.edit(stage=True)
        async with artifact.open("test.txt", "w") as f:
            await f.write("Test content")
        await artifact.commit(comment="Added test.txt")
        
        # List files
        files = await artifact.ls("/")
        print("Files:", [f["name"] for f in files])
        
        # Check existence
        exists = await artifact.exists("test.txt")
        print(f"File exists: {exists}")
        
        # Stage, copy, and commit
        await artifact.edit(stage=True)
        await artifact.copy("test.txt", "test_copy.txt") 
        await artifact.commit(comment="Copied test.txt")

        # Stage, remove, and commit
        await artifact.edit(stage=True)
        await artifact.rm("test_copy.txt")
        await artifact.commit(comment="Removed test_copy.txt")
        
        # Upload large files with parallel multipart support
        await artifact.upload(
            "large_model.bin",
            "/models/large_model.bin",
            enable_multipart=True,
            max_parallel_uploads=8,  # Upload parts in parallel
            chunk_size=20*1024*1024  # 20MB chunks
        )
        
        # Upload folders with concurrent file uploads
        await artifact.upload(
            "./dataset",
            "/data/dataset",
            enable_multipart=True,
            max_parallel_uploads=4
        )

# Run the async function
asyncio.run(main())
```

#### Async Workflow Example

```python
import asyncio
from hypha_artifact import AsyncHyphaArtifact

async def process_files():
    async with AsyncHyphaArtifact("data-processing", "workspace", "token") as artifact:
        
        # Stage changes before creating files
        await artifact.edit(stage=True)

        # Create multiple files concurrently
        tasks = []
        for i in range(5):
            async def create_file(index):
                async with artifact.open(f"file_{index}.txt", "w") as f:
                    await f.write(f"Content for file {index}")
            
            tasks.append(create_file(i))
        
        await asyncio.gather(*tasks)

        # Commit all changes at once
        await artifact.commit(comment="Added 5 files concurrently")
        
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

## Command Line Interface (CLI)

The `hypha-artifact` package includes a comprehensive CLI tool for managing artifacts from the command line:

```bash
# Install with CLI support
pip install hypha-artifact

# Upload files and folders
hypha-artifact --artifact-id=my-data upload local-file.txt /remote/path/
hypha-artifact --artifact-id=my-data upload ./my-project /projects/

# List and manage files
hypha-artifact --artifact-id=my-data ls /
hypha-artifact --artifact-id=my-data cat /data.txt
hypha-artifact --artifact-id=my-data rm /old-file.txt

# Large file support with multipart upload
hypha-artifact --artifact-id=my-data upload --enable-multipart large-file.zip /data/
```

For complete CLI documentation including all commands, options, and examples, see the [CLI Documentation](docs/CLI.md).

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
