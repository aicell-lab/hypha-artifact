# HyphaArtifact Documentation

`HyphaArtifact` and `AsyncHyphaArtifact` are fsspec-compatible interfaces for
Hypha artifacts that provide a file-system like interface to interact with
remote Hypha artifacts. This allows for operations such as reading,
writing, listing, and manipulating files stored in Hypha artifacts.

## Overview

The HyphaArtifact library provides both synchronous and asynchronous
file-system-like interfaces that follow the fsspec specification,
making it easy to interact with Hypha artifacts in a familiar way.

**⚡ Recommendation: Use `AsyncHyphaArtifact` for better performance and
scalability in most applications, especially when dealing with multiple file
operations or integrating with async frameworks.**

Both classes support various file operations including:

- Creating and reading files
- Listing directory contents
- Copying files between locations
- Removing files
- Checking file existence and properties
- Partial file reading with HTTP Range headers

## Installation

```bash
pip install hypha-artifact
```

For Pyodide environments:

```python
import micropip
await micropip.install("hypha-artifact")
```

## Authentication

For accessing hypha artifact in a workspace, you need to have a workspace token.
You can get the workspace token from the workspace's development page in the
hypha app. If the artifact is public, you can still perform operations on it
without a token.

## Quick Start

### Synchronous Version

```python
from hypha_artifact import HyphaArtifact

# Initialize
artifact = HyphaArtifact(
    artifact_alias="example_artifact", 
    workspace="your-workspace-id", 
    token="your-workspace-token"
)

# Create and write to a file
with artifact.open("hello.txt", "w") as f:
    f.write("Hello, Hypha!")

# Read file content
content = artifact.cat("hello.txt")
print(content)  # Output: Hello, Hypha!

# List files
files = artifact.ls("/")
print([f["name"] for f in files])

# Check existence and copy
if artifact.exists("hello.txt"):
    artifact.copy("hello.txt", "hello_copy.txt")

# Remove file
artifact.rm("hello_copy.txt")
```

### Asynchronous Version (Recommended)

```python
import asyncio
from hypha_artifact import AsyncHyphaArtifact

async def main():
    # Initialize and use as context manager
    async with AsyncHyphaArtifact(
        artifact_alias="example_artifact", 
        workspace="your-workspace-id", 
        token="your-workspace-token"
    ) as artifact:
        
        # Create and write to a file
        async with artifact.open("hello.txt", "w") as f:
            await f.write("Hello, Hypha!")
        
        # Read file content
        content = await artifact.cat("hello.txt")
        print(content)  # Output: Hello, Hypha!
        
        # List files
        files = await artifact.ls("/")
        print([f["name"] for f in files])
        
        # Check existence and copy
        if await artifact.exists("hello.txt"):
            await artifact.copy("hello.txt", "hello_copy.txt")
        
        # Remove file
        await artifact.rm("hello_copy.txt")

# Run the async function
asyncio.run(main())
```

## Detailed Usage

### File Operations

#### Creating a File

```python
# Synchronous
with artifact.open("path/to/file.txt", "w") as f:
    f.write("This is a test file")

# Asynchronous (recommended)
async with async_artifact:
    async with async_artifact.open("path/to/file.txt", "w") as f:
        await f.write("This is a test file")
```

#### Reading a File

```python
# Synchronous - Read entire file
content = artifact.cat("path/to/file.txt")
print(content)

# Synchronous - Open file for reading
with artifact.open("path/to/file.txt", "r") as f:
    content = f.read()
    print(content)

# Asynchronous (recommended) - Read entire file
async with async_artifact:
    content = await async_artifact.cat("path/to/file.txt")
    print(content)

# Asynchronous - Open file for reading
async with async_artifact:
    async with async_artifact.open("path/to/file.txt", "r") as f:
        content = await f.read()
        print(content)
```

#### Reading a Partial File with HTTP Range

One of the key features of both `HyphaArtifact` and `AsyncHyphaArtifact` is the
ability to read only part of a file using HTTP Range headers, which is
more efficient than downloading the entire file:

```python
# Synchronous - Read only the first 10 bytes
with artifact.open("path/to/large_file.txt", "r") as f:
    partial_content = f.read(10)
    print(partial_content)

# Asynchronous (recommended) - Read only the first 10 bytes
async with async_artifact:
    async with async_artifact.open("path/to/large_file.txt", "r") as f:
        partial_content = await f.read(10)
        print(partial_content)
```

#### Copying a File

```python
# Synchronous
artifact.copy("path/to/source.txt", "path/to/destination.txt")
# You can also use the cp alias
artifact.cp("path/to/source.txt", "path/to/destination.txt")

# Asynchronous (recommended)
async with async_artifact:
    await async_artifact.copy("path/to/source.txt", "path/to/destination.txt")
    # You can also use the cp alias
    await async_artifact.cp("path/to/source.txt", "path/to/destination.txt")
```

#### Checking if a File Exists

```python
# Synchronous
exists = artifact.exists("path/to/file.txt")
print(f"File exists: {exists}")

# Asynchronous (recommended)
async with async_artifact:
    exists = await async_artifact.exists("path/to/file.txt")
    print(f"File exists: {exists}")
```

