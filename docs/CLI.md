# Hypha Artifact CLI

A comprehensive command-line interface for managing Hypha artifacts.

## Installation

Install the package to make the `hypha-artifact` command available:

```bash
pip install -U hypha-artifact
```

## Configuration

### Environment Variables

The CLI uses the same environment variables as the hypha-apps-cli:

- `HYPHA_SERVER_URL`: The Hypha server URL (e.g., [https://hypha.aicell.io](https://hypha.aicell.io))
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

### Artifact Management Commands

#### Edit Artifact (`edit`)

Edit artifact manifest, config, or put the artifact in staging mode:

```bash
# Put artifact in staging mode
hypha-artifact --artifact-id=my-artifact edit --stage

# Put artifact in staging mode with comment
hypha-artifact --artifact-id=my-artifact edit --stage --comment "Starting new changes"

# Edit manifest from file
hypha-artifact --artifact-id=my-artifact edit --manifest manifest.yaml

# Edit config from file  
hypha-artifact --artifact-id=my-artifact edit --config config.json

# Create new version and stage
hypha-artifact --artifact-id=my-artifact edit --version "new" --stage

# Combine manifest, config, and staging
hypha-artifact --artifact-id=my-artifact edit --manifest manifest.yaml --config config.json --stage --comment "Major update"
```

**Options:**

- `--manifest PATH`: Path to manifest YAML/JSON file to update
- `--config PATH`: Path to config YAML/JSON file to update
- `--version VERSION`: Version to edit (or 'new' to create new version)
- `--stage`: Put artifact in staging mode for file modifications
- `--comment COMMENT`: Comment describing the changes

**Note:** Most file operations (upload, copy, remove) require the artifact to be in staging mode first.

#### Commit Changes (`commit`)

Commit staged changes to create a permanent version:

```bash
# Commit staged changes
hypha-artifact --artifact-id=my-artifact commit

# Commit with comment
hypha-artifact --artifact-id=my-artifact commit --comment "Added new dataset"

# Commit with specific version name
hypha-artifact --artifact-id=my-artifact commit --version "v1.2.0"

# Commit with both version and comment
hypha-artifact --artifact-id=my-artifact commit --version "release-2024" --comment "Production release"
```

**Options:**

- `--version VERSION`: Custom version name for the commit, if not provided, the system will determine it as "v1", "v2", etc.
- `--comment COMMENT`: Comment describing the commit

#### Discard Changes (`discard`)

Discard staged changes without committing:

```bash
# Discard all staged changes
hypha-artifact --artifact-id=my-artifact discard
```

This will revert the artifact to its last committed state, discarding all staged modifications.

### File Browsing Commands

#### List Files (`ls`)

List files and directories in an artifact:

```bash
# List root directory
hypha-artifact --artifact-id=my-artifact ls

# List specific directory
hypha-artifact --artifact-id=my-artifact ls /data

# List with names only (no details)
hypha-artifact --artifact-id=my-artifact ls --no-detail /

# List files from staged version
hypha-artifact --artifact-id=my-artifact ls --stage /
```

**Options:**

- `path`: Path to list (default: `/`)
- `--detail`: Show detailed information (default)
- `--no-detail`: Show names only
- `--stage`: List files from staged version instead of committed version

#### Display File Contents (`cat`)

Display the contents of files:

```bash
# Display single file
hypha-artifact --artifact-id=my-artifact cat /data.txt

# Display multiple files
hypha-artifact --artifact-id=my-artifact cat /file1.txt /file2.txt

# Recursively display all files in directory
hypha-artifact --artifact-id=my-artifact cat --recursive /data/

# Display from staged version
hypha-artifact --artifact-id=my-artifact cat --stage /data.txt
```

**Options:**

- `path`: File path to display
- `paths`: Additional file paths
- `-r, --recursive`: Recursively display directory contents
- `--stage`: Read file from staged version

#### File Head (`head`)

Show the first bytes of a file:

```bash
# Show first 1024 bytes (default)
hypha-artifact --artifact-id=my-artifact head /data.txt

# Show first 500 bytes
hypha-artifact --artifact-id=my-artifact head --bytes=500 /data.txt

# Show from staged version
hypha-artifact --artifact-id=my-artifact head --stage /data.txt
```

**Options:**

- `path`: File path
- `-n, --bytes`: Number of bytes to show (default: 1024)
- `--stage`: Read file from staged version

### File Operations Commands

#### Copy Files (`cp`)

Copy files or directories within an artifact:

```bash
# Copy file (requires staging mode)
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

**Note:** Requires artifact to be in staging mode. Use `edit --stage` first.

#### Remove Files (`rm`)

Remove files or directories:

```bash
# Remove files (requires staging mode)
hypha-artifact --artifact-id=my-artifact rm /file1.txt /file2.txt

# Remove directory recursively
hypha-artifact --artifact-id=my-artifact rm --recursive /directory
```

**Options:**

- `paths`: Paths to remove
- `-r, --recursive`: Remove directories recursively

**Note:** Requires artifact to be in staging mode. Use `edit --stage` first.

#### Create Directories (`mkdir`)

Create directories:

```bash
# Create directories (requires staging mode)
hypha-artifact --artifact-id=my-artifact mkdir /new-dir /another-dir

# Create with parent directories
hypha-artifact --artifact-id=my-artifact mkdir --parents /deep/nested/dir
```

**Options:**

- `paths`: Directory paths to create
- `-p, --parents`: Create parent directories (default: true)

**Note:** Requires artifact to be in staging mode. Use `edit --stage` first.

### File Information Commands

#### File Information (`info`)

Get detailed information about files or directories:

```bash
# Get info for single file
hypha-artifact --artifact-id=my-artifact info /data.txt

# Get info for multiple files
hypha-artifact --artifact-id=my-artifact info /file1.txt /dir1
```

**Options:**

- `paths`: Paths to get information for

#### Find Files (`find`)

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

#### File Size (`size`)

Get file sizes:

```bash
# Get size of single file
hypha-artifact --artifact-id=my-artifact size /data.txt

# Get sizes of multiple files
hypha-artifact --artifact-id=my-artifact size /file1.txt /file2.txt
```

**Options:**

- `paths`: File paths

#### Check Existence (`exists`)

Check if paths exist:

```bash
# Check single path
hypha-artifact --artifact-id=my-artifact exists /data.txt

# Check multiple paths
hypha-artifact --artifact-id=my-artifact exists /file1.txt /dir1 /missing.txt
```

**Options:**

- `paths`: Paths to check

### File Transfer Commands

#### Upload Files and Folders (`upload`)

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

**Note:** Uploads automatically handle staging, but you may need to commit changes afterward.

#### Download Files (`download`)

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

## Workflow Examples

### Basic Workflow

```bash
# 1. Put artifact in staging mode
hypha-artifact --artifact-id=my-data edit --stage

# 2. Upload files
hypha-artifact --artifact-id=my-data upload data.csv /datasets/data.csv

# 3. Make modifications
hypha-artifact --artifact-id=my-data cp /datasets/data.csv /backup/data-backup.csv

# 4. Commit changes
hypha-artifact --artifact-id=my-data commit --comment "Added dataset and backup"
```

### Working with Versions

```bash
# Create a new version and stage it
hypha-artifact --artifact-id=my-project edit --version "v2.0.0" --stage --comment "Starting v2.0"

# Make changes
hypha-artifact --artifact-id=my-project upload new-features/ /features/

# Commit with version info
hypha-artifact --artifact-id=my-project commit --version "v2.0.0" --comment "Released version 2.0"
```

### Discarding Changes

```bash
# Start making changes
hypha-artifact --artifact-id=my-data edit --stage
hypha-artifact --artifact-id=my-data upload test-file.txt /

# Decide to discard instead of committing
hypha-artifact --artifact-id=my-data discard
```

### Working with Configuration

```bash
# Update both manifest and config
hypha-artifact --artifact-id=my-model edit --manifest model-manifest.yaml --config model-config.json --stage

# Upload model files
hypha-artifact --artifact-id=my-model upload model.pkl /models/model.pkl

# Commit everything
hypha-artifact --artifact-id=my-model commit --comment "Updated model with new config"
```

## Advanced Usage Examples

### Batch Operations

```bash
# Upload multiple files
for file in *.csv; do
  hypha-artifact --artifact-id=my-data upload "$file" "/datasets/$file"
done

# Check existence of multiple files
hypha-artifact --artifact-id=my-data exists /config.json /data.csv /model.pkl
```

### Large File Handling

```bash
# Upload large files with optimized settings
hypha-artifact --artifact-id=my-data upload --enable-multipart --chunk-size=20971520 large-dataset.tar.gz /data/

# Upload entire large project
hypha-artifact --artifact-id=my-data upload --enable-multipart ./large-ml-project /projects/ml-project
```

### Staged vs Committed Content

```bash
# View committed version
hypha-artifact --artifact-id=my-data ls /
hypha-artifact --artifact-id=my-data cat /config.json

# Make changes in staging
hypha-artifact --artifact-id=my-data edit --stage
hypha-artifact --artifact-id=my-data upload new-config.json /config.json

# View staged version
hypha-artifact --artifact-id=my-data ls --stage /
hypha-artifact --artifact-id=my-data cat --stage /config.json

# Compare the two versions before committing
diff <(hypha-artifact --artifact-id=my-data cat /config.json) <(hypha-artifact --artifact-id=my-data cat --stage /config.json)
```

## Error Handling

The CLI provides clear error messages and helpful suggestions:

- ❌ **Missing environment variables**: Clear instructions on what to set
- ❌ **File not found**: Specific path information
- ❌ **Staging required**: Suggestions to use `edit --stage` first
- ❌ **Permission denied**: Authentication troubleshooting
- ❌ **Network errors**: Connection troubleshooting
- ✅ **Success confirmations**: Clear feedback on completed operations

Common error scenarios:

```bash
# Trying to modify without staging
$ hypha-artifact --artifact-id=my-data upload file.txt /
❌ Error uploading: Artifact must be in staging mode
💡 This operation requires the artifact to be in staging mode.
   Use: hypha-artifact --artifact-id=my-data edit --stage

# Missing credentials
$ hypha-artifact --artifact-id=my-data ls /
❌ Missing HYPHA_TOKEN environment variable
```

## Tips and Best Practices

1. **Always stage before modifications**: Use `edit --stage` before upload, copy, or remove operations
2. **Use meaningful commit messages**: Include `--comment` with your commits for better tracking
3. **Version your important changes**: Use `--version` for significant updates
4. **Check before committing**: Use `--stage` flag with `ls` and `cat` to preview changes
5. **Use .env files**: Store credentials safely in a `.env` file
6. **Combine operations**: Chain commands for complex workflows
7. **Use multipart for large files**: Enable `--enable-multipart` for files over 100MB
8. **Verify uploads**: Use `exists` and `size` commands to verify successful transfers
