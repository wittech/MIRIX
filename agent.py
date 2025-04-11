import io
import os
import re
import time
import json
import yaml
import uuid
import copy
import pytz
import openai
import base64
import tiktoken
import traceback
import threading
from google import genai
from dotenv import load_dotenv
from datetime import datetime, timezone
from constants import TEMPORARY_MESSAGE_LIMIT, MAXIMUM_NUM_IMAGES_IN_CLOUD



def count_tokens(messages, model="gpt-4", chat=True):
    encoding = tiktoken.encoding_for_model(model)

    if not chat:
        return len(encoding.encode(messages))

    tokens_per_message = 4  # every message has some extra tokens (e.g. for role, delimiters, etc.)
    tokens_per_name = -1    # if a name is provided, adjust the count
    total_tokens = 0
    for message in messages:
        total_tokens += tokens_per_message
        for key, value in message.items():
            if key == 'content':
                if isinstance(value, str):
                    total_tokens += len(encoding.encode(value))
                else:
                    for subvalue in value:
                        if subvalue['type'] == 'text':
                            total_tokens += len(encoding.encode(subvalue['text']))
                        else:
                            total_tokens += 512
            else:
                total_tokens += len(encoding.encode(value))
            if key == "name":
                total_tokens += tokens_per_name
    total_tokens += 2  # priming tokens for the reply
    return total_tokens

# Convert images to base64
def encode_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")

