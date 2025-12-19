import httpx
import logging
from typing import Optional
from src.config import YANDEX_API_KEY, YANDEX_FOLDER_ID

logger = logging.getLogger(__name__)


class YandexSpeechKitService:
    def __init__(self):
        self.api_key = YANDEX_API_KEY
        self.folder_id = YANDEX_FOLDER_ID
        # Стабильный эндпоинт v1 (работает с OGG по умолчанию)
        self.stt_url = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
        self.tts_url = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"

    async def speech_to_text(self, audio_bytes: bytes) -> Optional[str]:
        """
        Распознает речь через API v1.
        Идеально подходит для голосовых сообщений Telegram.
        """
        headers = {"Authorization": f"Api-Key {self.api_key}"}

        # Параметры передаются в URL
        params = {
            "folderId": self.folder_id,
            "lang": "ru-RU",
            "topic": "general",
            "format": "oggopus"  # Telegram по умолчанию использует OGG OPUS
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.stt_url,
                    headers=headers,
                    params=params,
                    content=audio_bytes,  # Отправляем байты напрямую
                    timeout=30.0
                )

                if response.status_code != 200:
                    logger.error(f"STT v1 Error {response.status_code}: {response.text}")
                    return None

                # Ответ v1 прост: {"result": "Текст"}
                return response.json().get("result")

            except Exception as e:
                logger.error(f"STT Critical Error: {e}")
                return None

    async def text_to_speech(self, text: str) -> Optional[bytes]:
        """Синтезирует речь (API v1)."""
        headers = {"Authorization": f"Api-Key {self.api_key}"}
        data = {
            "folderId": self.folder_id,
            "text": text,
            "voice": "filipp",
            "emotion": "good"
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.tts_url, headers=headers, data=data, timeout=60.0)
                if response.status_code != 200:
                    return None
                return response.content
            except Exception:
                return None