"""Separate process so the writer's CUDA allocations die before H3 renders."""
import json
import sys
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

request_path, response_path, model_path = sys.argv[1:]
r = json.load(open(request_path))
torch.manual_seed(r['seed'])
tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True, trust_remote_code=False)
model = AutoModelForCausalLM.from_pretrained(model_path, local_files_only=True,
    trust_remote_code=False, torch_dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda')
inputs = tokenizer.apply_chat_template(r['messages'], tokenize=True, add_generation_prompt=True,
    return_dict=True, return_tensors='pt').to('cuda')
with torch.inference_mode():
    output = model.generate(**inputs, max_new_tokens=6500, do_sample=True,
        temperature=0.5, top_p=0.9, top_k=20, pad_token_id=tokenizer.eos_token_id)
text = tokenizer.decode(output[0, inputs['input_ids'].shape[-1]:], skip_special_tokens=True)
open(response_path, 'w').write(text)
