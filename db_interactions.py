import sqlite3
import pandas as pd

con = sqlite3.connect("registrations.db",autocommit=True)
cur = con.cursor()

cur.execute("CREATE TABLE IF NOT EXISTS registration(timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, discord_id BIGINT, discord_username VARCHAR(256), tournament_name VARCHAR(256), server_id BIGINT, game_username VARCHAR(256), challonge_id BIGINT, rating FLOAT)")
cur.execute("CREATE TABLE IF NOT EXISTS thread(timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, discord_id BIGINT, server_id BIGINT, challonge_match_id BIGINT, state VARCHAR(32), challonge_player1_id BIGINT, challonge_player2_id BIGINT, tournament_url VARCHAR(64))")
cur.execute("CREATE TABLE IF NOT EXISTS tournament(timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, tournament_name VARCHAR(128), thread_channel BIGINT, participant_role BIGINT, server_id BIGINT, registrations_open BOOLEAN, is_tetrio BOOLEAN, rank_cap VARCHAR(8), rank_floor VARCHAR(8))")
cur.execute("CREATE TABLE IF NOT EXISTS serverSetting(timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, server_id BIGINT, logging_channel BIGINT, registration_channel BIGINT, registration_info_id BIGINT, registration_id BIGINT, max_active_brackets INT DEFAULT 5)")
cur.execute("CREATE TABLE IF NOT EXISTS bracket(timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, tournament_url VARCHAR(256), tournament_name VARCHAR(128), server_id BIGINT, is_open BOOLEAN)")

cur.close()

async def execute_dql(sql):
    db_df = pd.read_sql_query(sql, con)
    db_df.to_csv('return.csv', index=False)
    
async def execute_dml(sql):
    cur = con.cursor()
    res = cur.execute(sql)
    cur.close()


async def check_if_tournament_exists(tournament_name : str, guild_id : int) -> bool:
    cur = con.cursor()
    res = cur.execute("SELECT COUNT(*) FROM tournament WHERE tournament_name = ? AND server_id = ?",(tournament_name, guild_id))
    data = res.fetchall()
    cur.close()
    print(data)
    return False if data[0][0] == 0 else True

