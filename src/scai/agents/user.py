from typing import (
    Any,
    Dict,
    List, 
)

from langchain.prompts.chat import (
    ChatPromptTemplate, 
    SystemMessagePromptTemplate,
    AIMessagePromptTemplate,
    HumanMessagePromptTemplate,
)

from langchain.chains.llm import LLMChain
from langchain.chat_models.base import BaseChatModel

from scai.prompts.user.models import UserPrompt
from scai.prompts.task.models import TaskPrompt
from scai.prompts.metrics.models import MetricPrompt

from scai.memory.buffer import ConversationBuffer

from scai.agents.base import BaseAgent


class UserModel(BaseAgent):
    """LLM Chain for running the User."""
    def __init__(
        self, 
        llm: BaseChatModel, 
        model_id: str, 
    ) -> None:
        super().__init__(llm, model_id)
    
    def _get_chat_history_prompt_templates(
        self,
        buffer: ConversationBuffer,
        task_prompt: TaskPrompt,
        metric_prompt: MetricPrompt,
    ) -> List[ChatPromptTemplate]:
        """
        Returns the chat history prompt templates for the user
        """
        chat_memory = self._get_chat_history(buffer, memory_type="chat") # check if chat memory exists
        assistant_response_0 = chat_memory[f"{self.model_id}_assistant"][0]['response'] # get the initial assistant response
        # if we are at the beginning of a conversation
        if chat_memory.get(f"{self.model_id}_user") is None or len(chat_memory[f"{self.model_id}_user"]) == 0: 
            chat_history_prompt_templates = [
                HumanMessagePromptTemplate.from_template(
                    f"{task_prompt.preamble} {task_prompt.content} {task_prompt.user_connective} {assistant_response_0} \n\n{metric_prompt.subjective_content}"
                )
            ]
            return chat_history_prompt_templates
        # if we are not at the beginning of a conversation, need to get the conversation history
        chat_history_prompt_templates = [
            template
            for assistant, user in zip(chat_memory[f"{self.model_id}_assistant"], chat_memory[f"{self.model_id}_user"])
            for template in (HumanMessagePromptTemplate.from_template(assistant['response']), # flipping human and assistant templates
                             AIMessagePromptTemplate.from_template(user['response']))
        ]
        # add initial prompt including task
        chat_history_prompt_templates.insert(0, HumanMessagePromptTemplate.from_template(f"{task_prompt.preamble} {task_prompt.content} {task_prompt.user_connective} {assistant_response_0}"))
        # pop redundant assistant response at the beginning (now part of the message above)
        chat_history_prompt_templates.pop(1)
        # add the most recent assistant response and request for new answer (n_user answers is always = n_assistant_answers - 1 at this stage, so we have to add one more)
        chat_history_prompt_templates.append(HumanMessagePromptTemplate.from_template(chat_memory[f"{self.model_id}_assistant"][-1]['response'] + "\n\n" + f"{metric_prompt.subjective_content}"))
        return chat_history_prompt_templates
    
    def _get_chat_history_prompt_templates_collective(
        self,
        buffer: ConversationBuffer,
        task_prompt: TaskPrompt,
        metric_prompt: MetricPrompt,
    ) -> Dict[str, ChatPromptTemplate]:
        """
        Returns the chat history prompt templates for the user rating other conversations
        """
        chat_memory = self._get_chat_history(buffer, memory_type="chat") # check if chat memory exists
        # data structures for storing the assistant responses and user responses from other conversations
        chat_history_prompt_templates_collective = {}
        assistant_responses = {}
        # if we are at the beginning of a conversation
        # if chat_memory.get(f"{self.model_id}_user") is None or len(chat_memory[f"{self.model_id}_user"]) == 0: 
        # TODO: what does it mean if this conversation has also multiple turns? currently only showing the most recent turn, but can also show others.
        for model_id in buffer.load_memory_variables(memory_type='chat').keys():
            if model_id != f"{self.model_id}_assistant" and 'assistant' in model_id:
                assistant_responses[model_id] = chat_memory[model_id][-1]['response'] # get most recent assistant response
                chat_history_prompt_templates = [
                    HumanMessagePromptTemplate.from_template(
                        f"\n{task_prompt.preamble} {task_prompt.content} {task_prompt.user_connective} {assistant_responses[model_id]}\n{metric_prompt.collective_content}"
                    )
                ]
                chat_history_prompt_templates_collective[model_id] = chat_history_prompt_templates
        return chat_history_prompt_templates_collective
        # if we are not at the beginning of a conversation, need to get the conversation history, get unique model ids
        # model_ids = set([model_id.split('_')[0] for model_id in chat_memory.keys()])
        # # remove own model id
        # model_ids.remove(self.model_id)
        # for model_id in model_ids:
        #     assistant_response_0 = chat_memory[f"{model_id}_assistant"][0]['response'] # get the initial assistant response
        #     chat_history_prompt_templates = [
        #         template
        #         for assistant, user in zip(chat_memory[f"{model_id}_assistant"], chat_memory[f"{model_id}_user"])
        #         for template in (HumanMessagePromptTemplate.from_template(assistant['response']), 
        #                          AIMessagePromptTemplate.from_template(user['response']))
        #     ]
        #     # insert the initial request at the beginning of the chat history
        #     chat_history_prompt_templates.insert(0, HumanMessagePromptTemplate.from_template(f"{task_prompt.preamble} {task_prompt.content} {task_prompt.user_connective} '{assistant_response_0}'"))
        #     # pop redundant second item
        #     chat_history_prompt_templates.pop(1)
        #     # pop the final feedback which is redundant
        #     chat_history_prompt_templates.pop(-1)
        #     # add the missing assistant and final request 
        #     chat_history_prompt_templates[-1] = HumanMessagePromptTemplate.from_template(f"{chat_history_prompt_templates[-1].prompt.template}\n{metric_prompt.collective_content}")
        #     # add to dictionary
        #     chat_history_prompt_templates_collective[f"{model_id}_assistant"] = chat_history_prompt_templates
        # return chat_history_prompt_templates_collective

    def _get_prompt(
        self, 
        buffer: ConversationBuffer,
        user_prompt: UserPrompt,
        task_prompt: TaskPrompt,
        metric_prompt: MetricPrompt,
    ) -> ChatPromptTemplate:
        """
        Get prompt for user.
        """
        system_prompt_template = SystemMessagePromptTemplate.from_template(user_prompt.content)
        chat_history_prompt_templates = self._get_chat_history_prompt_templates(buffer, task_prompt, metric_prompt)
        return ChatPromptTemplate.from_messages([system_prompt_template, *chat_history_prompt_templates])
    
    def _get_prompt_collective(
        self, 
        buffer: ConversationBuffer,
        user_prompt: UserPrompt,
        task_prompt: TaskPrompt,
        metric_prompt: MetricPrompt,
    ) -> Dict[str, ChatPromptTemplate]:
        """
        Get prompt for other users.
        """
        system_prompt_template = SystemMessagePromptTemplate.from_template(user_prompt.content)
        chat_history_prompt_templates_collective = self._get_chat_history_prompt_templates_collective(buffer, task_prompt, metric_prompt)
        chat_prompt_templates_collective = {model_id:
                ChatPromptTemplate.from_messages([system_prompt_template, *chat_history_prompt_template_collective])
                for model_id, chat_history_prompt_template_collective in chat_history_prompt_templates_collective.items()
            }
        return chat_prompt_templates_collective
    
    def _get_response(
        self,
        chat_prompt_template: ChatPromptTemplate,
        system_message: str,
        task_prompt: TaskPrompt,
        metric_prompt: MetricPrompt,
        max_tokens: int,
    ) -> str:
        """
        Returns the response from the assistant.
        """
        chain = LLMChain(llm=self.llm, prompt=chat_prompt_template)
        response = chain.run(system_message=system_message,
                             task=task_prompt.content,
                             max_tokens=max_tokens,
                             stop=['System:'])  
        response = self._format_response(response, [metric_prompt.subjective_metric.capitalize(), 'Response'])
        return response
    
    def _get_response_collective(
        self,
        chat_prompt_templates: Dict[str, ChatPromptTemplate],
        system_message: str,
        task_prompt: TaskPrompt,
        metric_prompt: MetricPrompt,
        max_tokens: int,
    ) -> Dict[str, Any]:
        """
        Gets response for other users.
        """
        responses_collective = {}
        for model_id, chat_prompt_template in chat_prompt_templates.items():
            if 'assistant' in model_id:
                chain = LLMChain(llm=self.llm, prompt=chat_prompt_template) 
                response = chain.run(system_message=system_message,
                                    task=task_prompt.content,
                                    max_tokens=max_tokens,
                                    stop=['System:'])
                response = self._format_response(response, [metric_prompt.collective_metric.capitalize()])
                responses_collective[model_id] = response
        return responses_collective
    
    def run(
        self,
        buffer: ConversationBuffer,
        user_prompt: UserPrompt,
        task_prompt: TaskPrompt,
        metric_prompt: MetricPrompt,
        turn: int,
        test_run: bool = True,
        verbose: bool = False,
        max_tokens: int = 100,
    ) -> Dict[str, Any]:
        """Runs the user.

        Args:
            buffer (ConversationBuffer): Conversation buffer containing the chat history
            user_prompt (UserPrompt): User prompt containing the user's response
            task_prompt (TaskPrompt): Task prompt containing the task
            metric_prompt (MetricPrompt): Metric prompt containing the metrics
            turn (int): Turn number
            test_run (bool, optional): Whether this is a test run. Defaults to True.
            verbose (bool, optional): Whether to print the chat history. Defaults to False.
            max_tokens (int, optional): Maximum number of tokens to generate. Defaults to 100.

        Returns:
            A dictionary containing the user's response, input prompt, and all other metrics we want to track.
        """
        system_message = user_prompt.persona
        chat_prompt_template = self._get_prompt(buffer, user_prompt, task_prompt, metric_prompt)
        chat_prompt_templates_collective = self._get_prompt_collective(buffer, user_prompt, task_prompt, metric_prompt)
        prompt_string = chat_prompt_template.format(system_message=system_message, 
                                                    task=task_prompt.task,
                                                    metric_prompt=metric_prompt.subjective_content,
                                                    max_tokens=max_tokens)
        prompt_strings_collective = {model_id: chat_prompt_template_collective.format(system_message=system_message,
                                                                  task=task_prompt.task,
                                                                  metric_prompt=metric_prompt.collective_content,
                                                                  max_tokens=max_tokens)
                                for model_id, chat_prompt_template_collective in chat_prompt_templates_collective.items()
                            }
        if test_run:
            print('===================================')
            print(f'USER {str(self.model_id)} turn {turn}')
            print('prompt')
            print(prompt_string)
            print('response')
            print(f"user_response_{self.model_id}, turn {turn}.")
            print(metric_prompt.subjective_metric, int(self.model_id) + turn + 1)
            print(prompt_strings_collective)
            print({model_id: int(self.model_id) + turn + 6 for model_id in chat_prompt_templates_collective.keys()})
            
            return {
                'prompt': prompt_string,
                'response': f"user_response_{self.model_id}, turn {turn}.",
                metric_prompt.subjective_metric: int(self.model_id) + turn + 1,
                'prompts_collective': prompt_strings_collective,     
                'responses_collective': {model_id: int(self.model_id) + turn + 6 for model_id in chat_prompt_templates_collective.keys()},
                'turn': turn
            }

        response = self._get_response(chat_prompt_template, system_message, task_prompt, metric_prompt, max_tokens)
        responses_collective = self._get_response_collective(chat_prompt_templates_collective, system_message, task_prompt, metric_prompt, max_tokens)

        if verbose:
            print('===================================')
            print(f'USER {str(self.model_id)} turn {turn}')
            print('prompt')
            print(prompt_string)
            print('response')
            print(response['Response'])
            print(metric_prompt.subjective_metric, response[metric_prompt.subjective_metric.capitalize()])
            print(prompt_strings_collective)
            print(responses_collective)

        return {
            'prompt': prompt_string, 
            'response': response['Response'],
            metric_prompt.subjective_metric: response[metric_prompt.subjective_metric.capitalize()],
            'prompts_collective': prompt_strings_collective,
            'responses_collective': responses_collective,
            'turn': turn
        }