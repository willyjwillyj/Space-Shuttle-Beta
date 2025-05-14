import discord
from discord import app_commands
import db_interactions as db
import tetrio as tetrio
import challonge_util as challonge
import requests
from discord.app_commands import checks 
from discord.ext.commands import has_permissions

import csv
import os
from dotenv import load_dotenv
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
test_servers = [345648584907030539, 1364758407042826321, 1364774379396927518, 1364775095406694461]
async def get_textchannel(guild_id : int, channel_id : int) -> None | discord.TextChannel:
    return client.get_guild(guild_id).get_channel(channel_id)

async def log(guild_id : int, msg : str) -> None:
    channel = await db.get_logging_channel(guild_id)
    if channel is not None:
        channel = await get_textchannel(guild_id,channel)
        if channel is not None:
            await channel.send(content=msg)

async def add_role(guild_id : int, user_id : int, role_id : int) -> None:
    guild = client.get_guild(guild_id)
    user = guild.get_member(user_id)
    role = guild.get_role(role_id)
    if role is not None:
        await user.add_roles(role)

async def remove_role(guild_id : int, user_id : int, role_id : int) -> None:
    guild = client.get_guild(guild_id)
    user = guild.get_member(user_id)
    role = guild.get_role(role_id)
    if role is not None:
        await user.remove_roles(role)

class confirm_action_view(discord.ui.View):
    confirm_button = discord.ui.Button(label="Confirm",style=discord.ButtonStyle.success)
    abort_button = discord.ui.Button(label="Abort",style=discord.ButtonStyle.danger)
    async def success_callback(itx : discord.Interaction):
        await itx.response.edit_message(content="You clicked the confirm button, but no implementation was provided. This is an error message. Please report this error to the developer",view=discord.ui.View())
    confirm_button.callback = success_callback
    async def abort_callback(itx : discord.Interaction):
        await itx.response.edit_message(content="Aborted operation",view=discord.ui.View())
    abort_button.callback = abort_callback
    responded = False
    def __init__(self, itx : discord.Interaction, confirm_callback = None, abort_callback = None, *, timeout = 180,):
        super().__init__(timeout=timeout)
        self.itx = itx
        if confirm_callback is not None:
            self.confirm_button.callback = confirm_callback
        if abort_callback is not None:
            self.abort_button.callback = abort_callback
        self.add_item(self.confirm_button)
        self.add_item(self.abort_button)
    async def interaction_check(self,itx : discord.Interaction):
        self.responded = True
        return True
    async def on_timeout(self):
        if not self.responded:
            await self.itx.followup.send(content="This action has timed out. If you would like to try again, please enter the command again", view=discord.ui.View(),ephemeral=True)

async def register_for_tournament(itx : discord.Interaction, tournament_name : str):
    is_registered = await db.check_if_player_registered_for_tournament(itx.guild.id,itx.user.id,tournament_name)
    if is_registered:
        async def remove_player(itx : discord.Interaction, tournament_name : str, user_id : int, guild_id : int):
            await db.remove_from_tournament(guild_id,user_id,tournament_name)
            await itx.response.edit_message(content=f"Removed registration for {tournament_name}",view=discord.ui.View())
            await update_tournament_status(itx.guild_id)
            await log(itx.guild.id,f"player {itx.user.name} removed their registration for {tournament_name}")
            role = await db.get_tournament_role(itx.guild.id, tournament_name)
            await remove_role(itx.guild.id, itx.user.id, role)
        async def cancel_removal(itx : discord.Interaction):
            await itx.response.edit_message(content="Cancelled removal of registration",view=discord.ui.View())
        await itx.response.send_message(f"You are already registered for {tournament_name}. Would you like to remove your registration?",view=confirm_action_view(itx, lambda interaction,tournament_name=tournament_name,itx=itx : remove_player(interaction, tournament_name,itx.user.id,itx.guild.id), lambda interaction: cancel_removal(interaction)),ephemeral=True)
    else:
        is_tetrio = await db.is_tournament_tetrio(itx.guild.id, tournament_name)
        await itx.response.send_modal(registration_modal(itx.guild.id,is_tetrio,tournament_name, title=f"Register for {tournament_name}"))



