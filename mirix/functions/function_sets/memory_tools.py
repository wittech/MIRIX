from typing import List, Optional

from mirix.agent import Agent, AgentState
from mirix.schemas.knowledge_vault import KnowledgeVaultItemBase
from mirix.schemas.episodic_event import EpisodicEventForLLM
from mirix.schemas.resource_memory import ResourceMemoryItemBase
from mirix.schemas.procedural_memory import ProceduralMemoryItemBase
from mirix.schemas.semantic_memory import SemanticMemoryItemBase

def core_memory_append(self: "Agent", agent_state: "AgentState", label: str, content: str) -> Optional[str]:  # type: ignore
    """
    Append to the contents of core memory.

    Args:
        label (str): Section of the memory to be edited (persona or human).
        content (str): Content to write to the memory. All unicode (including emojis) are supported.

    Returns:
        Optional[str]: None is always returned as this function does not produce a response.
    """
    current_value = str(agent_state.memory.get_block(label).value)
    new_value = (current_value + "\n" + str(content)).strip()
    agent_state.memory.update_block_value(label=label, value=new_value)
    return None


def core_memory_replace(self: "Agent", agent_state: "AgentState", label: str, old_content: str, new_content: str) -> Optional[str]:  # type: ignore
    """
    (TEST) Replace the contents of core memory. To delete memories, use an empty string for new_content. Note that the old_content needs to be a substring of the current content. And make sure to include newline character when writing the string.

    Args:
        label (str): Section of the memory to be edited (persona or human).
        old_content (str): String to replace. Must be an exact match and **NEVER** be empty. 
        new_content (str): Content to write to the memory. All unicode (including emojis) are supported.

    Returns:
        Optional[str]: None is always returned as this function does not produce a response.
    """
    current_value = str(agent_state.memory.get_block(label).value)
    if old_content not in current_value:
        raise ValueError(f"Old content '{old_content}' not found in memory block '{label}'")
    new_value = current_value.replace(str(old_content), str(new_content))
    agent_state.memory.update_block_value(label=label, value=new_value)
    return None

def episodic_memory_insert(self: "Agent", items: List[EpisodicEventForLLM]):
    """
    The tool to update episodic memory. The item being inserted into the episodic memory is an event either happened on the user or the assistant.

    Args:
        items (array): List of episodic memory items to insert.

    Returns:
        Optional[str]: None is always returned as this function does not produce a response.
    """
    for item in items:
        self.episodic_memory_manager.insert_event(
            agent_state=self.agent_state,
            timestamp=item['occurred_at'],
            event_type=item['event_type'],
            actor=item['actor'],
            summary=item['summary'],
            details=item['details'],
            organization_id=self.user.organization_id
        )
    response = "Events inserted! Now you need to check if there are repeated events shown in the system prompt."
    return response

def episodic_memory_append(self: "Agent", event_id: str, new_summary: str = None, new_details: str = None):
    """
    The tool to merge the new episodic event into the selected episodic event by event_id, should be used when the user is continuing doing the same thing with more details.
        
    Args:
        event_id (str): This is the id of which episodic event to append to. 
        new_summary (str): The updated summary. Note that it will overwrite the old summary so make sure to include the information from the old summary. The new summary needs to be only slightly different from the old summary.
        new_details (str): The new details to add into the details of the selected episodic event.
    
    Returns:
        Optional[str]: None is always returned as this function does not produce a response.
    """

    episodic_event = self.episodic_memory_manager.update_event(
        event_id=event_id,
        new_summary=new_summary,
        new_details=new_details
    )
    response = "These are the `summary` and the `details` of the updated event:\n", str({'event_id': episodic_event.id, 'summary': episodic_event.summary, 'details': episodic_event.details}) + "\nIf the `details` are too verbose, or the `summary` cannot cover the information in the `details`, call episodic_memory_replace to update this event."
    return response

def episodic_memory_replace(self: "Agent", event_ids: List[str], new_items: List[EpisodicEventForLLM]):
    """
    The tool to merge existing episodic events into a new episodic event when there are repeated events. This function will delete the old episodic events and create a new episodic event with the new summary and details.

    Args:
        event_ids (str): The ids of the episodic events to be replaced.
        new_items: New episodic events to be added. Mostly it should be one event.
    
    Returns:
        Optional[str]: None is always returned as this function does not produce a response.
    """

    for event_id in event_ids:
        # It will raise an error if the event_id is not found in the episodic memory.
        self.episodic_memory_manager.get_episodic_event_by_id(event_id)

    for event_id in event_ids:
        self.episodic_memory_manager.delete_event_by_id(event_id)

    for new_item in new_items:
        self.episodic_memory_manager.insert_event(
            agent_state=self.agent_state,
            timestamp=new_item['occurred_at'],
            event_type=new_item['event_type'],
            actor=new_item['actor'],
            summary=new_item['summary'],
            details=new_item['details'],
            organization_id=self.user.organization_id
        )

