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
# https://e911-2a03-6f00-5-1-00-4bce.ngrok-free.app
# https://f230-2a00-1370-818c-206b-a9e6-f5bd-2f6b-ffce.ngrok-free.app
# https://7091-213-87-149-231.ngrok-free.app
# https://959b-213-87-130-177.ngrok-free.app
# https://cf69-213-87-135-249.ngrok-free.app
# https://ab11-213-87-146-135.ngrok-free.app
# https://afdf-2a00-1370-818c-206b-a9e6-f5bd-2f6b-ffce.ngrok-free.app

# Web server settings
WEBAPP_HOST = '0.0.0.0'
WEBAPP_PORT = 3001
