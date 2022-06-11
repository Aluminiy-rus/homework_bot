import json
import logging
import os
import sys
import time
from http import HTTPStatus
from urllib.error import HTTPError

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

ENV_CHECK_LIST = {
    'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
    'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
    'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
}

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    handlers=[
        logging.StreamHandler(sys.stdout)
    ],
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
invalid_chatid = []


def send_message(bot, message):
    """Отправляем сообщение."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.info('удачная отправка сообщения в Telegram')
    except telegram.TelegramError as error:
        logger.error(f'Сбой при отправке сообщения в Telegram: {error}')


def get_api_answer(current_timestamp):
    """Делаем запрос к API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK.value:
            logger.error('API возвращает код, отличный от 200')
            raise HTTPError('API возвращает код, отличный от 200')
        try:
            response = response.json()
            return response
        except json.decoder.JSONDecodeError:
            logger.error('Не удалось преобразовать в JSON')
    except requests.exceptions.RequestException as error:
        raise SystemExit(error)


def check_response(response):
    """Проверяем ответ API на корректность."""
    if isinstance(response, dict):
        if 'homeworks' not in response:
            raise KeyError("Ключ 'homeworks' не найден")
    if response['homeworks'] is not None:
        if not isinstance(response['homeworks'], list):
            logger.error("Значение по ключу 'homeworks' не является списком")
            raise TypeError(
                "Значение по ключу 'homeworks' не является списком"
            )
        homeworks = response['homeworks']
        return homeworks
    logger.error("Ключ 'homeworks' не найден")
    raise KeyError("Ключ 'homeworks' не найден")


def parse_status(homework):
    """При обновлении статуса анализируем ответ API."""
    if 'homework_name' not in homework:
        logger.error("Необнаружено имя домашней работы")
        raise KeyError("Необнаружено имя домашней работы")
    homework_name = homework['homework_name']
    if 'status' not in homework:
        logger.error("Необнаружен статус домашней работы")
        raise KeyError("Необнаружен статус домашней работы")
    if homework['status'] not in HOMEWORK_STATUSES:
        logger.error("Обнаружен недокументированный статус домашней работы")
        raise KeyError("Обнаружен недокументированный статус домашней работы")
    homework_status = homework['status']
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяем доступность переменных окружения."""
    for key, value in ENV_CHECK_LIST.items():
        if value is not None:
            logger.critical(f"Ошибка переменных окружения: '{key}'")
            raise KeyError("Ошибка переменных окружения")
    if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        return True
    else:
        return False


def main():
    """Основная логика работы бота."""
    if check_tokens():
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        current_timestamp = int(time.time())
        while True:
            try:
                response = get_api_answer(current_timestamp)
                homeworks = check_response(response)
                if homeworks:
                    message = parse_status(homeworks[0])
                    send_message(bot, message)
                else:
                    logger.debug("Отсутствуют новые статусы домашней работы")

                current_timestamp = response.get('current_date')
                time.sleep(RETRY_TIME)
            except Exception as error:
                message = f'Сбой в работе программы: {error}'
                logger.error(message)
                send_message(bot, message)
                time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