def check_episodic_memory(self: "Agent", event_ids: List[str]) -> List[EpisodicEventForLLM]:
    """
    The tool to check the episodic memory. This function will return the episodic events with the given event_ids.

    Args:
        event_ids (str): The ids of the episodic events to be checked.
    
    Returns:
        List[EpisodicEventForLLM]: List of episodic events with the given event_ids.
    """
    episodic_events = [
        self.episodic_memory_manager.get_episodic_event_by_id(event_id) for event_id in event_ids
    ]

    formatted_results = [{'event_id': x.id, 'timestamp': x.occurred_at, 'event_type': x.event_type, 'actor': x.actor, 'summary': x.summary, 'details': x.details} for x in episodic_events]

    return formatted_results

def resource_memory_insert(self: "Agent", items: List[ResourceMemoryItemBase]):
    """
    The tool to insert new items into resource memory.

    Args:
        items (array): List of resource memory items to insert.
    
    Returns:
        Optional[str]: None is always returned as this function does not produce a response.
    """

    for item in items:
        self.resource_memory_manager.insert_resource(
            agent_state=self.agent_state,
            title=item['title'],
            summary=item['summary'],
            resource_type=item['resource_type'],
            content=item['content'],
            organization_id=self.user.organization_id
        )

def resource_memory_update(self: "Agent", old_ids: List[str], new_items: List[ResourceMemoryItemBase]):
    """
    The tool to update and delete items in the resource memory. To update the memory, set the old_ids to be the ids of the items that needs to be updated and new_items as the updated items. Note that the number of new items does not need to be the same as the number of old ids as it is not a one-to-one mapping. To delete the memory, set the old_ids to be the ids of the items that needs to be deleted and new_items as an empty list.

    Args:
        old_ids (array): List of ids of the items to be deleted (or updated).
        new_items (array): List of new resource memory items to insert. If this is an empty list, then it means that the items are being deleted.
    """
    for old_id in old_ids:
        self.resource_memory_manager.delete_resource_by_id(
            resource_id=old_id
        )
    
    for item in new_items:
        self.resource_memory_manager.insert_resource(
            agent_state=self.agent_state,
            title=item['title'],
            summary=item['summary'],
            resource_type=item['resource_type'],
            content=item['content'],
            organization_id=self.user.organization_id
        )

def procedural_memory_insert(self: "Agent", items: List[ProceduralMemoryItemBase]):
    """
    The tool to insert new procedures into procedural memory. 

    Args:
        items (array): List of procedural memory items to insert.
        
    Returns:
        Optional[str]: None is always returned as this function does not produce a response.
    """
    for item in items:
        self.procedural_memory_manager.insert_procedure(
            agent_state=self.agent_state,
            entry_type=item['entry_type'],
            description=item['description'],
            steps=item['steps'],
            organization_id=self.user.organization_id,
        )

def procedural_memory_update(self: "Agent", old_ids: List[str], new_items: List[ProceduralMemoryItemBase]):
    """
    The tool to update/delete items in the procedural memory. To update the memory, set the old_ids to be the ids of the items that needs to be updated and new_items as the updated items. Note that the number of new items does not need to be the same as the number of old ids as it is not a one-to-one mapping. To delete the memory, set the old_ids to be the ids of the items that needs to be deleted and new_items as an empty list.
    
    Args:
        old_ids (array): List of ids of the items to be deleted (or updated).
        new_items (array): List of new procedural memory items to insert. If this is an empty list, then it means that the items are being deleted.
    
    Returns:
        Optional[str]: None is always returned as this function does not produce a response.
    """
    for old_id in old_ids:
        self.procedural_memory_manager.delete_procedure_by_id(
            procedure_id=old_id
        )
    
    for item in new_items:
        self.procedural_memory_manager.insert_procedure(
            agent_state=self.agent_state,
            entry_type=item['entry_type'],
            description=item['description'],
            steps=item['steps'],
            organization_id=self.user.organization_id,
        )

def semantic_memory_insert(self: "Agent", items: List[SemanticMemoryItemBase]):
    """
    The tool to insert items into semantic memory. 

    Args:
        items (array): List of semantic memory items to insert.

    Returns:
        Optional[str]: None is always returned as this function does not produce a response.
    """
    for item in items:
        self.semantic_memory_manager.insert_semantic_item(
            agent_state=self.agent_state,
            concept=item['concept'],
            definition=item['definition'],
            details=item['details'],
            source=item['source'],
            organization_id=self.user.organization_id
        )

