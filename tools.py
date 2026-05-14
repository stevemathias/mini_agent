"""
Tool implementations and schemas for the mini agent.

Add your own tools here:
  1. Write the Python function
  2. Add it to TOOL_FUNCTIONS
  3. Add its JSON schema to TOOL_SCHEMAS
"""

import datetime as _dt
from datetime import datetime
from pathlib import Path

_MCP_SERVER = str(Path(__file__).parent / "mcp_server.py")

_WORKSPACE = Path("workspace")


def _safe_path(relative_path: str) -> Path:
    target = (_WORKSPACE / relative_path).resolve()
    if not str(target).startswith(str(_WORKSPACE.resolve())):
        raise ValueError(f"path '{relative_path}' escapes the workspace")
    return target


# --- Implementations ---

def get_current_date() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def calculate(expression: str) -> str:
    # eval with empty builtins — safe enough for a demo, not for production
    _locals = {
        "datetime": _dt,
        "date": _dt.date,
        "timedelta": _dt.timedelta,
    }
    try:
        result = eval(expression, {"__builtins__": {}}, _locals)
        return str(result)
    except Exception as e:
        return f"Error: {e}"


def get_weather(city: str) -> str:
    import json
    import urllib.error
    import urllib.parse
    import urllib.request

    _WMO = {
        0: "clear sky",
        1: "mainly clear", 2: "partly cloudy", 3: "overcast",
        45: "fog", 48: "icy fog",
        51: "light drizzle", 53: "moderate drizzle", 55: "heavy drizzle",
        61: "slight rain", 63: "moderate rain", 65: "heavy rain",
        71: "slight snow", 73: "moderate snow", 75: "heavy snow", 77: "snow grains",
        80: "rain showers", 81: "moderate rain showers", 82: "heavy rain showers",
        85: "snow showers", 86: "heavy snow showers",
        95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with heavy hail",
    }

    geo_url = "https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(
        {"name": city, "count": 1, "language": "en", "format": "json"}
    )
    try:
        with urllib.request.urlopen(geo_url, timeout=10) as r:
            geo = json.loads(r.read())
    except Exception as e:
        return f"Error looking up '{city}': {e}"

    results = geo.get("results")
    if not results:
        return f"City '{city}' not found"

    loc = results[0]
    lat, lon = loc["latitude"], loc["longitude"]
    label = loc.get("name", city)
    if country := loc.get("country"):
        label = f"{label}, {country}"

    weather_url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(
        {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weathercode,windspeed_10m",
            "timezone": "auto",
        }
    )
    try:
        with urllib.request.urlopen(weather_url, timeout=10) as r:
            data = json.loads(r.read())
    except Exception as e:
        return f"Error fetching weather: {e}"

    c = data.get("current", {})
    condition = _WMO.get(c.get("weathercode", 0), f"code {c.get('weathercode')}")
    return (
        f"{label}: {c.get('temperature_2m')}°C"
        f" (feels like {c.get('apparent_temperature')}°C)"
        f", {condition}"
        f", {c.get('relative_humidity_2m')}% humidity"
        f", wind {c.get('windspeed_10m')} km/h"
    )


def read_file(path: str) -> str:
    try:
        return _safe_path(path).read_text()
    except FileNotFoundError:
        return f"Error: '{path}' not found in workspace"
    except ValueError as e:
        return f"Error: {e}"


def write_file(path: str, content: str) -> str:
    try:
        p = _safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"wrote {len(content)} chars to '{path}'"
    except ValueError as e:
        return f"Error: {e}"


def _import_call_mcp():
    try:
        from mcp_client import call_mcp
        return call_mcp
    except ImportError:
        raise RuntimeError("mcp package not installed — run: pip install mcp")


def mcp_to_uppercase(text: str) -> str:
    return _import_call_mcp()(_MCP_SERVER, "to_uppercase", text=text)


def mcp_count_words(text: str) -> int:
    return _import_call_mcp()(_MCP_SERVER, "count_words", text=text)


def web_search(query: str, count: int = 5) -> str:
    import json
    import os
    import urllib.error
    import urllib.parse
    import urllib.request

    api_key = os.environ.get("BRAVE_API_KEY")
    if not api_key:
        return "Error: BRAVE_API_KEY not set in environment"

    url = "https://api.search.brave.com/res/v1/web/search?" + urllib.parse.urlencode(
        {"q": query, "count": min(count, 10)}
    )
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "X-Subscription-Token": api_key},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return f"Error: Brave Search API returned {e.code} {e.reason}"
    except Exception as e:
        return f"Error: {e}"

    results = data.get("web", {}).get("results", [])
    if not results:
        return f"No results found for '{query}'"

    lines = [f"Search results for '{query}':\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        url = r.get("url", "")
        desc = r.get("description", "")
        lines.append(f"{i}. {title}\n   {url}\n   {desc}")
    return "\n".join(lines)


# --- Registry: name → callable ---

TOOL_FUNCTIONS: dict = {
    "get_current_date": get_current_date,
    "calculate": calculate,
    "get_weather": get_weather,
    "web_search": web_search,
    "read_file": read_file,
    "write_file": write_file,
    "to_uppercase": mcp_to_uppercase,
    "count_words": mcp_count_words,
}


# --- Schemas (OpenAI function-calling format) ---

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_current_date",
            "description": "Returns the current date and time.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Evaluates a mathematical expression and returns the result.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "A Python math expression, e.g. '2 ** 10' or '847 * 0.15'",
                    }
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Gets current weather for a city via Open-Meteo (temperature, conditions, humidity, wind).",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name, e.g. 'Tokyo'"}
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file in the workspace directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path inside workspace/, e.g. 'notes.txt'"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file in the workspace directory, creating it if it doesn't exist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path inside workspace/, e.g. 'output.txt'"},
                    "content": {"type": "string", "description": "Text content to write"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "to_uppercase",
            "description": "Convert text to uppercase. Runs via an MCP server subprocess.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to convert"}
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "count_words",
            "description": "Count the number of words in a string. Runs via an MCP server subprocess.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to count words in"}
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Searches the web via Brave Search and returns the top results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "count": {
                        "type": "integer",
                        "description": "Number of results to return (1–10, default 5)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
]


def call_tool(name: str, arguments: dict) -> str:
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return f"Unknown tool: '{name}'"
    try:
        return str(fn(**arguments))
    except Exception as e:
        return f"Tool '{name}' raised an error: {e}"
