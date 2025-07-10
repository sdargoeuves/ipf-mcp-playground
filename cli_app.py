from agents import Agent, Runner, set_trace_processors
from agents.mcp import MCPServerStdio
from agents.extensions.models.litellm_model import LitellmModel
from langsmith.wrappers import OpenAIAgentsTracingProcessor
from langsmith import traceable
import asyncio
import dotenv
import os

dotenv.load_dotenv(dotenv.find_dotenv())

async def setup_agent():
    ipf_mcp_server = MCPServerStdio(
        name="IP Fabric Assistant MCP Server",
        params={
            "command": "uv",
            "args": ["run", "python","src/mcp_ipf/server.py"],
        },
        client_session_timeout_seconds=60,
    )
    await ipf_mcp_server.__aenter__()
    ipfabric_agent = Agent(
        name="IP Fabric Assistant",
        handoff_description="Specialist agent for network visibility and analysis using IP Fabric snapshots",
        instructions=(
            "You are an expert in interpreting IP Fabric snapshot data. "
            "Use the tools provided by the MCP server to answer network-related questions. "
            "You can list snapshots, devices, interfaces, VLANS, routes, BGP neighbors or perform basic visibility triage using point-in-time snapshot data. "
            "All your answers should reflect what's currently available in the specified snapshot, if not specified, use the latest snapshot. "
            "You can give insights using multiple snapshot data points. "
            "Do not fabricate data. If a tool does not return results, explain that clearly. "
            "Unless the user directly asks for a specific snapshot, always use the latest snapshot. You can use the tool set_snapshot to change the snapshot context for your answers. "
        ),
        mcp_servers=[ipf_mcp_server],
        model=LitellmModel(model=os.getenv("AI_MODEL", "gpt-4.0"), api_key=os.getenv("AI_API_KEY")),
    )
    return ipfabric_agent, ipf_mcp_server

async def chat_loop(agent):
    print("\nChat with the IP Fabric Agent (type 'exit' to quit):\n")
    while True:
        msg = input("You: ").strip()
        if msg.lower() in ["exit", "quit"]:
            break
        result = await Runner.run(starting_agent=agent, input=msg)
        print(f"Assistant: {result.final_output}\n")

# @traceable(name="ipf-mcp")
async def main():
    agent, mcp_server = await setup_agent()
    try:
        await chat_loop(agent)
    finally:
        await mcp_server.__aexit__(None, None, None)


if __name__ == "__main__":
    set_trace_processors([OpenAIAgentsTracingProcessor()])
    asyncio.run(main())
