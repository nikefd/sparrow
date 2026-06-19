"""Minimal end-to-end example: a weather agent in ~30 lines.

Run (needs an OpenAI-compatible key):
    export SPARROW_LLM_API_KEY=sk-...        # e.g. a DeepSeek key
    python examples/weather_agent.py

Shows the whole shape: define tools with @tool, assemble an AgentConfig, run the
Agent, and consume the event stream.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sparrow import tool, AgentConfig, Agent


# ── 1. Define tools (your domain) ────────────────────────────────────
@tool(description="Get current weather for a city", source="demo-weather")
def get_weather(city: str) -> dict:
    # A real tool would call an API; we fake it deterministically.
    fake = {"Beijing": "sunny, 24°C", "London": "rainy, 14°C"}
    return {"city": city, "weather": fake.get(city, "unknown")}


@tool(description="List cities we have weather data for", source="demo-weather")
def list_cities() -> dict:
    return {"cities": ["Beijing", "London"]}


# ── 2. Assemble config ───────────────────────────────────────────────
config = AgentConfig(
    system_prompt=(
        "You are a weather assistant. Always call a tool to get real data; "
        "never invent weather. Answer concisely."
    ),
    tools=[get_weather, list_cities],
)


# ── 3. Run and stream events ─────────────────────────────────────────
def main():
    messages = [{"role": "user", "content": "What's the weather in Beijing?"}]
    for event in Agent(config).run(messages):
        if event.type == "tool_call":
            print(f"  → calling {event.data['name']}({event.data['arguments']})")
        elif event.type == "tool_result":
            print(f"  ← {event.data['summary']}")
        elif event.type == "final":
            print(f"\nAnswer: {event.data['content']}")
            print(f"Sources: {event.data['citations']}")
        elif event.type == "error":
            print(f"Error: {event.data}")


if __name__ == "__main__":
    main()
