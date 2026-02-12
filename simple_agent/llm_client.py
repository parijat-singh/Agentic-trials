import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

class LLMClient:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables. Please check your .env file.")
        
        self.client = OpenAI(api_key=self.api_key)

    def get_completion(self, messages, model=None, stop=None):
        """
        Sends messages to the LLM and returns the response content.
        Argument 'stop' can be a list of strings to stop generation at.
        """
        # User defined model in .env takes precedence, otherwise usage default, otherwise hardcoded default
        msg_model = model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
        try:
            response = self.client.chat.completions.create(
                model=msg_model,
                messages=messages,
                temperature=0,  # Deterministic for tool usage
                stop=stop
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error communicating with LLM: {str(e)}"
