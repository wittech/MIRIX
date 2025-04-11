from typing import TYPE_CHECKING
from datetime import datetime

from sqlalchemy import Column, DateTime, String, JSON
from sqlalchemy.orm import Mapped, mapped_column, declared_attr, relationship

from mirix.orm.sqlalchemy_base import SqlalchemyBase
from mirix.orm.mixins import OrganizationMixin

from mirix.schemas.episodic_event import EpisodicEvent as PydanticEpisodicEvent

from mirix.orm.custom_columns import CommonVector, EmbeddingConfigColumn
from mirix.constants import MAX_EMBEDDING_DIM
from mirix.settings import settings

if TYPE_CHECKING:
    from mirix.orm.organization import Organization


class EpisodicEvent(SqlalchemyBase, OrganizationMixin):
    """
    Represents an event in the 'episodic memory' system, capturing
    timestamped interactions or observations with a short summary
    and optional detailed notes or metadata.
    """

    __tablename__ = "episodic_events"
    __pydantic_model__ = PydanticEpisodicEvent

    # Primary key
    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        doc="Unique ID for the episodic event",
    )

    # When did this event occur? (You can store creation time or an explicit event time.)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime,
        doc="Timestamp when the event occurred or was recorded"
    )

    # Who or what triggered this event (e.g., 'user', 'assistant', 'system', etc.)
    actor: Mapped[str] = mapped_column(
        String,
        doc="Identifies the actor/source of this event"
    )

    event_type: Mapped[str] = mapped_column(
        String,
        doc="Type/category of the episodic event (e.g., user_message, inference, system_notification)"
    )

    # A brief summary/title of the event
    summary: Mapped[str] = mapped_column(
        String,
        doc="Short summary of the event"
    )

    # A longer description or narrative if needed
    details: Mapped[str] = mapped_column(
        String,
        nullable=True,
        doc="Detailed description or narrative about this event"
    )

    # Arbitrary JSON metadata for extra fields (e.g., references, tags, confidence, etc.)
    metadata_: Mapped[dict] = mapped_column(
        JSON,
        default={},
        nullable=True,
        doc="Additional metadata for flexible storage"
    )

    embedding_config: Mapped[dict] = mapped_column(EmbeddingConfigColumn, doc="Embedding configuration")
    
    # Vector embedding field based on database type
    if settings.mirix_pg_uri_no_default:
        from pgvector.sqlalchemy import Vector
        details_embedding = mapped_column(Vector(MAX_EMBEDDING_DIM))
        summary_embedding = mapped_column(Vector(MAX_EMBEDDING_DIM))
    else:
        details_embedding = Column(CommonVector)
        summary_embedding = Column(CommonVector)

    @declared_attr
    def organization(cls) -> Mapped["Organization"]:
        """
        Relationship to the Organization that owns this event.
        Matches back_populates on the 'EpisodicEvent' relationship in Organization.
        """
        return relationship(
            "Organization",
            back_populates="episodic_events",
            lazy="selectin"
        )
