
import json
from urllib import request, error


class GeminiClientError(RuntimeError):
    pass


class GeminiClient:
    def __init__(self, api_key: str, model: str, base_url: str, timeout_seconds: int = 30):
        self.api_key = (api_key or '').strip()
        self.model = model
        self.base_url = base_url.rstrip('/')
        self.timeout_seconds = timeout_seconds

    def generate_text(self, prompt: str) -> str:
        if not self.api_key:
            raise GeminiClientError('AI_API_KEY não configurada.')
        url = f"{self.base_url}/models/{self.model}:generateContent"
        payload = {
            "generationConfig": {"temperature": 0.3},
            "contents": [{"parts": [{"text": prompt}]}],
        }
        req = request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'x-goog-api-key': self.api_key,
            },
            method='POST',
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                raw = resp.read().decode('utf-8')
        except error.HTTPError as exc:
            body = exc.read().decode('utf-8', errors='ignore')
            raise GeminiClientError(f'Erro HTTP do Gemini: {exc.code} {body[:300]}') from exc
        except Exception as exc:
            raise GeminiClientError(f'Falha ao chamar Gemini: {exc}') from exc

        try:
            parsed = json.loads(raw)
            return parsed['candidates'][0]['content']['parts'][0]['text'].strip()
        except Exception as exc:
            raise GeminiClientError(f'Resposta inesperada do Gemini: {raw[:300]}') from exc
