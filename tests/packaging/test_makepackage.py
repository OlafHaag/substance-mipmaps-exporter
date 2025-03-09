from pathlib import Path
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

import pytest

from buildscripts.makepackage import (
    IgnoreFileFilter,
    add_file_to_package,
    check_metadata,
    get_repository_root,
    package_plugin,
    read_metadata,
    walk,
)


class TestReadMetadata:
    """Test suite for the read_metadata function."""

    @pytest.fixture
    def tmp_metadata_file(self, tmp_path: Path) -> Path:
        """Fixture to create a temporary metadata file."""
        return tmp_path / "pluginInfo.json"

    def test_valid(self, tmp_metadata_file: Path) -> None:
        """Test reading valid metadata."""
        # Arrange
        tmp_metadata_file.write_text('{"name": "test_plugin", "version": "1.0.0"}')

        # Act
        metadata = read_metadata(tmp_metadata_file)

        # Assert
        assert metadata == {"name": "test_plugin", "version": "1.0.0"}

    def test_invalid_json(self, tmp_metadata_file: Path) -> None:
        """Test reading invalid JSON metadata."""
        # Arrange
        tmp_metadata_file.write_text("{invalid_json}")

        # Act & Assert
        with pytest.raises(OSError):
            read_metadata(tmp_metadata_file)

    def test_missing_file(self, tmp_metadata_file: Path) -> None:
        """Test reading metadata from a missing file."""
        # Act & Assert
        with pytest.raises(OSError):
            read_metadata(tmp_metadata_file)

    def test_empty_file(self, tmp_metadata_file: Path) -> None:
        """Test reading metadata from an empty file."""
        # Arrange
        tmp_metadata_file.write_text("")

        # Act & Assert
        with pytest.raises(OSError):
            read_metadata(tmp_metadata_file)


class TestCheckMetadata:
    """Test suite for the check_metadata function."""

    def test_missing_name(self) -> None:
        """Test checking metadata when the name is missing."""
        # Arrange
        metadata = {"version": "1.0.0"}

        # Act & Assert
        with pytest.raises(ValueError):
            check_metadata(metadata)


class TestIgnoreFileFilter:
    """Test suite for the IgnoreFileFilter class."""

    @pytest.fixture
    def tmp_ignore_file(self, tmp_path: Path) -> Path:
        """Fixture to create a temporary ignore file."""
        ignore_file = tmp_path / ".sdpackageignore"
        ignore_file.write_text("*.pyc\n__pycache__/\ndebug.py\n")
        return ignore_file

    def test_includes_non_ignored_files(self, tmp_ignore_file: Path) -> None:
        """Test that IgnoreFileFilter includes non-ignored files."""
        self._test_ignore_file_inclusion_exclusion(tmp_ignore_file, "test.txt", True)

    @pytest.mark.parametrize(
        "filename, expected",
        [("test.pyc", False), ("debug.py", False)],
        ids=["ignored file: test.pyc", "ignored file: debug.py"],
    )
    def test_excludes_ignored_files(self, tmp_ignore_file: Path, filename: str, expected: bool) -> None:
        """Test that IgnoreFileFilter excludes ignored files."""
        self._test_ignore_file_inclusion_exclusion(tmp_ignore_file, filename, expected=expected)

    def _test_ignore_file_inclusion_exclusion(self, tmp_ignore_file: Path, filename: str, expected: bool) -> None:
        """Test that IgnoreFileFilter includes or excludes files based on the ignore file."""
        ignore_filter = IgnoreFileFilter(tmp_ignore_file)
        file_path = tmp_ignore_file.parent / filename

        # Act
        result = ignore_filter.filter(file_path)

        # Assert
        assert result is expected

    def test_excludes_ignored_directories(self, tmp_ignore_file: Path) -> None:
        """Test that IgnoreFileFilter excludes ignored directories."""
        # Arrange
        ignore_filter = IgnoreFileFilter(tmp_ignore_file)
        ignored_directory = tmp_ignore_file.parent / "__pycache__" / "test.py"

        # Act
        result = ignore_filter.filter(ignored_directory)

        # Assert
        assert result is False

    def test_includes_ignore_file_itself(self, tmp_ignore_file: Path) -> None:
        """Test that IgnoreFileFilter includes the ignore file itself."""
        # Arrange
        ignore_filter = IgnoreFileFilter(tmp_ignore_file)

        # Act
        result = ignore_filter.filter(tmp_ignore_file)

        # Assert
        assert result is False


