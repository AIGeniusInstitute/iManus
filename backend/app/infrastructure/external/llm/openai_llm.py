from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI, BadRequestError
from app.domain.external.llm import LLM
from app.core.config import get_settings
import logging
import asyncio
import time


logger = logging.getLogger(__name__)


class OpenAILLM(LLM):
    def __init__(self):
        settings = get_settings()
        self.client = AsyncOpenAI(api_key=settings.api_key, base_url=settings.api_base)

        self._model_name = settings.model_name
        self._temperature = settings.temperature
        self._max_tokens = settings.max_tokens
        logger.info(f"Initialized OpenAI LLM with model: {self._model_name}")

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def temperature(self) -> float:
        return self._temperature

    @property
    def max_tokens(self) -> int:
        return self._max_tokens

    async def ask(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        response_format: Optional[Dict[str, Any]] = None,
        tool_choice: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send chat request to OpenAI API with retry mechanism and intelligent max_tokens adjustment"""
        max_retries = 4
        base_delay = 1.0
        max_tokens = self._max_tokens

        for attempt in range(max_retries + 1):  # every try
            response = None
            try:
                if attempt > 0:
                    delay = base_delay * (2 ** (attempt - 1))  # back off
                    logger.info(
                        f"Retrying OpenAI API request (attempt {attempt + 1}/{max_retries + 1}) after {delay}s delay"
                    )
                    await asyncio.sleep(delay)

                if tools:
                    logger.debug(
                        f"Sending request to OpenAI with tools, model: {self._model_name}, max_tokens: {max_tokens}, attempt: {attempt + 1}"
                    )
                    response = await self.client.chat.completions.create(
                        model=self._model_name,
                        temperature=self._temperature,
                        max_tokens=max_tokens,
                        messages=messages,
                        tools=tools,
                        response_format=response_format,
                        tool_choice=tool_choice,
                        parallel_tool_calls=False,
                    )
                else:
                    logger.debug(
                        f"Sending request to OpenAI without tools, model: {self._model_name}, max_tokens: {max_tokens}, attempt: {attempt + 1}"
                    )
                    response = await self.client.chat.completions.create(
                        model=self._model_name,
                        temperature=self._temperature,
                        max_tokens=max_tokens,
                        messages=messages,
                        response_format=response_format,
                    )

                logger.debug(f"Response from OpenAI: {response.model_dump()}")

                if not response or not response.choices:
                    error_msg = f"OpenAI API returned invalid response (no choices) on attempt {attempt + 1}"
                    logger.error(error_msg)
                    if attempt == max_retries:
                        raise ValueError(
                            f"Failed after {max_retries + 1} attempts: {error_msg}"
                        )
                    continue

                return response.choices[0].message.model_dump()

            except BadRequestError as e:
                # Handle max_tokens too large error
                error_msg = str(e)
                if (
                    "max_tokens" in error_msg.lower()
                    or "too large" in error_msg.lower()
                ):
                    # Reduce max_tokens by half and retry
                    new_max_tokens = max(512, max_tokens // 2)
                    logger.warning(
                        f"max_tokens ({max_tokens}) is too large. Reducing to {new_max_tokens} and retrying. Error: {error_msg}"
                    )
                    max_tokens = new_max_tokens
                    if attempt < max_retries:
                        continue
                    else:
                        logger.error(
                            f"Failed to adjust max_tokens after {max_retries + 1} attempts"
                        )
                        raise e
                else:
                    logger.error(
                        f"BadRequestError on attempt {attempt + 1}: {error_msg}"
                    )
                    if attempt == max_retries:
                        raise e
                    continue
            except Exception as e:
                error_msg = (
                    f"Error calling OpenAI API on attempt {attempt + 1}: {str(e)}"
                )
                logger.error(error_msg)
                if attempt == max_retries:
                    raise e
                continue
