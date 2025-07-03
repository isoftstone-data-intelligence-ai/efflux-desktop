import base64
import os
import sys
from typing import Optional

def check_file_and_create(file_url: str, init_str:Optional[str] = None):
    # 获取文件夹路径
    folder_path = os.path.dirname(file_url)
    if not folder_path:
        # 获取当前工作目录
        folder_path = current_directory()
        print("当前目录是:", current_directory)
    # 如果文件夹不存在，则创建文件夹
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)  # 创建多级目录
        print(f"Folder {folder_path} has been created.")
    # 如果文件不存在，则创建该文件
    if not os.path.exists(file_url):
        with open(file_url, 'w') as file:  # 打开文件并自动创建
            print(f"File {file_url} has been created.")
            if init_str:
                file.write(init_str)
            pass  # 不需要写入任何内容，仅用于创建文件

def current_directory():
    # 获取当前工作目录
    return os.getcwd()

def check_file(file_url: str):
    # 判断文件是否存在
    if os.path.exists(file_url):
        return True
    return False

def del_file(file_url: str):
    if os.path.exists(file_url):
        os.remove(file_url)
        print(f"File {file_url} has been removed.")
    else:
        print(f"File {file_url} does not exist.")

def open_and_base64(file_path: str) -> str:
    with open(file_path, "rb") as f:
        file_content = f.read()
        base64_encoded = base64.b64encode(file_content).decode("utf-8")
        return base64_encoded


def get_resource_path(relative_path):
    # PyInstaller 包装后的文件会有 _MEIPASS 属性
    # if hasattr(sys, '_MEIPASS'):
    #     # 打包后的路径
    #     base_path = sys._MEIPASS
    # else:
    #     # 非打包环境
    #     base_path = os.path.abspath(".")
    base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

from pdfminer.high_level import extract_text

def extract_pdf_text(file_path):
    try:
        text = extract_text(file_path)
        return text
    except Exception as e:
        print(f"读取 PDF 时出错: {e}")
        return None

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTTextBox, LTTextLine, LTAnno

def extract_table_like_text(file_path):
    rows = []
    for page_layout in extract_pages(file_path):
        items = []
        for element in page_layout:
            if isinstance(element, (LTTextBox, LTTextLine)):
                print(f"找到的文本: {element.get_text()}")
                if hasattr(element, 'bbox'):
                    print(f"文本的边界框: {element.bbox}")
                    for text_line in element:
                        if hasattr(text_line, 'bbox'):
                            x0, y0, x1, y1 = text_line.bbox
                            text = text_line.get_text().strip()
                            if text:
                                # 记录 (y 坐标, x 坐标, 文本)
                                items.append((y1, x0, text))
            elif isinstance(element, LTAnno):
                print("找到注释，跳过...")

            # if isinstance(element, LTTextContainer):
            #     for text_line in element:
            #         x0, y0, x1, y1 = text_line.bbox
            #         text = text_line.get_text().strip()
            #         if text:
            #             # 记录 (y 坐标, x 坐标, 文本)
            #             items.append((y1, x0, text))

        # 按 y 从高到底排序（上到下）
        items.sort(key=lambda i: -i[0])

        current_row_y = None
        current_row = []

        for y, x, text in items:
            if current_row_y is None or abs(current_row_y - y) > 5:
                # 保存上一行
                if current_row:
                    # 按 x 从大到小排序（右到左）
                    # current_row.sort(key=lambda i: -i[0])
                    rows.append([t for _, t in current_row])
                current_row = [(x, text)]
                current_row_y = y
            else:
                current_row.append((x, text))

        # 最后一行
        if current_row:
            current_row.sort(key=lambda i: -i[0])
            rows.append([t for _, t in current_row])

    return rows