class registration_modal(discord.ui.Modal):
    guild_id = 0
    is_tetrio = False
    tournament_name = "ERROR VALUE"
    label = "ERROR VALUE"
    def __init__(self, guild_id, is_tetrio, tournament_name, *, title = "", timeout = None, custom_id = "r_modal"):
        super().__init__(title=title, timeout=timeout, custom_id=custom_id)
        self.guild_id = guild_id
        self.is_tetrio = is_tetrio
        self.tournament_name = tournament_name
        self.label = "Enter your TETR.IO username" if self.is_tetrio else f"Enter your rating for {self.tournament_name}"
        self.name = discord.ui.TextInput(label=self.label)
        self.add_item(self.name)

    
    async def on_submit(self, itx : discord.Interaction):
        
        input = self.name.value
        if not self.is_tetrio:
            await db.insert_into_tournament(itx.user.id,itx.user.name,itx.guild.id,self.tournament_name,input)
            role = await db.get_tournament_role(itx.guild.id, self.tournament_name)
            await add_role(itx.guild.id, itx.user.id, role)
            await itx.response.send_message(f"Successfully registered for {self.tournament_name} with rating {input}",ephemeral=True)
            await log(itx.guild.id,f"Player {itx.user.name} registered for {self.tournament_name} with rating {input}")
            await update_tournament_status(itx.guild_id)
        else: 
            t_data = await tetrio.get_player_data(self.name.value)
            if t_data["success"] == False:
                if t_data["error"]["msg"] == "No such user! | Either you mistyped something, or the account no longer exists.":
                    await itx.response.send_message("Registration Failed: No such user! | Either you mistyped something, or the account no longer exists.", ephemeral=True)
                else:
                    await itx.response.send_message("Registration Failed: An unknown error occured. Please contact staff", ephemeral=True)
            elif t_data["data"]["tr"] == -1:
                await itx.response.send_message("Registration Failed: You must have a TR on TETR.IO to register for the tournament", ephemeral=True)
            else:
                caps = await db.get_floor_and_cap(itx.guild.id, self.tournament_name)
                if (caps[0] is not None or caps[1] is not None):
                    if t_data["data"]["rank"] == "z":
                        await itx.response.send_message("Registration Failed: You must have a letter rank in order to play in a capped or floored tournament", ephemeral=True)
                    else:
                        peak_rank = tetrio.ranks[t_data["data"]["bestrank"]]
                        if t_data["data"]["past"] is not None:
                            for i in t_data["data"]["past"]:
                                if t_data["data"]["past"][i]["bestrank"] is not None:
                                    peak_rank = min(peak_rank, tetrio.ranks[t_data["data"]["past"][i]["bestrank"]])
                        if(caps[0] is not None and peak_rank > tetrio.ranks[caps[0]]):
                            await itx.response.send_message("Registration Failed. Your peak rank is too low to play in this tournament", ephemeral=True)
                        elif(caps[1] is not None and peak_rank < tetrio.ranks[caps[1]]):
                            await itx.response.send_message("Registration Failed. Your peak rank is too high to play in this tournament", ephemeral=True)
                        else:
                            username = await tetrio.get_player_id(self.name.value)
                            rating = t_data["data"]["tr"]
                            await db.insert_into_tournament(itx.user.id,itx.user.name,itx.guild.id,self.tournament_name,rating,username)
                            await itx.response.send_message(f"Successfully registered for {self.tournament_name} under username {input}",ephemeral=True)
                            role = await db.get_tournament_role(itx.guild.id, self.tournament_name)
                            await add_role(itx.guild.id, itx.user.id, role)
                            await log(itx.guild.id,f"Player {itx.user.name} registered for {self.tournament_name} under username {input} with rating {rating}")
                            await update_tournament_status(itx.guild_id)

class registration_view(discord.ui.View):
    def __init__(self, guild_id, tournaments, *, timeout = None):
        super().__init__(timeout=timeout)
        for i in tournaments:
            button = discord.ui.Button(label=i)
            button.custom_id = f"{guild_id}-{i}"
            button.callback = lambda itx, i=i: register_for_tournament(itx, i)
            self.add_item(button)

        
    


