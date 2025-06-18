from openai import OpenAI

client = OpenAI(
    api_key="sk-tux3DQDGdsY3QRbFBf79Ba10C395452c9bC9B16952A6B51c", # 换成你在后台生成的 Key "sk-***"
    base_url="https://aihubmix.com/v1"
)
file = client.files.create(
    file=open("/home/liang/projects/efflux-desktop/README.md", "rb"),
    purpose="user_data"
)
response = client.responses.create(
    model="gpt-4o-mini", # codex-mini-latest 可用
    # model="gpt-4.1",
    input=[
        {
            "role": "user",
            "content": [
                # {
                #     "type": "input_file",
                #     "file_id": file.id,
                # },
                # {
                #     "type": "input_text",
                #     "text": "What is the first dragon in the book?",
                # },
                { "type": "input_text", "text": "what is in this image?" },
                {
                    "type": "input_image",
                    "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"
                }
            ]
        }
    ]
)

print(response)