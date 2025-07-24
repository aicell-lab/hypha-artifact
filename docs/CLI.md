# Hypha Artifact CLI

A comprehensive command-line interface for managing Hypha artifacts.

## Installation

Install the package to make the `hypha-artifact` command available:

```bash
pip install -e .
```

## Configuration

### Environment Variables

The CLI uses the same environment variables as the hypha-apps-cli:

- `HYPHA_SERVER_URL`: The Hypha server URL (e.g., https://hypha.aicell.io)
- `HYPHA_TOKEN`: Your authentication token
- `HYPHA_WORKSPACE`: Your workspace name
- `HYPHA_CLIENT_ID`: Optional client ID (defaults to "hypha-artifact-cli")

### Setup

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your values:
   ```bash
   HYPHA_SERVER_URL=https://hypha.aicell.io
   HYPHA_TOKEN=your_token_here
   HYPHA_WORKSPACE=your_workspace_name
   ```

3. Get your token from the Hypha server dashboard under "My Workspace" → "Development" tab.

## Usage

The general command format is:

```bash
hypha-artifact --artifact-id=ARTIFACT_ID [GLOBAL_OPTIONS] COMMAND [COMMAND_OPTIONS]
```

### Global Options

- `--artifact-id ARTIFACT_ID`: Required. The artifact ID (can include workspace: `workspace/artifact`)
- `--workspace WORKSPACE`: Optional. Override workspace from environment
- `--token TOKEN`: Optional. Override token from environment  
- `--server-url SERVER_URL`: Optional. Override server URL from environment

## Commands

### List Files (`ls`)

List files and directories in an artifact:

```bash
# List root directory
hypha-artifact --artifact-id=my-artifact ls

# List specific directory
hypha-artifact --artifact-id=my-artifact ls /data

# List with names only (no details)
hypha-artifact --artifact-id=my-artifact ls --no-detail /
```

**Options:**
- `path`: Path to list (default: `/`)
- `--detail`: Show detailed information (default)
- `--no-detail`: Show names only

### Display File Contents (`cat`)

Display the contents of files:

```bash
# Display single file
hypha-artifact --artifact-id=my-artifact cat /data.txt

# Display multiple files
hypha-artifact --artifact-id=my-artifact cat /file1.txt /file2.txt

# Recursively display all files in directory
hypha-artifact --artifact-id=my-artifact cat --recursive /data/
```

**Options:**
- `path`: File path to display
- `paths`: Additional file paths
- `-r, --recursive`: Recursively display directory contents

### Copy Files (`cp`)

Copy files or directories within an artifact:

```bash
# Copy file
hypha-artifact --artifact-id=my-artifact cp /source.txt /destination.txt

# Copy directory recursively
hypha-artifact --artifact-id=my-artifact cp --recursive /src-dir /dst-dir

# Copy with maximum depth limit
hypha-artifact --artifact-id=my-artifact cp --recursive --maxdepth=2 /src /dst
```

**Options:**
- `source`: Source path
- `destination`: Destination path
- `-r, --recursive`: Copy directories recursively
- `--maxdepth`: Maximum recursion depth

### Remove Files (`rm`)

Remove files or directories:

```bash
# Remove files
hypha-artifact --artifact-id=my-artifact rm /file1.txt /file2.txt

# Remove directory recursively
hypha-artifact --artifact-id=my-artifact rm --recursive /directory
```

**Options:**
- `paths`: Paths to remove
- `-r, --recursive`: Remove directories recursively

### Create Directories (`mkdir`)

Create directories (note: in Hypha artifacts, directories are created implicitly):

```bash
# Create directories
hypha-artifact --artifact-id=my-artifact mkdir /new-dir /another-dir

# Create with parent directories
hypha-artifact --artifact-id=my-artifact mkdir --parents /deep/nested/dir
```

**Options:**
- `paths`: Directory paths to create
- `-p, --parents`: Create parent directories (default: true)

### File Information (`info`)

Get detailed information about files or directories:

```bash
# Get info for single file
hypha-artifact --artifact-id=my-artifact info /data.txt

# Get info for multiple files
hypha-artifact --artifact-id=my-artifact info /file1.txt /dir1
```

**Options:**
- `paths`: Paths to get information for

### Find Files (`find`)

Find files recursively:

```bash
# Find all files from root
hypha-artifact --artifact-id=my-artifact find

# Find files in specific directory
hypha-artifact --artifact-id=my-artifact find /data

# Find with directories included
hypha-artifact --artifact-id=my-artifact find --include-dirs /

# Find with detailed information
hypha-artifact --artifact-id=my-artifact find --detail /

# Find with maximum depth
hypha-artifact --artifact-id=my-artifact find --maxdepth=3 /
```

**Options:**
- `path`: Base path to search from (default: `/`)
- `--maxdepth`: Maximum recursion depth
- `--include-dirs`: Include directories in results
- `--detail`: Show detailed information

### File Head (`head`)

Show the first bytes of a file:

```bash
# Show first 1024 bytes (default)
hypha-artifact --artifact-id=my-artifact head /data.txt

# Show first 500 bytes
hypha-artifact --artifact-id=my-artifact head --bytes=500 /data.txt
```

**Options:**
- `path`: File path
- `-n, --bytes`: Number of bytes to show (default: 1024)

### File Size (`size`)

Get file sizes:

```bash
# Get size of single file
hypha-artifact --artifact-id=my-artifact size /data.txt

# Get sizes of multiple files
hypha-artifact --artifact-id=my-artifact size /file1.txt /file2.txt
```

**Options:**
- `paths`: File paths

### Check Existence (`exists`)

Check if paths exist:

```bash
# Check single path
hypha-artifact --artifact-id=my-artifact exists /data.txt

# Check multiple paths
hypha-artifact --artifact-id=my-artifact exists /file1.txt /dir1 /missing.txt
```

**Options:**
- `paths`: Paths to check

### Upload Files and Folders (`upload`)

Upload local files or folders to the artifact with optional multipart support for large files:

```bash
# Upload file with same name
hypha-artifact --artifact-id=my-artifact upload local-file.txt

# Upload file with different name
hypha-artifact --artifact-id=my-artifact upload local-file.txt /remote-name.txt

# Upload to directory
hypha-artifact --artifact-id=my-artifact upload document.pdf /documents/document.pdf

# Upload entire folder to root
hypha-artifact --artifact-id=my-artifact upload ./my-project

# Upload folder to specific remote path
hypha-artifact --artifact-id=my-artifact upload ./my-project /projects/my-project

# Upload only files (no subdirectories)
hypha-artifact --artifact-id=my-artifact upload --no-recursive ./flat-folder /data/

# Force multipart upload for any file
hypha-artifact --artifact-id=my-artifact upload --enable-multipart large-file.zip /data/

# Upload with multipart for large files in folder
hypha-artifact --artifact-id=my-artifact upload --enable-multipart ./large-dataset /datasets/

# Customize multipart settings
hypha-artifact --artifact-id=my-artifact upload --multipart-threshold=50000000 --chunk-size=5000000 big-file.tar.gz /backups/
```

**Options:**
- `local_path`: Local file or folder path to upload
- `remote_path`: Remote path in artifact (optional, defaults to same name)
- `--recursive`: Upload subdirectories recursively when uploading folders (default: true)
- `--no-recursive`: Don't upload subdirectories
- `--enable-multipart`: Force multipart upload even for small files
- `--multipart-threshold`: File size threshold for automatic multipart upload in bytes (default: 100MB)
- `--chunk-size`: Size of each part in multipart upload in bytes (default: 10MB)

### Download Files (`download`) 

Download files from the artifact to local filesystem:

```bash
# Download file with same name
hypha-artifact --artifact-id=my-artifact download /data.txt

# Download file with different name
hypha-artifact --artifact-id=my-artifact download /data.txt local-data.txt

# Download from directory
hypha-artifact --artifact-id=my-artifact download /documents/report.pdf ./report.pdf
```

**Options:**
- `remote_path`: Remote file path in artifact
- `local_path`: Local file path (optional, defaults to same name)

## Examples

### Basic File Operations

```bash
# Set up environment
export HYPHA_SERVER_URL=https://hypha.aicell.io
export HYPHA_TOKEN=your_token
export HYPHA_WORKSPACE=your_workspace

# List artifact contents
hypha-artifact --artifact-id=my-data ls /

# Upload a local file
hypha-artifact --artifact-id=my-data upload data.csv /datasets/data.csv

# View file contents
hypha-artifact --artifact-id=my-data cat /datasets/data.csv

# Copy file within artifact
hypha-artifact --artifact-id=my-data cp /datasets/data.csv /backup/data-backup.csv

# Download file
hypha-artifact --artifact-id=my-data download /datasets/data.csv ./local-data.csv

# Remove file
hypha-artifact --artifact-id=my-data rm /backup/data-backup.csv
```

### Working with Directories

```bash
# Create directory structure
hypha-artifact --artifact-id=my-data mkdir /projects/analysis /projects/results

# Upload multiple files
hypha-artifact --artifact-id=my-data upload script.py /projects/analysis/script.py
hypha-artifact --artifact-id=my-data upload results.json /projects/results/results.json

# Find all Python files
hypha-artifact --artifact-id=my-data find / | grep "\.py$"

# Copy entire directory
hypha-artifact --artifact-id=my-data cp --recursive /projects /archive/projects-backup

# List directory with details
hypha-artifact --artifact-id=my-data ls --detail /projects
```

### Advanced Usage

```bash
# Get detailed information about files
hypha-artifact --artifact-id=my-data info /datasets/data.csv /projects/script.py

# Find files with size information
hypha-artifact --artifact-id=my-data find --detail / | grep "file"

# Check if multiple files exist
hypha-artifact --artifact-id=my-data exists /config.json /data.csv /missing.txt

# Get file sizes
hypha-artifact --artifact-id=my-data size /datasets/data.csv /projects/results.json

# Preview file contents
hypha-artifact --artifact-id=my-data head --bytes=200 /datasets/data.csv

# Upload large files with multipart
hypha-artifact --artifact-id=my-data upload --enable-multipart --chunk-size=20971520 large-model.bin /models/

# Upload entire project folder
hypha-artifact --artifact-id=my-data upload ./my-ml-project /projects/ml-project --enable-multipart

# Upload only specific file types from folder (using shell)
find ./data -name "*.csv" -exec hypha-artifact --artifact-id=my-data upload {} /datasets/ \;
```

### Using with Different Workspaces

```bash
# Override workspace
hypha-artifact --artifact-id=shared-data --workspace=public-workspace ls /

# Use workspace in artifact ID
hypha-artifact --artifact-id=public-workspace/shared-data ls /

# Override multiple parameters
hypha-artifact --workspace=test --token=test-token --artifact-id=test-data ls /
```

## Error Handling

The CLI provides clear error messages:

- ❌ Missing environment variables
- ❌ File not found
- ❌ Permission denied  
- ❌ Network errors
- ✅ Success confirmations

## Tips

1. **Use .env files**: Store your credentials safely in a `.env` file in your project directory
2. **Tab completion**: Most shells support tab completion for command and file names
3. **Batch operations**: Use shell loops for batch operations:
   ```bash
   for file in *.txt; do
     hypha-artifact --artifact-id=my-data upload "$file" "/uploads/$file"
   done
   ```
4. **Combine with other tools**: Pipe CLI output to other commands:
   ```bash
   hypha-artifact --artifact-id=my-data ls --no-detail / | grep "\.csv$"
   ``` 