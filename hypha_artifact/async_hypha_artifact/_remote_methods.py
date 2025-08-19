"""Private methods for handling remote HTTP requests."""

from __future__ import annotations

from enum import StrEnum


class ArtifactMethod(StrEnum):
    """The available artifact methods."""

    PUT_FILE = "put_file"
    """Requests a pre-signed URL to upload a file to the artifact.

    The artifact must be in staging mode to upload files.

    Args:
        file_path (str): The path within the artifact where the file will be stored.
        download_weight (float): The download weight for the file (default is 1.0).

    Returns:
        str: A pre-signed URL for uploading the file.
    """

    LIST_FILES = "list_files"
    """Lists files and directories within a specified path in the artifact.

    Args:
        dir_path (str | None): The directory path within the artifact to list.
            If None, lists contents from the root of the artifact.
        limit (int): The maximum number of items to return (default is 1000).
        version (str | None): The version of the artifact to list files from.
            If None, uses the latest committed version. Can be "stage".

    Returns:
        list[dict]: A list of items (files and directories) found at the path.
            Each item is a dictionary with details like 'name', 'type', 'size'.
    """

    GET_FILE = "get_file"
    """Generates a pre-signed URL to download a file from the artifact stored in S3.

    Args:
        self (Self): The instance of the AsyncHyphaArtifact class.
        file_path (str): The relative path of the file to be downloaded
            (e.g., "data.csv").
        silent (bool, optional): A boolean to suppress the download count increment.
            Default is False.
        version (str | None, optional): The version of the artifact to download from.
        limit (int, optional): The maximum number of items to return.
            Default is 1000.

    Returns:
        str: A pre-signed URL for downloading the file.
    """

    PUT_FILE_START_MULTIPART = "put_file_start_multipart"
    """Start a multipart upload for a file.

    Args:
        file_path (str): The path within the artifact where the file will be stored.
        part_count (int): The number of parts for the multipart upload.
        expires_in (int): Expiration time in seconds (default: 7200 = 2 hours).
        download_weight (float): The download weight for the file (default is 1.0).

    Returns:
        dict: Multipart upload information including upload_id and parts.
    """

    PUT_FILE_COMPLETE_MULTIPART = "put_file_complete_multipart"
    """Complete a multipart upload.

    Args:
        upload_id (str): The upload ID from put_file_start_multipart.
        parts (list): List of completed parts with part_number and etag.
    """

    REMOVE_FILE = "remove_file"
    """Removes a file from the artifact's staged version.

    The artifact must be in staging mode. This operation updates the
    staged manifest.

    Args:
        file_path (str): The path of the file to remove within the artifact.
    """

    EDIT = "edit"
    """Edits the artifact's metadata and saves it.

    This includes the manifest, type, configuration, secrets, and versioning
    information.

    Args:
        manifest (dict[str, Any] | None): The manifest data to set for the artifact.
        type (str | None): The type of the artifact (e.g., "generic", "collection").
        config (dict[str, Any] | None): Configuration dictionary for the artifact.
        secrets (dict[str, str] | None): Secrets to store with the artifact.
        version (str | None): The version to edit or create.
            Can be "new" for a new version, "stage", or a specific version string.
        comment (str | None): A comment for this version or edit.
        stage (bool): If True, edits are made to a staging version.
    """

    COMMIT = "commit"
    """Commits the staged changes to the artifact.

    This finalizes the staged manifest and files, creating a new version or
    updating an existing one.

    Args:
        version (str | None): The version string for the commit.
            If None, a new version is typically created. Cannot be "stage".
        comment (str | None): A comment describing the commit.
    """

    DISCARD = "discard"
    """Discards all staged changes for an artifact, reverting to the last committed
        state.

    Parameters:
        artifact_id: The id of the artifact to discard changes for. Can be a UUID or
        alias.

    Returns:
        A dictionary containing the artifact reverted to its last committed state.
    """

    CREATE = "create"
    """Creates a new artifact or collection with the specified manifest."""

    DELETE = "delete"
    """Deletes an artifact, its manifest, and all associated files from both the
    database and S3 storage.

    Args:
        artifact_id (str): The id of the artifact to delete. Can be a UUID or alias.

    Returns:
        A dictionary containing the result of the delete operation.
    """

    LIST = "list"
    """Retrieve a list of child artifacts within a specified collection, supporting
        keyword-based fuzzy search, field-specific filters, and flexible ordering.
        This function allows detailed control over the search and pagination of
        artifacts in a collection, including staged artifacts if specified.

    Parameters:

        artifact_id (str): The id of the parent artifact or collection to list children
            from. It can be an uuid generated by create or edit function, or it can be
            an alias of the artifact under the current workspace. If you want to refer
            to an artifact in another workspace, you should use the full alias in the
            format of "workspace_id/alias". If not specified, the function lists all
            top-level artifacts in the current workspace.

        keywords (List[str], optional): A list of search terms used for fuzzy searching
            across all manifest fields. Each term is searched independently, and
            results matching any term will be included. For example,
            ["sample", "dataset"] returns artifacts containing either
            "sample" or "dataset" in any field of the manifest.

        filters (dict, optional): A dictionary where each key is a manifest field name
            and each value specifies the match for that field. Filters support both
            exact and range-based matching, depending on the field. You can filter
            based on the keys inside the manifest, as well as internal fields like
            permissions and view/download statistics. Supported internal
            fields include:

            type: Matches the artifact type exactly, e.g., {"type": "application"}.
            created_by: Matches the exact creator ID, e.g., {"created_by": "user123"}.
            created_at and last_modified: Accept a single timestamp (lower bound) or
                a range for filtering. For example,
                {"created_at": [1620000000, 1630000000]} filters artifacts created
                between the two timestamps.
            view_count and download_count: Accept a single value or a range for
                filtering, as with date fields. For example, {"view_count": [10, 100]}
                filters artifacts viewed between 10 and 100 times.
            permissions/<user_id>: Searches for artifacts with specific permissions
                assigned to the given user_id.
            version: Matches the exact version of the artifact, it only support
                "stage", "committed" or "*" (both staged or committed). If stage is
                specified, this filter should align with the stage parameter.
            manifest: Matches the exact value of the field, e.g.,
                "manifest": {"name": "example-dataset"}. These filters also support
                fuzzy matching if a value contains a wildcard (*),
                e.g., "manifest": {"name": "dataset*"}, depending on the SQL backend.
            config: Matches the exact value of the field in the config, e.g.,
                "config": {"collection_schema": {"type": "object"}}.

        mode (str, optional): Defines how multiple conditions
            (from keywords and filters) are combined. Use "AND" to ensure all
            conditions must match, or "OR" to include artifacts meeting any condition.
            Default is "AND".

        offset (int, optional): The number of artifacts to skip before listing results.
            Default is 0.

        limit (int, optional): The maximum number of artifacts to return.
            Default is 100.

        order_by (str, optional): The field used to order results. Options include:
            Built-in fields: view_count, download_count, last_modified, created_at,
                and id.
            Custom JSON fields: manifest.<field_name> or config.<field_name>
                (e.g., manifest.likes, config.priority).
            Use a suffix < or > to specify ascending or descending order, respectively
                (e.g., view_count< for ascending, manifest.likes> for descending).
            Default ordering is ascending by id if not specified.

        silent (bool, optional): If True, prevents incrementing the view count for
            the parent artifact when listing children. Default is False.

        stage: Controls which artifacts to return based on their staging status:
            True: Return only staged artifacts
            False: Return only committed artifacts (default)
            'all': Return both staged and committed artifacts

    Returns: A list of artifacts that match the search criteria, each represented by
        a dictionary containing all the fields."""
