"""
Single place that constructs the chat LLM client, so provider/model choice
is configured once (backend.config) instead of scattered across modules.
"""
from backend.config import settings

_llm = None


def get_chat_llm(model: str = None, temperature: float = 0.2):
    """Returns a LangChain chat model. Cached for the default model/temperature."""
    global _llm
    model = model or settings.LLM_MODEL

    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set; cannot create the chat LLM.")

    if _llm is not None and model == settings.LLM_MODEL and temperature == 0.2:
        return _llm

    from langchain_groq import ChatGroq

    llm = ChatGroq(
        groq_api_key=settings.GROQ_API_KEY,
        model_name=model,
        temperature=temperature,
    )

    if model == settings.LLM_MODEL and temperature == 0.2:
        _llm = llm
    return llm
