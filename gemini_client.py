import asyncio
import os
from contextlib import AsyncExitStack
from dotenv import load_dotenv
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# Gemini rejects several JSON Schema fields that MCP includes by default.
# This recursively strips them before the schema is sent to the API.
_GEMINI_UNSUPPORTED = {"additional_properties", "additionalProperties", "$schema", "$defs", "default"}

def clean_schema(obj):
    if isinstance(obj, dict):
        return {k: clean_schema(v) for k, v in obj.items() if k not in _GEMINI_UNSUPPORTED}
    if isinstance(obj, list):
        return [clean_schema(v) for v in obj]
    return obj

SERVERS = [
    {"name": "enzyme",  "args": ["src/enzyme_server.py"]},
    {"name": "safety",  "args": ["src/safety_server.py"]},
]

async def main():
    async with AsyncExitStack() as stack:

        # Connect to all servers, collect sessions and tools
        sessions: dict[str, ClientSession] = {}
        tool_to_session: dict[str, ClientSession] = {}
        all_gemini_functions: list[types.FunctionDeclaration] = []

        for server in SERVERS:
            params = StdioServerParameters(command="python", args=server["args"])
            read, write = await stack.enter_async_context(stdio_client(params))
            session: ClientSession = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            tools_result = await session.list_tools()
            sessions[server["name"]] = session
            print(f"[{server['name']}] connected — {len(tools_result.tools)} tools: "
                  f"{[t.name for t in tools_result.tools]}", flush=True)

            for t in tools_result.tools:
                # Last-write wins if two servers share a name (shouldn't happen)
                tool_to_session[t.name] = session
                schema = clean_schema(t.inputSchema) if t.inputSchema else {}
                all_gemini_functions.append(
                    types.FunctionDeclaration(
                        name=t.name,
                        description=t.description or "",
                        parameters=schema
                    )
                )

        gemini_tool_list = [types.Tool(function_declarations=all_gemini_functions)]
        print(f"\nTotal tools loaded: {len(all_gemini_functions)}\n", flush=True)

        async def ask(question: str) -> str:
            contents = [types.Content(role="user", parts=[types.Part(text=question)])]
            while True:
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=contents,
                    config=types.GenerateContentConfig(tools=gemini_tool_list)
                )
                candidate = response.candidates[0].content
                contents.append(candidate)

                fn_calls = [p for p in candidate.parts if p.function_call]
                if not fn_calls:
                    return " ".join(p.text for p in candidate.parts if p.text)

                tool_results = []
                for part in fn_calls:
                    fc = part.function_call
                    session = tool_to_session.get(fc.name)
                    if session is None:
                        print(f"  [warning: no server found for tool '{fc.name}']", flush=True)
                        continue
                    print(f"  [calling tool: {fc.name} with {dict(fc.args)}]", flush=True)
                    result = await session.call_tool(fc.name, dict(fc.args))
                    tool_results.append(types.Part(
                        function_response=types.FunctionResponse(
                            name=fc.name,
                            response={"result": str(result.content)}
                        )
                    ))
                contents.append(types.Content(role="user", parts=tool_results))

        print("Bio Arm Assistant (Gemini + MCP) — type 'quit' to exit\n", flush=True)
        while True:
            user_input = input("You: ").strip()
            if user_input.lower() in ("quit", "exit"):
                break
            if not user_input:
                continue
            answer = await ask(user_input)
            print(f"Assistant: {answer}\n", flush=True)

asyncio.run(main())