from langchain_core.language_models.base import BaseLanguageModel
from typing import Optional
from rise import rise

class GAssistLLM(BaseLanguageModel):
    """LangChain-compatible wrapper for NVIDIA G-Assist SLM."""
    def __init__(self):
        rise.register_rise_client()

    def _call(self, prompt: str, stop: Optional[list] = None) -> str:
        response = rise.send_rise_command(prompt)
        return response

    def invoke(self, prompt: str, stop: Optional[list] = None) -> str:
        return self._call(prompt, stop) 