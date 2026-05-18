import os, base64
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
with open('preprocessed_test.png', 'rb') as f:
    img = base64.b64encode(f.read()).decode('ascii')
res = client.chat.completions.create(model='gpt-4o', messages=[{'role':'user', 'content': [{'type':'text', 'text':'What text do you see in this image? Transcribe exactly.'}, {'type':'image_url', 'image_url': {'url': f'data:image/png;base64,{img}'}}]}])
print(res.choices[0].message.content)
