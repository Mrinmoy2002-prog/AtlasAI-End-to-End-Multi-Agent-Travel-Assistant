import os 
import re 
import certifi
import airportsdata
import pycountry
import requests
from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# 1. ENVIRONMENT & SSL CONFIGURATION
# -----------------------------------------------------------------------------

# Load environment variables from a local .env file (e.g., AVIATIONSTACK_API_KEY)
load_dotenv()

# Force requests and Python to use Certifi's bundle of SSL certificates.
# This avoids SSL certificate verification errors when making HTTPS requests.
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

# Fetch the API key for AviationStack from the environment variables
API_KEY = os.getenv("AVIATIONSTACK_API_KEY")

# Set a default departure airport code (IATA) if the user only provides a destination.
# Default is 'DAC' (Dhaka, Bangladesh).
DEFAULT_ORIGIN_IATA = os.getenv("DEFAULT_ORIGIN_IATA", "DAC")

# Base URL endpoint for querying flight status from AviationStack
BASE_URL = "https://api.aviationstack.com/v1/flights"

# Load the local airport dataset keyed by IATA codes (e.g., 'JFK', 'LHR', 'DAC')
AIRPORTS = airportsdata.load("IATA")


# -----------------------------------------------------------------------------
# 2. LOOKUP DICTIONARIES FOR NICKNAMES, CITIES, AND MAIN AIRPORTS
# -----------------------------------------------------------------------------

# Map common country aliases, abbreviations, and informal names to standard 2-letter ISO country codes
COUNTRY_ALIASES = {
    "usa": "US",
    "u.s.a": "US",
    "u.s.": "US",
    "america": "US",
    "united states": "US",
    "uk": "GB",
    "u.k.": "GB",
    "britain": "GB",
    "england": "GB",
    "uae": "AE",
    "dubai": "AE",
    "south korea": "KR",
    "korea": "KR",
    "russia": "RU",
    "vietnam": "VN",
    "bangladesh": "BD",
    "india": "IN",
    "japan": "JP",
    "china": "CN",
    "singapore": "SG",
    "malaysia": "MY",
    "thailand": "TH",
    "indonesia": "ID",
    "nepal": "NP",
    "qatar": "QA",
    "saudi arabia": "SA",
    "turkey": "TR",
    "canada": "CA",
    "australia": "AU",
    "germany": "DE",
    "france": "FR",
    "italy": "IT",
    "spain": "ES",
}

# A default "main" international airport code for major countries
COUNTRY_MAIN_AIRPORT = {
    "BD": "DAC",
    "IN": "DEL",
    "JP": "NRT",
    "US": "JFK",
    "GB": "LHR",
    "AE": "DXB",
    "SG": "SIN",
    "MY": "KUL",
    "TH": "BKK",
    "ID": "CGK",
    "CN": "PEK",
    "KR": "ICN",
    "NP": "KTM",
    "QA": "DOH",
    "SA": "JED",
    "TR": "IST",
    "CA": "YYZ",
    "AU": "SYD",
    "DE": "FRA",
    "FR": "CDG",
    "IT": "FCO",
    "ES": "MAD",
}

# A mapping of common city names to their primary international airport IATA code
CITY_MAIN_AIRPORT = {
    "dhaka": "DAC",
    "delhi": "DEL",
    "new delhi": "DEL",
    "mumbai": "BOM",
    "kolkata": "CCU",
    "chennai": "MAA",
    "bangalore": "BLR",
    "bengaluru": "BLR",
    "tokyo": "NRT",
    "osaka": "KIX",
    "kyoto": "KIX",
    "new york": "JFK",
    "london": "LHR",
    "dubai": "DXB",
    "singapore": "SIN",
    "kuala lumpur": "KUL",
    "bangkok": "BKK",
    "doha": "DOH",
    "istanbul": "IST",
    "toronto": "YYZ",
    "sydney": "SYD",
    "paris": "CDG",
    "rome": "FCO",
    "madrid": "MAD",
    "frankfurt": "FRA",
}


