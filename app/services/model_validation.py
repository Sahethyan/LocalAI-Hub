import logging

from app.services.ollama_client import OllamaClient, OllamaConnectionError

logger = logging.getLogger(__name__)


def _model_names_from_tags(data: dict) -> set[str]:
    names: set[str] = set()
    for entry in data.get("models") or []:
        if isinstance(entry, dict):
            if name := entry.get("name"):
                names.add(name)
            if model := entry.get("model"):
                names.add(model)
    return names


async def soft_validate_model(model: str, ollama: OllamaClient) -> str:
    """
    Soft whitelist: log a warning if the model is absent from the last /api/tags
    fetch, but always return the requested name so chat can proceed offline.
    """
    try:
        data = await ollama.list_models()
    except OllamaConnectionError:
        logger.warning(
            "Skipping model whitelist check for %r (Ollama unreachable)", model
        )
        return model

    known = _model_names_from_tags(data)
    if known and model not in known:
        logger.warning(
            "Model %r not in Ollama catalog (%d models); proceeding anyway",
            model,
            len(known),
        )
    return model