#### Listing Files

```python
# Synchronous
files = artifact.ls("/path/to/dir")
for file in files:
    print(file["name"])

# List only file names without details
file_names = artifact.ls("/path/to/dir", detail=False)
print(file_names)

# Asynchronous (recommended)
async with async_artifact:
    files = await async_artifact.ls("/path/to/dir")
    for file in files:
        print(file["name"])

    # List only file names without details
    file_names = await async_artifact.ls("/path/to/dir", detail=False)
    print(file_names)
```

#### Getting File Info

```python
# Synchronous
info = artifact.info("path/to/file.txt")
print(f"File size: {info['size']} bytes")
print(f"Last modified: {info['last_modified']}")

# Asynchronous (recommended)
async with async_artifact:
    info = await async_artifact.info("path/to/file.txt")
    print(f"File size: {info['size']} bytes")
    print(f"Last modified: {info['last_modified']}")
```

#### Removing a File

```python
# Synchronous
artifact.rm("path/to/file.txt")
# You can also use the delete alias
artifact.delete("path/to/file.txt")

# Asynchronous (recommended)
async with async_artifact:
    await async_artifact.rm("path/to/file.txt")
    # You can also use the delete alias
    await async_artifact.delete("path/to/file.txt")
```

#### Creating Directories

```python
# Synchronous
artifact.mkdir("path/to/new/dir")
# Create a directory and parent directories if they don't exist
artifact.makedirs("path/to/nested/dir")

# Asynchronous (recommended)
async with async_artifact:
    await async_artifact.mkdir("path/to/new/dir")
    # Create a directory and parent directories if they don't exist
    await async_artifact.makedirs("path/to/nested/dir")
```

### Advanced Operations

#### Finding Files

```python
# Synchronous
files = artifact.find("/path/to/dir")
print(files)

# Find files with detailed information
file_details = artifact.find("/path/to/dir", detail=True)
print(file_details)

# Asynchronous (recommended)
async with async_artifact:
    files = await async_artifact.find("/path/to/dir")
    print(files)

    # Find files with detailed information
    file_details = await async_artifact.find("/path/to/dir", detail=True)
    print(file_details)
```

#### Getting First Bytes of a File

```python
# Synchronous
head = artifact.head("path/to/file.txt", size=100)
print(head)

# Asynchronous (recommended)
async with async_artifact:
    head = await async_artifact.head("path/to/file.txt", size=100)
    print(head)
```

#### Getting File Size

```python
# Synchronous
size = artifact.size("path/to/file.txt")
print(f"File size: {size} bytes")

# Get sizes of multiple files
sizes = artifact.sizes(["file1.txt", "file2.txt"])
print(sizes)

# Asynchronous (recommended)
async with async_artifact:
    size = await async_artifact.size("path/to/file.txt")
    print(f"File size: {size} bytes")

    # Get sizes of multiple files
    sizes = await async_artifact.sizes(["file1.txt", "file2.txt"])
    print(sizes)
```

## Context Manager Usage

### Async Context Manager (Recommended)

The async version supports multiple context manager patterns:

```python
import asyncio
from hypha_artifact import AsyncHyphaArtifact

async def main():
    # Method 1: Use artifact as async context manager
    async with AsyncHyphaArtifact("example_artifact", "workspace", "token") as artifact:
        # All operations within this block
        async with artifact.open("test.txt", "w") as f:
            await f.write("Test content")
        
        content = await artifact.cat("test.txt")
        print(content)
    
    # Method 2: Manual connection management
    artifact = AsyncHyphaArtifact("example_artifact", "workspace", "token")
    async with artifact:
        # Your operations here
        files = await artifact.ls("/")
        print(files)

asyncio.run(main())
```

### Concurrent Operations

The async version excels at handling multiple operations concurrently:

```python
import asyncio
from hypha_artifact import AsyncHyphaArtifact

async def process_multiple_files():
    async with AsyncHyphaArtifact("example_artifact", "workspace", "token") as artifact:
        
        # Create multiple files concurrently
        async def create_file(index):
            async with artifact.open(f"file_{index}.txt", "w") as f:
                await f.write(f"Content for file {index}")
        
        # Run file creation concurrently
        await asyncio.gather(*[create_file(i) for i in range(5)])
        
        # Read all files concurrently
        file_contents = await asyncio.gather(*[
            artifact.cat(f"file_{i}.txt") for i in range(5)
        ])
        
        for i, content in enumerate(file_contents):
            print(f"File {i}: {content}")

asyncio.run(process_multiple_files())
```

## Error Handling

Both classes raise appropriate exceptions when operations fail:

- `FileNotFoundError`: When attempting to access a non-existent file
- `IOError`: For various I/O related errors
- `PermissionError`: For permission-related issues
- `KeyError`: When an artifact doesn't exist

### Synchronous Error Handling

```python
try:
    content = artifact.cat("non_existent_file.txt")
except FileNotFoundError as e:
    print(f"File not found: {e}")
```

### Asynchronous Error Handling

