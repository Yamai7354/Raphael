import os
import instructor
from litellm import completion


def get_instructor_client():
    """
    Returns an instructor-patched LiteLLM client for structured data generation.
    Usage:
        client = get_instructor_client()
        resp = client.chat.completions.create(
            model="gpt-4o", # LiteLLM handles routing to Azure/OpenAI/Ollama seamlessly
            response_model=MyPydanticModel,
            messages=[...]
        )
    """
    # instructor.from_litellm automatically patches the litellm completion function
    # to support typed Pydantic responses.
    client = instructor.from_litellm(completion)
    return client


# Optional: Add litellm fallback/routing configurations here
