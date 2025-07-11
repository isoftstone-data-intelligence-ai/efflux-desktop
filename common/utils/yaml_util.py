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

# 插入或修改某个键值对
def update_yaml_key(filename: str, key: str, value) -> None:
    # 加载现有的 YAML 数据
    yaml_data = load_yaml(filename)
    # 更新或插入键值对
    yaml_data[key] = value
    # 保存更新后的数据到文件
    save_yaml(filename, yaml_data)
