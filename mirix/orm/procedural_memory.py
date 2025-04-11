from typing import TYPE_CHECKING

from sqlalchemy import Column, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, declared_attr, relationship

from mirix.orm.sqlalchemy_base import SqlalchemyBase
from mirix.orm.mixins import OrganizationMixin

from mirix.schemas.procedural_memory import ProceduralMemoryItem as PydanticProceduralMemoryItem
from mirix.orm.custom_columns import CommonVector, EmbeddingConfigColumn
from mirix.constants import MAX_EMBEDDING_DIM
from mirix.settings import settings

if TYPE_CHECKING:
    from mirix.orm.organization import Organization


class ProceduralMemoryItem(SqlalchemyBase, OrganizationMixin):
    """
    Stores procedural memory entries, such as workflows, step-by-step guides, or how-to knowledge.
    
    type:        The category or tag of the procedure (e.g. 'workflow', 'guide', 'script')
    description: Short descriptive text about what this procedure accomplishes
    steps:       Step-by-step instructions or method
    metadata_:   Additional fields/notes
    """

    __tablename__ = "procedural_memory_items"
    __pydantic_model__ = PydanticProceduralMemoryItem

    # Primary key
    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        doc="Unique ID for this procedural memory entry",
    )

    # Distinguish the type/category of the procedure
    entry_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
        doc="Category or type (e.g. 'workflow', 'guide', 'script')"
    )

    # A human-friendly description of this procedure
    description: Mapped[str] = mapped_column(
        String,
        nullable=True,
        doc="Short description or title of the procedure"
    )

    # Steps or instructions stored as a JSON object/list
    steps: Mapped[str] = mapped_column(
        String,
        nullable=True,
        doc="Step-by-step instructions or method stored in JSON"
    )

    # Optional metadata
    metadata_: Mapped[dict] = mapped_column(
        JSON,
        default={},
        nullable=True,
        doc="Arbitrary additional metadata as a JSON object"
    )

    embedding_config: Mapped[dict] = mapped_column(EmbeddingConfigColumn, doc="Embedding configuration")
    
    # Vector embedding field based on database type
    if settings.mirix_pg_uri_no_default:
        from pgvector.sqlalchemy import Vector
        description_embedding = mapped_column(Vector(MAX_EMBEDDING_DIM))
        steps_embedding = mapped_column(Vector(MAX_EMBEDDING_DIM))
    else:
        description_embedding = Column(CommonVector)
        steps_embedding = Column(CommonVector)


    @declared_attr
    def organization(cls) -> Mapped["Organization"]:
        """
        Relationship to organization (mirroring your existing patterns).
        Adjust 'back_populates' to match the collection name in your `Organization` model.
        """
        return relationship(
            "Organization",
            back_populates="procedural_memory_items",
            lazy="selectin"
        )
