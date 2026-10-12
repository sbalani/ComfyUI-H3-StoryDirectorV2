# ComfyUI-H3-StoryDirectorV2

Endangered AI custom nodes for native MiniMax H3 in ComfyUI.

## Installation

```sh
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/sbalani/ComfyUI-H3-StoryDirectorV2.git
cd ComfyUI-H3-StoryDirectorV2
/path/to/comfy-python -m pip install -r requirements.txt
```

Use the same Python/venv that launches ComfyUI, then restart ComfyUI and refresh the browser. Do not install a second PyTorch build.

Tested with ComfyUI 0.39.0. Story Director requires [Fantastic H3 PromptBuilder](https://github.com/Adudeguyman/ComfyUI-Fantastic-MiniMaxH3-PromptBuilder), the H3 models, FP16 video VAE, audio VAE and text encoder. For automatic story planning install Qwen/Qwen3-4B-Instruct-2507 under `ComfyUI/models/LLM/Qwen3-4B-Instruct-2507`; use `download_writer.py` with ComfyUI's Python. Edited-plan rendering does not require that writer. Model weights and user outputs are not distributed here.

[Usage guide](USER_GUIDE.md). Workflow downloads are distributed separately by Endangered AI; this repository contains the installable node source.

[Patreon](https://www.patreon.com/endangeredai) · [YouTube](https://www.youtube.com/@endangeredai) · [Website](https://endangeredai.com/)