def semantic_memory_update(self: "Agent", old_ids: List[str], new_items: List[SemanticMemoryItemBase]):
    """
    The tool to update/delete items in the semantic memory. To update the memory, set the old_ids to be the ids of the items that needs to be updated and new_items as the updated items. Note that the number of new items does not need to be the same as the number of old ids as it is not a one-to-one mapping. To delete the memory, set the old_ids to be the ids of the items that needs to be deleted and new_items as an empty list.

    Args:
        old_ids (array): List of ids of the items to be deleted (or updated).
        new_items (array): List of new semantic memory items to insert. If this is an empty list, then it means that the items are being deleted.
    
    Returns:
        Optional[str]: None is always returned as this function does not produce a response.
    """

    for old_id in old_ids:
        self.semantic_memory_manager.delete_semantic_item_by_id(
            semantic_item_id=old_id
        )
    
    for item in new_items:
        self.semantic_memory_manager.insert_semantic_item(
            agent_state=self.agent_state,
            concept=item['concept'],
            definition=item['definition'],
            details=item['details'],
            source=item['source'],
            organization_id=self.user.organization_id
        )

def knowledge_vault_insert(self: "Agent", items: List[KnowledgeVaultItemBase]):
    """
    The tool to update knowledge vault.

    Args:
        items (array): List of knowledge vault items to insert.
        
    Returns:
        Optional[str]: None is always returned as this function does not produce a response.
    """
    for item in items:
        self.knowledge_vault_manager.insert_knowledge(
            agent_state=self.agent_state,
            entry_type=item['entry_type'],
            source=item['source'],
            sensitivity=item['sensitivity'],
            secret_value=item['secret_value'],
            description=item['description'],
            organization_id=self.user.organization_id
        )

def knowledge_vault_update(self: "Agent", old_ids: List[str], new_items: List[KnowledgeVaultItemBase]):
    """
    The tool to update/delete items in the knowledge vault. To update the knowledge_vault, set the old_ids to be the ids of the items that needs to be updated and new_items as the updated items. Note that the number of new items does not need to be the same as the number of old ids as it is not a one-to-one mapping. To delete the memory, set the old_ids to be the ids of the items that needs to be deleted and new_items as an empty list.
    
    Args:
        old_ids (array): List of ids of the items to be deleted (or updated).
        new_items (array): List of new knowledge vault items to insert. If this is an empty list, then it means that the items are being deleted.
    
    Returns:
        Optional[str]: None is always returned as this function does not produce a response
    """
    for old_id in old_ids:
        self.knowledge_vault_manager.delete_knowledge_by_id(
            knowledge_id=old_id
        )
    
    for item in new_items:
        self.knowledge_vault_manager.insert_knowledge(
            agent_state=self.agent_state,
            entry_type=item['entry_type'],
            source=item['source'],
            sensitivity=item['sensitivity'],
            secret_value=item['secret_value'],
            organization_id=self.user.organization_id
        )

def trigger_memory_update(self: "Agent", user_message: object, memory_types: List[str], instructions: List[str]) -> Optional[str]:
    """
    Choose which memory to update. This function will trigger another memory agent which is specifically in charge of handling the corresponding memory to update its memory.

    Args:
        memory_types (List[str]): The types of memory to update. It should be chosen from the following: "core", "episodic", "resource", "procedural", "knowledge_vault", "semantic". For instance, ['episodic', 'resource'].
        instructions (List[str]): The instructions for the corresponding memory manager to update the memory. It should be a list of strings. For instance, ['save multiple events: 1. user went to..., 2. user decided ...', 'extract the details from the screenshots and save the file `llm.py`'].
        
    Returns:
        Optional[str]: None is always returned as this function does not produce a response.
    """

    from mirix import create_client

    client = create_client()
    agents = client.list_agents()

    # TODO: need to connect different memory agents in database
    for idx, memory_type in enumerate(memory_types):

        if memory_type == "core":
            agent_type = "core_memory_agent"
        elif memory_type == "episodic":
            agent_type = "episodic_memory_agent"
        elif memory_type == "resource":
            agent_type = "resource_memory_agent"
        elif memory_type == "procedural":
            agent_type = "procedural_memory_agent"
        elif memory_type == "knowledge_vault":
            agent_type = "knowledge_vault_agent"
        elif memory_type == 'semantic':
            agent_type = "semantic_memory_agent"
        else:
            raise ValueError(f"Memory type '{memory_type}' is not supported. Please choose from 'episodic', 'resource', 'procedural', 'knowledge_vault', 'semantic'.")

        for agent in agents:
            if agent.agent_type == agent_type:
                user_message['message'] = user_message['message'] + '\n[Instruction from Meta Memory Manager]: ' + instructions[idx]
                client.send_message(agent_id=agent.id, role='user', **user_message)

def finish_memory_update(self: "Agent"):
    """
    Finish the memory update process. This function should be called after the Memory is updated.

    Returns:
        Optional[str]: None is always returned as this function does not produce a response.
    """
    return None