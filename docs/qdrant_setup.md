# Qdrant Vector Database Setup for The Great Work

## Overview

Qdrant provides semantic search capabilities for The Great Work, enabling:
- Natural language queries about game mechanics
- Scholar relationship discovery
- Press archive semantic search
- Expedition outcome pattern matching
- Implementation documentation search

## Quick Start

### 1. Start Qdrant Service

```bash
# Start Qdrant using Docker Compose
docker-compose up -d qdrant

# Verify Qdrant is running
curl http://localhost:6333/health
```

### 2. Initialize Collection

```bash
# Setup the knowledge collection
python -m great_work.tools.qdrant_manager --setup

# View collection statistics
python -m great_work.tools.qdrant_manager --stats
```

### 3. MCP Server Integration

The `.mcp.json` file configures the MCP server for Claude integration:

```json
{
  "mcpServers": {
    "qdrant-great-work": {
      "command": "uvx",
      "args": ["mcp-server-qdrant"],
      "env": {
        "QDRANT_URL": "http://localhost:6333",
        "COLLECTION_NAME": "great-work-knowledge",
        "EMBEDDING_MODEL": "sentence-transformers/all-MiniLM-L6-v2"
      }
    }
  }
}
```

## Use Cases

### 1. Game Mechanics Knowledge Base

Store and query:
- Confidence wager tables and outcomes
- Expedition resolution rules
- Influence economy mechanics
- Scholar memory and relationship systems

### 2. Scholar Profiles and Relationships

Index:
- Scholar personalities and catchphrases
- Relationship histories and grudges
- Defection patterns and loyalty metrics
- Career progression paths

### 3. Press Archive Search

Enable semantic search over:
- Academic bulletins
- Research manifestos
- Discovery reports
- Retraction notices
- Academic gossip

### 4. Expedition Outcomes

Pattern match:
- Successful expedition strategies
- Spectacular failure discoveries
- Sideways discovery chains
- Preparation depth correlations

## Data Schema

Documents in the collection follow this structure:

```python
{
    "id": str,           # Unique identifier
    "category": str,     # mechanics|gameplay|scholars|press|expeditions
    "title": str,        # Brief title
    "content": str,      # Full text content
    "metadata": {
        "timestamp": str,      # ISO timestamp
        "player_id": str,      # Associated player (if applicable)
        "scholar_id": str,     # Associated scholar (if applicable)
        "expedition_id": str,  # Associated expedition (if applicable)
        "tags": List[str],    # Searchable tags
    }
}
```

## Integration with Game Service

```python
from great_work.tools.qdrant_manager import QdrantManager

# Initialize manager
qdrant = QdrantManager()

# Store a press release
qdrant.store_press(
    press_id="pr_123",
    headline="Dr. Fieldstone's Bronze Age Breakthrough",
    content="...",
    metadata={"scholar_id": "fieldstone", "confidence": "certain"}
)

# Search for related content
results = qdrant.search("Bronze Age discoveries by Fieldstone")
```

## Administration

### Health Check
```bash
curl http://localhost:6333/health
```

### Collection Info
```bash
curl http://localhost:6333/collections/great-work-knowledge
```

### Delete Collection (WARNING: Destructive)
```bash
curl -X DELETE http://localhost:6333/collections/great-work-knowledge
```

### Backup
```bash
# Backup Qdrant storage
tar -czf qdrant_backup_$(date +%Y%m%d).tar.gz ./qdrant_storage/
```

## Troubleshooting

### Port Conflicts
If port 6333 is in use:
1. Edit `docker-compose.yml` to use different ports
2. Update `.mcp.json` with new URL
3. Restart services

### Collection Already Exists
```bash
# Reset collection (WARNING: deletes all data)
curl -X DELETE http://localhost:6333/collections/great-work-knowledge
python -m great_work.tools.qdrant_manager --setup
```

### MCP Server Not Found
```bash
# Install MCP server for Qdrant
pip install mcp-server-qdrant
# or
uvx mcp-server-qdrant
```

## Future Enhancements

1. **Auto-indexing**: Automatically index new press releases and expeditions
2. **Scholar Embeddings**: Generate embeddings for scholar personalities
3. **Similarity Search**: Find similar expeditions or theories
4. **Cluster Analysis**: Identify gameplay patterns and strategies
5. **LLM Integration**: Use embeddings for narrative generation context