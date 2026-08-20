import json
import os
from datetime import datetime

BRAIN_DIR = "/Users/arunbalakrishnan/.gemini/antigravity/brain"

def extract_metrics(conv_id):
    transcript_path = os.path.join(BRAIN_DIR, conv_id, ".system_generated", "logs", "transcript_full.jsonl")
    if not os.path.exists(transcript_path):
        transcript_path = os.path.join(BRAIN_DIR, conv_id, ".system_generated", "logs", "transcript.jsonl")
        if not os.path.exists(transcript_path):
            return None

    total_chars = 0
    llm_steps = 0
    nested_subagents = []

    with open(transcript_path, 'r') as f:
        for line in f:
            try:
                data = json.loads(line)
            except:
                continue
            
            if data.get('source') == 'MODEL' or data.get('type') == 'PLANNER_RESPONSE':
                llm_steps += 1
                total_chars += len(line)

            if "Created the following subagents:" in line:
                parts = line.split('"conversationId":')
                for part in parts[1:]:
                    cid = part.split('"')[1]
                    nested_subagents.append(cid)

    tokens = total_chars // 4

    return {
        "llm_steps": llm_steps,
        "tokens": tokens,
        "subagents": nested_subagents
    }

def aggregate_metrics(root_id):
    metrics = extract_metrics(root_id)
    if not metrics:
        return None
    
    total_steps = metrics["llm_steps"]
    total_tokens = metrics["tokens"]

    for sub_id in metrics["subagents"]:
        sub_m = aggregate_metrics(sub_id)
        if sub_m:
            total_steps += sub_m["llm_steps"]
            total_tokens += sub_m["tokens"]
    
    return {
        "total_llm_steps": total_steps,
        "total_tokens": total_tokens,
        "agents_involved": 1 + len(metrics["subagents"])
    }

cells = {
    "Git Single Agent (Phase 2)": "385aefc5-cc3e-4be0-916b-8452ca0ce8f1",
    "Git Multi-Agent (Phase 2)": "1a440753-aee0-4159-9b98-90094999d5e8",
    "Nool Single Agent (Phase 2)": "c4762376-576e-4dab-888a-4478b87e7828",
    "Nool Multi-Agent (Phase 2)": "3cbb27d5-bd6f-4cee-a827-8432ba6b594c"
}

results = {}
for name, cid in cells.items():
    res = aggregate_metrics(cid)
    results[name] = res

print(json.dumps(results, indent=2))
