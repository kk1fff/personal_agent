"""CLI entry point for Notion indexer."""

import argparse
import asyncio
import sys
import logging
from typing import Optional

from ..config.config_loader import load_config
from ..llm.gemini_llm import GeminiLLM
from ..llm.ollama_llm import OllamaLLM
from ..llm.openai_llm import OpenAILLM
from ..memory.embeddings import EmbeddingGenerator
from ..memory.vector_store import VectorStore
from ..utils.logging import setup_logging
from .client import NotionClient
from .indexer import NotionIndexer
from .models import TraversalProgress


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        description="Index Notion workspace for semantic search",
        prog="notion-indexer",
    )

    parser.add_argument(
        "-c",
        "--config",
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v, -vv, -vvv)",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reindex all pages, ignoring change detection",
    )

    parser.add_argument(
        "--workspace",
        type=str,
        help="Index only a specific workspace by name",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be indexed without making changes",
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show index statistics and exit",
    )

    return parser


def create_llm(config):
    """
    Create LLM instance based on configuration.

    Args:
        config: Application configuration

    Returns:
        BaseLLM instance
    """
    provider = config.llm.provider.lower()

    if provider == "ollama":
        if not config.llm.ollama:
            raise ValueError("Ollama configuration is required")
        return OllamaLLM(
            model=config.llm.ollama.model,
            base_url=config.llm.ollama.base_url,
            temperature=config.llm.ollama.temperature,
            max_tokens=config.llm.ollama.max_tokens,
            context_window=config.llm.ollama.context_window,
        )

    elif provider == "openai":
        if not config.llm.openai:
            raise ValueError("OpenAI configuration is required")
        return OpenAILLM(
            api_key=config.llm.openai.api_key,
            model=config.llm.openai.model,
            temperature=config.llm.openai.temperature,
            max_tokens=config.llm.openai.max_tokens,
            organization_id=config.llm.openai.organization_id,
        )

    elif provider == "gemini":
        if not config.llm.gemini:
            raise ValueError("Gemini configuration is required")
        return GeminiLLM(
            api_key=config.llm.gemini.api_key,
            model=config.llm.gemini.model,
            temperature=config.llm.gemini.temperature,
            max_tokens=config.llm.gemini.max_tokens,
            safety_settings=config.llm.gemini.safety_settings,
        )

    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def print_progress(progress: TraversalProgress) -> None:
    """Print progress bar and status."""
    status = f"\rPages: {progress.pages_processed} processed"
    if progress.pages_skipped > 0:
        status += f", {progress.pages_skipped} skipped"
    if progress.current_page_title:
        # Truncate long titles
        title = progress.current_page_title
        if len(title) > 40:
            title = title[:37] + "..."
        status += f" | Current: {title}"
    print(status, end="", flush=True)


async def run_indexer(args: argparse.Namespace) -> int:
    """
    Run the indexer with given arguments.

    Args:
        args: Parsed command line arguments

    Returns:
        Exit code (0 for success)
    """
    logger = logging.getLogger(__name__)

    # Load configuration
    try:
        config = load_config(args.config)
    except FileNotFoundError:
        print(f"Error: Configuration file not found: {args.config}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        return 1

    # Check Notion configuration
    if not config.tools.notion:
        print("Error: Notion configuration not found in config file", file=sys.stderr)
        return 1

    if not config.tools.notion.api_key:
        print("Error: Notion API key not configured", file=sys.stderr)
        return 1

    if not config.tools.notion.workspaces:
        print("Error: No Notion workspaces configured", file=sys.stderr)
        return 1

    notion_config = config.tools.notion

    # Filter workspaces if specified
    workspaces = notion_config.workspaces
    if args.workspace:
        workspaces = [w for w in workspaces if w.name == args.workspace]
        if not workspaces:
            print(f"Error: Workspace '{args.workspace}' not found", file=sys.stderr)
            print("Available workspaces:", file=sys.stderr)
            for w in notion_config.workspaces:
                print(f"  - {w.name}", file=sys.stderr)
            return 1

    # Initialize components
    try:
        notion_client = NotionClient(
            api_key=notion_config.api_key,
            rate_limit_delay=notion_config.rate_limit_delay,
        )

        vector_store = VectorStore(
            db_path=config.database.vector_db_path,
            collection_name=notion_config.index_collection,
        )

        embedding_generator = EmbeddingGenerator()
        llm = create_llm(config)

    except ImportError as e:
        print(f"Error: Missing dependency: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error initializing components: {e}", file=sys.stderr)
        return 1

    # Show stats only
    if args.stats:
        print(f"Index collection: {notion_config.index_collection}")
        print(f"Vector DB path: {config.database.vector_db_path}")
        print(f"Configured workspaces: {len(notion_config.workspaces)}")
        for w in notion_config.workspaces:
            print(f"  - {w.name}: {len(w.root_page_ids)} root pages, {len(w.database_ids)} databases")
        return 0

    # Dry run mode
    if args.dry_run:
        print("DRY RUN - No changes will be made\n")
        for workspace in workspaces:
            print(f"Workspace: {workspace.name}")
            print(f"  Root pages: {workspace.root_page_ids}")
            print(f"  Databases: {workspace.database_ids}")
            print(f"  Exclusions: {workspace.exclude_page_ids}")
            print(f"  Max depth: {workspace.max_depth}")
            print()

            # Traverse to show what would be indexed
            from .traversal import WorkspaceTraverser

            traverser = WorkspaceTraverser(
                client=notion_client,
                workspace_config=workspace,
            )

            print("  Pages to index:")
            count = 0
            for page_id, title, path in traverser.traverse():
                print(f"    - {path}")
                count += 1
                if count >= 50:
                    print(f"    ... and more (showing first 50)")
                    break

            print(f"\n  Total pages found: {traverser.progress.total_pages_found}")
            print()
        return 0

    # Create indexer
    indexer = NotionIndexer(
        notion_client=notion_client,
        llm=llm,
        vector_store=vector_store,
        embedding_generator=embedding_generator,
    )

    # Index each workspace
    total_indexed = 0
    total_skipped = 0
    total_failed = 0

    for workspace in workspaces:
        print(f"\nIndexing workspace: {workspace.name}")
        print("-" * 40)

        # Use progress callback for verbose output
        progress_callback = print_progress if args.verbose >= 1 else None

        stats = await indexer.index_workspace(
            workspace_config=workspace,
            force_reindex=args.force,
            progress_callback=progress_callback,
        )

        # Clear progress line
        if progress_callback:
            print()

        print(f"  Indexed: {stats.pages_indexed}")
        print(f"  Skipped: {stats.pages_skipped}")
        print(f"  Failed: {stats.pages_failed}")

        if stats.errors and args.verbose >= 2:
            print("  Errors:")
            for error in stats.errors[:10]:
                print(f"    - {error}")
            if len(stats.errors) > 10:
                print(f"    ... and {len(stats.errors) - 10} more")

        total_indexed += stats.pages_indexed
        total_skipped += stats.pages_skipped
        total_failed += stats.pages_failed

    # Summary
    print("\n" + "=" * 40)
    print("SUMMARY")
    print("=" * 40)
    print(f"Total indexed: {total_indexed}")
    print(f"Total skipped: {total_skipped}")
    print(f"Total failed: {total_failed}")

    return 0 if total_failed == 0 else 1


def main():
    """Main entry point for CLI."""
    parser = create_parser()
    args = parser.parse_args()

    # Setup logging based on verbosity
    setup_logging(verbosity=args.verbose)

    try:
        exit_code = asyncio.run(run_indexer(args))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nIndexing cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
