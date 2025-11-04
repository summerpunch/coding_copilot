"""File scanning and discovery with ignore pattern support."""

import os
from pathlib import Path
from typing import List, Tuple, Set, Optional
import fnmatch


class FileScanner:
    """Scans directory for files with ignore pattern support."""

    DEFAULT_IGNORE_PATTERNS = [
        # Version control
        '.git', '.svn', '.hg',
        # Python
        '__pycache__', '*.pyc', '*.pyo', '*.pyd',
        '.Python', '*.egg-info', '.pytest_cache', '.mypy_cache',
        '.venv', 'venv', 'env', 'ENV',
        # Node
        'node_modules', 'npm-debug.log', 'yarn-error.log',
        # Build artifacts
        'build', 'dist', '*.so', '*.dylib', '*.dll',
        # IDEs
        '.idea', '.vscode', '*.swp', '*.swo', '*~',
        # Databases
        '*.sqlite', '*.sqlite-shm', '*.sqlite-wal', '*.db',
        # OS
        '.DS_Store', 'Thumbs.db', 'desktop.ini',
        # Other
        '*.log', '.env.local', '.env.*.local',
    ]

    def __init__(
        self,
        base_path: Optional[str] = None,
        max_depth: int = 5,
        custom_ignore_patterns: Optional[List[str]] = None,
        respect_gitignore: bool = True,
    ):
        """Initialize file scanner.

        Args:
            base_path: Base directory to scan (default: current directory)
            max_depth: Maximum directory depth to scan
            custom_ignore_patterns: Additional patterns to ignore
            respect_gitignore: Whether to parse and respect .gitignore files
        """
        self.base_path = Path(base_path or os.getcwd()).resolve()
        self.max_depth = max_depth
        self.respect_gitignore = respect_gitignore

        # Combine default and custom ignore patterns
        self.ignore_patterns = self.DEFAULT_IGNORE_PATTERNS.copy()
        if custom_ignore_patterns:
            self.ignore_patterns.extend(custom_ignore_patterns)

        # Load gitignore patterns if enabled
        self.gitignore_patterns: Set[str] = set()
        if respect_gitignore:
            self._load_gitignore_patterns()

        # Cache for scanned files
        self._cache: Optional[List[Tuple[str, str, bool]]] = None
        self._cache_mtime: float = 0

    def _load_gitignore_patterns(self):
        """Load patterns from .gitignore file."""
        gitignore_path = self.base_path / '.gitignore'

        if not gitignore_path.exists():
            return

        try:
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith('#'):
                        # Remove leading slash for consistency
                        if line.startswith('/'):
                            line = line[1:]
                        self.gitignore_patterns.add(line)
        except Exception:
            # Silently ignore errors reading gitignore
            pass

    def _should_ignore(self, path: Path, relative_path: str) -> bool:
        """Check if a path should be ignored.

        Args:
            path: Absolute path to check
            relative_path: Path relative to base_path

        Returns:
            True if path should be ignored
        """
        name = path.name

        # Always ignore hidden files (except .env, .gitignore)
        if name.startswith('.') and name not in ['.env', '.gitignore', '.envrc']:
            return True

        # Check against ignore patterns
        for pattern in self.ignore_patterns:
            if '*' in pattern:
                # Wildcard pattern
                if fnmatch.fnmatch(name, pattern):
                    return True
            else:
                # Exact match
                if name == pattern:
                    return True

        # Check against gitignore patterns
        if self.gitignore_patterns:
            for pattern in self.gitignore_patterns:
                # Simple gitignore pattern matching
                if pattern.endswith('/'):
                    # Directory pattern
                    if path.is_dir() and fnmatch.fnmatch(name, pattern.rstrip('/')):
                        return True
                else:
                    # File or directory pattern
                    if fnmatch.fnmatch(name, pattern):
                        return True
                    # Also check against relative path
                    if fnmatch.fnmatch(relative_path, pattern):
                        return True

        return False

    def _scan_directory(
        self,
        current_path: Path,
        depth: int,
        results: List[Tuple[str, str, bool]],
    ) -> None:
        """Recursively scan directory.

        Args:
            current_path: Current directory being scanned
            depth: Current depth level
            results: List to append results to (rel_path, abs_path, is_dir)
        """
        if depth > self.max_depth:
            return

        try:
            items = sorted(current_path.iterdir())
        except PermissionError:
            return

        for item in items:
            try:
                rel_path = str(item.relative_to(self.base_path))

                # Check if should ignore
                if self._should_ignore(item, rel_path):
                    continue

                if item.is_dir():
                    # Add directory with trailing slash
                    results.append((rel_path + "/", str(item), True))
                    # Recurse into directory
                    self._scan_directory(item, depth + 1, results)
                else:
                    # Add file
                    results.append((rel_path, str(item), False))

            except (OSError, PermissionError):
                # Skip files/dirs we can't access
                continue

    def scan(self, use_cache: bool = True) -> List[Tuple[str, str, bool]]:
        """Scan directory and return list of files.

        Args:
            use_cache: Whether to use cached results if available

        Returns:
            List of tuples: (relative_path, absolute_path, is_directory)
        """
        # Check if cache is still valid
        if use_cache and self._cache is not None:
            try:
                current_mtime = os.path.getmtime(self.base_path)
                if current_mtime == self._cache_mtime:
                    return self._cache
            except OSError:
                pass

        # Scan directory
        results: List[Tuple[str, str, bool]] = []
        self._scan_directory(self.base_path, depth=0, results=results)

        # Update cache
        try:
            self._cache = results
            self._cache_mtime = os.path.getmtime(self.base_path)
        except OSError:
            pass

        return results

    def invalidate_cache(self):
        """Invalidate the file cache."""
        self._cache = None
        self._cache_mtime = 0

    def find_file(self, partial_path: str) -> List[Tuple[str, str]]:
        """Find files matching a partial path.

        Args:
            partial_path: Partial file path to search for

        Returns:
            List of tuples: (relative_path, absolute_path)
        """
        files = self.scan()
        partial_lower = partial_path.lower()

        matches = []
        for rel_path, abs_path, is_dir in files:
            if partial_lower in rel_path.lower():
                matches.append((rel_path, abs_path))

        return matches

    def resolve_path(self, user_input: str) -> Optional[str]:
        """Resolve user input to an absolute path.

        Args:
            user_input: User's file path input (may be relative)

        Returns:
            Absolute path if found, None otherwise
        """
        # Try as-is first
        path = Path(user_input)
        if path.is_absolute() and path.exists():
            return str(path)

        # Try relative to base_path
        path = self.base_path / user_input
        if path.exists():
            return str(path.resolve())

        # Try fuzzy matching
        matches = self.find_file(user_input)
        if matches:
            # Return first exact match or first partial match
            for rel_path, abs_path in matches:
                if rel_path == user_input:
                    return abs_path
            return matches[0][1]

        return None