@tree.command(
        name="create_tournament_generic",
        description="Create a generic tournament for your server",
)
@has_permissions(manage_roles=True)
async def create_tournament_generic(itx : discord.Interaction, tournament_name : str, thread_channel : discord.TextChannel=None, participant_role : discord.Role=None):
    user_id = itx.user.id
    guild_id = itx.guild.id
    thread_id = thread_channel.id if thread_channel is not None else None
    participant_id = participant_role.id if participant_role is not None else None
    tournament_exists = await db.check_if_tournament_exists(tournament_name=tournament_name, guild_id=guild_id)
    if(tournament_exists):
        await itx.response.send_message(f"Error in creating tournament. Tournament with name {tournament_name} already exists for this server.")
    else: 
        await db.insert_tournament(tournament_name=tournament_name, guild_id=guild_id, thread_channel=thread_id, participant_role=participant_id)
        res_string = f"Created tournament {tournament_name}.\n"
        if thread_channel is not None:
            res_string += f"Registered thread channel for tournament as <#{thread_channel.id}>\n"
        if participant_role is not None:
            res_string += f"Registered participant role as <@&{participant_role.id}>\n"
        await itx.response.send_message(res_string)


@tree.command(
        name="create_tournament_tetrio",
        description="Create a tetrio tournament for your server",
)
@has_permissions(manage_roles=True)
async def create_tournament_tetrio(itx : discord.Interaction, tournament_name : str, rank_cap : str=None, rank_floor : str=None ,thread_channel : discord.TextChannel=None, participant_role : discord.Role=None):
    user_id = itx.user.id
    guild_id = itx.guild.id
    thread_id = thread_channel.id if thread_channel is not None else None
    participant_id = participant_role.id if participant_role is not None else None
    rank_cap = rank_cap.lower() if rank_cap is not None else None
    rank_floor = rank_floor.lower() if rank_floor is not None else None
    tournament_exists = await db.check_if_tournament_exists(tournament_name=tournament_name, guild_id=guild_id)
    if(tournament_exists):
        await itx.response.send_message(f"Error in creating tournament. Tournament with name {tournament_name} already exists for this server.")
        return
    if rank_cap is not None:
        if rank_cap not in tetrio.ranks:
            await itx.response.send_message(f"Error in creating tournament. {rank_cap} is not a valid rank")
            return
    if rank_floor is not None:
        if rank_floor not in tetrio.ranks:
            await itx.response.send_message(f"Error in creating tournament. {rank_floor} is not a valid rank")
            return
    await db.insert_tournament(tournament_name=tournament_name, guild_id=guild_id, thread_channel=thread_id,participant_role=participant_id, is_tetrio=True, rank_cap=rank_cap ,rank_floor=rank_floor)
    res_string = f"Created tournament {tournament_name}.\n"
    if thread_channel is not None:
        res_string += f"Registered thread channel for tournament as <#{thread_channel.id}>\n"
    if participant_role is not None:
        res_string += f"Registered participant role as <@&{participant_role.id}>\n"
    if rank_cap is not None:
        res_string += f"Registered rank cap as {rank_cap}\n"
    if rank_floor is not None:
        res_string += f"Registered rank floor as {rank_floor}"
    await itx.response.send_message(res_string)

@tree.command(
        name="get_tournaments",
        description="Get all of the tournaments for your server",
)
@has_permissions(manage_roles=True)
async def get_tournaments(itx : discord.Interaction):
    tours = await db.get_tournaments_by_server(itx.guild.id)
    if not os.path.isdir(f"{itx.guild.id}"):
        os.mkdir(f"{itx.guild.id}")
    with open(f"{itx.guild.id}/tournaments.csv","w",newline='') as f:
        writer = csv.writer(f)
        
        writer.writerows(tours)
    await itx.response.send_message("Tournaments in this server:", file=discord.File(f"{itx.guild.id}/tournaments.csv"))

@tree.command(
        name="delete_tournament",
        description="Remove tournament from your server",
)
@has_permissions(manage_roles=True)
async def remove_tournament(itx : discord.Interaction, tournament_name : str):
    guild_id = itx.guild.id
    tournament_exists = await db.check_if_tournament_exists(tournament_name=tournament_name, guild_id=guild_id)
    if not tournament_exists:
        await itx.response.send_message(f"Error in deleting tournament. Tournament with name {tournament_name} doos not exist for this server.")
        return
    async def delete_tour(itx : discord.Interaction, tournament_name : str, guild_id : int):
        await db.remove_tournament(guild_id=guild_id,tournament_name=tournament_name)
        await itx.response.edit_message(content=f"Deleted tournament {tournament_name}",view=discord.ui.View())
    await itx.response.send_message(f"Delete tournament {tournament_name}?",view=confirm_action_view(itx,confirm_callback=lambda interaction,tournament_name=tournament_name,guild_id=guild_id: delete_tour(itx=interaction,tournament_name=tournament_name, guild_id=guild_id)))
    itx.followup
    pass

