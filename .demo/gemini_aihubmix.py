from google import genai
from google.genai import types
import logging
import os
import sys
from dotenv import load_dotenv
from pathlib import Path

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
logging.info(f"Current directory: {current_dir}")
logging.info(f"Project root: {project_root}")
sys.path.insert(0, project_root)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

# 更新文件类型映射
FILE_TYPE_MAP = {
    ".pdf": ("application/pdf", "PDF"),
    ".html": ("text/html", "HTML"),
    ".js": ("text/javascript", "JavaScript"),
    ".py": ("text/x-python", "Python"),
    ".txt": ("text/plain", "文本"),
    ".css": ("text/css", "CSS"),
    ".md": ("text/md", "Markdown"),
    ".csv": ("text/csv", "CSV"),
    ".xml": ("text/xml", "XML"),
    ".rtf": ("text/rtf", "RTF"),
    # 添加图片格式支持
    ".png": ("image/png", "PNG"),
    ".jpeg": ("image/jpeg", "JPEG"),
    ".jpg": ("image/jpeg", "JPEG"),  # 补充常见的 .jpg 扩展名
    ".webp": ("image/webp", "WEBP"),
    ".heic": ("image/heic", "HEIC"),
    ".heif": ("image/heif", "HEIF")
}

def handle_file(file_path: str) -> types.Part:
    """处理文件路径，返回模型可识别的Part对象"""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    suffix = path.suffix.lower()
    if suffix not in FILE_TYPE_MAP:
        supported = ", ".join(ft[1] for ft in FILE_TYPE_MAP.values())
        raise ValueError(f"不支持的文件格式: {suffix}（仅支持{supported}）")

    mime_type, _ = FILE_TYPE_MAP[suffix]
    logger.info(f"处理文件: {file_path} ({mime_type})")
    return types.Part(
        inline_data=types.Blob(
            data=path.read_bytes(),
            mime_type=mime_type
        )
    )

def process_inputs(inputs: list) -> list[types.Part]:
    """处理输入列表，生成模型需要的Part列表"""
    parts = []
    for item in inputs:
        if item["type"] == "file":
            parts.append(handle_file(item["content"]))
        elif item["type"] == "txt":
            parts.append(types.Part(text=item["content"]))
        else:
            raise ValueError(f"不支持的输入类型: {item['type']}（仅支持file/txt）")
    return parts

# 核心功能封装函数
def generate_response(inputs: list) -> str:
    """
    生成模型响应并返回处理后的结果
    :param inputs: 输入列表（格式同process_inputs要求）
    :return: 处理后的文本结果
    """
    client = genai.Client(
        api_key=os.getenv("AIHUBMIX_API_KEY"),
        http_options={"base_url": "https://aihubmix.com/gemini"}
    )

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=types.Content(parts=process_inputs(inputs)),
        config=types.GenerateContentConfig(
            tools=[types.Tool(code_execution=types.ToolCodeExecution)]
        )
    )

    result = []
    for part in response.candidates[0].content.parts:
        if part.text is not None:
            result.append(part.text)
        if getattr(part, "executable_code", None) is not None:
            result.append(f"Generated code:\n{part.executable_code.code}")
        if getattr(part, "code_execution_result", None) is not None:
            result.append(f"Execution result:\n{part.code_execution_result.output}")

    return "\n\n".join(result)  # 将各部分结果合并为字符串返回

if __name__ == '__main__':
    demo_inputs = [
        # {"type": "file", "content": "/home/liang/projects/efflux-desktop/README.md"},
        # {"type": "txt", "content": "请分析上面的 Markdown 文件内容，并总结成20字左右的简介。"}
        {"type": "file", "content": "/home/liang/screenshot.png"},
        {"type": "txt", "content": "请分析上面的 图片内容，并推测出处。"}
    ]

    try:
        # 调用封装函数获取结果
        final_result = generate_response(demo_inputs)
        # 统一打印结果
        print(final_result)
    except Exception as e:
        logger.error(f"执行失败: {str(e)}")
        sys.exit(1)