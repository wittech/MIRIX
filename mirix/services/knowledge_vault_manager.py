import uuid
from typing import List, Optional, Dict, Any

from rapidfuzz import fuzz
from mirix.orm.errors import NoResultFound
from mirix.orm.knowledgevault import KnowledgeVaultItem
from mirix.schemas.user import User as PydanticUser
from mirix.schemas.knowledge_vault import KnowledgeVaultItem as PydanticKnowledgeVaultItem
from mirix.utils import enforce_types
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from mirix.schemas.agent import AgentState
from mirix.embeddings import embedding_model
from difflib import SequenceMatcher
from mirix.services.utils import build_query, update_timezone


class KnowledgeVaultManager:
    """Manager class to handle business logic related to Knowledge Vault Items."""

    def __init__(self):
        from mirix.server.server import db_context
        self.session_maker = db_context

    @update_timezone
    @enforce_types
    def get_item_by_id(self, knowledge_vault_item_id: str, actor: PydanticUser, timezone_str: str) -> Optional[PydanticKnowledgeVaultItem]:
        """Fetch a knowledge vault item by ID."""
        with self.session_maker() as session:
            try:
                item = KnowledgeVaultItem.read(db_session=session, identifier=knowledge_vault_item_id, actor=actor)
                return item.to_pydantic()
            except NoResultFound:
                raise NoResultFound(f"Knowledge vault item with id {knowledge_vault_item_id} not found.")

    @enforce_types
    def create_item(self, knowledge_vault_item: PydanticKnowledgeVaultItem) -> PydanticKnowledgeVaultItem:
        """Create a new knowledge vault item."""

        item_data = knowledge_vault_item.model_dump()
        
        # Validate required fields
        required_fields = ["entry_type", 'secret_value', 'sensitivity']
        for field in required_fields:
            if field not in item_data:
                raise ValueError(f"Required field '{field}' missing from knowledge vault item data")
        
        item_data.setdefault("id", str(uuid.uuid4()))
        item_data.setdefault("metadata_", {})
        
        # Create the knowledge vault item
        with self.session_maker() as session:
            knowledge_item = KnowledgeVaultItem(**item_data)
            knowledge_item.create(session)
            
            # Return the created item as a Pydantic model
            return knowledge_item.to_pydantic()

    @enforce_types
    def create_many_items(self, knowledge_vault_items: List[PydanticKnowledgeVaultItem], actor: PydanticUser) -> List[PydanticKnowledgeVaultItem]:
        """Create multiple knowledge vault items."""
        return [self.create_item(k, actor) for k in knowledge_vault_items]
    
    @enforce_types
    def insert_knowledge(self, 
                         agent_state: AgentState,
                         entry_type: str,
                         source: str,
                         sensitivity: str,
                         secret_value: str,
                         description: str,
                         organization_id: str):
        """Insert knowledge into the knowledge vault."""
        try:

            embed_model = embedding_model(agent_state.embedding_config)
            description_embedding = embed_model.get_text_embedding(description)

            knowledge = self.create_item(
                PydanticKnowledgeVaultItem(
                    entry_type=entry_type,
                    source=source,
                    description=description,
                    sensitivity=sensitivity,
                    secret_value=secret_value,
                    organization_id=organization_id,
                    description_embedding=description_embedding,
                    embedding_config=agent_state.embedding_config,
                )
            )
            return knowledge

        except Exception as e:
            raise e

    @update_timezone
    @enforce_types
    def list_knowledge(self,
                       agent_state: AgentState,
                       query: str = '',
                       search_field: str = '',
                       search_method: str = 'string_match',
                       timestamp_str: str = None,
                       limit: Optional[int] = 50,) -> List[PydanticKnowledgeVaultItem]:
        """
        Retrieve knowledge vault items according to the query.
        """
        with self.session_maker() as session:

            if query == '':
                result = session.execute(select(KnowledgeVaultItem))
                knowledge_vault_items = result.scalars().all()
                return [item.to_pydantic() for item in knowledge_vault_items][-limit:]
            
            else:

                base_query = select(
                    KnowledgeVaultItem.id.label("id"),
                    KnowledgeVaultItem.created_at.label("created_at"),
                    KnowledgeVaultItem.entry_type.label("entry_type"),
                    KnowledgeVaultItem.source.label("source"),
                    KnowledgeVaultItem.sensitivity.label("sensitivity"),
                    KnowledgeVaultItem.secret_value.label("secret_value"),
                    KnowledgeVaultItem.description.label("description"),
                    KnowledgeVaultItem.metadata_.label("metadata_"),
                    KnowledgeVaultItem.organization_id.label("organization_id"),
                )

                if search_method == 'semantic_match':
                    embed_query = True
                    embedding_config = agent_state.embedding_config

                    main_query = build_query(
                        base_query=base_query,
                        query_text=query,
                        embed_query=embed_query,
                        embedding_config=embedding_config,
                        search_field=getattr(KnowledgeVaultItem, search_field + "_embedding"),
                        target_class=KnowledgeVaultItem,
                    )

                elif search_method == 'string_match':

                    search_field = getattr(KnowledgeVaultItem, search_field)
                    main_query = base_query.where(func.lower(search_field).contains(func.lower(query)))
                
                elif search_method == 'fuzzy_match':
                    # Fuzzy matching: load all candidate items into memory,
                    # then compute fuzzy matching score using RapidFuzz.
                    result = session.execute(select(KnowledgeVaultItem))
                    all_items = result.scalars().all()
                    scored_items = []
                    for item in all_items:
                        # Determine which field to use:
                        # 1. If a search_field is provided (like "description" etc.) use that.
                        # 2. Otherwise, fallback to the description.
                        if search_field and hasattr(item, search_field):
                            text_to_search = getattr(item, search_field)
                        else:
                            text_to_search = item.description
                        
                        # Compute the fuzzy matching score using partial_ratio.
                        score = fuzz.partial_ratio(query.lower(), text_to_search.lower())
                        scored_items.append((score, item))
                    
                    # Sort items descending by score and pick the top ones
                    scored_items.sort(key=lambda x: x[0], reverse=True)
                    top_items = [item for score, item in scored_items[:limit]]
                    return [item.to_pydantic() for item in top_items]

            if limit:
                main_query = main_query.limit(limit)

            knowledge_vault_items = []
            results = list(session.execute(main_query))
            for row in results:
                data = dict(row._mapping)
                knowledge_vault_items.append(KnowledgeVaultItem(**data))

            return [item.to_pydantic() for item in knowledge_vault_items]
        
    @enforce_types
    def delete_knowledge_by_id(self, knowledge_vault_item_id: str) -> None:
        """Delete a knowledge vault item by ID."""
        with self.session_maker() as session:
            try:
                item = KnowledgeVaultItem.read(db_session=session, identifier=knowledge_vault_item_id)
                item.hard_delete(session)
            except NoResultFound:
                raise NoResultFound(f"Knowledge vault item with id {knowledge_vault_item_id} not found.")
