from __future__ import annotations

from openai import APIConnectionError, APIError, AuthenticationError, OpenAI, RateLimitError


class LLMClientError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, *, api_key: str, base_url: str, model: str) -> None:
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def chat(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content = response.choices[0].message.content
            if not content:
                raise LLMClientError("Empty response from model")
            return content.strip()
        except AuthenticationError as exc:
            raise LLMClientError("Authentication failed. Check API key.") from exc
        except RateLimitError as exc:
            raise LLMClientError("Rate limit reached. Retry later.") from exc
        except APIConnectionError as exc:
            raise LLMClientError("Connection failed. Check base_url/network.") from exc
        except APIError as exc:
            raise LLMClientError(f"LLM API error: {exc}") from exc
        except Exception as exc:
            raise LLMClientError(f"Unexpected LLM error: {exc}") from exc
