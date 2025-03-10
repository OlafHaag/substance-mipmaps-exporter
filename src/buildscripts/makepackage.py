"""This module is used to build the plugin file."""

import fnmatch
import json
import logging
import os
import sys
from collections.abc import Generator
from pathlib import Path
from zipfile import ZipFile

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def get_repository_root() -> Path:
    """Find the root of the repository by looking for the .git directory."""
    this_dir = Path(__file__).resolve().parent
    try:
        return next(parent for parent in this_dir.parents if (parent / ".git").exists())
    except StopIteration:
        msg = "Error while finding repository root."
        raise FileNotFoundError(msg) from None


class IgnoreFileFilter:
    """
    This class is used to filter files based on an ignore file.

    It will ignore files that match the patterns in the file.
    """

    def __init__(self, filename: str | Path) -> None:
        self.__globs = []
        self.__dirs_to_ignore = []

        self._ignore_file_path = Path(filename)
        if not self._ignore_file_path.exists():
            logging.error(f"Ignore file {filename} does not exist")
            msg = f"Ignore file {filename} does not exist"
            raise FileNotFoundError(msg)

        # Read the ignore file and ignore empty lines and comments.
        lines = [
            exclusion
            for line in self._ignore_file_path.read_text().splitlines()
            if (exclusion := line.strip()) and not exclusion.startswith("#")
        ]
        for line in lines:
            if line.endswith("/"):
                self.__dirs_to_ignore.append(line[:-1])
            else:
                self.__globs.append(line)

    def filter(self, filepath: str | Path) -> bool:
        """
        Determine if a file should be included based on ignore patterns.

        :param filepath: The path of the file to check.
        :return: True if the file should be included, otherwise False.
        """
        filepath = Path(filepath).resolve()

        # Ignore the ignore file itself.
        if filepath == self._ignore_file_path.resolve():
            return False

        filename = filepath.name
        dirs = set(filepath.parts)

        # Check if the file matches any glob pattern or is in any ignored directory.
        return not any(fnmatch.fnmatch(filename, pattern) for pattern in self.__globs) and all(
            pattern not in dirs for pattern in self.__dirs_to_ignore
        )


def read_metadata(metadata_file: str | Path) -> dict[str, str]:
    """
    Read the metadata from the pluginInfo.json file.

    :return: The metadata as a dictionary if the file exists and is proper json.
    """
    metadata_file = Path(metadata_file)
    try:
        with metadata_file.open() as f:
            return json.load(f)
    except Exception as e:
        msg = f"Error while reading metadata: {e}"
        raise OSError(msg) from e


def check_metadata(metadata: dict[str, str]) -> None:
    """
    Check if the metadata contains the required "name" entry.

    :param metadata: The metadata dictionary to check.
    :return: True if the "name" entry is present, otherwise False.
    """
    if "name" not in metadata:
        logging.error('"name" metadata entry is missing')
        msg = '"name" metadata entry is missing'
        raise ValueError(msg)


def walk(directory: str | Path) -> Generator[Path, None, None]:
    """
    Walk through the directory and yield file paths.

    :param directory: The directory to walk through.
    :return: Yields file paths.
    """
    for path in Path(directory).rglob("*"):
        if path.is_file():
            yield path


def add_file_to_package(
    zfile: ZipFile, filepath: str | Path, strip_path: str | Path, archive_folder: str | None = None
) -> None:
    """
    Add a file to the package zip file.

    :param zfile: The zip file object.
    :param filepath: The path of the file to add.
    :param strip_path: The base directory to strip from the file path in the archive. Keep rest as relative path.
    :param archive_folder: The name of the folder in the archive to place the file into. If None, then root.
    :raises ValueError: If the archive folder is not a valid identifier.
    :raises OSError: If an error occurs while adding the file to the package.
    """
    logging.info(f"Adding file {filepath} to package")
    # Check that the archive folder can be used as a directory name.
    if archive_folder and not archive_folder.isidentifier():
        msg = (
            f"Invalid archive folder name: {archive_folder}. "
            "Must be a valid identifier, so it can be used as a directory name."
        )
        logging.error(msg)
        raise ValueError(msg)
    # Create the path for the file in the zip archive.
    if archive_folder:
        archive_filepath = Path(archive_folder) / Path(filepath).relative_to(strip_path)
    else:
        archive_filepath = Path(filepath).relative_to(strip_path)
    try:
        zfile.write(filepath, arcname=str(archive_filepath))
    except OSError as e:
        msg = f"Error adding file {filepath} to package: {e}"
        logging.error(msg)
        raise


def package_plugin(plugin_dir: Path, extra_files: list[str | Path] | None = None) -> None:
    """Create the plugin package.

    The structure of a package has to be:
    <plugin_name>.sdplugin/
        ├── <plugin_folder>/
            ├── pluginInfo.json
            ├── <extra files>
            ├── <python_pkg>/
                ├── __init__.py
                ├── <plugin files>

    :param plugin_dir: The directory of the plugin to package.
    :param extra_files: List of extra files to include in the package's root.
    :raises RuntimeError: If an error occurs while creating the package.
    :raises FileNotFoundError: If the plugin directory does not exist.
    :raises ValueError: If the plugin name is not a valid identifier.
    :raises OSError: If an error occurs while reading the metadata or creating the package.
    :raises Exception: If an unexpected error occurs.
    """
    error_msg = "Error while creating package. Check the logs for more details."
    try:
        repo_root = get_repository_root()
        dist_dir = repo_root / "dist"
    except FileNotFoundError as e:
        logging.error(e)
        raise RuntimeError(error_msg) from e

    try:
        dist_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logging.error(f"Error creating dist directory: {e}")
        raise RuntimeError(error_msg) from e

    # Save the current dir and switch to the package dir.
    saved_dir = Path.cwd()

    package_filepath = dist_dir / f"{plugin_dir.name}.sdplugin"

    try:
        file_filter = IgnoreFileFilter(repo_root / ".sdpackageignore")
    except FileNotFoundError as e:
        logging.error(e)
        raise RuntimeError(error_msg) from e

    extra_files = extra_files or []
    try:
        with ZipFile(package_filepath, "w") as zfile:
            for filepath in walk(plugin_dir):
                if file_filter.filter(filepath):
                    add_file_to_package(zfile, filepath, plugin_dir.parent, plugin_dir.name)
            for extra_file in extra_files:
                extra_file_path = Path(extra_file).absolute()
                if extra_file_path.exists():
                    add_file_to_package(zfile, extra_file_path, repo_root.absolute(), plugin_dir.name)
                else:
                    msg = f"Extra file {extra_file} not found."
                    raise FileNotFoundError(msg)
    except (ValueError, OSError) as e:
        logging.error(f"Error while packaging plugin: {e}")
        raise RuntimeError(error_msg) from e
    finally:
        # Restore the saved directory.
        os.chdir(saved_dir)


if __name__ == "__main__":
    root_dir = get_repository_root()
    try:
        metadata_file = root_dir / "pluginInfo.json"
        if not metadata_file.exists():
            msg = f"{metadata_file} not found."
            raise FileNotFoundError(msg)
        metadata = read_metadata(metadata_file)
        check_metadata(metadata)
    except (OSError, ValueError) as e:
        logging.error(e)
        sys.exit(1)
    try:
        # Simply build the path to the plugin, as using importlib would require the package to be imported.
        plugin_dir = root_dir / "src" / "custommipmapsexport"
        package_plugin(plugin_dir, [metadata_file, "README.md", "LICENSE"])
    except (ValueError, OSError, RuntimeError) as e:
        logging.error(e)
        sys.exit(1)
