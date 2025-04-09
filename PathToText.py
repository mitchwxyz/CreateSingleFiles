import argparse
import re
from pathlib import Path

from markitdown import MarkItDown


class Path2File:
    """A class for processing files in a folder, including fetching, writing, and cleaning up content."""

    DEFAULT_FILE_NAME = "Merged.md"
    STANDARD_EXCLUDED_FILE_TYPES = (
        ".DS_Store",
        ".gitignore",
        ".lock",
        DEFAULT_FILE_NAME,
    )
    STANDARD_EXCLUDED_PATHS = (
        ".git",
        ".venv",
        "__pycache__",
        ".ruff_cache",
    )

    def __init__(
        self,
        input_folder,
        output_file_path,
        included_file_types,
        excluded_file_types,
        excluded_folders,
        map_only=False,
    ):
        """Initialize Path2File with input/output paths and file filtering options.

        Args:
            input_folder: Path to folder containing source files
            output_file_path: Path where output file will be written
            included_file_types: List of file extensions to include
            excluded_file_types: List of file extensions to exclude
            excluded_folders: List of folder names to exclude
            map_only: If True, only output directory structure

        """
        self.input_folder = Path(input_folder)
        self.output_path = output_file_path
        self.included_file_types = included_file_types
        self.excluded_file_types = (
            list(self.STANDARD_EXCLUDED_FILE_TYPES) + excluded_file_types
        )
        self.excluded_folders = list(self.STANDARD_EXCLUDED_PATHS) + excluded_folders
        self.map_only = map_only
        self.ignored_patterns = []
        self.md = MarkItDown()

    @property
    def output_file(self) -> Path:
        """Get the path of the output file.

        Returns:
            Path: Path object for the output file location

        """
        if not self.output_path:
            return self.input_folder / self.DEFAULT_FILE_NAME
        elif Path(self.output_path).is_dir():
            return Path(self.output_path) / self.DEFAULT_FILE_NAME
        return Path(self.output_path)

    def fetch_all_files(self):
        """Fetch files from the input folder based on inclusion/exclusion criteria and .gitignore patterns."""
        if self.map_only:
            return []

        self._read_gitignore()
        files_data = []

        for root, directories, files in Path(self.input_folder).walk():
            root_path = Path(root)

            # Filter out ignored directories and standard excluded paths
            directories[:] = [
                dir
                for dir in directories
                if not self._is_ignored(root_path / dir)
                and dir not in self.excluded_folders
            ]
            for file in files:
                file_path = root_path / file
                if self._is_ignored(file_path):
                    print(f"Skipping file {file_path}: Matched .gitignore pattern.")
                    continue

                if self._file_matches_criteria(file_path.name):
                    file_data = self._process_file(file_path)
                    if file_data:
                        files_data.append(file_data)
        return files_data

    def write_to_file(self, files_data) -> bool:
        """Write the collected file contents to the output file."""
        if not files_data and not self.map_only:
            print("No Files in this Directory. Done.")
            return False
        with self.output_file.open("w", encoding="utf-8") as f:
            f.write("# Folder Structure\n")
            f.write(f"```\n{self._map_directory_structure()}\n```")
            if files_data:
                f.write("\n\n# File Contents\n")
                for file_data in files_data:
                    f.write(file_data)
        return True

    def clean_up_text(self):
        """Clean up the output file by removing excessive newlines."""
        with self.output_file.open(encoding="utf-8") as f:
            text = f.read()
        cleaned_text = re.sub("\n{3,}", "\n\n", text)
        with self.output_file.open("w", encoding="utf-8") as f:
            f.write(cleaned_text)

    def _read_gitignore(self):
        """Read patterns from the .gitignore file if it exists."""
        gitignore_path = self.input_folder / ".gitignore"
        if gitignore_path.exists():
            with gitignore_path.open(encoding="utf-8") as gitignore_file:
                self.ignored_patterns = [
                    line.strip()
                    for line in gitignore_file
                    if line.strip() and not line.strip().startswith("#")
                ]

    def _is_ignored(self, path):
        """Check if a file or directory matches any .gitignore pattern or should be excluded."""
        relative_path = path.relative_to(self.input_folder)
        return any(
            re.fullmatch(pattern.replace("*", ".*"), str(relative_path))
            for pattern in self.ignored_patterns
        )

    def _file_matches_criteria(self, file_name):
        """Check if the given file matches inclusion and exclusion criteria."""
        return (
            not self.excluded_file_types
            or not any(file_name.endswith(ext) for ext in self.excluded_file_types)
        ) and (
            not self.included_file_types
            or any(file_name.endswith(ext) for ext in self.included_file_types)
        )

    def _process_file(self, file_path):
        """Process the given file and return its content."""
        relative_path = file_path.relative_to(self.input_folder)
        file_extension = file_path.suffix
        file_content = ""

        supported_extensions = (".pdf", ".pptx", ".docx", ".xlsx")
        try:
            if any(file_extension.endswith(ext) for ext in supported_extensions):
                result = self.md.convert(str(file_path))
                file_content += result.text_content
            else:
                with file_path.open("rb") as f:
                    content = f.read()
                file_content += content.decode("utf-8", errors="replace")
        except Exception as e:
            print(f"Error processing file {file_path}: {e}")
            return None

        print(f"Processed file {file_path}: size {file_path.stat().st_size} bytes")
        return f"## {relative_path}\n```{file_extension[1:]}\n{file_content}\n```\n\n"

    def _map_directory_structure(self) -> str:
        """Create a text representation of the directory structure.

        Returns:
            str: Text representation of directory tree

        """

        def recursive_list(dir_path: Path, prefix=""):
            try:
                entries = [entry for entry in dir_path.iterdir()]
            except PermissionError:
                return  # Skip directories where access is denied

            # Filter out excluded folders and hidden files
            entries = [
                entry
                for entry in entries
                if entry.name not in self.excluded_folders + self.excluded_file_types
            ]
            entries.sort(key=lambda x: (not x.is_dir(), x.name))

            for i, entry in enumerate(entries):
                is_last = i == len(entries) - 1
                part = "└── " if is_last else "├── "
                yield f"{prefix}{part}{entry.name}"

                if entry.is_dir():
                    extension = "    " if is_last else "│   "
                    yield from recursive_list(entry, prefix=prefix + extension)

        return "\n".join(recursive_list(self.input_folder))


