# from tools.flight_tool import search_flights
# from tools.tavily_tool import tavily_search
# from backend import run_travel_agent
# from test_mcp_client import get_all_tools,get_tavily_search_tool,tavily_search_agent
from rich import print
import asyncio
from mcp_client import get_all_tools
from mcp_client import flight_search_agent,tavily_search_agent,weather_agent,forecast_agent,extract_destination_from_query
# res = search_flights("Plan a 7 days Japan trip from Bangladesh")
# print(res)


# user_input = input("Enter travel request: ")

# response = run_travel_agent(
#     user_input=user_input,3
#     thread_id="test_user"
# )

# print("\nFINAL RESPONSE:\n")
# print(response["answer"])
if __name__ == "__main__":
    # query = input("Enter your query :")
    # result = asyncio.run(tavily_search_agent(query))
    # # print(result)
    # print(result[0]["text"]["results"][0].content)

    choice = input("Choose '1' for tavily_search or '2' for flight_search or '3' for weather_tool or '4' for forecast_tool :")

    if choice == '1':
        print("Tavily Search \n")
        query = input("Enter your query :")
        result = asyncio.run(tavily_search_agent(query))
        print(result)

    elif choice == '2':
        print("Flight Tool \n")
        query = input("Enter your query :")
        result = asyncio.run(flight_search_agent(query))
        print(result)

    elif choice == '3':
        print("Weather Tool \n")   
        query = input("Enter your query :")
        city = extract_destination_from_query(query)
        result = asyncio.run(weather_agent(city))
        print(result)

    else:
        print("Forecast Tool \n")   
        query = input("Enter your query :")
        city = extract_destination_from_query(query)
        result = asyncio.run(forecast_agent(city))
        print(result)


    # asyncio.run(get_all_tools())