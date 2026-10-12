from pathlib import Path
from huggingface_hub import snapshot_download
if __name__ == '__main__':
    comfy = Path(__file__).resolve().parents[2]
    snapshot_download('Qwen/Qwen3-4B-Instruct-2507', revision='cdbee75f17c01a7cc42f958dc650907174af0554', local_dir=comfy/'models/LLM/Qwen3-4B-Instruct-2507', allow_patterns=['*.json','*.safetensors','*.txt','*.jinja','LICENSE','README.md'])
