import uuid
from typing import List, Optional, Dict, Any

import numpy as np
from mirix.orm.errors import NoResultFound
from mirix.orm.semantic_memory import SemanticMemoryItem
from mirix.schemas.user import User as PydanticUser
from mirix.schemas.semantic_memory import (
    SemanticMemoryItem as PydanticSemanticMemoryItem,
    SemanticMemoryItemUpdate
)
from mirix.utils import enforce_types
from pydantic import BaseModel
from sqlalchemy import select, func
from rapidfuzz import fuzz

from mirix.schemas.agent import AgentState
from mirix.embeddings import embedding_model, parse_and_chunk_text
from mirix.orm.sqlite_functions import adapt_array
from mirix.schemas.embedding_config import EmbeddingConfig
from mirix.services.utils import build_query, update_timezone

class SemanticMemoryManager:
    """Manager class to handle business logic related to Semantic Memory Items."""

    def __init__(self):
        from mirix.server.server import db_context
        self.session_maker = db_context

    @update_timezone
    @enforce_types
    def get_item_by_id(self, item_id: str, actor: PydanticUser, timezone_str: str) -> Optional[PydanticSemanticMemoryItem]:
        """Fetch a semantic memory item by ID."""
        with self.session_maker() as session:
            try:
                item = SemanticMemoryItem.read(db_session=session, identifier=item_id, actor=actor)
                return item.to_pydantic()
            except NoResultFound:
                raise NoResultFound(f"Semantic memory item with id {item_id} not found.")

    @enforce_types
    def create_item(self, item_data: PydanticSemanticMemoryItem) -> PydanticSemanticMemoryItem:
        """Create a new semantic memory item."""
        data_dict = item_data.model_dump()

        # Validate required fields
        required_fields = ["concept", "definition"]
        for field in required_fields:
            if field not in data_dict or not data_dict[field]:
                raise ValueError(f"Required field '{field}' missing from semantic memory data")

        data_dict.setdefault("id", str(uuid.uuid4()))
        data_dict.setdefault("metadata_", {})

        with self.session_maker() as session:
            item = SemanticMemoryItem(**data_dict)
            item.create(session)
            return item.to_pydantic()

    @enforce_types
    def update_item(self, item_update: SemanticMemoryItemUpdate, actor: PydanticUser) -> PydanticSemanticMemoryItem:
        """Update an existing semantic memory item."""
        with self.session_maker() as session:
            item = SemanticMemoryItem.read(db_session=session, identifier=item_update.id, actor=actor)
            update_data = item_update.model_dump(exclude_unset=True)
            for k, v in update_data.items():
                if k not in ["id", "updated_at"]:
                    setattr(item, k, v)
            item.updated_at = item_update.updated_at
            item.update(session, actor=actor)
            return item.to_pydantic()

    @enforce_types
    def create_many_items(self, items: List[PydanticSemanticMemoryItem], actor: PydanticUser) -> List[PydanticSemanticMemoryItem]:
        """Create multiple semantic memory items."""
        return [self.create_item(i) for i in items]

    @update_timezone
    @enforce_types
    def list_semantic_items(self, 
                            agent_state: AgentState,
                            query: str = '', 
                            search_field: str = '',
                            search_method: str = 'semantic_match',
                            limit: Optional[int] = 50,
                            timezone_str: str = None) -> List[PydanticSemanticMemoryItem]:
        """
        List semantic memory items.
        """
        with self.session_maker() as session:
            
            if query == '':
                result = session.execute(select(SemanticMemoryItem))
                semantic_items = result.scalars().all()
                return [item.to_pydantic() for item in semantic_items]

            else:
                
                base_query = select(
                    SemanticMemoryItem.id.label("id"),
                    SemanticMemoryItem.created_at.label("created_at"),
                    SemanticMemoryItem.concept.label("concept"),
                    SemanticMemoryItem.definition.label("definition"),
                    SemanticMemoryItem.details.label("details"),
                    SemanticMemoryItem.source.label("source"),
                    SemanticMemoryItem.concept_embedding.label("concept_embedding"),
                    SemanticMemoryItem.definition_embedding.label("definition_embedding"),
                    SemanticMemoryItem.details_embedding.label("details_embedding"),
                    SemanticMemoryItem.embedding_config.label("embedding_config"),
                    SemanticMemoryItem.organization_id.label("organization_id"),
                    SemanticMemoryItem.metadata_.label("metadata_"),
                )

                if search_method == 'semantic_match':
                    embed_query = True
                    embedding_config = agent_state.embedding_config

                    main_query = build_query(
                        base_query=base_query,
                        query_text=query,
                        embed_query=embed_query,
                        embedding_config=embedding_config,
                        search_field=eval("SemanticMemoryItem." + search_field + "_embedding"),
                        target_class=SemanticMemoryItem,
                    )

                elif search_method == 'string_match':

                    search_field = eval("SemanticMemoryItem." + search_field)
                    main_query = base_query.where(func.lower(search_field).contains(query.lower()))

                elif search_method == 'fuzzy_match':
                    # Fuzzy matching: load all candidate items into memory and compute a fuzzy match score.
                    result = session.execute(select(SemanticMemoryItem))
                    all_items = result.scalars().all()
                    scored_items = []
                    for item in all_items:
                        # Determine which field to use:
                        # 1. If a search_field is provided (e.g., "concept" or "definition") and exists in the item, use it.
                        # 2. Otherwise, default to using the "concept" field.
                        if search_field and hasattr(item, search_field):
                            text_to_search = getattr(item, search_field)
                        else:
                            text_to_search = item.concept
                        # Compute the fuzzy matching score using partial_ratio for better short-to-long matching.
                        score = fuzz.partial_ratio(query.lower(), text_to_search.lower())
                        scored_items.append((score, item))
                    
                    # Sort items descending by score and pick the top ones.
                    scored_items.sort(key=lambda x: x[0], reverse=True)
                    top_items = [item for score, item in scored_items[:limit]]
                    return [item.to_pydantic() for item in top_items]

            if limit:
                main_query = main_query.limit(limit)

            results = list(session.execute(main_query))

            semantic_items = []
            for row in results:
                data = dict(row._mapping)
                semantic_items.append(SemanticMemoryItem(**data))

            return [item.to_pydantic() for item in semantic_items]

    @enforce_types
    def insert_semantic_item(
        self,
        agent_state: AgentState,
        concept: str,
        definition: str,
        details: Optional[str],
        source: Optional[str],
        organization_id: str
    ) -> PydanticSemanticMemoryItem:
        """
        Create a new semantic memory entry using provided parameters.
        """
        try:
            # TODO: need to check if we need to chunk the text
            embed_model = embedding_model(agent_state.embedding_config)
            concept_embedding = embed_model.get_text_embedding(concept)
            definition_embedding = embed_model.get_text_embedding(definition)
            details_embedding = embed_model.get_text_embedding(details)

            semantic_item = self.create_item(
                item_data=PydanticSemanticMemoryItem(
                    concept=concept,
                    definition=definition,
                    details=details,
                    source=source,
                    organization_id=organization_id,
                    details_embedding=details_embedding,
                    concept_embedding=concept_embedding,
                    definition_embedding=definition_embedding,
                    embedding_config=agent_state.embedding_config,
                )
            )
            return semantic_item
        except Exception as e:
            raise e


    def delete_semantic_item_by_id(self, id: str) -> None:
        """Delete a semantic memory item by ID."""
        with self.session_maker() as session:
            try:
                item = SemanticMemoryItem.read(db_session=session, identifier=id)
                item.hard_delete(session)
            except NoResultFound:
                raise NoResultFound(f"Semantic memory item with id {id} not found.")