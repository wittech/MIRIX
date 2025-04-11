import uuid
from typing import List, Optional, Dict, Any

import numpy as np
from mirix.orm.errors import NoResultFound
from mirix.orm.procedural_memory import ProceduralMemoryItem
from mirix.schemas.user import User as PydanticUser
from mirix.schemas.procedural_memory import (
    ProceduralMemoryItem as PydanticProceduralMemoryItem,
    ProceduralMemoryItemUpdate
)
from mirix.utils import enforce_types
from pydantic import BaseModel, Field
from sqlalchemy import select

from mirix.schemas.agent import AgentState
from mirix.embeddings import embedding_model, parse_and_chunk_text
from mirix.orm.sqlite_functions import adapt_array
from mirix.schemas.embedding_config import EmbeddingConfig
from sqlalchemy import Select, func, literal, select, union_all
from mirix.services.utils import build_query, update_timezone
from rapidfuzz import fuzz


class ProceduralMemoryManager:
    """Manager class to handle business logic related to Procedural Memory Items."""

    def __init__(self):
        from mirix.server.server import db_context
        self.session_maker = db_context

    @update_timezone
    @enforce_types
    def get_item_by_id(self, item_id: str, actor: PydanticUser, timezone_str: str) -> Optional[PydanticProceduralMemoryItem]:
        """Fetch a procedural memory item by ID."""
        with self.session_maker() as session:
            try:
                item = ProceduralMemoryItem.read(db_session=session, identifier=item_id, actor=actor)
                return item.to_pydantic()
            except NoResultFound:
                raise NoResultFound(f"Procedural memory item with id {item_id} not found.")

    @enforce_types
    def create_item(self, item_data: PydanticProceduralMemoryItem) -> PydanticProceduralMemoryItem:
        """Create a new procedural memory item."""
        data_dict = item_data.model_dump()

        # Validate required fields
        required_fields = ["entry_type"]
        for field in required_fields:
            if field not in data_dict:
                raise ValueError(f"Required field '{field}' missing from procedural memory data")

        data_dict.setdefault("id", str(uuid.uuid4()))
        data_dict.setdefault("metadata_", {})

        with self.session_maker() as session:
            item = ProceduralMemoryItem(**data_dict)
            item.create(session)
            return item.to_pydantic()

    @enforce_types
    def update_item(self, item_update: ProceduralMemoryItemUpdate, actor: PydanticUser) -> PydanticProceduralMemoryItem:
        """Update an existing procedural memory item."""
        with self.session_maker() as session:
            item = ProceduralMemoryItem.read(db_session=session, identifier=item_update.id, actor=actor)
            update_data = item_update.model_dump(exclude_unset=True)
            for k, v in update_data.items():
                if k not in ["id", "updated_at"]:  # or allow updated_at if you want
                    setattr(item, k, v)
            item.updated_at = item_update.updated_at  # or get_utc_time
            item.update(session, actor=actor)
            return item.to_pydantic()

    @enforce_types
    def create_many_items(self, items: List[PydanticProceduralMemoryItem], actor: PydanticUser) -> List[PydanticProceduralMemoryItem]:
        """Create multiple procedural memory items."""
        return [self.create_item(i, actor) for i in items]

    @update_timezone
    @enforce_types
    def list_procedures(self, 
                        agent_state: AgentState,
                        query: str = '', 
                        search_field: str = '',
                        search_method: str = 'semantic_match',
                        limit: Optional[int] = 50,
                        timezone_str: str = None) -> List[PydanticProceduralMemoryItem]:
        """
        List all episodic events
        """
        with self.session_maker() as session:
            
            if query == '':
                result = session.execute(select(ProceduralMemoryItem))
                episodic_events = result.scalars().all()
                return [event.to_pydantic() for event in episodic_events]
            
            else:

                base_query = select(
                    ProceduralMemoryItem.id.label("id"),
                    ProceduralMemoryItem.created_at.label("created_at"),
                    ProceduralMemoryItem.entry_type.label("entry_type"),
                    ProceduralMemoryItem.description.label("description"),
                    ProceduralMemoryItem.steps.label("steps"),
                    ProceduralMemoryItem.steps_embedding.label("steps_embedding"),
                    ProceduralMemoryItem.description_embedding.label("description_embedding"),
                    ProceduralMemoryItem.embedding_config.label("embedding_config"),
                    ProceduralMemoryItem.organization_id.label("organization_id"),
                    ProceduralMemoryItem.metadata_.label("metadata_"),
                )

                if search_method == 'semantic_match':

                    main_query = build_query(
                        base_query=base_query,
                        query_text=query,
                        embed_query=True,
                        embedding_config=agent_state.embedding_config,
                        search_field = eval("ProceduralMemoryItem." + search_field + "_embedding"),
                        target_class=ProceduralMemoryItem,
                    )

                elif search_method == 'string_match':

                    search_field = eval("ProceduralMemoryItem." + search_field)
                    main_query = base_query.where(func.lower(search_field).contains(query.lower()))

                elif search_method == 'fuzzy_match':
                    # For fuzzy matching, load all candidate items into memory.
                    result = session.execute(select(ProceduralMemoryItem))
                    all_items = result.scalars().all()
                    scored_items = []
                    for item in all_items:
                        # Use the provided search_field if available; default to 'description'
                        if search_field and hasattr(item, search_field):
                            text_to_search = getattr(item, search_field)
                        else:
                            text_to_search = item.description
                            
                        # Compute a fuzzy matching score using partial_ratio,
                        # which is suited for comparing a short query to longer text.
                        score = fuzz.partial_ratio(query.lower(), text_to_search.lower())
                        scored_items.append((score, item))
                    
                    # Sort items by score in descending order and select the top ones.
                    scored_items.sort(key=lambda x: x[0], reverse=True)
                    top_items = [item for score, item in scored_items[:limit]]
                    return [item.to_pydantic() for item in top_items]

                if limit:
                    main_query = main_query.limit(limit)

                results = list(session.execute(main_query))
                
                procedures = []
                for row in results:
                    data = dict(row._mapping)
                    procedures.append(ProceduralMemoryItem(**data))
                
                return [procedure.to_pydantic() for procedure in procedures]

    @enforce_types
    def insert_procedure(self,
                         agent_state: AgentState,
                         entry_type: str,
                         description: Optional[str],
                         steps: str,
                         organization_id: str) -> PydanticProceduralMemoryItem:
        
        try:

            # TODO: need to check if we need to chunk the text
            embed_model = embedding_model(agent_state.embedding_config)
            description_embedding = embed_model.get_text_embedding(description)
            steps_embedding = embed_model.get_text_embedding(steps)

            procedure = self.create_item(
                item_data=PydanticProceduralMemoryItem(
                    entry_type=entry_type,
                    description=description,
                    steps=steps,
                    organization_id=organization_id,
                    description_embedding=description_embedding,
                    steps_embedding=steps_embedding,
                    embedding_config=agent_state.embedding_config,
                ),
            )
            return procedure
        
        except Exception as e:
            raise e     
        
    def delete_procedure_by_id(self, id: str) -> None:
        """Delete a procedural memory item by ID."""
        with self.session_maker() as session:
            try:
                item = ProceduralMemoryItem.read(db_session=session, identifier=id)
                item.hard_delete(session)
            except NoResultFound:
                raise NoResultFound(f"Procedural memory item with id {id} not found.")
