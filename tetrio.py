import requests

ranks = {
    "x+": 1,
    "x": 2,
    "u": 3,
    "ss": 4, 
    "s+": 5,
    "s": 6,
    "s-": 7,
    "a+": 8,
    "a": 9,
    "a-": 10,
    "b+": 11,
    "b": 12,
    "b-": 13,
    "c+": 14,
    "c": 15,
    "c-": 16,
    "d+": 17,
    "d": 18,
}

async def get_player_data(usr:str):
    headers = requests.utils.default_headers()
    headers["User-Agent"] = "Space Shuttle"
    data = requests.get(f"https://ch.tetr.io/api/users/{usr.lower()}/summaries/league", headers=headers)
    return data.json()

async def get_player_id(usr:str):
    headers = requests.utils.default_headers()
    headers["User-Agent"] = "Space Shuttle"
    data = requests.get(f"https://ch.tetr.io/api/users/{usr.lower()}", headers=headers)
    item = data.json()
    return item["data"]["_id"]