# -----------------------------------------------------------------------------
# 3. HELPER FUNCTIONS FOR TEXT CLEANING & COUNTRY/AIRPORT MATCHING
# -----------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """
    Cleans raw user input by removing extra spaces, special characters, 
    and common non-location travel words (like 'flight', 'hotel', 'budget').
    """
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)  # Keep only letters, numbers, and spaces
    text = re.sub(r"\s+", " ", text)          # Collapse multiple spaces into one
    
    # List of noise words that don't help identify a location
    stop_words = [
        "flight", "flights", "ticket", "tickets", "trip", "travel",
        "plan", "complete", "days", "day", "including", "hotel",
        "hotels", "sightseeing", "under", "budget", "info", "information"
    ]
    words = [w for w in text.split() if w not in stop_words]
    return " ".join(words).strip()


def country_name_to_code(text: str):
    """
    Attempts to convert a text input (e.g. 'United States' or 'USA') 
    into a 2-letter country code (e.g. 'US').
    """
    text = clean_text(text)

    # 1. Direct match in our hardcoded aliases dictionary
    if text in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[text]

    # 2. Try looking up with the pycountry library
    try:
        country = pycountry.countries.lookup(text)
        return country.alpha_2
    except LookupError:
        pass

    # 3. Search if any valid country name exists inside the user's text
    for country in pycountry.countries:
        country_name = country.name.lower()
        if country_name in text:
            return country.alpha_2

    # 4. Search if any alias exists inside the text
    for alias, code in COUNTRY_ALIASES.items():
        if alias in text:
            return code

    return None


def airport_country_matches(airport: dict, country_code: str) -> bool:
    """
    Checks if a given airport dictionary record belongs to the specified 2-letter country code.
    """
    airport_country = str(airport.get("country", "")).upper().strip()

    # Direct match on 2-letter country code
    if airport_country == country_code:
        return True

    # Fallback check against full country name from pycountry
    try:
        country = pycountry.countries.get(alpha_2=country_code)
        if country and airport_country.lower() == country.name.lower():
            return True
    except Exception:
        pass

    return False


def get_best_airport_for_country(country_code: str):
    """
    Finds the single best airport IATA code for a given country.
    First checks our predefined dictionary, then scores remaining airports in that country.
    """
    # Check if we already have a preferred main airport configured for this country
    preferred = COUNTRY_MAIN_AIRPORT.get(country_code)
    if preferred and preferred in AIRPORTS:
        return preferred

    candidates = []

    # If no preferred airport exists, search all airports in the dataset and score them
    for iata, airport in AIRPORTS.items():
        if not iata:
            continue

        if airport_country_matches(airport, country_code):
            name = str(airport.get("name", "")).lower()
            city = str(airport.get("city", "")).lower()

            score = 0
            # Higher score given to large international hubs
            if "international" in name:
                score += 50
            if "intl" in name:
                score += 40
            if "capital" in name:
                score += 20
            if city:
                score += 5

            candidates.append((score, iata))

    if not candidates:
        return None

    # Return the highest-scoring airport IATA code
    candidates.sort(reverse=True)
    return candidates[0][1]


# -----------------------------------------------------------------------------
# 4. LOCATION RESOLUTION & ROUTE PARSING
# -----------------------------------------------------------------------------

def resolve_location_to_iata(location: str):
    """
    Takes any string (country, city, airport name, or IATA code) 
    and attempts to translate it into a valid 3-letter IATA code.
    """
    if not location:
        return None

    raw_location = location.strip()

    # 1. If it's already a 3-letter uppercase code, verify it exists in our airport list
    if re.fullmatch(r"[A-Za-z]{3}", raw_location):
        code = raw_location.upper()
        if code in AIRPORTS:
            return code

    location_clean = clean_text(raw_location)
    if not location_clean:
        return None

    # 2. Check if it matches a known city name in our map
    if location_clean in CITY_MAIN_AIRPORT:
        return CITY_MAIN_AIRPORT[location_clean]

    # 3. Check if it matches a known country
    country_code = country_name_to_code(location_clean)
    if country_code:
        airport = get_best_airport_for_country(country_code)
        if airport:
            return airport

    # 4. Fallback search: scan through all airport records to find city/name matches
    city_matches = []
    for iata, airport in AIRPORTS.items():
        city = str(airport.get("city", "")).lower().strip()
        name = str(airport.get("name", "")).lower().strip()

        score = 0
        if city == location_clean:
            score += 100
        elif location_clean in city:
            score += 70

        if location_clean in name:
            score += 50
        if "international" in name:
            score += 10

        if score > 0:
            city_matches.append((score, iata))

    # Pick the highest scoring airport match
    if city_matches:
        city_matches.sort(reverse=True)
        return city_matches[0][1]

    return None


def find_location_mentions(query: str):
    """
    Scans a natural language sentence and extracts any mentioned countries or cities.
    """
    q = query.lower()
    mentions = []

    # Check for country aliases in the prompt
    for alias in COUNTRY_ALIASES:
        if re.search(rf"\b{re.escape(alias)}\b", q):
            mentions.append(alias)

    # Check for full country names in the prompt
    for country in pycountry.countries:
        name = country.name.lower()
        if len(name) >= 4 and re.search(rf"\b{re.escape(name)}\b", q):
            mentions.append(name)

    # Check for city names in the prompt
    for city in CITY_MAIN_AIRPORT:
        if re.search(rf"\b{re.escape(city)}\b", q):
            mentions.append(city)

    # Deduplicate while preserving order of occurrence
    unique_mentions = []
    for item in mentions:
        if item not in unique_mentions:
            unique_mentions.append(item)

    return unique_mentions


def parse_route(query: str):
    """
    Extracts departure and arrival IATA codes from a query sentence.
    Returns a tuple: (departure_iata, arrival_iata).
    """
    q = query.strip()
    q_lower = q.lower()

    # 1. Global flights query (no filters)
    global_keywords = [
        "all country", "all countries", "global flight",
        "global flights", "all flight", "all flights",
        "worldwide flight", "worldwide flights",
    ]
    if any(keyword in q_lower for keyword in global_keywords):
        return None, None

    # 2. Extract explicit 3-letter IATA codes (e.g., "DAC to NRT")
    codes = re.findall(r"\b[A-Z]{3}\b", q)
    if len(codes) >= 2:
        dep = codes[0].upper()
        arr = codes[1].upper()
        return dep, arr

    # 3. Pattern matching: "from [ORIGIN] to [DESTINATION]"
    match = re.search(
        r"\bfrom\s+(.+?)\s+\bto\s+(.+?)(?:\s+(?:on|for|under|including|with|in|at)\b|[.!?]|$)",
        q_lower,
    )
    if match:
        dep_iata = resolve_location_to_iata(match.group(1))
        arr_iata = resolve_location_to_iata(match.group(2))
        return dep_iata, arr_iata

    # 4. Pattern matching: "to [DESTINATION] from [ORIGIN]"
    match = re.search(
        r"\bto\s+(.+?)\s+\bfrom\s+(.+?)(?:\s+(?:on|for|under|including|with|in|at)\b|[.!?]|$)",
        q_lower,
    )
    if match:
        arr_iata = resolve_location_to_iata(match.group(1))
        dep_iata = resolve_location_to_iata(match.group(2))
        return dep_iata, arr_iata

    # 5. Pattern matching: "flights from [ORIGIN]"
    match = re.search(r"\bfrom\s+(.+?)(?:[.!?]|$)", q_lower)
    if match:
        dep_iata = resolve_location_to_iata(match.group(1))
        return dep_iata, None

    # 6. Pattern matching: "flights to [DESTINATION]"
    match = re.search(r"\bto\s+(.+?)(?:[.!?]|$)", q_lower)
    if match:
        arr_iata = resolve_location_to_iata(match.group(2) if len(match.groups()) > 1 else match.group(1))
        return None, arr_iata

    # 7. Fallback: find any city/country mentions in sentence order
    mentions = find_location_mentions(q)

    # If two locations are mentioned, first is origin, second is destination
    if len(mentions) >= 2:
        dep_iata = resolve_location_to_iata(mentions[0])
        arr_iata = resolve_location_to_iata(mentions[1])
        return dep_iata, arr_iata

    # If only one location is mentioned, assume it's the destination and use default origin
    if len(mentions) == 1:
        arr_iata = resolve_location_to_iata(mentions[0])
        return DEFAULT_ORIGIN_IATA, arr_iata

    return None, None


# -----------------------------------------------------------------------------
# 5. RESPONSE FORMATTING & API EXECUTION
# -----------------------------------------------------------------------------

def format_flight(flight: dict):
    """
    Takes a raw JSON flight object from AviationStack and formats it into a human-readable text string.
    """
    airline = flight.get("airline", {}).get("name") or "Unknown airline"
    flight_number = flight.get("flight", {}).get("iata") or "Unknown flight number"
    status = flight.get("flight_status") or "Unknown"

    dep = flight.get("departure", {}) or {}
    arr = flight.get("arrival", {}) or {}

    dep_airport = dep.get("airport") or "Unknown departure airport"
    dep_iata = dep.get("iata") or "Unknown"
    dep_terminal = dep.get("terminal") or "N/A"
    dep_gate = dep.get("gate") or "N/A"
    dep_scheduled = dep.get("scheduled") or "Unknown"
    dep_delay = dep.get("delay")
    dep_delay_text = f"{dep_delay} minutes" if dep_delay is not None else "N/A"

    arr_airport = arr.get("airport") or "Unknown arrival airport"
    arr_iata = arr.get("iata") or "Unknown"
    arr_terminal = arr.get("terminal") or "N/A"
    arr_gate = arr.get("gate") or "N/A"
    arr_scheduled = arr.get("scheduled") or "Unknown"
    arr_delay = arr.get("delay")
    arr_delay_text = f"{arr_delay} minutes" if arr_delay is not None else "N/A"

    return f"""
