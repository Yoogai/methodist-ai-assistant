import base64
import logging
import requests
from src.config import YANDEX_API_KEY, YANDEX_FOLDER_ID

logger = logging.getLogger(__name__)


class YandexOCRService:
    def __init__(self):
        """
        Инициализация сервиса распознавания текста Yandex Vision.
        Использует стандартный API-ключ для аутентификации.
        """
        self.api_url = "https://vision.api.cloud.yandex.net/vision/v1/batchAnalyze"
        self.api_key = YANDEX_API_KEY
        self.folder_id = YANDEX_FOLDER_ID
        self.headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json"
        }

    def recognize_text(self, image_bytes: bytes) -> str:
        """
        Отправляет изображение в облачный сервис Yandex Vision и возвращает распознанный текст.

        :param image_bytes: Бинарные данные изображения.
        :return: Строка с распознанным текстом или пустая строка в случае ошибки.
        """
        # Кодирование изображения в формат Base64, требуемый API
        encoded_image = base64.b64encode(image_bytes).decode("utf-8")

        # Формирование полезной нагрузки запроса согласно документации Yandex Cloud
        payload = {
            "folderId": self.folder_id,
            "analyze_specs": [{
                "content": encoded_image,
                "features": [{
                    "type": "TEXT_DETECTION",
                    "text_detection_config": {
                        "language_codes": ["ru", "en"]
                    }
                }]
            }]
        }

        try:
            response = requests.post(self.api_url, headers=self.headers, json=payload, timeout=30)

            if response.status_code != 200:
                logger.error(f"Ошибка Yandex Vision API: {response.status_code} - {response.text}")
                return ""

            result = response.json()

            # Иерархический парсинг ответа: результаты -> текстовое обнаружение -> страницы -> блоки -> строки
            full_text = []
            try:
                # Проверка наличия данных в ответе
                if 'results' in result and result['results'][0]['results']:
                    text_detection = result['results'][0]['results'][0].get('textDetection')

                    if not text_detection:
                        logger.warning("Текст на изображении не обнаружен.")
                        return ""

                    for page in text_detection.get('pages', []):
                        for block in page.get('blocks', []):
                            for line in block.get('lines', []):
                                # Объединение слов в строку
                                line_text = " ".join([word['text'] for word in line.get('words', [])])
                                full_text.append(line_text)
                            full_text.append("")  # Разделитель между блоками текста

                    return "\n".join(full_text).strip()

            except (KeyError, IndexError) as e:
                logger.error(f"Ошибка при парсинге JSON ответа Vision: {e}")
                return ""

        except Exception as e:
            logger.error(f"Критическая ошибка в YandexOCRService: {e}")
            return ""

        return ""