def encode_image_from_pil(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")  # Change format if needed (JPEG, etc.)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

class AgentWrapper():
    
    def __init__(self, agent_config_file):

        with open(agent_config_file, "r") as f:
            agent_config = yaml.safe_load(f)

        self.agent_name = agent_config['agent_name']
        self.model_name = agent_config['model_name']

        if self.agent_name == 'mirix':

            from mirix import create_client
            from mirix import LLMConfig, EmbeddingConfig
            from mirix.schemas.agent import AgentType
            from mirix.prompts import gpt_system
            from mirix.schemas.memory import ChatMemory

            self.client = create_client()
            self.client.set_default_llm_config(LLMConfig.default_config("gpt-4o-mini")) 
            self.client.set_default_embedding_config(EmbeddingConfig.default_config("text-embedding-3-small"))

            if len(self.client.list_agents()) > 0:

                all_agent_states = self.client.list_agents()

                for agent_state in all_agent_states:
                    if agent_state.name == 'chat_agent':
                        self.agent_state = agent_state
                    elif agent_state.name == 'episodic_memory_agent':
                        self.episodic_memory_agent_state = agent_state
                    elif agent_state.name == 'procedural_memory_agent':
                        self.procedural_memory_agent_state = agent_state
                    elif agent_state.name == 'knowledge_vault_agent':
                        self.knowledge_vault_agent_state = agent_state
                    elif agent_state.name == 'meta_memory_agent':
                        self.meta_memory_agent_state = agent_state
                    elif agent_state.name == 'semantic_memory_agent':
                        self.semantic_memory_agent_state = agent_state
                    elif agent_state.name == 'core_memory_agent': 
                        self.core_memory_agent_state = agent_state

                # TODO: need to update the agents if there are things changed
                # For instance, the functions in the file `function_sets.memory_tools.py` might get changed.

                # 1. Check if the functions are updated

                ## 1.1 existing function descriptions are modified:
                self.client.server.tool_manager.upsert_base_tools(self.client.user)

                ## 1.2 existing function code is modified -> No need to do anything, it will automatically use the newest code in `memory_tools.py`

                ## TODO: 1.3 deal with the cases when new functions are added

                # 2. Check if the system prompt is changed:
                from mirix.services.helpers.agent_manager_helper import derive_system_message
                for agent_state in all_agent_states:
                        system = gpt_system.get_system_text(agent_state.name)
                        if not agent_state.system == system:
                            self.client.server.agent_manager.update_system_prompt(agent_id=agent_state.id, system_prompt=system, actor=self.client.user)

            else:

                core_memory = ChatMemory(
                    human="",
                    persona="You are a helpful personal assitant who can help the user remember things."
                )

                # create an agent that is only used for updating the memory
                self.episodic_memory_agent_state = self.client.create_agent(
                    name='episodic_memory_agent',
                    agent_type=AgentType.episodic_memory_agent,
                    memory=core_memory,
                    system=gpt_system.get_system_text("episodic_memory_agent"),
                    include_base_tools=False
                )

                self.procedural_memory_agent_state = self.client.create_agent(
                    name='procedural_memory_agent',
                    agent_type=AgentType.procedural_memory_agent,
                    memory=core_memory,
                    system=gpt_system.get_system_text("procedural_memory_agent"),
                    include_base_tools=False
                )

                self.knowledge_vault_agent_state = self.client.create_agent(
                    name='knowledge_vault_agent',
                    agent_type=AgentType.knowledge_vault_agent,
                    memory=core_memory,
                    system=gpt_system.get_system_text("knowledge_vault_agent"),
                    include_base_tools=False
                )

                self.meta_memory_agent_state = self.client.create_agent(
                    name='meta_memory_agent',
                    agent_type=AgentType.meta_memory_agent,
                    memory=core_memory,
                    system=gpt_system.get_system_text("meta_memory_agent"),
                    include_base_tools=False
                )

                self.semantic_memory_agent_state = self.client.create_agent(
                    name='semantic_memory_agent',
                    agent_type=AgentType.semantic_memory_agent,
                    memory=core_memory,
                    system=gpt_system.get_system_text("semantic_memory_agent"),
                    include_base_tools=False
                )

                self.core_memory_agent_state = self.client.create_agent(
                    name='core_memory_agent',
                    agent_type=AgentType.core_memory_agent,
                    memory=core_memory,
                    system=gpt_system.get_system_text("core_memory_agent"),
                    include_base_tools=False
                )

                self.resource_memory_agent_state = self.client.create_agent(
                    name='resource_memory_agent',
                    agent_type=AgentType.resource_memory_agent,
                    memory=core_memory,
                    system=gpt_system.get_system_text("resource_memory_agent"),
                    include_base_tools=False
                )

                self.agent_state = self.client.create_agent(
                    name='chat_agent',
                    memory=core_memory,
                    system=gpt_system.get_system_text("chat_agent")
                )

            self.set_model(self.model_name)
            self.set_timezone(self.client.server.user_manager.get_user_by_id(self.client.user_id).timezone)
            self.set_persona("chill_buddy")
            self.temporary_messages = [[]]
            self.temporary_user_messages = [[]]
            self.temporary_message_limit = TEMPORARY_MESSAGE_LIMIT
            self.message_queue = {}

            if self.model_name in ['gemini-2.0-flash', 'gemini-1.5-pro', 'gemini-2.0-flash-lite']:
                load_dotenv()
                self.google_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
                print("Retrieving existing files from Google Clouds...")
                
                existing_files = [x for x in self.google_client.files.list()]
                existing_image_names = set([file.name for file in existing_files])
                print("# of Existing files in Google Clouds:", len(existing_image_names))

                # update the database, delete the files that are in the database but got deleted somehow (potentially due to the calls unrelated to Mirix) in the cloud
                for file_name in self.client.server.cloud_file_mapping_manager.list_all_cloud_file_ids():
                    if file_name not in existing_image_names:
                        self.client.server.cloud_file_mapping_manager.delete_mapping(cloud_file_id=file_name)

                # since there might be images that belong to other projects, we need to delete those in `existing_files`
                cloud_file_names_in_database = set(self.client.server.cloud_file_mapping_manager.list_all_cloud_file_ids())
                remaining_indices = []
                for idx, file_name in enumerate(existing_image_names):
                    if file_name in cloud_file_names_in_database:
                        remaining_indices.append(idx)
                
                existing_files = [existing_files[i] for i in remaining_indices]
                self.existing_files = existing_files
                self.uri_to_create_time = {file.uri: {'create_time': file.create_time, 'filename': file.name} for file in existing_files}

                print("# of Existing files in Google Clouds that belong to Mirix:", len(self.uri_to_create_time))

        elif self.agent_name in ['gpt-4o', 'gpt-4o-mini', 'qwen2-vl-7b-instruct']:

            with open("./system/system.txt", "r") as f:
                self.system = f.read()
            
            self.messages = [
                {'role': 'system', 'content': self.system},
                {'role': 'user', 'content': []}
            ]

            if self.agent_name == 'qwen2-vl-7b-instruct':
                api_key = "lm-studio"
                self.client = openai.OpenAI(base_url="http://localhost:1234/v1", api_key=api_key)
            else:
                load_dotenv()
                api_key = os.getenv("OPENAI_API_KEY")
                self.client = openai.OpenAI(api_key=api_key)
            
        elif self.agent_name == 'gemini':

            with open("./system/system.txt", "r") as f:
                self.system = f.read()

            self.contents = [
                {'role': 'user', 'parts': [{'text': self.system}]},
                {'role': 'user', 'parts': []}
            ]

            self.buffer = []

            load_dotenv()
            api_key = os.getenv("GEMINI_API_KEY")
            self.client = genai.Client(api_key=api_key)

        if self.agent_name == 'debug':
            self.context = []
    
    def upload_file(self, filename):

        if self.client.server.cloud_file_mapping_manager.check_if_existing(local_file_id=filename):
            cloud_file_name = self.client.server.cloud_file_mapping_manager.get_cloud_file(local_file_id=filename)
            return [x for x in self.existing_files if x.name == cloud_file_name][0]
        else:
            # upload to the cloud
            file_ref = self.google_client.files.upload(file=filename)
            self.uri_to_create_time[file_ref.uri] = {'create_time': file_ref.create_time, 'filename': file_ref.name}
            self.client.server.cloud_file_mapping_manager.add_mapping(local_file_id=filename, cloud_file_id=file_ref.name, force_add=True)
            return file_ref
 
    def delete_files(self, file_names, google_client):
        for file_name in file_names:
            try:
                google_client.files.delete(name=file_name)
                self.client.server.cloud_file_mapping_manager.delete_mapping(cloud_file_id=file_name)
            except:
                continue

    def send_message_in_queue(self, kwargs, memorizing=None):

        # only need to support mirix for now
        assert self.agent_name == 'mirix'
            
        message_uuid = uuid.uuid4()

        if self.agent_name == 'mirix':
            self.message_queue[message_uuid] = {
                'kwargs': kwargs,
                'started': False,
                'finished': False,
                'type': 'meta_memory' if memorizing else 'chat'
            }

        while not self.check_if_earlier_requests_are_finished(message_uuid):
            
            time.sleep(0.1)
        
        else:

            self.message_queue[message_uuid]['started'] = True

            agent_id = self.agent_state.id if self.message_queue[message_uuid]['type'] == 'chat' else self.meta_memory_agent_state.id
            
            response = self.client.send_message(
                agent_id=agent_id,
                role='user',
                **self.message_queue[message_uuid]['kwargs']
            )

            self.message_queue[message_uuid]['finished'] = True

            # delete this message from the queue
            del self.message_queue[message_uuid]
            return response

    def check_if_earlier_requests_are_finished(self, message_uuid):

        message_queue = copy.deepcopy(self.message_queue)
        if not message_uuid in message_queue:
            raise ValueError("Message not found in the queue.")
        idx = list(message_queue.keys()).index(message_uuid)
        current_message = message_queue[message_uuid]
        for message in list(message_queue.values())[:idx]:
            if message['type'] == current_message['type']:
                if not message['finished']:
                    return False
        return True

    def set_timezone(self, timezone_str):
        """
        timezone_str: Something like "Asia/Shanghai (UTC+8:00)".
        """
        print("Setting timezone to:", timezone_str)
        print(timezone_str.split(" ")[-1])

        self.client.server.user_manager.update_user_timezone(timezone_str, self.client.user.id)
        self.timezone_str = timezone_str
        self.timezone = pytz.timezone(timezone_str.split(" (")[0])

    def set_persona(self, persona_name):
        self.client.update_persona(persona_name)

    def set_model(self, new_model):

        if self.agent_name == 'gemini':
            self.model_name = new_model

        elif self.agent_name == 'mirix':
            
            from mirix import LLMConfig
            from mirix.agent import Agent
            
            if new_model == 'gpt-4o-mini' or new_model == 'gpt-4o':
                llm_config = LLMConfig.default_config(new_model)

            elif new_model == 'gemini-2.0-flash' or new_model == 'gemini-1.5-pro' or new_model == 'gemini-2.0-flash-lite':
                llm_config = LLMConfig(
                    model_endpoint_type="google_ai",
                    model_endpoint="https://generativelanguage.googleapis.com",
                    model=new_model,
                    context_window=1000000
                )

            elif new_model == 'claude-3-5-sonnet-20241022':
                llm_config = LLMConfig(
                    model_endpoint_type="anthropic",
                    model_endpoint="https://api.anthropic.com/v1",
                    model="claude-3-5-sonnet-20241022",
                    context_window=200000
                )
            else:
                raise ValueError(f"Model '{new_model}' not supported.")
            
            for agent_state in self.client.list_agents():

                agent = Agent(interface=self.client.interface,
                              agent_state=agent_state,
                              user=self.client.server.user_manager.get_user_by_id(self.client.user_id))
                
                agent.agent_manager.update_llm_config(agent_id=agent.agent_state.id, llm_config=llm_config, actor=agent.user)

    def clear_old_screenshots(self):
        
        if len(self.message_queue) > 0:
            return # do not clear if there are messages in the queue

        assert self.agent_name == 'mirix'
        
        if len(self.uri_to_create_time) > MAXIMUM_NUM_IMAGES_IN_CLOUD:
            # find the oldest files according to self.uri_to_create_time
            files_to_delete = sorted(self.uri_to_create_time.items(), key=lambda x: x[1]['create_time'])[:len(self.uri_to_create_time) - MAXIMUM_NUM_IMAGES_IN_CLOUD]
            file_names_to_delete = [x[1]['filename'] for x in files_to_delete]

            for x in files_to_delete:
                # TODO: there is a bug here. 
                del self.uri_to_create_time[x[0]]

            print("Deleting files:", file_names_to_delete)
            threading.Thread(target=self.delete_files, args=([x for x in file_names_to_delete], self.google_client)).start()

    def absorb_screenshots_into_memory(self):

        message = 'The followings are the screenshots taken from the computer of the user:\n'
        for idx, (timestamp, file_ref) in enumerate(self.temporary_messages[-1]):
            message += f"Timestamp: {timestamp} Image Index {idx}:\n<image>{file_ref.uri}</image>\n"
        message = message.strip()
        self.temporary_messages.append([])

        user_message_added = False
        if self.agent_name == 'mirix' and len(self.temporary_user_messages[-1]) > 0:
            message += '\nThe followings are the conversations between the user and the Chat Agent while taking the screenshots:\n'
            # also need to add the user agent conversation
            for idx, user_message in enumerate(self.temporary_user_messages[-1]):
                message += f"role: {user_message['role']}; content: {user_message['content']}\n"
            message = message.strip()
            self.temporary_user_messages.append([])
            user_message_added = True

        original_file_refs = [file_ref for _, file_ref in self.temporary_messages[-2]]
        image_uris = {
            'image_uris': copy.deepcopy([x.uri for x in original_file_refs]),
            'existing_image_uris': set(list(self.uri_to_create_time.keys()))
        }

        if self.agent_name == 'mirix':
        
            if user_message_added:
                message += "\n[System Message] Interpret the provided screenshots and the conversations between the user and the chat agent, according to what the user is doing, trigger the appropriate memory update."
            else:
                message += "\n[System Message] Interpret the provided screenshots, according to what the user is doing on the computer, trigger the appropriate memory update with the function `trigger_memory_update`."

            response = self.send_message_in_queue({
                'message': message,
                'image_uris': image_uris,
            }, memorizing=True)

        self.temporary_messages.pop(0)

        if self.agent_name == 'mirix' and user_message_added:
            self.temporary_user_messages.pop(0)

    def send_message(self, *args, **kwargs):
        try:
            return self._send_message(*args, **kwargs)
        except Exception as e:
            traceback.print_exc()  # This prints the full traceback to stderr.
            return "ERROR"

    def _send_message(self, message=None, images=None, image_uris=None, memorizing=False, delete_images=True, specific_timestamps=None):
        
        if self.agent_name == 'debug':
            self.context.append(message)
            return len(self.context)

        if self.agent_name == 'gemini':

            if memorizing:

                if images is not None:
                    
                    assert len(images) == 1
                    filename = f'./tmp/image_{uuid.uuid4()}.png'
                    images[0].save(filename)
                    file_ref = self.client.files.upload(file=filename)
                
                elif image_uris is not None:

                    assert len(image_uris) == 1
                    filename = image_uris[0]
                    file_ref = self.client.files.upload(file=image_uris[0])

                if delete_images:
                    # remove file
                    os.remove(filename)

                if specific_timestamps is not None:
                    timestamp = specific_timestamps[0]
                else:
                    timestamp = str(datetime.now(self.timezone))
                self.buffer.append([{'text': 'Timestamp: ' + timestamp}, {'file_data': {'mime_type': 'image/png', 'file_uri': file_ref.uri}}])

            else:
                
                # need to put buffer into self.contents
                while len(self.buffer) > 0:
                    content = self.buffer.pop(0)
                    self.contents[-1]['parts'].extend(content)

                self.contents[-1]['parts'].append({'text': message})
                assert image_uris is None

                print("Contents:", self.contents)
                print()

                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=self.contents
                )
                self.contents.append({'role': 'model', 'parts': [{'text': response.text}]})
                self.contents.append({'role': 'user', 'parts': []})
                print(response)
                return response.text

        elif self.agent_name in ['gpt-4o', 'gpt-4o-mini', 'qwen2-vl-7b-instruct']:
            
            if memorizing:

                assert not (images is not None and image_uris is not None)
                if images is not None:
                    assert len(images) == 1
                    image_base64 = encode_image_from_pil(images[0])
                else:
                    assert len(image_uris) == 1
                    image_base64 = encode_image(image_uris[0])

                # it means now we are saving the screenshots
                self.messages[-1]['content'].append({'type': 'text', 'text': 'Timestamp: ' + str(datetime.now(self.timezone))})

                self.messages[-1]['content'].append(
                    {'type': 'image_url', 'image_url': {'url': f"data:image/png;base64,{image_base64}"}}
                )

                while count_tokens(self.messages) > 100000:
                    self.messages = self.messages[:1] + self.messages[2:]
                
                print("Total number of tokens:", count_tokens(self.messages))

            else:

                self.messages[-1]['content'].append({
                    'type': 'text', 'text': message
                })
                
                if image_uris is not None:
                    for image_uri in image_uris:
                        image_base64 = encode_image(image_uri)
                        self.messages[-1]['content'].append({
                            'type': 'image_url', 'image_url': {'url': f"data:image/png;base64,{image_base64}"}
                        })

                self.messages.append({
                    'role': 'assistant',
                    'content': response.choices[0].message.content
                })

                self.messages.append({
                    'role': 'user',
                    'content': []
                })

                return response.choices[0].message.content

        elif self.agent_name == 'mirix':

            if memorizing:

                if images is not None:
                    assert len(images) == 1
                    filename = f'./tmp/image_{uuid.uuid4()}.png'
                    images[0].save(filename)
                else:
                    assert image_uris is not None
                    assert len(image_uris) == 1
                    filename = image_uris[0]
                
                if self.model_name in ['gemini-2.0-flash', 'gemini-1.5-pro', 'gemini-2.0-flash-lite']:
                    
                    file_ref = self.upload_file(filename)

                    if delete_images:
                        # remove file
                        while True:
                            try:
                                os.remove(filename)
                                assert not os.path.exists(filename)
                                break
                            except:
                                time.sleep(0.1)
                                continue

                    # accumulate images until it hits self.temporary_message_limit
                    if specific_timestamps is not None:
                        timestamp = specific_timestamps[0]
                    else:
                        timestamp = datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S')

                    self.temporary_messages[-1].append(
                        (timestamp, file_ref)
                    )

                else:
                    if specific_timestamps is not None:
                        timestamp = specific_timestamps[0]
                    else:
                        timestamp = datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S')
                    
                    # accumulate images until it hits self.temporary_message_limit
                    self.temporary_messages[-1].append(
                        (timestamp, filename)
                    )

                if len(self.temporary_messages[-1]) == self.temporary_message_limit:
                    self.absorb_screenshots_into_memory()
                    self.clear_old_screenshots()

            else:

                # get the most recent images
                most_recent_images = self.temporary_messages[-1]
                if len(most_recent_images) < self.temporary_message_limit and len(self.temporary_messages) > 1:
                    most_recent_images = self.temporary_messages[-2] + most_recent_images
                    most_recent_images = most_recent_images[-self.temporary_message_limit:]

                if len(most_recent_images) > 0:

                    ## put the images into the message
                    # cur_message = f"[System Message] These are the recent {len(most_recent_images)} screenshots from the user's screen:\n"
                    # for idx, (timestamp, file_ref) in enumerate(most_recent_images):
                    #     cur_message += f"{timestamp} Image Index {idx}:\n<image>{file_ref.uri}</image>\n"
                    # cur_message = cur_message.strip()
                    cur_message = []
                    for idx, (timestamp, file_ref) in enumerate(most_recent_images):
                        cur_message.append(
                            {
                                'timestamp': timestamp,
                                'image': f"<image>{file_ref.uri}</image>"
                            }
                        )
                        
                else:
                    cur_message = None

                # get the response according to the message
                response = self.send_message_in_queue(
                    {
                        'message': message,
                        'image_uris': {'existing_image_uris': set(list(self.uri_to_create_time.keys()))},
                        'force_response': True,
                        'extra_message': cur_message # the screenshots should not be saved in the database
                    }
                )

                try:
                    response = json.loads(response.messages[-2].tool_call.arguments)['message']
                except:
                    print("Response:", response)
                    response = response.messages[-1].assistant_message
                
                self.temporary_user_messages[-1].extend(
                    [{'role': 'user', 'content': message},
                        {'role': 'assistant', 'content': response}]
                )
                
                return response