@tree.command(
        name="open_registration",
        description="open registrations for a tournament",
)
@has_permissions(manage_roles=True)
async def open_registration(itx : discord.Interaction, tournament_name : str):
    tournament_exists = await db.check_if_tournament_exists(tournament_name=tournament_name,guild_id=itx.guild.id)
    if not tournament_exists:
        await itx.response.send_message(f"Could not open registrations for tournament {tournament_name} because the tournament does not exist")
        return
    await db.set_tournament_registrations_state(itx.guild.id, tournament_name,True)
    await itx.response.send_message(f"Set registrations to open for tournament {tournament_name}. make sure to run /update_registrations to reflect changes")
    

@tree.command(
        name="close_registration",
        description="close registrations for a tournament",
)
@has_permissions(manage_roles=True)
async def close_registration(itx : discord.Interaction, tournament_name : str):
    tournament_exists = await db.check_if_tournament_exists(tournament_name=tournament_name,guild_id=itx.guild.id)
    if not tournament_exists:
        await itx.response.send_message(f"Could not close registrations for tournament {tournament_name} because the tournament does not exist")
        return
    await db.set_tournament_registrations_state(itx.guild.id, tournament_name,False)
    await itx.response.send_message(f"Set registrations to closed for tournament {tournament_name}. make sure to run /update_registrations to reflect changes")

@tree.command(
        name="set_thread_channel",
        description="set thread channel for a tournament",
)
@has_permissions(manage_roles=True)
async def set_thread_channel(itx : discord.Interaction, tournament_name : str, thread_channel : discord.TextChannel):
    pass

@tree.command(
        name="set_registration_channel",
        description="set registration channel for a server. This command will automatically create a registration message",
)
@has_permissions(manage_roles=True)
async def set_registration_channel(itx : discord.Interaction, registration_channel : discord.TextChannel):
    await db.configure_server_if_not_setup(itx.guild.id)
    await db.set_registration_channel(itx.guild.id, registration_channel.id)
    c1 = await registration_channel.send("INFO TEXT")
    c2 = await registration_channel.send("Register for a tournament by clicking one of the below tournaments")
    await db.set_registration_messages(itx.guild.id, c1.id, c2.id)
    await itx.response.send_message(f"Configured registration channel for this server as <#{registration_channel.id}>. Make sure to run /update_registrations to get registration buttons")

@tree.command(
        name="set_logging_channel",
        description="set logging channel for a server.",
)
@has_permissions(manage_roles=True)
async def set_logging_channel(itx : discord.Interaction, logging_channel : discord.TextChannel):
    await db.configure_server_if_not_setup(itx.guild.id)
    await db.set_logging_channel(itx.guild.id, logging_channel.id)
    await itx.response.send_message(f"Configured logging channel for this server as <#{logging_channel.id}>")

@tree.command(
        name="update_registrations",
        description="update registration messages to show new tournaments",
)
@has_permissions(manage_roles=True)
async def update_registrations(itx : discord.Interaction):
    ids = await db.get_registration_messages_info(itx.guild.id)
    text_channel = itx.guild.get_channel(ids[0])
    message = await text_channel.fetch_message(ids[1])
    tournaments = await db.get_open_tournaments(itx.guild.id)
    client.add_view(registration_view(itx.guild.id, tournaments),message_id=ids[1])
    await message.edit(content="Register for a tournament by clicking one of the below tournaments",view=registration_view(itx.guild.id, tournaments))
    await itx.response.send_message(f"Updated the registration message at <#{ids[0]}>")
    await update_tournament_status(itx.guild.id)

async def update_tournament_status(guild_id : int):
    guild = client.get_guild(guild_id)
    ids = await db.get_registration_messages_info(guild_id)
    text_channel = guild.get_channel(ids[0])
    message = await text_channel.fetch_message(ids[2])
    tournaments = await db.get_open_tournaments(guild_id)
    content = "### Current Open Tournaments:\n"
    for i in tournaments:
        participant_count = await db.get_participant_count(i)
        content += F"{i} - {participant_count} Registrations\n"
    await message.edit(content=content)

