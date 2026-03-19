
from google import genai
from google.genai import types


class GeminiClientError(RuntimeError):
    pass


class GeminiClient:
    """
    Cliente para a API Gemini usando o SDK oficial google-genai.
    Migrado de HTTP direto (urllib) para o SDK em março/2026.
    """

    def __init__(self, api_key: str, model: str, base_url: str = "", timeout_seconds: int = 30):
        self.api_key = (api_key or "").strip()
        self.model = model
        self.timeout_seconds = timeout_seconds
        # base_url ignorado — o SDK gerencia endpoints internamente.

    def _client(self) -> genai.Client:
        if not self.api_key:
            raise GeminiClientError("AI_API_KEY não configurada.")
        return genai.Client(api_key=self.api_key)

    def generate_text(self, prompt: str) -> str:
        try:
            client = self._client()
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.3),
            )
            return response.text.strip()
        except GeminiClientError:
            raise
        except Exception as exc:
            raise GeminiClientError(f"Falha ao chamar Gemini ({self.model}): {exc}") from exc
