import anthropic
from pathlib import Path

client = anthropic.Anthropic(
    api_key="sk-tux3DQDGdsY3QRbFBf79Ba10C395452c9bC9B16952A6B51c", # 换成你在 AiHubMix 生成的密钥
    base_url="https://aihubmix.com"
)
# r = client.beta.files.upload(
#     file=Path("/home/liang/projects/efflux-desktop/README.md"),
# )
# print('r -----------------------------------')
# print(r)
message = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "你是谁"}
    ]
)
print(message.content)