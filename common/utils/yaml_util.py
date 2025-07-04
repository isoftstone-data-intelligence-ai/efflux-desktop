import yaml
from typing import Dict
from common.utils.file_util import get_resource_path, check_file_and_create

# 读取 YAML 文件并解析为字典
def load_yaml(filename: str) -> Dict:
    with open(get_resource_path(filename), 'r') as file:
        return yaml.safe_load(file)

# 写入数据到 YAML 文件
def save_yaml(filename: str, data: Dict) -> None:
    check_file_and_create(get_resource_path(filename))
    with open(get_resource_path(filename), 'w', encoding='utf-8') as file:
        yaml.dump(data, file, default_flow_style=False, allow_unicode=True)

# 根据渠道获取模型类型，并将其保存在字典中
def get_model_types_by_channel(yaml_data: Dict) -> Dict:
    model_dict = {}

    # 遍历 YAML 数据中的每个渠道
    for channel, models in yaml_data.items():
        model_dict[channel] = models  # 将渠道的模型列表保存在字典中

    return model_dict