```python
async def safe_file_operation():
    async with async_artifact:
        try:
            content = await async_artifact.cat("non_existent_file.txt")
        except FileNotFoundError as e:
            print(f"File not found: {e}")
```

## Working with HTTP Range Headers

Both classes implement HTTP Range headers to efficiently fetch portions of files:

```python
# Synchronous
with artifact.open("large_file.txt", "r") as f:
    f.seek(1000)  # Move to position 1000
    data = f.read(500)  # Read 500 bytes starting from position 1000

# Asynchronous (recommended)
async with async_artifact:
    async with async_artifact.open("large_file.txt", "r") as f:
        await f.seek(1000)  # Move to position 1000
        data = await f.read(500)  # Read 500 bytes starting from position 1000
```

This is particularly useful for large files where you don't need the entire content.

## Complete Examples

### Synchronous Example

```python
from hypha_artifact import HyphaArtifact
import os
from dotenv import load_dotenv

# Load token from .env file
load_dotenv()

# Initialize artifact object
artifact = HyphaArtifact(
    artifact_alias="example_artifact", 
    workspace="your-workspace-id", 
    token="your-workspace-token"
)

# Create a test file
with artifact.open("test_folder/example_file.txt", "w") as f:
    f.write("This is a test file")

# Check if the file exists
exists = artifact.exists("test_folder/example_file.txt")
print(f"File exists: {exists}")

# List files in the test folder
files = artifact.ls("/test_folder", detail=False)
print("Files in test_folder:", files)

# Read file content
content = artifact.cat("test_folder/example_file.txt")
print(f"File content: {content}")

# Read only partial content
with artifact.open("test_folder/example_file.txt", "r") as f:
    partial = f.read(10)
    print(f"First 10 bytes: {partial}")

# Copy the file
artifact.copy("test_folder/example_file.txt", "test_folder/copy_of_example_file.txt")

# Remove the copied file
artifact.rm("test_folder/copy_of_example_file.txt")
```

### Asynchronous Example (Recommended)

```python
import asyncio
from hypha_artifact import AsyncHyphaArtifact
import os
from dotenv import load_dotenv

async def main():
    # Load token from .env file
    load_dotenv()

    # Initialize async artifact object
    async with AsyncHyphaArtifact(
        artifact_alias="example_artifact", 
        workspace="your-workspace-id", 
        token="your-workspace-token"
    ) as artifact:

        # Create a test file
        async with artifact.open("test_folder/example_file.txt", "w") as f:
            await f.write("This is a test file")

        # Check if the file exists
        exists = await artifact.exists("test_folder/example_file.txt")
        print(f"File exists: {exists}")

        # List files in the test folder
        files = await artifact.ls("/test_folder", detail=False)
        print("Files in test_folder:", files)

        # Read file content
        content = await artifact.cat("test_folder/example_file.txt")
        print(f"File content: {content}")

        # Read only partial content
        async with artifact.open("test_folder/example_file.txt", "r") as f:
            partial = await f.read(10)
            print(f"First 10 bytes: {partial}")

        # Copy the file
        await artifact.copy("test_folder/example_file.txt", "test_folder/copy_of_example_file.txt")

        # Remove the copied file
        await artifact.rm("test_folder/copy_of_example_file.txt")

# Run the async function
asyncio.run(main())
```

## Implementation Details

Both `HyphaArtifact` and `AsyncHyphaArtifact` classes use HTTP requests to
interact with the Hypha artifact service. Under the hood, they:

1. Use the `httpx` library make HTTP requests
2. Authenticate using a personal token
3. Extract workspace information from the token
4. Provide an fsspec-compatible interface for file operations
5. Use HTTP Range headers for efficient partial file reading

The async version provides better performance when:

- Handling multiple file operations concurrently
- Integrating with async web frameworks (FastAPI, aiohttp, etc.)
- Building scalable applications with many I/O operations
- Working with large files that benefit from non-blocking operations

## Best Practices

1. **Use the async version (`AsyncHyphaArtifact`) for better performance and scalability**
2. Always close file handles properly by using context managers (`with` statements)
3. Check file existence before operations to avoid errors
4. Use partial file reading with HTTP Range headers for large files
5. Use meaningful directory structures within artifacts
6. Handle errors appropriately in your application
7. For async operations, prefer concurrent execution using `asyncio.gather()`
when possible

## Advanced Configuration

Both classes can be configured with additional options if needed. These include:

- Custom artifact URLs
- Alternative authentication methods
- File encoding options

## Troubleshooting

Common issues and solutions:

1. **Authentication failures:**
   - Ensure your personal token is correctly set in the .env file
   - Check that the token has the appropriate permissions

2. **File not found errors:**
   - Verify the file path is correct (case-sensitive)
   - Check if the artifact exists and is accessible

3. **Permission issues:**
   - Ensure your token has the appropriate permissions for the operations

4. **Connection issues:**
   - Check your internet connection
   - Verify the Hypha server is accessible

5. **Async-specific issues:**
   - Ensure you're using `await` with all async operations
   - Use proper async context managers (`async with`)
   - Don't mix sync and async operations in the same context
