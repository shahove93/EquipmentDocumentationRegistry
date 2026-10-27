"""Read-only native metadata observer: local alerts only; NO runtime mutations."""
import json, pathlib, time
base = pathlib.Path(r"D:/Antigravity/EquipmentDocumentationRegistry/docs/workflow/evidence")
source = pathlib.Path(r"C:/Users/user/.codex/sessions/2026/10/26/rollout-2026-10-26T17-23-26-01a17898-41af-7330-a918-0ae1d1531fd5.jsonl")
stop = base / "TASK-MVP-05-C2-call5-observer.stop"
target = base / "TASK-MVP-05-C2-call5-observer.json"
sent = False
with source.open(encoding="utf-8") as stream:
    while not stop.exists():
        line=stream.readline()
        if not line:
            time.sleep(2)
            continue
        try: row=json.loads(line)
        except ValueError: continue
        p=row.get("payload",{})
        if row.get("type")!="event_msg" or p.get("type")!="token_count": continue
        usage=(p.get("info") or {}).get("total_token_usage") or {}
        count=usage.get("input_tokens",0)
        state={"source":str(source),"observed_at":row.get("timestamp"),
               "input":count,"cached_included":usage.get("cached_input_tokens"),
               "checkpoint450k":count>=450000,"actions":"READ_ONLY_ALERT_ONLY"}
        target.write_text(json.dumps(state,indent=2),encoding="utf-8")
        if count>=450000 and not sent:
            print(json.dumps({"alert":"C2_RESUME_450K_CHECKPOINT","input":count}),flush=True)
            sent=True
print("read-only observer ended",flush=True)