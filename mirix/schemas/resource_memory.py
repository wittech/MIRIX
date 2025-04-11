from datetime import datetime
from typing import Dict, List, Optional, Any

from pydantic import Field

from mirix.schemas.mirix_base import MirixBase
from mirix.schemas.embedding_config import EmbeddingConfig
from mirix.utils import get_utc_time

class ResourceMemoryItemBase(MirixBase):
    """
    Base schema for resource memory items - storing docs, user files, references, etc.
    """
    __id_prefix__ = "res_item"
    title: str = Field(..., description="Short name/title of the resource")
    summary: str = Field(None, description="Short description or summary of the resource")
    resource_type: str = Field(..., description="File type or format (e.g. 'doc', 'markdown', 'pdf_text')")
    content: str = Field(..., description="Full or partial text content of the resource")

class ResourceMemoryItem(ResourceMemoryItemBase):
    """
    Full schema for resource memory items with DB fields.
    """
    id: str = ResourceMemoryItemBase.generate_id_field()
    created_at: datetime = Field(default_factory=get_utc_time, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    organization_id: str = Field(..., description="The unique identifier of the organization")
    summary_embedding: Optional[List[float]] = Field(None, description="The embedding of the summary")
    embedding_config: Optional[EmbeddingConfig] = Field(None, description="The embedding configuration used by the event")
    metadata_: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary additional metadata (tags, creation date, etc.)")

class ResourceMemoryItemUpdate(MirixBase):
    """Schema for updating an existing resource memory item."""
    id: str = Field(..., description="Unique ID for this resource memory entry")
    title: Optional[str] = Field(None, description="Short name/title of the resource")
    summary: Optional[str] = Field(None, description="Short description or summary of the resource")
    resource_type: Optional[str] = Field(None, description="File type/format (e.g. 'doc', 'markdown')")
    content: Optional[str] = Field(None, description="Full or partial text content")
    organization_id: Optional[str] = Field(None, description="The organization ID")
    updated_at: datetime = Field(default_factory=get_utc_time, description="Update timestamp")
    summary_embedding: Optional[List[float]] = Field(None, description="The embedding of the summary")
    embedding_config: Optional[EmbeddingConfig] = Field(None, description="The embedding configuration used by the event")
    metadata_: Optional[Dict[str, Any]] = Field(None, description="Arbitrary additional metadata")

class ResourceMemoryItemResponse(ResourceMemoryItem):
    """Response schema for resource memory item with additional fields if needed."""
    pass
