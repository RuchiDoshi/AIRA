import asyncio
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

async def main():
    server_params = StdioServerParameters(
        command="python",
        args=["src/server.py"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("MCP connected!", flush=True)

            # Get tools
            tools_result = await session.list_tools()
            mcp_tools = tools_result.tools
            print(f"Loaded {len(mcp_tools)} tools: {[t.name for t in mcp_tools]}", flush=True)

            # Convert to Gemini format
            gemini_functions = [
                types.FunctionDeclaration(
                    name=t.name,
                    description=t.description or "",
                    parameters=t.inputSchema if t.inputSchema else {}
                )
                for t in mcp_tools
            ]
            gemini_tool_list = [types.Tool(function_declarations=gemini_functions)]

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
                        print(f"  [calling tool: {fc.name} with {dict(fc.args)}]", flush=True)
                        result = await session.call_tool(fc.name, dict(fc.args))
                        tool_results.append(types.Part(
                            function_response=types.FunctionResponse(
                                name=fc.name,
                                response={"result": str(result.content)}
                            )
                        ))
                    contents.append(types.Content(role="user", parts=tool_results))

            print("\nBio Arm Assistant (Gemini + MCP) — type 'quit' to exit\n", flush=True)
            while True:
                user_input = input("You: ").strip()
                if user_input.lower() in ("quit", "exit"):
                    break
                if not user_input:
                    continue
                answer = await ask(user_input)
                print(f"Assistant: {answer}\n", flush=True)

asyncio.run(main())