class TestWalk:
    """Test suite for the walk function."""

    def test_walk_includes_files(self, tmp_path: Path) -> None:
        """Test that walk includes files."""
        # Arrange
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.touch()
        file2.touch()

        # Act
        result = list(walk(tmp_path))

        # Assert
        assert file1 in result
        assert file2 in result

    def test_walk_excludes_directories(self, tmp_path: Path) -> None:
        """Test that walk excludes directories."""
        # Arrange
        dir1 = tmp_path / "dir1"
        dir1.mkdir()
        file1 = dir1 / "file1.txt"
        file1.touch()

        # Act
        result = list(walk(tmp_path))

        # Assert
        assert file1 in result
        assert dir1 not in result

    def test_walk_includes_nested_files(self, tmp_path: Path) -> None:
        """Test that walk includes nested files."""
        # Arrange
        dir1 = tmp_path / "dir1"
        dir1.mkdir()
        file1 = dir1 / "file1.txt"
        file1.touch()

        # Act
        result = list(walk(tmp_path))

        # Assert
        assert file1 in result


class TestGetRepositoryRoot:
    """Test suite for the get_repository_root function."""

    @patch("buildscripts.makepackage.Path")
    def test_get_repository_root_valid(self, mock_path: MagicMock) -> None:
        """Test finding the repository root when the .git directory exists."""
        # Arrange
        mock_path.return_value.resolve.return_value.parent = mock_path
        mock_path.parents = [mock_path, mock_path]
        mock_path.__truediv__.return_value.exists.return_value = True

        # Act
        repo_root = get_repository_root()

        # Assert
        assert repo_root == mock_path

    @patch("buildscripts.makepackage.Path")
    def test_get_repository_root_invalid(self, mock_path: MagicMock) -> None:
        """Test finding the repository root when the .git directory does not exist."""
        # Arrange
        mock_path.return_value.resolve.return_value.parent = mock_path
        mock_path.parents = [mock_path, mock_path]
        mock_path.__truediv__.return_value.exists.return_value = False

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            get_repository_root()


class TestAddFileToPackage:
    """Test suite for the add_file_to_package function."""

    @pytest.mark.parametrize(
        "filepath, strip_path, archive_subdir, expected_archive_name",
        [
            ("file.txt", "base", None, "file.txt"),
            ("file.txt", "base", "inside_dir", "inside_dir/file.txt"),
            ("subdir/file.txt", "base", "inside_dir", "inside_dir/subdir/file.txt"),
            # Probably many edge cases missing here.
        ],
        ids=["simple_path", "target_subfolder", "nested_path"],
    )
    @patch("buildscripts.makepackage.get_repository_root")
    def test_add_file_to_package(
        self,
        mock_get_repository_root: MagicMock,
        filepath: str,
        strip_path: str,
        archive_subdir: str,
        expected_archive_name: str,
        tmp_path: Path,
    ) -> None:
        """Test adding files to the package zip file with various paths."""
        # Arrange
        mock_get_repository_root.return_value = tmp_path
        zip_file = tmp_path / "test.zip"
        file_content = b"test content"
        tmp_file_path = tmp_path / strip_path / filepath
        tmp_file_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_file_path.write_bytes(file_content)

        with ZipFile(zip_file, "w") as zfile:
            # Act
            add_file_to_package(zfile, tmp_file_path, tmp_path / strip_path, archive_subdir)

        # Assert
        with ZipFile(zip_file, "r") as zfile:
            assert expected_archive_name in zfile.namelist()
            with zfile.open(expected_archive_name) as f:
                assert f.read() == file_content

    @pytest.mark.parametrize(
        "filepath, strip_path, archive_subdir, expected_error",
        [
            ("file.txt", "base", "my.folder", ValueError),
            ("nonexistent.txt", "base", None, FileNotFoundError),
        ],
        ids=["invalid_archive_subdir_name", "nonexistent_file"],
    )
    @patch("buildscripts.makepackage.get_repository_root")
    def test_add_file_to_package_error(
        self,
        mock_get_repository_root: MagicMock,
        filepath: str,
        strip_path: str,
        archive_subdir: str,
        expected_error: Exception,
        tmp_path: Path,
    ) -> None:
        """Test error handling when adding files to the package zip file."""
        # Arrange
        mock_get_repository_root.return_value = tmp_path
        zip_file = tmp_path / "test.zip"

        with ZipFile(zip_file, "w") as zfile:
            # Act & Assert
            with pytest.raises(expected_error):  # type: ignore[call-overload]
                add_file_to_package(zfile, tmp_path / strip_path / filepath, tmp_path / strip_path, archive_subdir)


