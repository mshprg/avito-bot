import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ.get('BOT_TOKEN')
DATABASE_URL = os.environ.get('DATABASE_URL')
ROOT_USER_IDS = eval(os.environ.get('ROOT_USER_ID'))
AVITO_CLIENT_ID = os.environ.get('AVITO_CLIENT_ID')
AVITO_CLIENT_SECRET = os.environ.get('AVITO_CLIENT_SECRET')
BUCKET_NAME = os.environ.get('BUCKET_NAME')

# Webhook settings
WEBHOOK_HOST = os.environ.get('WEBHOOK_HOST')  # ngrok URL или ваш сервер
WEBHOOK_PATH = '/webhook'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
# https://ff4f-2a00-1370-818c-206b-2509-507b-e8e3-5318.ngrok-free.app
# https://b1bf-185-145-125-177.ngrok-free.app
# https://6c0a-2a00-1370-818c-206b-a0b3-b8cf-d7fb-73ab.ngrok-free.app

# Web server settings
WEBAPP_HOST = '0.0.0.0'
WEBAPP_PORT = 3001
