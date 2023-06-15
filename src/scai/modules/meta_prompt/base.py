"""meta-prompt."""
from typing import (
    Any,
    Dict,
    List, 
    Optional
)

from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    AIMessagePromptTemplate,
    HumanMessagePromptTemplate,
)

from langchain.schema import (
    AIMessage,
    BaseMessage,
    ChatMessage,
    HumanMessage,
    SystemMessage,
)

from scai.modules.meta_prompt.models import MetaPrompt
from scai.modules.meta_prompt.prompts import META_PROMPTS
from scai.modules.memory.buffer import CustomConversationBufferWindowMemory

from scai.modules.task.models import TaskPrompt

from langchain import LLMChain


class MetaPromptModel():
    """Code for running meta-prompt.
    Example:
        .. code-block:: python
    """

    def __init__(self, llm) -> None:
        self.llm = llm
    
    def _convert_message_to_dict(self, message: BaseMessage) -> dict:
        if isinstance(message, ChatMessage):
            message_dict = {"role": message.role, "content": message.content}
        elif isinstance(message, HumanMessage):
            message_dict = {"role": "user", "content": message.content}
        elif isinstance(message, AIMessage):
            message_dict = {"role": "assistant", "content": message.content}
        elif isinstance(message, SystemMessage):
            message_dict = {"role": "system", "content": message.content}
        else:
            raise ValueError(f"Got unknown type {message}")
        if "name" in message.additional_kwargs:
            message_dict["name"] = message.additional_kwargs["name"]
        return message_dict

    def sort_message(self, item):
        """
        Sort by messages by conversation id.
        """
        message_id = item[1]
        parts = message_id.split('_')
        return int(parts[1])

    def run(
        self,
        buffer: CustomConversationBufferWindowMemory,
        meta_prompt: MetaPrompt,
        task_prompt: TaskPrompt,
    ) -> str:
        """Run meta-prompt."""
        meta_prompt_template = SystemMessagePromptTemplate.from_template(meta_prompt.content)
        # convert chat into dict
        chat_message_dict = [self._convert_message_to_dict(m) for m in buffer.load_memory_variables(var_type="chat")['history']]
        # sort messages by conversation id
        pairs = zip(chat_message_dict, buffer.chat_memory.message_ids)
        sorted_pairs = sorted(pairs, key=self.sort_message)
        sorted_chat_message_dict, sorted_message_ids = zip(*sorted_pairs)
        # create chat history
        chat_history = """"""
        last_conversation_id = None
        for m, m_id in zip(sorted_chat_message_dict, sorted_message_ids):
            current_conversation_id = m_id.split('_')[1]
            if current_conversation_id != last_conversation_id:
                chat_history += f"\nConversation {current_conversation_id}:\n"
                last_conversation_id = current_conversation_id
            if m['role'] == "user":
                chat_history += f"User {current_conversation_id}: {m['content']}\n"
            elif m['role'] == "assistant":
                chat_history += f"Assistant: {m['content']}\n"
        # convert system message into dict
        system_message_dict = [self._convert_message_to_dict(m) for m in buffer.load_memory_variables(var_type="system")['history']]
        # create system message
        system_history = "\n".join([f"{m['role']}: {m['content']}" for m in system_message_dict])
        # create prompt 
        meta_chat_prompt = ChatPromptTemplate.from_messages([meta_prompt_template])
        response = meta_chat_prompt.format(task=task_prompt.content,
                                           chat_history=chat_history,  
                                           system_history=system_history,
                                           max_tokens=meta_prompt.max_tokens)
        return response
        # # run meta-prompt
        # chain = LLMChain(llm=self.llm, prompt=meta_chat_prompt)
        # response = chain.run(chat_history=chat_history, assistant_system_message=system_history, max_tokens=max_tokens, stop=["System:"])
        # return response