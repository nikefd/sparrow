"""Approval + checkpoint/resume example — human in the loop.

Tools marked ``writes=True`` are routed through an approver before they run. When
the agent wants to call one, the run pauses (a checkpoint is persisted) and the
generator ends. You inspect the pending call, then ``resume`` once you have a
verdict — the run picks up exactly where it left off, even across a restart.

This example uses a sqlite checkpoint store and an auto-approver driven by a
callback, so it runs without interactive input.

Run:
    export SPARROW_LLM_API_KEY=sk-...
    python examples/approval_agent.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sparrow import tool, AgentConfig, Agent
from sparrow.adapters.sqlite_store import SqliteStore
from sparrow.adapters.auto_approver import AutoApprover
from sparrow.core.models import Decision


@tool(description="Delete a file by name", source="fs", writes=True)
def delete_file(name: str = "", conversation_id: str = "") -> dict:
    return {"ok": True, "deleted": name, "_summary": f"deleted {name}"}


# A policy that approves reads but would reject anything touching "prod".
def policy(call) -> Decision:
    if "prod" in str(call.arguments).lower():
        return Decision(verdict="reject", reason="never touch prod")
    return Decision(verdict="approve")


config = AgentConfig(
    system_prompt="You are a file assistant. Use tools to act on the user's request.",
    tools=[delete_file],
)


def main():
    store = SqliteStore(Path(tempfile.mkdtemp()) / "checkpoints.db")
    agent = Agent(config, store=store, approver=AutoApprover(policy=policy))

    msg = [{"role": "user", "content": "Please delete temp.log"}]
    run_id = None
    for event in agent.run(msg, run_id="demo-run"):
        if event.type == "awaiting_approval":
            run_id = event.data["run_id"]
            print(f"  ⏸ paused for approval: {event.data['call']['name']}"
                  f"({event.data['call']['arguments']})")
        elif event.type == "tool_result":
            print(f"  ← {event.data['summary']}")
        elif event.type == "final":
            print(f"\nAnswer: {event.data['content']}")

    # The run paused at the write tool. Resume it (the approver's policy decides).
    if run_id:
        print("  ▶ resuming after verdict…")
        for event in agent.resume(run_id):
            if event.type == "tool_result":
                print(f"  ← {event.data['summary']}")
            elif event.type == "final":
                print(f"\nAnswer: {event.data['content']}")


if __name__ == "__main__":
    main()
