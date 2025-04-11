from typing import List, Optional
from mirix.agent import Agent, AgentState


def send_message(self: "Agent",  agent_state: "AgentState", message: str, topic: str = None) -> Optional[str]:
    """
    Sends a message to the human user. Meanwhile, whenever this function is called, the agent needs to include the `topic` of the current focus. It can be the same as before, it can also be updated when the agent is focusing on something different.

    Args:
        message (str): Message contents. All unicode (including emojis) are supported.
        topic (str): The focus of the agent right now. It is used to track the most recent topic in the conversation and will be used to retrieve the relevant memories from each memory component. 

    Returns:
        Optional[str]: None is always returned as this function does not produce a response.
    """
    # FIXME passing of msg_obj here is a hack, unclear if guaranteed to be the correct reference
    self.interface.assistant_message(message)  # , msg_obj=self._messages[-1])
    agent_state.topic = topic
    return None


# def wrap_message(self: "Agent",  agent_state: "AgentState", content: str, message_type: str, topic: str = None) -> Optional[str]:
#     """
#     This function should be called whenever the agent is not calling other functions. If the agent wants to send out the message to the user, it should call this function with `message_type` being `assitant`; If the agent is doing reasoning and chaining, then it should call this function with `message_type` being `reasoning`. Each time this function is called, the agent needs to include the `topic` of the current focus. It can be the same as before, it can also be updated when the agent is focusing on something different.
    
#     Args:
#         content (str): Message contents. All unicode (including emojis) are supported.
#         message_type (str): The type of the message, It should be chosen from the following: 'assistant' (the agent is sending a message to the user), 'reasoning' (the agent is doing reasoning and chaining). 
#         topic (str): The focus of the agent right now. It is used to track the most recent topic in the conversation and will be used to retrieve the relevant memories from each memory component. 

#     Returns:
#         Optional[str]: None is always returned as this function does not produce a response.
#     """
#     # FIXME passing of msg_obj here is a hack, unclear if guaranteed to be the correct reference
#     if message_type == 'assistant':
#         self.interface.assistant_message(content)  # , msg_obj=self._messages[-1])
#     else:
#         self.interface.internal_monologue(content)
#     agent_state.topic = topic
#     return None

def conversation_search(self: "Agent", query: str, page: Optional[int] = 0) -> Optional[str]:
    """
    Search prior conversation history using case-insensitive string matching.

    Args:
        query (str): String to search for.
        page (int): Allows you to page through results. Only use on a follow-up query. Defaults to 0 (first page).

    Returns:
        str: Query result string
    """

    import math

    from mirix.constants import RETRIEVAL_QUERY_DEFAULT_PAGE_SIZE
    from mirix.utils import json_dumps

    if page is None or (isinstance(page, str) and page.lower().strip() == "none"):
        page = 0
    try:
        page = int(page)
    except:
        raise ValueError(f"'page' argument must be an integer")
    count = RETRIEVAL_QUERY_DEFAULT_PAGE_SIZE
    # TODO: add paging by page number. currently cursor only works with strings.
    # original: start=page * count
    messages = self.message_manager.list_user_messages_for_agent(
        agent_id=self.agent_state.id,
        actor=self.user,
        query_text=query,
        limit=count,
    )
    total = len(messages)
    num_pages = math.ceil(total / count) - 1  # 0 index
    if len(messages) == 0:
        results_str = f"No results found."
    else:
        results_pref = f"Showing {len(messages)} of {total} results (page {page}/{num_pages}):"
        results_formatted = [message.text for message in messages]
        results_str = f"{results_pref} {json_dumps(results_formatted)}"
    return results_str