def main():
    """Process files in a directory and output contents to a single markdown file.

    Returns:
        Path: Path to the generated output file, or None if no files were processed

    """
    parser = argparse.ArgumentParser(
        description="Scrape files from a folder and write to a text file"
    )
    parser.add_argument("directory", help="Path to the folder to process")
    parser.add_argument(
        "--output_name",
        type=str,
        nargs="?",
        help=f"Path and filename for the output file. Defaults to {Path2File.DEFAULT_FILE_NAME}",
    )
    parser.add_argument(
        "--exclude_types",
        default=[],
        nargs="+",
        help="file types to exclude (Ex: .svg .png)",
    )
    parser.add_argument(
        "--include_types",
        default=[],
        nargs="+",
        help="file types to include (Ex: .txt .py)",
    )
    parser.add_argument(
        "--exclude_folders",
        default=[],
        nargs="+",
        help="folders to exclude from processing (Ex: .git .venv)",
    )
    parser.add_argument(
        "--map_only",
        action="store_true",
        help="output the file structure only, no file contents.",
    )

    args = parser.parse_args()
    output_file_path = Path(args.directory) / (
        args.output_name or Path2File.DEFAULT_FILE_NAME
    )

    processor = Path2File(
        input_folder=args.directory,
        output_file_path=output_file_path,
        excluded_file_types=args.exclude_types,
        included_file_types=args.include_types,
        excluded_folders=args.exclude_folders,
        map_only=args.map_only,
    )

    print("Fetching all files...")
    files_data = processor.fetch_all_files()

    write_successful = processor.write_to_file(files_data)

    if not write_successful:
        return None

    print("Cleaning up file...")
    processor.clean_up_text()

    print("Done.")
    return output_file_path


if __name__ == "__main__":
    print(main())
