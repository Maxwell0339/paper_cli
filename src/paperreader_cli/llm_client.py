from __future__ import annotations

from dataclasses import dataclass
import threading
import time

from openai import APIConnectionError, APIError, AuthenticationError, OpenAI, RateLimitError


class LLMClientError(RuntimeError):
    pass


@dataclass(slots=True)
class ChatResult:
    content: str
    total_tokens: int


class LLMClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        request_timeout: int = 120,
        max_retries: int = 3,
        rate_limit_qps: float = 1.5,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._base_url = base_url
        self._local = threading.local()
        self.request_timeout = max(10, int(request_timeout))
        self.max_retries = max(0, int(max_retries))
        self.rate_limit_qps = max(0.1, float(rate_limit_qps))
        self._min_interval = 1.0 / self.rate_limit_qps
        self._rate_lock = threading.Lock()
        self._last_call_at = 0.0

    def _get_client(self) -> OpenAI:
        client = getattr(self._local, "client", None)
        if client is None:
            client = OpenAI(api_key=self._api_key, base_url=self._base_url)
            self._local.client = client
        return client

    def _acquire_rate_slot(self) -> None:
        sleep_for = 0.0
        with self._rate_lock:
            now = time.monotonic()
            scheduled_at = max(now, self._last_call_at + self._min_interval)
            self._last_call_at = scheduled_at
            sleep_for = max(0.0, scheduled_at - now)
        if sleep_for > 0:
            time.sleep(sleep_for)

    def chat(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> ChatResult:
        client = self._get_client()
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self._acquire_rate_slot()
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    temperature=temperature,
                    timeout=self.request_timeout,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                content = response.choices[0].message.content
                if not content:
                    raise LLMClientError("Empty response from model")
                usage = getattr(response, "usage", None)
                total_tokens = int(getattr(usage, "total_tokens", 0) or 0)
                return ChatResult(content=content.strip(), total_tokens=total_tokens)
            except AuthenticationError as exc:
                raise LLMClientError("Authentication failed. Check API key.") from exc
            except (RateLimitError, APIConnectionError, APIError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                backoff_seconds = min(8.0, 0.8 * (2 ** attempt))
                time.sleep(backoff_seconds)
            except Exception as exc:
                raise LLMClientError(f"Unexpected LLM error: {exc}") from exc

        if isinstance(last_error, RateLimitError):
            raise LLMClientError("Rate limit reached after retries. Retry later.") from last_error
        if isinstance(last_error, APIConnectionError):
            raise LLMClientError("Connection failed after retries. Check base_url/network.") from last_error
        if isinstance(last_error, APIError):
            raise LLMClientError(f"LLM API error after retries: {last_error}") from last_error
        raise LLMClientError("LLM request failed for unknown reason.")