def search_in_memory(self: "Agent", memory_type: str, query: str, search_field: str, search_method: str, timezone_str: str) -> Optional[str]:
    """
    Choose which memory to search. 
    
    Args:
        memory_type: The type of memory to search in. It should be chosen from the following: "episodic", "resource", "procedural", "knowledge_vault", "semantic", "all". Here "all" means searching in all the memories. 
        query: The keywords/query used to search in the memory.        
        search_field: The field to search in the memory. It should be chosen from the attributes of the corresponding memory. For "episodic" memory, it can be 'summary', 'details'; for "resource" memory, it can be 'summary', 'content'; for "procedural" memory, it can be 'description', 'steps'; for "knowledge_vault", it can be 'secret_value', 'description'; for semantic memory, it can be 'concept', 'definition', 'details'. For "all", it should also be "null" as the system will search all memories with default fields. 
        search_method: The method to search in the memory. It should be chosen from the following methods: 'string_match' (find the content that contains the `query`), 'fuzzy_match' (find the content that has similar strings as the `query`), 'semantic_match' (use text embeddings to find the most similar embeddings in the memory). 
    
    Returns:
        str: Query result string
    """

    if memory_type == 'episodic' or memory_type == 'all':
        episodic_events = self.episodic_memory_manager.list_episodic_events(
            agent_state=self.agent_state,
            query=query,
            search_field=search_field if search_field != 'null' else 'summary',
            search_method=search_method,
            limit=10,
            timezone_str=timezone_str,
        )
        formatted_results_from_episodic = [{'event_id': x.id, 'timestamp': x.occurred_at, 'event_type': x.event_type, 'actor': x.actor, 'summary': x.summary, 'details': x.details} for x in episodic_events]
        if memory_type == 'episodic':
            return formatted_results_from_episodic, len(formatted_results_from_episodic)

    if memory_type == 'resource' or memory_type == 'all':
        resource_memories = self.resource_memory_manager.list_resources(agent_state=self.agent_state,
            query=query,
            search_field=search_field if search_field != 'null' else 'summary',
            search_method=search_method,
            limit=10,
            timezone_str=timezone_str,
        )
        formatted_results_resource = [{'resource_id': x.id, 'resource_type': x.resource_type, 'summary': x.summary, 'content': x.content} for x in resource_memories]
        if memory_type == 'resource':
            return formatted_results_resource, len(formatted_results_resource)
    
    if memory_type == 'procedural' or memory_type == 'all':
        procedural_memories = self.procedural_memory_manager.list_procedures(agent_state=self.agent_state,
            query=query,
            search_field=search_field if search_field != 'null' else 'description',
            search_method=search_method,
            limit=10,
            timezone_str=timezone_str,
        )
        formatted_results_procedural = [{'procedure_id': x.id, 'entry_type': x.entry_type, 'description': x.description, 'steps': x.steps} for x in procedural_memories]
        if memory_type == 'procedural':
            return formatted_results_procedural, len(formatted_results_procedural)
    
    if memory_type == 'knowledge_vault' or memory_type == 'all':
        knowledge_vault_memories = self.knowledge_vault_manager.list_knowledge(agent_state=self.agent_state,
            query=query,
            search_field=search_field if search_field != 'null' else 'description',
            search_method=search_method,
            limit=10,
            timezone_str=timezone_str,
        )
        formatted_results_knowledge_vault = [{'knowledge_id': x.id, 'entry_type': x.entry_type, 'source': x.source, 'sensitivity': x.sensitivity, 'secret_value': x.secret_value, 'description': x.description} for x in knowledge_vault_memories]
        if memory_type == 'knowledge_vault':
            return formatted_results_knowledge_vault, len(formatted_results_knowledge_vault)

    if memory_type == 'semantic' or memory_type == 'all':
        semantic_memories = self.semantic_memory_manager.list_semantic_items(agent_state=self.agent_state,
            query=query,
            search_field=search_field if search_field != 'null' else 'concept',
            search_method=search_method,
            limit=10,
            timezone_str=timezone_str,
        )
        # concept, definition, details, source
        formatted_results_semantic = [{'semantic_id': x.id, 'concept': x.concept, 'definition': x.definition, 'details': x.details, 'source': x.source} for x in semantic_memories]
        if memory_type == 'semantic':
            return formatted_results_semantic, len(formatted_results_semantic)

    else:
        raise ValueError(f"Memory type '{memory_type}' is not supported. Please choose from 'episodic', 'resource', 'procedural', 'knowledge_vault', 'semantic'.")

    return formatted_results_from_episodic + formatted_results_resource + formatted_results_procedural + formatted_results_knowledge_vault + formatted_results_semantic, len(formatted_results_from_episodic) + len(formatted_results_resource) + len(formatted_results_procedural) + len(formatted_results_knowledge_vault) + len(formatted_results_semantic)