from datetime import datetime
from typing import Dict, List, Optional, Any

from pydantic import Field

from mirix.schemas.mirix_base import MirixBase
from mirix.utils import get_utc_time
from mirix.schemas.embedding_config import EmbeddingConfig

class SemanticMemoryItemBase(MirixBase):
    """
    Base schema for storing semantic memory items (e.g., general knowledge, concepts, facts).
    """
    __id_prefix__ = "sem_item"
    concept: str = Field(..., description="The title or main concept for the knowledge entry")
    definition: str = Field(..., description="A concise explanation or summary of the concept")
    details: str = Field(..., description="Detailed explanation or additional context for the concept")
    source: str = Field(..., description="Reference or origin of this information (e.g., book, article, movie)")

class SemanticMemoryItem(SemanticMemoryItemBase):
    """
    Full semantic memory item schema, including database-related fields.
    """
    id: str = SemanticMemoryItemBase.generate_id_field()
    created_at: datetime = Field(default_factory=get_utc_time, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    metadata_: Dict[str, Any] = Field(default_factory=dict, description="Additional arbitrary metadata as a JSON object")
    organization_id: str = Field(..., description="The unique identifier of the organization")
    details_embedding: Optional[List[float]] = Field(None, description="The embedding of the details")
    concept_embedding: Optional[List[float]] = Field(None, description="The embedding of the concept")
    definition_embedding: Optional[List[float]] = Field(None, description="The embedding of the definition")
    embedding_config: Optional[EmbeddingConfig] = Field(None, description="The embedding configuration used by the event")

class SemanticMemoryItemUpdate(MirixBase):
    """
    Schema for updating an existing semantic memory item.
    """
    id: str = Field(..., description="Unique ID for this semantic memory entry")
    concept: Optional[str] = Field(None, description="The title or main concept for the knowledge entry")
    definition: Optional[str] = Field(None, description="A concise explanation or summary of the concept")
    details: Optional[str] = Field(None, description="Detailed explanation or additional context for the concept")
    source: Optional[str] = Field(None, description="Reference or origin of this information (e.g., book, article, movie)")
    metadata_: Optional[Dict[str, Any]] = Field(None, description="Additional arbitrary metadata as a JSON object")
    organization_id: Optional[str] = Field(None, description="The organization ID")
    updated_at: datetime = Field(default_factory=get_utc_time, description="Update timestamp")
    details_embedding: Optional[List[float]] = Field(None, description="The embedding of the details")
    concept_embedding: Optional[List[float]] = Field(None, description="The embedding of the concept")
    definition_embedding: Optional[List[float]] = Field(None, description="The embedding of the definition")
    embedding_config: Optional[EmbeddingConfig] = Field(None, description="The embedding configuration used by the event")


class SemanticMemoryItemResponse(SemanticMemoryItem):
    """
    Response schema for semantic memory item.
    """
    pass
