import numpy as np
from typing import List, Optional, Dict, Any
from mirix.constants import (
    CORE_MEMORY_TOOLS, BASE_TOOLS, 
    MAX_EMBEDDING_DIM, 
    EPISODIC_MEMORY_TOOLS, PROCEDURAL_MEMORY_TOOLS,
    RESOURCE_MEMORY_TOOLS, KNOWLEDGE_VAULT_TOOLS, META_MEMORY_TOOLS
)
from mirix.orm.sqlite_functions import adapt_array
from mirix.schemas.embedding_config import EmbeddingConfig
from mirix.embeddings import embedding_model, parse_and_chunk_text
from sqlalchemy import Select, func, literal, select, union_all
from functools import wraps
import pytz

def build_query(base_query,
                search_field,
                query_text: Optional[str]=None,
                embed_query: bool=True,
                embedding_config: Optional[EmbeddingConfig]=None,
                ascending: bool=True,
                target_class: object=None):
        """
        Build a query based on the query text
        """

        embedded_text = None
        if embed_query:
            assert embedding_config is not None, "embedding_config must be specified for vector search"
            assert query_text is not None, "query_text must be specified for vector search"
            embedded_text = embedding_model(embedding_config).get_text_embedding(query_text)
            embedded_text = np.array(embedded_text)
            embedded_text = np.pad(embedded_text, (0, MAX_EMBEDDING_DIM - embedded_text.shape[0]), mode="constant").tolist()

        main_query = base_query.order_by(None)

        if embedded_text:
            # SQLite with custom vector type
            query_embedding_binary = np.frombuffer(bytes(adapt_array(embedded_text)), dtype=np.float32)

            if ascending:
                main_query = main_query.order_by(
                    func.cosine_distance(search_field, query_embedding_binary).asc(),
                    target_class.created_at.asc(),
                    target_class.id.asc(),
                )
            else:
                main_query = main_query.order_by(
                    func.cosine_distance(search_field, query_embedding_binary).asc(),
                    target_class.created_at.desc(),
                    target_class.id.asc(),
                )
    
        else:
            # TODO: add other kinds of search
            raise NotImplementedError
        
        return main_query

def update_timezone(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Access timezone_str from kwargs (it will be None if not provided)
        timezone_str = kwargs.get('timezone_str')

        if timezone_str is None:
            # try finding the actor:
            actor = kwargs.get('actor')
            timezone_str = actor.timezone if actor else None
        
        # Call the original function to get its result
        results = func(*args, **kwargs)

        if timezone_str:
            for result in results:
                if hasattr(result, 'occurred_at'):
                    if result.occurred_at.tzinfo is None:
                        result.occurred_at = pytz.utc.localize(result.occurred_at)
                    target_tz = pytz.timezone(timezone_str.split(" (")[0])
                    result.occurred_at = result.occurred_at.astimezone(target_tz)
                if hasattr(result, 'created_at'):
                    if result.created_at.tzinfo is None:
                        result.created_at = pytz.utc.localize(result.created_at)
                    target_tz = pytz.timezone(timezone_str.split(" (")[0])
                    result.created_at = result.created_at.astimezone(target_tz)
        
        return results

    return wrapper