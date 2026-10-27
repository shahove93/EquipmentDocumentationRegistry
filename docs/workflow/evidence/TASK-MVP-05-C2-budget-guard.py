"""Local metadata-only C2 budget guard; no provider prompts or secret output."""
import json, pathlib, subprocess, time
base = pathlib.Path(r"D:/Antigravity/EquipmentDocumentationRegistry/docs/workflow/evidence")
rollout = pathlib.Path(r"C:/Users/user/.codex/sessions/2026/10/26/rollout-2026-10-26T16-54-35-01a1787d-d5be-78b0-9142-9dc30a8311a0.jsonl")
orca = r"C:/Users/user/AppData/Local/Programs/orca/resources/bin/orca.exe"
dispatch = "ctx_00fa3aee8c79"
stop_file = base / "TASK-MVP-05-C2-budget-guard.stop"
state_file = base / "TASK-MVP-05-C2-budget-guard.json"
checkpoint_sent = False
def call(args):
    p = subprocess.run([orca] + args + ["--json"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", creationflags=subprocess.CREATE_NO_WINDOW)
    return {"exit": p.returncode, "receipt": p.stdout[:14000]}
with rollout.open(encoding="utf-8") as stream:
    while not stop_file.exists():
        line = stream.readline()
        if not line:
            time.sleep(2)
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        p = row.get("payload", {})
        if row.get("type") != "event_msg" or p.get("type") != "token_count":
            continue
        usage = (p.get("info") or {}).get("total_token_usage") or {}
        count = usage.get("input_tokens", 0)
        snapshot = {"source": str(rollout), "observed_at": row.get("timestamp"),
                    "input": count, "cached_included": usage.get("cached_input_tokens"),
                    "checkpoint_sent": checkpoint_sent}
        if count >= 600000 and not checkpoint_sent:
            snapshot["checkpoint"] = call(["orchestration", "send", "--to", "dispatch:" + dispatch,
                "--subject", "C2 budget600k checkpoint: block new work",
                "--body", "Local native token metadata reached600k. STOP new edits/checks at this checkpoint and ask coordinator with actual progress. No silent continuation. Writer900k includes finalization; reviewer450k untouched. Guard will stop the exact writer around800k to protect before900k."])
            checkpoint_sent = True
        if count >= 800000:
            snapshot["budget_stop"] = call(["orchestration", "worker-stop", "--dispatch", dispatch])
            state_file.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({"guard": "budget_stop", "input": count}), flush=True)
            break
        state_file.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
print("budget guard ended", flush=True)