"""Vector database interface for memory storage."""

from typing import List, Optional

try:
    import chromadb
    from chromadb.config import Settings
except ImportError:
    chromadb = None


class VectorStore:
    """Vector database for storing and retrieving conversation embeddings."""

    def __init__(self, db_path: str = "vector_db", collection_name: str = "conversations"):
        """
        Initialize vector store.

        Args:
            db_path: Path to vector database directory
            collection_name: Name of the collection to use
        """
        if chromadb is None:
            raise ImportError(
                "chromadb is required for vector storage. "
                "Install it with: pip install chromadb"
            )

        self.client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self.collection_name = collection_name

    def store(
        self,
        text: str,
        embedding: List[float],
        metadata: Optional[dict] = None,
        id: Optional[str] = None,
    ) -> str:
        """
        Store a text with its embedding.

        Args:
            text: Text content
            embedding: Embedding vector
            metadata: Optional metadata dictionary
            id: Optional unique ID (auto-generated if not provided)

        Returns:
            ID of the stored item
        """
        if metadata is None:
            metadata = {}

        if id is None:
            import uuid
            id = str(uuid.uuid4())

        self.collection.add(
            ids=[id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata],
        )

        return id

    def search(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        filter_metadata: Optional[dict] = None,
    ) -> List[dict]:
        """
        Search for similar items.

        Args:
            query_embedding: Query embedding vector
            n_results: Number of results to return
            filter_metadata: Optional metadata filter

        Returns:
            List of dictionaries with 'text', 'metadata', 'distance', and 'id' keys
        """
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filter_metadata,
        )

        formatted_results = []
        if results["ids"] and len(results["ids"][0]) > 0:
            for i in range(len(results["ids"][0])):
                formatted_results.append(
                    {
                        "id": results["ids"][0][i],
                        "text": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i] if "distances" in results else None,
                    }
                )

        return formatted_results

    def delete(self, id: str) -> None:
        """
        Delete an item by ID.

        Args:
            id: ID of item to delete
        """
        self.collection.delete(ids=[id])

    def get_by_id(self, id: str) -> Optional[dict]:
        """
        Get an item by ID.

        Args:
            id: Item ID

        Returns:
            Dictionary with 'text', 'metadata', and 'id' or None if not found
        """
        results = self.collection.get(ids=[id])

        if results["ids"]:
            return {
                "id": results["ids"][0],
                "text": results["documents"][0],
                "metadata": results["metadatas"][0],
            }

        return None

