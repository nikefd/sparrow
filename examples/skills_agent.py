"""Skills example — progressive disclosure.

A skill bundles a "when to use" line with instructions and tools that stay hidden
until the model activates the skill. Up front the model only sees the skill's
name + when; it must call ``activate_skill`` to unlock the rest. This keeps the
context small when you have many capabilities.

Run:
    export SPARROW_LLM_API_KEY=sk-...
    python examples/skills_agent.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sparrow import tool, AgentConfig, Agent, Skill


@tool(description="Compute compound interest", source="finance")
def compound_interest(principal: float, rate: float, years: int) -> dict:
    return {"result": round(principal * (1 + rate) ** years, 2)}


# The tool above is gated behind a skill: it won't appear in the model's tool
# list until it activates the "finance" skill.
finance_skill = Skill(
    name="finance",
    when="when the user asks about interest, savings growth, or investment returns",
    instructions="Use compound_interest for growth questions. Always state assumptions.",
    tools=["compound_interest"],
)

config = AgentConfig(
    system_prompt="You are a helpful assistant. Activate a skill when it fits the task.",
    tools=[compound_interest],
    skills=[finance_skill],
)


def main():
    msg = [{"role": "user", "content": "If I invest 1000 at 5% for 10 years, what do I get?"}]
    for event in Agent(config).run(msg):
        if event.type == "skill_activated":
            print(f"  ✦ activated skill: {event.data['name']}")
        elif event.type == "tool_call":
            print(f"  → {event.data['name']}({event.data['arguments']})")
        elif event.type == "final":
            print(f"\nAnswer: {event.data['content']}")


if __name__ == "__main__":
    main()
