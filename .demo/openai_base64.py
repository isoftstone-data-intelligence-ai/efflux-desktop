import base64
from openai import OpenAI
client = OpenAI(
    api_key="sk-tux3DQDGdsY3QRbFBf79Ba10C395452c9bC9B16952A6B51c", # 换成你在后台生成的 Key "sk-***"
    base_url="https://aihubmix.com/v1"
)

with open("/home/liang/projects/efflux-desktop/README.md", "rb") as f:
    data = f.read()

base64_string = base64.b64encode(data).decode("utf-8")

response = client.responses.create(
    model="gpt-4o-mini",    # 成功
    # model="claude-sonnet-4-20250514",   # 失败
    # model="claude-3-5-sonnet-20241022",     # 失败
    # model="anthropic-3-5-sonnet-20240620",     # 失败
    # model="claude-3-5-haiku-20241022",     # 失败
    # model="gemini-2.5-flash",     # 失败
    input=[
        {
            "role": "user",
            "content": [
                # {
                #     "type": "input_file",
                #     "filename": "README.md",
                #     "file_data": f"data:application/pdf;base64,{base64_string}",
                # },
                {
                    "type": "input_text",
                    "text": "你是谁",
                    # "text": "请分析上面的 Markdown 文件内容，并总结成20字左右的简介。",
                },
            ],
        },
    ]
)

print(response.output_text)