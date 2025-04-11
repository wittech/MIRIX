from datetime import datetime
from typing import Dict, Optional, Any, List

from pydantic import Field

from mirix.schemas.mirix_base import MirixBase
from mirix.utils import get_utc_time
from mirix.schemas.embedding_config import EmbeddingConfig

class ProceduralMemoryItemBase(MirixBase):
    """
    Base schema for storing procedural knowledge (e.g., workflows, methods).
    """
    __id_prefix__ = "proc_item"
    entry_type: str = Field(..., description="Category (e.g., 'workflow', 'guide', 'script')")
    description: str = Field(None, description="Short descriptive text about the procedure")
    steps: str = Field(..., description="Step-by-step instructions or method in JSON format")

class ProceduralMemoryItem(ProceduralMemoryItemBase):
    """
    Full procedural memory item schema, with database-related fields.
    """
    id: str = ProceduralMemoryItemBase.generate_id_field()
    created_at: datetime = Field(default_factory=get_utc_time, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    organization_id: str = Field(..., description="The unique identifier of the organization")
    metadata_: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary additional metadata")
    description_embedding: Optional[List[float]] = Field(None, description="The embedding of the description")
    steps_embedding: Optional[List[float]] = Field(None, description="The embedding of the steps")
    embedding_config: Optional[EmbeddingConfig] = Field(None, description="The embedding configuration used by the event")

class ProceduralMemoryItemUpdate(MirixBase):
    """Schema for updating an existing procedural memory item."""
    id: str = Field(..., description="Unique ID for this procedural memory entry")
    entry_type: Optional[str] = Field(None, description="Category (e.g., 'workflow', 'guide', 'script')")
    description: Optional[str] = Field(None, description="Short descriptive text")
    steps: Optional[str] = Field(None, description="Step-by-step instructions or method in JSON format")
    metadata_: Optional[Dict[str, Any]] = Field(None, description="Arbitrary additional metadata")
    organization_id: Optional[str] = Field(None, description="The organization ID")
    updated_at: datetime = Field(default_factory=get_utc_time, description="Update timestamp")
    steps_embedding: Optional[List[float]] = Field(None, description="The embedding of the event")
    description_embedding: Optional[List[float]] = Field(None, description="The embedding of the description")
    embedding_config: Optional[EmbeddingConfig] = Field(None, description="The embedding configuration used by the event")

class ProceduralMemoryItemResponse(ProceduralMemoryItem):
    """Response schema for procedural memory item."""
    pass
