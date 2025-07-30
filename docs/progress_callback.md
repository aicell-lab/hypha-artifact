# Progress Callback Feature

The `AsyncHyphaArtifact` class now supports progress callbacks for the `get` and `put` methods, allowing you to monitor the progress of file uploads and downloads with real-time feedback.

## Overview

The progress callback feature provides detailed information about file operations, including:
- Current operation status (info, success, error, warning)
- File being processed
- Progress indicators (current file / total files)
- Error messages with context

## Usage

### Basic Progress Callback Function

```python
def progress_callback(info: Dict[str, Any]):
    emoji = {
        "info": "ℹ️",
        "success": "✅", 
        "error": "❌",
        "warning": "⚠️",
    }.get(info.get("type", ""), "🔸")
    print(f"{emoji} {info.get('message', '')}")
```

### Using with get() method

```python
import asyncio
from hypha_artifact import AsyncHyphaArtifact

async def download_with_progress():
    async with AsyncHyphaArtifact("my-artifact", "workspace", "token") as artifact:
        await artifact.get(
            rpath="/remote/path",
            lpath="/local/path", 
            recursive=True,
            progress_callback=progress_callback
        )
```

### Using with put() method

```python
async def upload_with_progress():
    async with AsyncHyphaArtifact("my-artifact", "workspace", "token") as artifact:
        await artifact.edit(stage=True)
        await artifact.put(
            lpath="/local/path",
            rpath="/remote/path",
            recursive=True,
            progress_callback=progress_callback
        )
        await artifact.commit(comment="Uploaded with progress tracking")
```

## Callback Information

The progress callback receives a dictionary with the following keys:

| Key | Type | Description |
|-----|------|-------------|
| `type` | str | Message type: "info", "success", "error", or "warning" |
| `message` | str | Human-readable progress message |
| `file` | str | Current file being processed (if applicable) |
| `total_files` | int | Total number of files to process (if applicable) |
| `current_file` | int | Current file index (if applicable) |

## Example Output

```
ℹ️ Starting recursive upload from /local/path
ℹ️ Found 4 files to upload [0/4]
ℹ️ Uploading file 1/4: data/file1.csv [1/4] (data/file1.csv)
✅ Successfully uploaded: data/file1.csv (data/file1.csv)
ℹ️ Uploading file 2/4: data/file2.json [2/4] (data/file2.json)
✅ Successfully uploaded: data/file2.json (data/file2.json)
❌ Failed to upload data/file3.txt: File not found (data/file3.txt)
⚠️ Skipping data/file4.txt due to permissions (data/file4.txt)
```

## Advanced Usage

### Custom Progress Display

You can create custom progress displays by using the callback information:

```python
def custom_progress_callback(info: Dict[str, Any]):
    if info.get("type") == "info" and info.get("total_files"):
        current = info.get("current_file", 0)
        total = info.get("total_files", 0)
        if current > 0:
            percentage = (current / total) * 100
            print(f"Progress: {percentage:.1f}% ({current}/{total})")
    
    # Always show the message
    print(f"{info.get('message', '')}")
```

### Progress Bar Integration

```python
from tqdm import tqdm

class ProgressTracker:
    def __init__(self):
        self.pbar = None
        self.total_files = 0
    
    def callback(self, info: Dict[str, Any]):
        if info.get("type") == "info" and info.get("total_files"):
            self.total_files = info.get("total_files")
            self.pbar = tqdm(total=self.total_files, desc="Processing files")
        
        if info.get("type") == "success" and self.pbar:
            self.pbar.update(1)
        
        if info.get("type") == "error":
            print(f"❌ Error: {info.get('message')}")
    
    def close(self):
        if self.pbar:
            self.pbar.close()

# Usage
tracker = ProgressTracker()
await artifact.get(rpath="/remote", lpath="/local", progress_callback=tracker.callback)
tracker.close()
```

## Error Handling

The progress callback will be called with error information when operations fail:

```python
def error_aware_callback(info: Dict[str, Any]):
    if info.get("type") == "error":
        # Log error or take corrective action
        print(f"ERROR: {info.get('message')} for file {info.get('file')}")
    else:
        # Normal progress display
        print(f"{info.get('message')}")
```
