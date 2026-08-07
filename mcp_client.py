import os 
import sys
from pathlib import Path
import asyncio
import certifi
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
AVIATIONSTACK_API_KEY = os.getenv("AVIATIONSTACK_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

#Creating a llm
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=GROQ_API_KEY
)

WEATHER_SERVER_PATH = Path(__file__).parent / "custom_weather_mcp_server.py"
AVIATIONSTACK_SERVER_PATH = os.path.join(os.path.dirname(__file__), "aviationstack_mcp_server.py")

# Create a shared environment dictionary that preserves PATH and system variables
mcp_env = os.environ.copy()
if AVIATIONSTACK_API_KEY:
    mcp_env["AVIATIONSTACK_API_KEY"] = AVIATIONSTACK_API_KEY
# if OPENWEATHER_API_KEY:
#     mcp_env["OPENWEATHER_API_KEY"] = OPENWEATHER_API_KEY

client = MultiServerMCPClient(
    {
        "tavily": {
            "transport": "streamable_http",
            "url": (
                "https://mcp.tavily.com/mcp/"
                f"?tavilyApiKey={TAVILY_API_KEY}"
            )
        },

        "aviationstack": {
            "transport": "stdio",
            "command": sys.executable,  # Uses project's .venv python executable
            "args": [
                AVIATIONSTACK_SERVER_PATH
            ],
            "env": mcp_env
        },

        "weather": {
            "transport": "stdio",
            "command": sys.executable,  # Uses project's .venv python executable
            "args": [
                str(WEATHER_SERVER_PATH)
            ],
            "env": {
                "OPENWEATHER_API_KEY" : OPENWEATHER_API_KEY
            }  # Fixed: Now contains PATH and system environment variables
        }
    }
)

async def get_all_tools():
    tools = await client.get_tools()
    print("\n Available MCP Tools:\n")

    for tool in tools:
        print(f"- {tool.name}")


tavily_search_tool = None
flight_search_tool = None


async def initialize_mcp():
    global tavily_search_tool
    global flight_search_tool

    if tavily_search_tool is not None and flight_search_tool:
        return 

    tools = await client.get_tools()
    print("\n Available MCP Tools:\n")
    
    for tool in tools:
        print(tool.name)

    tavily_search_tool = next(tool for tool in tools if tool.name == "tavily_search")
    flight_search_tool = next(tool for tool in tools if tool.name == "search_flights")


async def tavily_search_agent(query : str):
    await initialize_mcp()
    result = await tavily_search_tool.ainvoke({"query": query})
    return result


async def flight_search_agent(query : str):
    await initialize_mcp()
    result = await flight_search_tool.ainvoke({"query": query})
    return result


# Functions regarding Weather Tool 
weather_tool = None
forecast_tool = None

async def initialize_weather_tools():
    global weather_tool
    global forecast_tool

    if weather_tool is not None and forecast_tool:
        return 

    tools = await client.get_tools()
    print("\n Available MCP Tools:\n")
    
    for tool in tools:
        print(tool.name)

    weather_tool = next(tool for tool in tools if tool.name == "get_current_weather")
    forecast_tool = next(tool for tool in tools if tool.name == "get_forecast")


async def weather_agent(city : str):
    await initialize_weather_tools()
    result = await weather_tool.ainvoke({"city": city})
    return result

async def forecast_agent(city : str):
    await initialize_weather_tools()
    result = await forecast_tool.ainvoke({"city": city})
    return result


def extract_destination_from_query(query:str):

    prompt = f"""
    Extract only the city from the rest sentence.

    Query:
    {query}

    Return only the city name.
    """

    response = llm.invoke(query)
    return response.content.strip()