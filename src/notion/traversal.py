"""Workspace hierarchy traversal for indexing."""

import logging
from typing import Callable, Iterator, Optional, Set, Tuple

from ..config.config_schema import NotionWorkspaceConfig
from .client import NotionClient
from .models import TraversalProgress


class WorkspaceTraverser:
    """Traverses Notion workspace hierarchy."""

    def __init__(
        self,
        client: NotionClient,
        workspace_config: NotionWorkspaceConfig,
        progress_callback: Optional[Callable[[TraversalProgress], None]] = None,
    ):
        """
        Initialize traverser.

        Args:
            client: NotionClient instance
            workspace_config: Workspace configuration
            progress_callback: Optional callback for progress updates
        """
        self.client = client
        self.config = workspace_config
        self.progress_callback = progress_callback
        self.visited: Set[str] = set()
        self.exclude_set: Set[str] = set(workspace_config.exclude_page_ids)
        self.logger = logging.getLogger(__name__)
        self.progress = TraversalProgress()

    def _update_progress(self, **kwargs) -> None:
        """Update progress and call callback if set."""
        for key, value in kwargs.items():
            if hasattr(self.progress, key):
                setattr(self.progress, key, value)
        if self.progress_callback:
            self.progress_callback(self.progress)

    def traverse(self) -> Iterator[Tuple[str, str, str]]:
        """
        Traverse the workspace and yield pages.

        Yields:
            Tuples of (page_id, title, breadcrumb_path)
        """
        self.visited.clear()
        self.progress = TraversalProgress()

        # Process root pages
        for page_id in self.config.root_page_ids:
            if page_id in self.exclude_set:
                self.logger.debug(f"Skipping excluded root page: {page_id}")
                continue

            yield from self._traverse_page(page_id, depth=0, parent_path="")

        # Process databases
        for database_id in self.config.database_ids:
            if database_id in self.exclude_set:
                self.logger.debug(f"Skipping excluded database: {database_id}")
                continue

            yield from self._traverse_database(database_id, parent_path="")

    def _traverse_page(
        self,
        page_id: str,
        depth: int = 0,
        parent_path: str = "",
    ) -> Iterator[Tuple[str, str, str]]:
        """
        Recursively traverse a page and its children.

        Args:
            page_id: Page ID to traverse
            depth: Current depth in hierarchy
            parent_path: Path of parent page

        Yields:
            Tuples of (page_id, title, breadcrumb_path)
        """
        # Check depth limit
        if depth > self.config.max_depth:
            self.logger.debug(f"Max depth reached at page: {page_id}")
            return

        # Check if already visited
        if page_id in self.visited:
            self.logger.debug(f"Already visited page: {page_id}")
            return

        # Check exclusion
        if page_id in self.exclude_set:
            self.logger.debug(f"Skipping excluded page: {page_id}")
            self._update_progress(pages_skipped=self.progress.pages_skipped + 1)
            return

        self.visited.add(page_id)

        try:
            # Check if this is a database
            if self.client.is_database(page_id):
                yield from self._traverse_database(page_id, parent_path)
                return

            # Fetch page
            page = self.client.get_page(page_id)
            title = self.client.get_page_title(page)

            # Build breadcrumb path
            path = self._build_path(parent_path, title)

            self._update_progress(
                total_pages_found=self.progress.total_pages_found + 1,
                current_page_title=title,
                current_depth=depth,
            )

            self.logger.debug(f"Traversing page: {path} (depth={depth})")

            # Yield this page
            yield (page_id, title, path)

            self._update_progress(
                pages_processed=self.progress.pages_processed + 1
            )

            # Get and traverse child pages
            child_page_ids = self.client.get_child_pages(page_id)
            for child_id in child_page_ids:
                yield from self._traverse_page(
                    child_id, depth=depth + 1, parent_path=path
                )

        except Exception as e:
            self.logger.error(f"Error traversing page {page_id}: {e}")
            self._update_progress(pages_skipped=self.progress.pages_skipped + 1)

    def _traverse_database(
        self,
        database_id: str,
        parent_path: str = "",
    ) -> Iterator[Tuple[str, str, str]]:
        """
        Traverse all pages in a database.

        Args:
            database_id: Database ID
            parent_path: Path prefix for database entries

        Yields:
            Tuples of (page_id, title, breadcrumb_path)
        """
        if database_id in self.visited:
            self.logger.debug(f"Already visited database: {database_id}")
            return

        self.visited.add(database_id)

        try:
            # Get database title
            database = self.client.get_database(database_id)
            db_title = self.client.get_database_title(database)

            # Build path for database
            db_path = self._build_path(parent_path, f"[{db_title}]")

            self.logger.debug(f"Traversing database: {db_path}")

            # Query all pages in database
            for page in self.client.query_database(database_id):
                page_id = page["id"]

                if page_id in self.exclude_set:
                    self.logger.debug(f"Skipping excluded database entry: {page_id}")
                    self._update_progress(
                        pages_skipped=self.progress.pages_skipped + 1
                    )
                    continue

                if page_id in self.visited:
                    continue

                self.visited.add(page_id)

                title = self.client.get_page_title(page)
                path = self._build_path(db_path, title)

                self._update_progress(
                    total_pages_found=self.progress.total_pages_found + 1,
                    current_page_title=title,
                )

                yield (page_id, title, path)

                self._update_progress(
                    pages_processed=self.progress.pages_processed + 1
                )

                # Database entries can have child pages too
                child_page_ids = self.client.get_child_pages(page_id)
                for child_id in child_page_ids:
                    yield from self._traverse_page(
                        child_id, depth=1, parent_path=path
                    )

        except Exception as e:
            self.logger.error(f"Error traversing database {database_id}: {e}")
            self._update_progress(pages_skipped=self.progress.pages_skipped + 1)

    def _build_path(self, parent_path: str, title: str) -> str:
        """
        Build breadcrumb path for a page.

        Args:
            parent_path: Parent's path
            title: Current page title

        Returns:
            Breadcrumb string like "General > Tax > 2025"
        """
        if parent_path:
            return f"{parent_path} > {title}"
        return title