Airline: {airline}
Flight: {flight_number}
Status: {status}

Departure:
- Airport: {dep_airport}
- IATA: {dep_iata}
- Terminal: {dep_terminal}
- Gate: {dep_gate}
- Scheduled: {dep_scheduled}
- Delay: {dep_delay_text}

Arrival:
- Airport: {arr_airport}
- IATA: {arr_iata}
- Terminal: {arr_terminal}
- Gate: {arr_gate}
- Scheduled: {arr_scheduled}
- Delay: {arr_delay_text}
""".strip()


def search_flights(query: str, limit: int = 10):
    """
    Main function: takes a query string, extracts origin/destination, 
    queries AviationStack API, and returns formatted flight data.
    """
    if not API_KEY:
        return (
            "Flight API error: AVIATIONSTACK_API_KEY is missing.\n"
            "Please add this in your .env file:\n"
            "AVIATIONSTACK_API_KEY=your_api_key_here"
        )

    # Extract departure and arrival IATA codes from the query
    dep_iata, arr_iata = parse_route(query)

    # Set up HTTP query parameters
    params = {
        "access_key": API_KEY,
        "limit": min(limit, 100),
    }

    if dep_iata:
        params["dep_iata"] = dep_iata
    if arr_iata:
        params["arr_iata"] = arr_iata

    # Call the AviationStack API
    try:
        response = requests.get(BASE_URL, params=params, timeout=30)
        data = response.json()
    except requests.exceptions.RequestException as e:
        return f"Flight API request failed: {e}"
    except ValueError:
        return "Flight API returned invalid JSON."

    # Handle API errors returned in JSON payload
    if "error" in data:
        error = data["error"]
        return (
            "Flight API error:\n"
            f"Code: {error.get('code', 'Unknown')}\n"
            f"Message: {error.get('message', 'Unknown error')}"
        )

    flight_data = data.get("data", [])

    # If no flights are returned
    if not flight_data:
        route_text = ""
        if dep_iata and arr_iata:
            route_text = f" for route {dep_iata} to {arr_iata}"
        elif dep_iata:
            route_text = f" from {dep_iata}"
        elif arr_iata:
            route_text = f" to {arr_iata}"

        return (
            f"No live flight data found{route_text}.\n\n"
            "Note: AviationStack provides live/status flight data, not ticket prices. "
            "For actual fare prices, use a flight-pricing API such as Amadeus."
        )

    # Construct the summary title based on extracted routes
    route_info = "Global live flights"
    if dep_iata and arr_iata:
        route_info = f"Live flights from {dep_iata} to {arr_iata}"
    elif dep_iata:
        route_info = f"Live flights from {dep_iata}"
    elif arr_iata:
        route_info = f"Live flights to {arr_iata}"

    # Format each individual flight result and join them together
    formatted_flights = [format_flight(flight) for flight in flight_data[:limit]]
    return f"{route_info}\n\n" + "\n\n---\n\n".join(formatted_flights)


# -----------------------------------------------------------------------------
# 6. SCRIPT ENTRY POINT (EXECUTION EXAMPLE)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # Test Case 1: Extract destination 'Japan' (NRT) and default origin 'Bangladesh' (DAC)
    print(search_flights("Plan a 7 days Japan trip from Bangladesh"))
    
    print("\n" + "=" * 80 + "\n")
    
    # Test Case 2: Worldwide search without route filtering
    print(search_flights("all country flight info"))