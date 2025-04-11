from typing import TYPE_CHECKING
from sqlalchemy import Column, JSON, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, declared_attr, relationship
from mirix.orm.sqlalchemy_base import SqlalchemyBase
from mirix.orm.mixins import OrganizationMixin
from mirix.schemas.semantic_memory import SemanticMemoryItem as PydanticSemanticMemoryItem
import datetime
from mirix.orm.custom_columns import CommonVector, EmbeddingConfigColumn
from mirix.constants import MAX_EMBEDDING_DIM
from mirix.settings import settings

if TYPE_CHECKING:
    from mirix.orm.organization import Organization


class SemanticMemoryItem(SqlalchemyBase, OrganizationMixin):
    """
    Stores semantic memory entries that represent general knowledge,
    concepts, facts, and language elements that can be accessed without 
    relying on specific contextual experiences.

    Attributes:
        id: Unique ID for this semantic memory entry.
        concept: The title or primary concept (e.g., "Simulated Reality", "Quantum Mechanics").
        definition: A concise definition or summary of the concept.
        details: A more detailed explanation or contextual description.
        source: The reference or origin of the information (e.g., book, article, movie).
        metadata_: Arbitrary additional metadata as a JSON object.
        created_at: Timestamp indicating when the entry was created.
    """

    __tablename__ = "semantic_memory_items"
    __pydantic_model__ = PydanticSemanticMemoryItem

    # Primary key
    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        doc="Unique ID for this semantic memory entry"
    )

    # The title or main concept of the knowledge entry
    concept: Mapped[str] = mapped_column(
        String,
        nullable=False,
        doc="The title or primary concept for the knowledge entry"
    )

    # A brief definition or summary of the concept
    definition: Mapped[str] = mapped_column(
        String,
        nullable=True,
        doc="A concise definition or summary of the concept"
    )

    # Detailed explanation or extended context about the concept
    details: Mapped[str] = mapped_column(
        String,
        nullable=True,
        doc="Detailed explanation or additional context for the concept"
    )

    # Reference or source of the general knowledge (e.g., book, article, or movie)
    source: Mapped[str] = mapped_column(
        String,
        nullable=True,
        doc="The reference or origin of this information (e.g., book, article, or movie)"
    )

    # Additional arbitrary metadata stored as a JSON object
    metadata_: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=True,
        doc="Additional arbitrary metadata as a JSON object"
    )

    # Timestamp indicating when this entry was created
    created_at: Mapped[DateTime] = mapped_column(
        DateTime,
        default=datetime.datetime.utcnow,
        nullable=False,
        doc="Timestamp when this semantic memory entry was created"
    )

    embedding_config: Mapped[dict] = mapped_column(EmbeddingConfigColumn, doc="Embedding configuration")
    
    # Vector embedding field based on database type
    if settings.mirix_pg_uri_no_default:
        from pgvector.sqlalchemy import Vector
        details_embedding = mapped_column(Vector(MAX_EMBEDDING_DIM))
        concept_embedding = mapped_column(Vector(MAX_EMBEDDING_DIM))
        definition_embedding = mapped_column(Vector(MAX_EMBEDDING_DIM))
    else:
        details_embedding = Column(CommonVector)
        concept_embedding = Column(CommonVector)
        definition_embedding = Column(CommonVector)

    @declared_attr
    def organization(cls) -> Mapped["Organization"]:
        """
        Relationship to organization, mirroring existing patterns.
        Adjust 'back_populates' to match the collection name in your `Organization` model.
        """
        return relationship(
            "Organization",
            back_populates="semantic_memory_items",
            lazy="selectin"
        )