@tree.command(
        name="link_bracket",
        description="link a bracket to your tournament. You can link multiple brackets to the same tournament",
)
@has_permissions(manage_roles=True)
async def link_bracket(itx : discord.Interaction, bracket_url_string : str, tournament_name : str):
    pass

@tree.command(
        name="unlink_bracket",
        description="unlink a bracket from your tournament.",
)
@has_permissions(manage_roles=True)
async def unlink_bracket(itx : discord.Interaction, bracket_url_string : str, tournament_name : str):
    pass

@tree.command(
        name="list_brackets",
        description="list all of the brackets in the server",
)
@has_permissions(manage_roles=True)
async def list_brackets(itx : discord.Interaction):
    pass

@tree.command(
        name="activate_bracket",
        description="activate a bracket for challonge polling.",
)
@has_permissions(manage_roles=True)
async def activate_bracket(itx : discord.Interaction, bracket_url_string : str):
    pass

@tree.command(
        name="deactivate_bracket",
        description="deactivate a bracket for challonge polling.",
)
@has_permissions(manage_roles=True)
async def deactivate_bracket(itx : discord.Interaction, bracket_url_string : str):
    pass

@tree.command(
        name="export_participants",
        description="Export participants from a tournament, sorted by rating.",
)
@has_permissions(manage_roles=True)
async def export_participants(itx : discord.Interaction, tournament_name : str):
    pass

@tree.command(
        name="export_seeding_list",
        description="Export participants from a tournament, sorted by rating.",
)
@has_permissions(manage_roles=True)
async def export_seeding(itx : discord.Interaction, tournament_name : str):
    pass

@tree.command(
        name="refresh_seeding_tetrio",
        description="refresh seeding for TETR.IO Tournaments.",
)
@has_permissions(manage_roles=True)
async def update_seeding_tetrio(itx : discord.Interaction, tournament_name : str, remove_ineligible : bool=True):
    pass

@tree.command(
        name="get_checkins",
        description="get a list of checked in players ",
)
@has_permissions(manage_roles=True)
async def get_checkins(itx : discord.Interaction, tournament_name : str, checkin_channel : discord.TextChannel, checkin_message : int):
    pass

@tree.command(
        name="view_player_counts",
        description="Get player counts for all tournaments in the server.",
)
@has_permissions(manage_roles=True)
async def get_player_counts(itx : discord.Interaction):
    pass








#TODO: Implement routine to check all open brackets and see if they are able to be closed. If so, send a warning to the server's logging channel reminding them to close tournaments once they are finished.
#TODO: Implement routine to add new updated threads to the queue
#TODO: Implement routine to publish threads from the queue


@tree.command(
        name="admin_update_bracket_cap",
        description="ADMIN ONLY",
        guild=discord.Object(id=345648584907030539),
)
@checks.has_role(350379931978432513)
async def update_bracket_cap(itx : discord.Interaction,server_id:int, limit : int):
    if(itx.user.id == 317475187391987713):
        pass
@tree.command(
        name="admin_execute_dql",
        description="ADMIN ONLY",
        guild=discord.Object(id=345648584907030539),
)
@checks.has_role(350379931978432513)
async def execute_dql(itx : discord.Interaction,sql:str):
    if(itx.user.id == 317475187391987713):
        await db.execute_dql(sql)
        await itx.response.send_message("Executed DQL Query",file=discord.File("return.csv"))
@tree.command(
        name="admin_execute_dml",
        description="ADMIN ONLY",
        guild=discord.Object(id=345648584907030539),
)
@checks.has_role(350379931978432513)
async def execute_dml(itx : discord.Interaction,sql:str):
    if(itx.user.id == 317475187391987713):
        await db.execute_dml(sql)
        await itx.response.send_message("Executed DML query")

async def register_previous_views():
    guilds = await db.get_guilds()
    for i in guilds:
        tours = await db.get_open_tournaments(i)
        m_id = await db.get_registration_messages_info(i)
        client.add_view(registration_view(i,tours),message_id=m_id[1])
        



@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')
    await register_previous_views()
    print("views synced")
    await tree.sync()
    print("commands registered")
client.run(os.getenv("DISCORD_CLIENT_SECRET"))