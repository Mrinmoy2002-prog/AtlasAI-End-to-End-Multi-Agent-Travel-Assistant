from tavily import TavilyClient
from dotenv import load_dotenv
import os
from rich import print

load_dotenv()

client  = TavilyClient(
    api_key=os.getenv("TAVILY_API_KEY")
)

def tavily_search(query:str):
    response = client.search(
        query=query,
        max_results=5
    )
    results = []

    for i,res in enumerate(response["results"],1):
        title = res.get("title","Unknown")
        url = res.get("url","")
        snippet = res.get("content","").strip()

        if len(snippet) > 300:
            snippet = snippet[:300].rsplit(" ",1)[0] + "..."

        results.append(f"{i}. **{title}**\n   {url}\n   {snippet}")

    return "\n\n".join(results)

