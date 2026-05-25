import httpx
import json
import logging
from typing import AsyncGenerator, List, Dict, Any, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

class PeftInferenceService:
    def __init__(self):
        # Default model and LoRA definitions
        self.base_url = settings.VLLM_API_URL
        self.headers = {}
        if settings.VLLM_API_KEY:
            self.headers["Authorization"] = f"Bearer {settings.VLLM_API_KEY}"

    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        use_peft: bool = True,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """
        Sends an async completion request to the vLLM server and yields tokens in real time.
        If use_peft is enabled, it sends the request directed to the enterprise style adapter.
        """
        # Determine target model string (e.g. adapter name vs base model name)
        model_name = settings.PRIMARY_MODEL
        if use_peft:
            # vLLM LoRA format requires referencing the loaded adapter name
            model_name = f"{settings.PRIMARY_MODEL}-lora-enterprise"
            logger.info(f"Targeting PEFT/LoRA adapter model: {model_name}")
        else:
            logger.info(f"Targeting Base model: {model_name}")

        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature if temperature is not None else settings.TEMPERATURE,
            "max_tokens": max_tokens if max_tokens is not None else settings.MAX_TOKENS,
            "stream": True
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=self.headers
                ) as response:
                    
                    if response.status_code != 200:
                        error_detail = await response.aread()
                        logger.error(f"vLLM API returned error status: {response.status_code}. Detail: {error_detail.decode()}")
                        yield f"[Inference Error: vLLM returned HTTP {response.status_code}]"
                        return

                    # Parse Server-Sent Events stream
                    async for line in response.iter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            data_str = line[len("data: "):]
                            if data_str.strip() == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                choice = data["choices"][0]
                                delta = choice.get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                            except (KeyError, json.JSONDecodeError):
                                continue

            except httpx.RequestError as e:
                logger.error(f"Failed to connect to vLLM server: {e}")
                yield f"[Connection Error: Could not connect to vLLM server at {self.base_url}]"

    async def generate(
        self,
        messages: List[Dict[str, str]],
        use_peft: bool = True,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Non-streaming completion for backend internal reasoning agents.
        """
        response_text = []
        async for token in self.generate_stream(messages, use_peft, temperature, max_tokens):
            if not token.startswith("[Inference Error") and not token.startswith("[Connection Error"):
                response_text.append(token)
            else:
                return f"Error: {token}"
        return "".join(response_text)

peft_inference = PeftInferenceService()
