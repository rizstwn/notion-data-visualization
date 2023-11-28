from dotenv import load_dotenv
import os

load_dotenv()
print(os.environ.get('DATABASE_ID'))
print(os.environ.get('NOTION_URL'))
print(os.environ.get('INTEGRATION_TOKEN'))
print(os.environ.get('NOTION_VERSION'))