from tools.flight_tool import search_flights
from tools.tavily_tool import tavily_search

res = search_flights("Plan a 7 days Japan trip from Bangladesh")
print(res)