async def insert_tournament(tournament_name : str, guild_id : int, thread_channel : int = None, is_tetrio : bool = False, rank_cap : str = None, rank_floor : str = None, participant_role : int = None) -> None:
    cur = con.cursor()
    cur.execute("INSERT INTO tournament (thread_channel, participant_role, tournament_name, server_id, registrations_open, is_tetrio, rank_cap, rank_floor) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (thread_channel, participant_role, tournament_name, guild_id, True, is_tetrio, rank_cap, rank_floor))
    cur.close()

async def get_tournaments_by_server(guild_id : int) -> list[list]:
    cur = con.cursor()
    res = cur.execute("SELECT * FROM tournament WHERE server_id = ? ORDER BY timestamp DESC",(guild_id,))
    col = [desc[0] for desc in cur.description]
    data = res.fetchall()
    data = [col] + data
    cur.close()
    return data
    
async def remove_tournament(guild_id: int, tournament_name: str) -> None:
    cur = con.cursor()
    cur.execute("DELETE FROM thread WHERE server_id = ? AND tournament_url in (SELECT tournament_url FROM bracket WHERE tournament_name = ? AND server_id = ?)",(guild_id,tournament_name,guild_id))
    cur.execute("DELETE FROM bracket WHERE server_id = ? AND tournament_name = ?",(guild_id,tournament_name))
    cur.execute("DELETE FROM registration WHERE server_id = ? AND tournament_name = ?",(guild_id,tournament_name))
    cur.execute("DELETE FROM tournament WHERE server_id = ? AND tournament_name = ?",(guild_id, tournament_name))
    cur.close()
    #TODO test that removing a tournament also removes records from the other tables so that the tournament namespace is properly restored to normal

async def set_tournament_registrations_state(guild_id: int, tournament_name : str, state : bool) -> None:
    cur = con.cursor()
    cur.execute("UPDATE tournament SET registrations_open = ? WHERE server_id = ? AND tournament_name = ?", (state, guild_id, tournament_name))
    cur.close()

async def configure_server_if_not_setup(guild_id : int) -> None:
    cur = con.cursor()
    res = cur.execute("SELECT COUNT(*) FROM serverSetting WHERE server_id = ?",(guild_id,))
    data = res.fetchall()
    if(data[0][0] == 0):
        cur.execute("INSERT INTO serverSetting (server_id) VALUES (?)",(guild_id,))
    cur.close()

async def set_logging_channel(guild_id : int, channel_id : int) -> None:
    cur = con.cursor()
    cur.execute("UPDATE serverSetting SET logging_channel = ? WHERE server_id = ?",(channel_id, guild_id))
    cur.close() 

async def set_registration_channel(guild_id : int, channel_id : int) -> None:
    cur = con.cursor()
    cur.execute("UPDATE serverSetting SET registration_channel = ? WHERE server_id = ?",(channel_id, guild_id))
    cur.close() 

async def set_registration_messages(guild_id : int, message_1_id : int, message_2_id) -> None:
    cur = con.cursor()
    cur.execute("UPDATE serverSetting SET registration_info_id = ?, registration_id = ? WHERE server_id = ?", (message_1_id, message_2_id, guild_id))
    cur.close() 

async def check_if_player_registered_for_tournament(guild_id : int, user_id : int, tournament_name : str) -> bool:
    cur = con.cursor()
    res = cur.execute("SELECT COUNT(*) FROM registration WHERE server_id = ? AND discord_id = ? AND tournament_name = ?",(guild_id,user_id,tournament_name))
    data = res.fetchall()
    cur.close()
    return False if data[0][0] == 0 else True

async def remove_from_tournament(guild_id : int, user_id : int, tournament_name : str) -> None:
    cur = con.cursor()
    res = cur.execute("DELETE FROM registration WHERE server_id = ? AND discord_id = ? AND tournament_name = ?",(guild_id,user_id,tournament_name))
    cur.close()

async def is_tournament_tetrio(guild_id : int, tournament_name : str) -> bool:
    cur = con.cursor()
    res = cur.execute("SELECT is_tetrio FROM tournament WHERE server_id = ? AND tournament_name = ?",(guild_id,tournament_name))
    data = res.fetchall()
    cur.close()
    return data[0][0]

async def get_logging_channel(guild_id : int) -> int:
    cur = con.cursor()
    res = cur.execute("SELECT logging_channel FROM serverSetting WHERE server_id = ?", (guild_id,))
    data = res.fetchall()
    cur.close()
    return data[0][0]

async def insert_into_tournament(discord_id : int, discord_username : str, server_id : int, tournament_name : str, rating : float, game_username : str = None) -> None:
    cur = con.cursor()
    cur.execute("INSERT INTO registration (discord_id, discord_username, server_id, tournament_name, rating, game_username) VALUES (?, ?, ?, ?, ?, ?)",(discord_id,discord_username,server_id,tournament_name,rating,game_username))
    cur.close()

async def get_floor_and_cap(guild_id : int, tournament_name : str) -> list[str, str]:
    cur = con.cursor()
    res = cur.execute("SELECT rank_floor, rank_cap FROM tournament WHERE server_id = ? AND tournament_name = ?",(guild_id, tournament_name))
    data = res.fetchall()
    cur.close()
    return data[0]

async def get_open_tournaments(guild_id : int) -> list[str]:
    cur = con.cursor()
    res = cur.execute("SELECT tournament_name FROM tournament WHERE server_id = ? AND registrations_open = TRUE",(guild_id,))
    data = res.fetchall()
    cur.close()
    out = []
    for i in data:
        out.append(i[0])
    return out

async def get_tournament_role(guild_id : int, tournament_name : str) -> str:
    cur = con.cursor()
    res = cur.execute("SELECT participant_role FROM tournament WHERE server_id = ? AND tournament_name = ?",(guild_id,tournament_name))
    data = res.fetchall()
    cur.close()
    print(data)
    return None if len(data) == 0 else data[0][0]

async def get_registration_messages_info(guild_id : int) -> list[int]:
    cur = con.cursor()
    res = cur.execute("SELECT registration_channel, registration_id, registration_info_id FROM serverSetting WHERE server_id = ?",(guild_id,))
    data = res.fetchall()
    cur.close()
    return data[0]

async def get_guilds() -> list[int]:
    cur = con.cursor()
    res = cur.execute("SELECT server_id FROM serverSetting")
    data = res.fetchall()
    cur.close()
    out = []
    for i in data:
        out.append(i[0])
    return out

async def get_participant_count(tournament_name : str) -> int:
    cur = con.cursor()
    res = cur.execute("SELECT COUNT(*) FROM registration WHERE tournament_name = ?",(tournament_name,))
    data = res.fetchall()
    cur.close()
    return data[0][0]