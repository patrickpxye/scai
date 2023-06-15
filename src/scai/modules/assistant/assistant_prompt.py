"""
The Assistant Prompt.
"""
from typing import Dict
    
from scai.modules.assistant.models import AssistantPrompt

ASSISTANT_PROMPT: Dict[str, AssistantPrompt] = {
    "assistant_prompt_1": AssistantPrompt(
        id="assistant_prompt_1",
        name="helpful_assistant",
        max_tokens=50,
        role="system",
        content="""{system_message} {task}""",
    ),
}