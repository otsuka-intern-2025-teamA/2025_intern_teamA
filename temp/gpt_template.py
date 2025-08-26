import os

import numpy as np
from openai import AzureOpenAI
from dotenv import load_dotenv
import time


#.envからAPIキーを読む準備
load_dotenv('.env', override=True)
API_VERSION = "2024-12-01-preview" #Azure openAI API version
'''
使用可能なモデル
gpt-5-mini: reasoning(high), input(text), output(text,image), description(https://platform.openai.com/docs/models/gpt-5-mini)
text-embedding-3-large: embedding model(https://platform.openai.com/docs/models/text-embedding-3-large)
'''
model_list = ['gpt-5-mini', 'text-embedding-3-large']

#Azure openAI API クライアントの作成
client = AzureOpenAI(
    api_version=API_VERSION,
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
)

'''
GPT5-miniに渡す入力
System prompt
Userの入力(text,image)
'''

messages = [
        {
            "role": "system",
            "content": "You are a kid who knows nothing about AI",
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text":"Explain me the GPT model. in 100 words."},
            ]
        }
    ]



start_time = time.time()
#Azure openAI API を呼び出す
response = client.chat.completions.create(
    messages=messages, #入力
    max_completion_tokens=12800, #最大トークン数
    model=model_list[0] #モデル選択
    # temperature パラメータは GPT-5-mini でサポートされていないため削除
)

print(response.choices[0].message.content)
print("--------------------------------------------------")
print("--- %s seconds ---" % (time.time() - start_time))


print(f'completion_tokens={response.usage.completion_tokens}, prompt_tokens={response.usage.prompt_tokens}, total_tokens={response.usage.total_tokens}')
print(f'reasoning_tokens={response.usage.completion_tokens_details.reasoning_tokens}')


dimensions = 1024 #最大の埋め込み次元数
input_text = ["first phrase","second phrase","third phrase"] #インプット
response = client.embeddings.create(
    input=input_text,
    dimensions=dimensions,
    model=model_list[1] #モデル選択
)

embeddings = np.zeros((len(input_text),dimensions)) #Embedding vectorを入れるためのnumpy配列

#埋め込み結果を表示
for i,item in enumerate(response.data):
    length = len(item.embedding)
    embeddings[i,:] = item.embedding
    print(
        f"data[{item.index}]: length={length}, "
        f"[{item.embedding[0]}, {item.embedding[1]}, "
        f"..., {item.embedding[length-2]}, {item.embedding[length-1]}]"
    )
print(response.usage)
print(f'embeddings shape: {embeddings.shape}')