class TestPackagePlugin:
    """Test suite for the package_plugin function."""

    @pytest.fixture
    def setup_repo(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        """Fixture to set up a temporary repository structure."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        (repo_root / "pluginInfo.json").write_text('{"name": "TestPlugin", "version": "1.0.0"}')
        (repo_root / "README.md").write_text("content1")
        (repo_root / "LICENSE").write_text("content2")
        (repo_root / "file1.py").write_text("content3")
        (repo_root / "file2.pyc").write_text("content4")
        (repo_root / "__pycache__").mkdir()
        (repo_root / "__pycache__" / "file3.txt").write_text("content5")
        (repo_root / ".sdpackageignore").write_text("*.pyc\n__pycache__/\ndebug.py\n")
        plugin_dir = repo_root / "src" / "test_plugin"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "__init__.py").write_text("content6")
        (plugin_dir / "debug.py").write_text("content7")
        (plugin_dir / "subfolder" / "__pycache__").mkdir(parents=True)
        (plugin_dir / "subfolder" / "file4.py").write_text("content8")
        (plugin_dir / "subfolder" / "__pycache__" / "file5.pyc").write_text("content9")
        monkeypatch.chdir(repo_root)
        return repo_root

    @patch("buildscripts.makepackage.get_repository_root")
    def test_package_plugin(self, mock_get_repository_root: MagicMock, setup_repo: Path) -> None:
        """Test creating the plugin package.

        The structure of a package has to be:
        <plugin_name>.sdplugin/
            ├── <plugin_folder>/
                ├── pluginInfo.json
                ├── <extra files>
                ├── <python_pkg>/
                    ├── __init__.py
                    ├── <plugin files>
        """
        # Arrange
        mock_get_repository_root.return_value = setup_repo
        build_dir = setup_repo / "build"
        plugin_dir = setup_repo / "src" / "test_plugin"
        package_path = build_dir / "test_plugin.sdplugin"

        # Act
        package_plugin(
            plugin_dir, extra_files=[setup_repo / "pluginInfo.json", setup_repo / "README.md", setup_repo / "LICENSE"]
        )

        # Assert
        assert package_path.exists()
        with ZipFile(package_path, "r") as zfile:
            assert "test_plugin/pluginInfo.json" in zfile.namelist()
            assert "test_plugin/README.md" in zfile.namelist()
            assert "test_plugin/LICENSE" in zfile.namelist()
            assert "file1.py" not in zfile.namelist()
            assert "file2.pyc" not in zfile.namelist()
            assert "test_plugin/file3.txt" not in zfile.namelist()
            assert "test_plugin/test_plugin/__init__.py" in zfile.namelist()
            assert "test_plugin/test_plugin/debug.py" not in zfile.namelist()
            assert "test_plugin/test_plugin/subfolder/file4.py" in zfile.namelist()
            assert "test_plugin/test_plugin/subfolder/__pycache__/file5.pyc" not in zfile.namelist()

    @patch("buildscripts.makepackage.get_repository_root", side_effect=FileNotFoundError("Repository root not found"))
    def test_package_plugin_repo_root_not_found(self, mock_get_repository_root: MagicMock, setup_repo: Path) -> None:
        """Test package_plugin when repository root is not found."""
        # Act & Assert
        with pytest.raises(RuntimeError, match="Error while creating package. Check the logs for more details."):
            package_plugin(setup_repo / "src" / "test_plugin")

    @patch("buildscripts.makepackage.get_repository_root")
    @patch("buildscripts.makepackage.IgnoreFileFilter", side_effect=FileNotFoundError("Ignore file not found"))
    def test_package_plugin_ignore_file_not_found(
        self, mock_ignore_file_filter: MagicMock, mock_get_repository_root: MagicMock, setup_repo: Path
    ) -> None:
        """Test package_plugin when the ignore file is not found."""
        # Arrange
        mock_get_repository_root.return_value = setup_repo

        # Act & Assert
        with pytest.raises(RuntimeError, match="Error while creating package. Check the logs for more details."):
            package_plugin(setup_repo / "src" / "test_plugin")

    @patch("buildscripts.makepackage.get_repository_root")
    @patch("buildscripts.makepackage.ZipFile", side_effect=OSError("Error creating zip file"))
    def test_package_plugin_zip_file_error(
        self, mock_zip_file: MagicMock, mock_get_repository_root: MagicMock, setup_repo: Path
    ) -> None:
        """Test package_plugin when there is an error creating the zip file."""
        # Arrange
        mock_get_repository_root.return_value = setup_repo

        # Act & Assert
        with pytest.raises(RuntimeError, match="Error while creating package. Check the logs for more details."):
            package_plugin(setup_repo / "src" / "test_plugin")
