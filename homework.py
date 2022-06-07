import logging
import os
import sys
import time
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


def send_message(bot, message):
    """Отправляем сообщение"""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.info('удачная отправка сообщения в Telegram')
    except Exception as error:
        logging.error(f'Сбой при отправке сообщения в Telegram: {error}')


def get_api_answer(current_timestamp):
    """Делаем запрос к API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = (requests.get(ENDPOINT, headers=HEADERS, params=params))
        if response.status_code != 200:
            logging.error('API возвращает код, отличный от 200')
            raise HTTPError('API возвращает код, отличный от 200')
        response = response.json()
        return response
    except requests.exceptions.RequestException as error:
        raise SystemExit(error)


def check_response(response):
    """Проверяем ответ API на корректность.."""
    if not isinstance(response['homeworks'], list):
        raise TypeError("Значение по ключу 'homeworks' не является списком")
    else:
        homeworks = response['homeworks']
        return homeworks


def parse_status(homework):
    """При обновлении статуса анализируем ответ API"""
    homework_name = homework['homework_name']
    if homework['status'] not in HOMEWORK_STATUSES:
        logging.error(
            "Обнаружен недокументированный статус домашней работы в ответе API"
        )
        raise KeyError
    else:
        homework_status = homework['status']
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяем доступность переменных окружения"""
    for key, value in ENV_CHECK_LIST.items():
        if value is False:
            logging.critical(f"Ошибка переменных окружения: '{key}'")
            raise KeyError
    if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID is not False:
        return True
    else:
        return False


def main():
    """Основная логика работы бота."""

    print(check_tokens())
    check_tokens()

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
                logging.debug("Отсутствуют новые статусы домашней работы")

            current_timestamp = response.get('current_date')
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
