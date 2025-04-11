import uuid
from typing import List, Optional, Dict, Any
from rapidfuzz import fuzz

from mirix.orm.errors import NoResultFound
from mirix.embeddings import embedding_model, parse_and_chunk_text
from mirix.orm.resource_memory import ResourceMemoryItem
from mirix.schemas.user import User as PydanticUser
from mirix.schemas.resource_memory import (
    ResourceMemoryItem as PydanticResourceMemoryItem,
    ResourceMemoryItemUpdate
)
from mirix.schemas.agent import AgentState
from mirix.utils import enforce_types
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from mirix.services.utils import build_query, update_timezone

class ResourceMemoryManager:
    """Manager class to handle logic related to Resource/Workspace Memory Items."""

    def __init__(self):
        from mirix.server.server import db_context
        self.session_maker = db_context

    @update_timezone
    @enforce_types
    def get_item_by_id(self, item_id: str, actor: PydanticUser, timezone_str: str) -> Optional[PydanticResourceMemoryItem]:
        """Fetch a resource memory item by ID."""
        with self.session_maker() as session:
            try:
                item = ResourceMemoryItem.read(db_session=session, identifier=item_id, actor=actor)
                return item.to_pydantic()
            except NoResultFound:
                raise NoResultFound(f"Resource memory item with id {item_id} not found.")

    @enforce_types
    def create_item(self, item_data: PydanticResourceMemoryItem) -> PydanticResourceMemoryItem:
        """Create a new resource memory item."""
        data_dict = item_data.model_dump()

        # Validate required fields
        required_fields = ["title", "summary", "content"]
        for field in required_fields:
            if field not in data_dict:
                raise ValueError(f"Required field '{field}' missing from resource memory data")

        data_dict.setdefault("id", str(uuid.uuid4()))
        data_dict.setdefault("metadata_", {})

        with self.session_maker() as session:
            item = ResourceMemoryItem(**data_dict)
            item.create(session)
            return item.to_pydantic()

    @enforce_types
    def update_item(self, item_update: ResourceMemoryItemUpdate, actor: PydanticUser) -> PydanticResourceMemoryItem:
        """Update an existing resource memory item."""
        with self.session_maker() as session:
            item = ResourceMemoryItem.read(db_session=session, identifier=item_update.id, actor=actor)
            update_data = item_update.model_dump(exclude_unset=True)
            for k, v in update_data.items():
                if k not in ["id", "updated_at"]:
                    setattr(item, k, v)
            item.updated_at = item_update.updated_at
            item.update(session, actor=actor)
            return item.to_pydantic()

    @enforce_types
    def create_many_items(self, items: List[PydanticResourceMemoryItem], actor: PydanticUser, limit: Optional[int] = 50) -> List[PydanticResourceMemoryItem]:
        """Create multiple resource memory items."""
        return [self.create_item(i, actor) for i in items]

    @update_timezone
    @enforce_types
    def list_resources(self,
                       agent_state: AgentState,
                       query: str = '',
                       search_field: str = 'content',
                       search_method: str = 'string_match',
                       limit: Optional[int] = 50,
                       timezone_str: str = None) -> List[PydanticResourceMemoryItem]:
        """retrieve resource according to the query"""

        with self.session_maker() as session:

            if query == '':
                result = session.execute(select(ResourceMemoryItem))
                episodic_events = result.scalars().all()
                return [event.to_pydantic() for event in episodic_events][-limit:]

            base_query = select(
                ResourceMemoryItem.id.label("id"),
                ResourceMemoryItem.title.label("title"),
                ResourceMemoryItem.summary.label("summary"),
                ResourceMemoryItem.content.label("content"),
                ResourceMemoryItem.summary_embedding.label("summary_embedding"),
                ResourceMemoryItem.embedding_config.label("embedding_config"),
                ResourceMemoryItem.created_at.label("created_at"),
                ResourceMemoryItem.resource_type.label("resource_type"),
                ResourceMemoryItem.organization_id.label("organization_id"),
                ResourceMemoryItem.metadata_.label("metadata_")
            )

            if search_method == 'string_match':
                main_query = base_query.where(func.lower(getattr(ResourceMemoryItem, search_field)).contains(query.lower()))
            elif search_method == 'semantic_match':
                embed_query = True
                embedding_config = agent_state.embedding_config

                main_query = build_query(
                    base_query=base_query,
                    query_text=query,
                    embed_query=embed_query,
                    embedding_config=embedding_config,
                    search_field = eval("ResourceMemoryItem." + search_field + "_embedding"),
                    target_class=ResourceMemoryItem,
                )

            elif search_method == "fuzzy_match":
                # For fuzzy matching, load all candidate items in memory.
                result = session.execute(select(ResourceMemoryItem))
                all_items = result.scalars().all()
                scored_items = []
                for item in all_items:
                    # Use the provided search_field if available; otherwise, fallback to using the 'summary'.
                    if search_field and hasattr(item, search_field):
                        text_to_search = getattr(item, search_field)
                    else:
                        text_to_search = item.summary
                    
                    # Compute a fuzzy matching score using fuzz.partial_ratio
                    score = fuzz.partial_ratio(query.lower(), text_to_search.lower())
                    scored_items.append((score, item))
                
                # Sort candidates by descending score and select top ones
                scored_items.sort(key=lambda x: x[0], reverse=True)
                top_items = [item for score, item in scored_items[:limit]]
                return [item.to_pydantic() for item in top_items]
        
            else:
                raise ValueError(f"Unknown search method: {search_method}")

            results = list(session.execute(main_query))[:limit]

            resource_memory_items = []

            for row in results:
                data = dict(row._mapping)
                resource_memory_items.append(ResourceMemoryItem(**data))
            
            return [item.to_pydantic() for item in resource_memory_items]

    @enforce_types
    def insert_resource(self, 
                        agent_state: AgentState,
                        title: str,
                        summary: str,
                        resource_type: str,
                        content: str,
                        organization_id: str
                        ) -> PydanticResourceMemoryItem:
        """Create a new resource memory item."""
        try:

            embed_model = embedding_model(agent_state.embedding_config)
            summary_embedding = embed_model.get_text_embedding(summary)

            resource = self.create_item(
                item_data=PydanticResourceMemoryItem(
                    title=title,
                    summary=summary,
                    content=content,
                    resource_type=resource_type,
                    organization_id=organization_id,
                    summary_embedding=summary_embedding,
                    embedding_config=agent_state.embedding_config,
                )
            )
            return resource
        
        except Exception as e:
            raise e     

    @enforce_types
    def delete_resource_by_id(self, item_id: str) -> None:
        """Delete a resource memory item by ID."""
        with self.session_maker() as session:
            try:
                item = ResourceMemoryItem.read(db_session=session, identifier=item_id)
                item.hard_delete(session)
            except NoResultFound:
                raise NoResultFound(f"Resource Memory record with id {id} not found.")
