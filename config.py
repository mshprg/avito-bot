import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ.get('BOT_TOKEN')
DATABASE_URL = os.environ.get('DATABASE_URL')
ROOT_USER_IDS = eval(os.environ.get('ROOT_USER_ID'))
AVITO_CLIENT_ID = os.environ.get('AVITO_CLIENT_ID')
AVITO_CLIENT_SECRET = os.environ.get('AVITO_CLIENT_SECRET')
BUCKET_NAME = os.environ.get('BUCKET_NAME')
MERCHANT_LOGIN = os.environ.get('MERCHANT_LOGIN')
MERCHANT_PASSWORD_1 = os.environ.get('MERCHANT_PASSWORD_1')
MERCHANT_PASSWORD_2 = os.environ.get('MERCHANT_PASSWORD_2')
SMSAERO_EMAIL = os.environ.get('SMSAERO_EMAIL')
SMSAERO_API_KEY = os.environ.get('SMSAERO_API_KEY')

# Webhook settings
WEBHOOK_HOST = os.environ.get('WEBHOOK_HOST')  # ngrok URL или ваш сервер
WEBHOOK_PATH = '/webhook'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
ROBOKASSA_PATH = '/result-payment/'

# Web server settings
WEBAPP_HOST = '0.0.0.0'
WEBAPP_PORT = 3001
