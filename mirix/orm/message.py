from typing import Optional

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mirix.orm.custom_columns import ToolCallColumn
from mirix.orm.mixins import AgentMixin, OrganizationMixin
from mirix.orm.sqlalchemy_base import SqlalchemyBase
from mirix.schemas.message import Message as PydanticMessage
from mirix.schemas.openai.chat_completions import ToolCall


class Message(SqlalchemyBase, OrganizationMixin, AgentMixin):
    """Defines data model for storing Message objects"""

    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_agent_created_at", "agent_id", "created_at"),)
    __pydantic_model__ = PydanticMessage

    id: Mapped[str] = mapped_column(primary_key=True, doc="Unique message identifier")
    role: Mapped[str] = mapped_column(doc="Message role (user/assistant/system/tool)")
    text: Mapped[Optional[str]] = mapped_column(nullable=True, doc="Message content")
    model: Mapped[Optional[str]] = mapped_column(nullable=True, doc="LLM model used")
    name: Mapped[Optional[str]] = mapped_column(nullable=True, doc="Name for multi-agent scenarios")
    tool_calls: Mapped[ToolCall] = mapped_column(ToolCallColumn, doc="Tool call information")
    tool_call_id: Mapped[Optional[str]] = mapped_column(nullable=True, doc="ID of the tool call")
    step_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("steps.id", ondelete="SET NULL"), nullable=True, doc="ID of the step that this message belongs to"
    )

    # Relationships
    agent: Mapped["Agent"] = relationship("Agent", back_populates="messages", lazy="selectin")
    organization: Mapped["Organization"] = relationship("Organization", back_populates="messages", lazy="selectin")
    step: Mapped["Step"] = relationship("Step", back_populates="messages", lazy="selectin")
