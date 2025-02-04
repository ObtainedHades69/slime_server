import discord, asyncio, shutil, os
from os.path import join
from discord.ext import commands, tasks
import bot_files.backend_functions as backend
from bot_files.backend_functions import send_command, format_args, server_status, lprint
from bot_files.extra import get_parameter, convert_to_bytes
import bot_files.components as components
import bot_files.slime_vars as slime_vars

ctx = 'server.py'
# ========== Server: autosave, Start/stop, Status, edit property, backup/restore.
class Server(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        if slime_vars.enable_autosave is True:
            self.autosave_task.start()
            lprint(ctx, f"Autosave task started (interval: {slime_vars.autosave_interval}m)")

    # ===== Servers, new, delete, editing, etc
    @commands.command(aliases=['select', 'sselect', 'selectserver', 'serverslist', 'ss', 'servers', 'listservers'])
    async def serverselect(self, ctx, *name):
        """
        Select server to use all other commands on. Each server has their own world_backups and server_restore folders.
        This command is also used to list available servers.

        Args:
            name: name of server to select, use ?selectserver list or without arguments to show list.

        Usage:
            ?selectserver list
            ?selectserver papermc
        """
        global slime_vars

        if 'bmode' in name:
            name = components.data('second_selected')
            if not name: return
        else: name = format_args(name)

        if not name and 'list' not in name:
            await ctx.send(f"**Current Server:** `{slime_vars.selected_server['server_name']}`")
            await ctx.send(f"Use `?serverselect list` or `?ss list` to list servers, and `?ss server_name` to switch.")
        elif 'list' in name:
            embed = discord.Embed(title='Server List :desktop:')
            for server, sdata in slime_vars.servers.items():
                # Shows server name, description, location, and Launch Command.
                embed.add_field(name=sdata['server_name'], value=f"Description: {sdata['server_description']}\nLocation: `{sdata['server_path']}`\nLaunch Command: `{sdata['server_launch_command']}`", inline=False)
            await ctx.send(embed=embed)
            await ctx.send(f"**Current Server:** `{slime_vars.selected_server['server_name']}`")
            await ctx.send(f"Use `?serverselect` to list, or `?ss [server]` to switch.")
        elif name in slime_vars.servers:
            if not slime_vars.enable_players_custom_status:
                await self.bot.change_presence(activity=discord.Activity(name=f"- {slime_vars.selected_server['server_name']}", type=1))
            slime_vars.selected_server = slime_vars.servers[name]
            slime_vars.config['bot_config']['selected_server'] = name
            slime_vars.update_vars(slime_vars.config)
            await ctx.send(f"**Selected Server:** {name}")
        else: await ctx.send("**ERROR:** Server not found.")

    @commands.command(aliases=['si'])
    async def serverinfo(self, ctx, *name):
        """Embed of server information."""
        global slime_vars

        server_name = get_parameter(name)

        # if get_parameter() returning bmode tuple, means no server was selected or server name given
        if 'bmode' in server_name:
            await ctx.send("No info to get.")
            return

        if server_name not in slime_vars.servers:
            # TODO simplify os isdir and join into function
            if os.path.isdir(join(slime_vars.servers_path, server_name)):
                await ctx.send("Server folder found, but no server configs.\nUse the Edit button to create a new config entry for it.")
                return
        data = slime_vars.servers[server_name]
        fields = [['Name', data['server_name']], ['server_description', data['server_description']], ['Launch Command', f"`{data['server_launch_command']}`"], ['Wait Time', data['startup_wait_time']]]
        await ctx.send(embed=components.new_embed(fields, 'Server Info'))
        await ctx.invoke(self.bot.get_command('_update_control_panel'), 'servers')

    @commands.command(hidden=True)
    async def servernew(self, ctx, interaction):
        """Create new server. Only works from control panel."""

        if interaction == 'submitted':
            await ctx.send("***Creating New Server...***")

            data_from_modal = components.data('servernew')
            new_server_name = data_from_modal['server_name']

            if new_server_name in slime_vars.servers:
                await ctx.send("Server name already used.")
                return

            # Tries to create new folder.
            if os.path.isdir(join(slime_vars.servers_path, new_server_name)):
                await ctx.send(f"Folder `{new_server_name}` already exists. Will create new servers entry in config.")
            else:
                try: backend.new_server(new_server_name)
                except:
                    await ctx.send("**Error**: Issue creating server.")
                    lprint(ctx, f"ERROR: Creating server: {new_server_name}")
                    return

            # Adds new server to servers dict.
            new_server = slime_vars.config['servers']['example'].copy()
            new_server.update(data_from_modal)
            # Updates server paths, replaces SELECTED_SERVER section in the paths with server name.
            new_server = backend.update_server_paths(new_server, new_server_name)
            # Adds server to config, then updates slime_vars globals so bot can use them without restart, then updates json.
            slime_vars.config['servers'][new_server_name] = new_server
            slime_vars.update_vars(slime_vars.config)
            await ctx.invoke(self.bot.get_command('serverinfo'), new_server_name)

            try: await ctx.invoke(self.bot.get_command('_update_control_panel'), 'servers')
            except: pass
            await ctx.send("Use `?selectserver` to use bot commands on new server.")

        else:
            modal_msg = await interaction.response.send_modal(components.new_modal(components.server_modal_fields('example'), 'New Server', 'servernew'))

    @commands.command(hidden=True)
    async def serveredit(self, ctx, interaction):
        """Edit server information. Updates servers.csv file."""

        # This only works with control panel right. This gets selected server's name.
        server_name = components.data('second_selected')
        if not server_name:
            await ctx.send("No server selected.")
            return
        if interaction == 'submitted':
            new_data = components.data('serveredit')

            server_path = join(slime_vars.servers_path, server_name)
            new_path = join(slime_vars.servers_path, new_data['server_name'])
            # Renames folder if name changed
            try: os.rename(server_path, new_path)
            except:
                await ctx.send("Server name already in use.")
                lprint(ctx, f"ERROR: Editing server info {server_path} > {new_path}")
                return
            await ctx.send("***Updating Server Info...***")

            example_server = slime_vars.servers['example'].copy()
            # Pops current server data, then updates it with new data.
            # Using .pop() so it effectively acts like deleting a server and then adding a new one.
            # Because if user changes the server name, it will create a new server but won't delete the old.
            to_replace = server_name  # Part of server paths to replace with new name
            if server_name in slime_vars.servers:
                server_data = slime_vars.config['servers'].pop(server_name)
            else:
                server_data = example_server
                to_replace = None  # If using example server, will replace SELECTED_SERVER text with server name
            server_data.update(new_data)
            # Updates old paths by finding and replacing server name in path
            server_data = backend.update_server_paths(server_data, server_name, to_replace)
            # Adds server and updates slime_vars globals and json file
            slime_vars.config['servers'][server_name] = server_data
            slime_vars.update_vars(slime_vars.config)

            await ctx.invoke(self.bot.get_command('serverinfo'), new_data['server_name'])
            lprint(ctx, f"Edited server info {server_path} > {new_path}")

            try: await ctx.invoke(self.bot.get_command('_update_control_panel'), 'servers')
            except: pass
        else:  # Sends modal dialog to input info
            # Creates server config if not exist. NOTE: Does not update json file unless modal is submitted and accepted.
            if server_name not in slime_vars.servers:
                slime_vars.servers[server_name] = slime_vars.servers['example'].copy()
                slime_vars.servers[server_name]['server_name'] = server_name

            modal_msg = await interaction.response.send_modal(components.new_modal(components.server_modal_fields(server_name), 'New Server', 'serveredit'))

    @commands.command(hidden=True)
    async def servercopy(self, ctx, interaction):
        """Copy server. Only works from control panel for now."""

        server_name = components.data('second_selected')

        if not server_name:
            await ctx.send("No server selected.")
            return

        if interaction == 'submitted':
            new_data = components.data('servercopy')

            # If server name already in use
            if new_data['server_name'] in slime_vars.servers:
                await ctx.send("Server name already used.")
                return

            await ctx.send("***Copying Server...***")
            server_path = join(slime_vars.servers_path, server_name)
            new_path = join(slime_vars.servers_path, new_data['server_name'])
            try: shutil.copytree(server_path, new_path)
            except:
                await ctx.send("**Error:** Issue copying server.")
                lprint(ctx, f"ERROR: Issue copying server: {server_path} > {new_path}")
                return

            # Makes a copy of default configs, then updates them with user input
            server_data = slime_vars.servers['example'].copy()
            server_data.update(new_data)
            # Adds new server then updates slime_vars globals and json file.
            slime_vars.config['servers'][new_data['server_name']] = new_data
            slime_vars.update_vars(slime_vars.config)

            await ctx.invoke(self.bot.get_command('serverinfo'), new_data['server_name'])
            lprint(ctx, f"ERROR: Copied server: {server_path} > {new_path}")

            try: await ctx.invoke(self.bot.get_command('_update_control_panel'), 'servers')
            except: pass
        else:
            modal_msg = await interaction.response.send_modal(components.new_modal(components.server_modal_fields(server_name), 'Copy Server', 'servercopy'))

    @commands.command(aliases=['sd', 'deleteserver'])
    async def serverdelete(self, ctx, *name):
        """
        Delete a server.

        Args:
            name: Server to delete. Case sensitive!

        Usage:
            ?serverdelete papermc
            ?sd valhesia 3
        """

        server_name = get_parameter(name)
        if not server_name:
            await ctx.send("No server selected.")
            return
        to_delete = join(slime_vars.servers_path, server_name)

        await ctx.send("***Deleting Server...***")
        try: backend.delete_dir(to_delete)
        except:
            if 'bmode' in to_delete: return False
            await ctx.send(f"**Error:** Issue deleting server: `{to_delete}`")
            return False

        try: slime_vars.servers.pop('server_name')
        except: pass

        await ctx.send(f"**Server Deleted:** `{to_delete}`")
        lprint(ctx, "Deleted server: " + to_delete)
        if server_name in slime_vars.servers:
            slime_vars.config['servers'].pop(server_name)
            slime_vars.update_vars(slime_vars.config)
        if 'bmode' in name:
            try: await ctx.invoke(self.bot.get_command('_update_control_panel'), 'servers')
            except: pass

    @commands.command(aliases=['sscan'])
    async def serverscan(self, ctx, *name):
        """
        Check if new serer folder has been added.

        Usage:
            ?serverscan
            ?sscan
        """

        global slime_vars
        new_servers_found = False
        example_server = slime_vars.config['servers']['example'].copy()

        await ctx.send("***Scanning for new servers...***")
        for folder in os.listdir(slime_vars.servers_path):
            # Checks if server already in 'slime_vars.servers' dict, and if 'folder' is actually a folder.
            if folder not in slime_vars.servers.keys() and os.path.isdir(join(slime_vars.servers_path, folder)):
                # Will update server server_name and file paths.
                slime_vars.config['servers'][folder] = backend.update_server_paths(example_server.copy(), folder)
                slime_vars.update_vars(slime_vars.config)  # Updates global vars and json file

                await ctx.send(f"**added:** `{folder}`")
                lprint(ctx, f"INFO: Added server: {folder}")
                new_servers_found = True

        if not new_servers_found: await ctx.send("No new servers found.")
        else:
            await ctx.invoke(self.bot.get_command('serverselect'))  # Shows all servers in Discord embed
            slime_vars.update_vars(slime_vars.config)

    # ===== Version
    @commands.command(aliases=['lversion', 'lver', 'lv'])
    async def latestversion(self, ctx):
        """Gets latest Minecraft server version number from official website."""

        response = backend.check_latest()
        await ctx.send(f"Latest version: `{response}`")
        lprint(ctx, "Fetched latest Minecraft server version: " + response)

    @commands.command(aliases=['updateserver', 'su', 'update'])
    async def serverupdate(self, ctx, now=''):
        """
        Updates server.jar file by downloading latest from official Minecraft website.

        Args:
            now optional: Stops server immediately without giving online players 15s warning.

        Usage:
            ?serverupdate
            ?su now

        Note: This will not make a backup beforehand, suggest doing so with ?serverbackup command.
        """

        lprint(ctx, f"Updating {slime_vars.selected_server['server_name']}...")
        await ctx.send(f"***Updating {slime_vars.selected_server['server_name']}...*** :arrows_counterclockwise:")

        # Halts server if running.
        if await server_status() is not False:
            await ctx.invoke(self.bot.get_command('serverstop'), now=now)
        await asyncio.sleep(5)

        await ctx.send(f"***Downloading latest server jar***")
        version, url = backend.download_latest()  # Updates server.jar file.
        if version:
            await ctx.send(f"Version: `{version}`\nSource: `{url}`\nNOTE: Next launch may take longer than usual.")
            await asyncio.sleep(3)
        else: await ctx.send("**ERROR:** Updating server failed. Possible incompatibility.\nSuggest restoring from a backup if updating corrupted any files.")
        lprint(ctx, "Server Updated")

    # ===== Save/Autosave
    @commands.command(aliases=['sa', 'save-all'])
    async def saveall(self, ctx):
        """Save current world using server save-all command."""

        if not await send_command('save-all'): return

        await ctx.send("World Saved  :floppy_disk:")
        await ctx.send("**NOTE:** This is not the same as making a backup using `?backup`.")
        lprint(ctx, "Saved World")

    @commands.command()
    async def autosaveon(self, ctx):
        """Enables autosave."""

        await ctx.invoke(self.bot.get_command('autosave'), arg='on')

    @commands.command()
    async def autosaveoff(self, ctx):
        """Disables autosave."""

        await ctx.invoke(self.bot.get_command('autosave'), arg='off')

    @commands.command(aliases=['asave'])
    async def autosave(self, ctx, arg=''):
        """
        Sends save-all command at interval of x minutes.

        Args:
            arg optional: turn on/off autosave, or set interval in minutes.

        Usage:
            ?autosave - Shows current state
            ?autosave on
            ?autosave 60 - will send 'save-all' command to server every 60min.
        """

        if not arg: await ctx.send(f"Usage: Update interval(min) `?autosave 60`, activate `?autosave on`.")

        # Parses user input and sets invertal for autosave.
        try: arg = int(arg)
        except: pass
        else:
            slime_vars.autosave_interval = arg

        # Enables/disables autosave tasks.loop(). Also edits slime_vars.py file, so autosave state can be saved on bot restarts.
        arg = str(arg)
        if arg.lower() in backend.enable_inputs:
            # Starts loop, updates enable_autosave, edits slime_vars.py, output to log
            self.autosave_task.start()
            slime_vars.enable_autosave = True
            lprint(ctx, f'Autosave: Enabled (interval: {slime_vars.autosave_interval}m)')
        elif arg.lower() in backend.disable_inputs:
            self.autosave_task.cancel()
            slime_vars.enable_autosave = False
            lprint(ctx, 'Autosave: Disabled')

        slime_vars.update_vars(slime_vars.config)
        status_msg = ':red_circle: **DISABLED** '
        if not await server_status(): status_msg = ":pause_button: **PAUSED**"
        elif slime_vars.enable_autosave: status_msg = ':green_circle: **ENABLED**'

        fields = [['Status', f"{status_msg} | **{slime_vars.autosave_interval}**min"],
                  ['Note', 'Auto save pauses if server unreachable (not same as disabled). Update server status with `?check` or `?stats`.']]
        await ctx.send(embed=components.new_embed(fields, 'Autosave :repeat::floppy_disk:'))
        lprint(ctx, 'Fetched autosave information')

    @tasks.loop(seconds=slime_vars.autosave_interval * 60)
    async def autosave_task(self):
        """Automatically sends save-all command to server at interval of x minutes."""

        await self.bot.wait_until_ready()
        # Will only send command if server is active. use ?check or ?stats to update server_active boolean so this can work.
        if await send_command('save-all', discord_msg=False):
            lprint(ctx, f"Autosaved (interval: {slime_vars.autosave_interval}m)")

    # ===== Status/Info
    @commands.command(aliases=['pingserver', 'ping'])
    async def serverping(self, ctx):
        """Uses ping command to see if server_address is reachable."""

        await ctx.send('***Pinging Server...***')
        response = backend.ping_address()
        await ctx.send(response)

    @commands.command(aliases=['check', 'checkstatus', 'statuscheck', 'active', 'refresh'])
    async def servercheck(self, ctx):
        """Checks if server is online."""

        await ctx.send('***Checking Server Status...***')
        response = await backend.server_status()
        if response:
            await ctx.send("**Server ACTIVE** :green_circle:")
        elif response is None:
            await ctx.send("**ERROR:** Unable to check server status.")
        else: await ctx.send("**Server INACTIVE** :red_circle:")

    @commands.command(aliases=['stat', 'stats', 'status', 'info'])
    async def serverstatus(self, ctx):
        """Shows server active status, version, motd, and online players"""

        sstatus = await server_status()
        if sstatus is True: status = '**ACTIVE** :green_circle:'
        elif sstatus is False: status = '**INACTIVE** :red_circle:'
        else: status = 'N/A'
        fields = [['Current Server', f"Status: {status}\nServer: {slime_vars.server_name}\nDescription: {slime_vars.server_description}\nVersion: {backend.server_version()}\nMOTD: {backend.server_motd()}"],
                  ['Autosave', f"{'Enabled' if slime_vars.enable_autosave is True else 'Disabled'} ({slime_vars.autosave_interval}min)"],
                  ['Address', f"URL: ||`{slime_vars.server_address}`|| ({backend.ping_address()})\nIP: ||`{backend.get_public_ip()}`|| (Use if URL inactive)"],
                  ['Location', f"`{slime_vars.server_path}`"],
                  ['Launch Command', f"`{slime_vars.server_launch_command}`"]]
        await ctx.send(embed=components.new_embed(fields, 'Server Status'))

        if status is not False:  # Only fetches players list if server online.
            await ctx.invoke(self.bot.get_command('players'))
        await ctx.invoke(self.bot.get_command('bannermsg'))
        lprint(ctx, "Fetched server status")

    @commands.command(aliases=['log', 'mlog'])
    async def serverlog(self, ctx, lines=10, match=None):
        """
        Show server log.

        Args:
            lines optional default(5): How many latest lines to show or how many matches to show if using 'match' argument.
            match optional: Filter lines, only show lines containing this. Must provide lines argument if using this one.

        Usage:
            ?serverlog - Defaults ot showing 5 lines
            ?log 10
            ?log 10 my coordinates - Gets 10 most recent lines containing 'my coordinates'.

        Note: When using the match argument, like '?log 5 hello', this doesn't mean it'll get the latest 5 lines and check
        if those lines contains 'hello'. Instead, it'll keep going through 'latest.log' until it finds 5 matches (or until the file ends).
        """

        # If received match argument, switches server_log mode.
        filter_mode, log_mode = False, True
        if match: filter_mode, log_mode = True, False

        await ctx.send(f"***Fetching {lines} Minecraft Log...*** :tools:")
        log_data = backend.server_log(match=match, file_path=slime_vars.server_log_filepath, lines=lines, log_mode=log_mode, filter_mode=filter_mode, return_reversed=True)
        if log_data:
            await ctx.send(file=discord.File(convert_to_bytes(log_data), 'server.log'))
            lprint(ctx, f"Fetched Minecraft Log: {lines}")
        else:
            await ctx.send("**Error:** Problem fetching data.")
            lprint(ctx, "ERROR: Issue getting minecraft log data")

    @commands.command(aliases=['sclog', 'connectionlog', 'connectionslog', 'serverconnectionlog', 'joinedlog', 'loginlog'])
    async def serverconnectionslog(self, ctx, lines=5):
        """
        Shows log lines relating to connections (joining, disconnects, kicks, etc).

        Args:
            lines optional default(5): Number of lines to show.

        Usage:
            ?clogs - Shows recent 5 lines
            ?clogs 10
        """

        await ctx.send(f"***Fetching {lines} Connection Log...*** :satellite:")

        match_list = ['joined the game', 'logged in with entity id', 'left the game', 'lost connection:', 'Kicked by an operator', ]
        # Get only log lines that are connection related.
        log_data = backend.server_log(match_list=match_list, lines=lines, filter_mode=True, return_reversed=True)
        if not log_data:
            await ctx.send("**ERROR:** Could not get chat log.")
            return

        await ctx.send(file=discord.File(convert_to_bytes(log_data), 'connections_log.log'))
        lprint(ctx, f"Fetched Connection Log: {lines}")

    @commands.command(aliases=['minecraftversion', 'mversion', 'version'])
    async def serverversion(self, ctx):
        """Gets Minecraft server version."""

        response = backend.server_version()
        await ctx.send(f"Current version: `{response}`")
        lprint(ctx, "Fetched Minecraft server version: " + response)

    # === Properties
    @commands.command(aliases=['property', 'pr'])
    async def properties(self, ctx, target_property='', *value):
        """
        Check or change a server.properties property. May require restart.

        Args:
            target_property: Target property to change, must be exact in casing and spelling and some may include a dash -.
            value optional: New value. For some properties you will need to input a lowercase true or false, and for others you may input a string (quotes not needed).

        Usage:
            ?property motd - Shows current value for 'motd'
            ?pr spawn-protection 2 - Updates 'spawn-protection' value to 2
            ?property all, ?pa - Shows all properties.

        Note: Passing in 'all' for target property argument (with nothing for value argument) will show all the properties.
        """

        if not target_property:
            await ctx.send("Usage: `?property <property_name> [new_value]`\nExample: `?property motd`, `?p motd Hello World!`\n"
                           "Show all properties using `?properties all` or `?pa`")
            return False

        if 'all' in target_property:
            await ctx.invoke(self.bot.get_command('propertiesall'))

        if value:
            await ctx.send("Property Updated  :memo:")
            value = ' '.join(value)
        else: value = ''

        backend.edit_file(target_property, value)
        fetched_property = backend.edit_file(target_property)
        await asyncio.sleep(2)

        if fetched_property:
            await ctx.send(f"`{fetched_property[0].strip()}`")
            lprint(ctx, f"Server property: {fetched_property[0].strip()}")
        else:
            await ctx.send(f"**ERROR:** 404 Property not found.")
            lprint(ctx, f"Server property not found: {target_property}")

    @commands.command(aliases=['pa', 'prall'])
    async def propertiesall(self, ctx):
        """Shows full server properties file."""
        global slime_vars

        if not os.path.isfile(slime_vars.server_properties_filepath):
            await ctx.send('**ERROR:** Could not get server properties file')
            return
        with open(slime_vars.server_properties_filepath, 'rb') as f:
            await ctx.send(file=discord.File(f, slime_vars.server_properties_filepath))

        #await ctx.invoke(self.bot.get_command('properties'), target_property='all')

    @commands.command(aliases=['serveronlinemode', 'omode', 'om'])
    async def onlinemode(self, ctx, mode=''):
        """
        Check or enable/disable onlinemode property. Restart required.

        Args:
            mode optional: Update onlinemode property in server.properties file. Must be in lowercase.

        Usage:
            ?onlinemode - Shows current state
            ?onlinemode true
            ?omode false
        """

        if not mode:
            online_mode = backend.edit_file('online-mode')[1]
            await ctx.send(f"online mode: `{online_mode}`")
            lprint(ctx, f"Fetched online-mode state: {online_mode}")
        elif mode in ['true', 'false']:
            backend.edit_file('online-mode', mode)
            server_property = backend.edit_file('online-mode')
            await ctx.send(f"Updated online mode: `{server_property[1]}`")
            await ctx.send("**Note:** Server restart required for change to take effect.")
            lprint(ctx, f"Updated online-mode: {server_property[1].strip()}")
        else: await ctx.send("Need a true or false argument (in lowercase).")

    @commands.command(aliases=['updatemotd', 'servermotd'])
    async def motd(self, ctx, *message):
        """
        Check or Update motd property. Restart required.

        Args:
            message optional: New message for message of the day for server. No quotes needed.

        Usage:
            ?motd - Shows current message set.
            ?motd YAGA YEWY!
        """

        message = format_args(message)
        motd_property = None
        if slime_vars.server_use_rcon:
            motd_property = backend.server_motd()
        elif slime_vars.server_files_access:
            backend.edit_file('motd', message)  # Doesn't edit message if message is blank
            motd_property = backend.edit_file('motd')
            if motd_property: motd_property = motd_property[1].strip()

        if not motd_property:
            await ctx.send('**Error:** Fetching server motd failed.')
            return

        if message:
            await ctx.send(f"Updated MOTD: `{motd_property}`")
            lprint(ctx, "Updated MOTD: " + motd_property)
        else:
            await ctx.send(f"Current MOTD: `{motd_property}`")
            lprint(ctx, "Fetched MOTD: " + motd_property)

    @commands.command(aliases=['serverrcon'])
    async def rcon(self, ctx, state=''):
        """
        Check RCON status, enable/disable enable-rcon property. Restart required.

        Args:
            state: Set enable-rcon property in server.properties file, true or false must be in lowercase.

        Usage:
            ?rcon
            ?rcon true
            ?rcon false
        """

        if state in ['true', 'false', '']:
            response = backend.edit_file('enable-rcon', state)
            await ctx.send(f"`{response[0]}`")
        else: await ctx.send("Need a true or false argument (in lowercase).")

    # ===== Start/Stop
    @commands.command(aliases=['startserver', 'start'])
    async def serverstart(self, ctx):
        """
        Start Minecraft server.

        Note: Depending on your system, server may take 15 to 40+ seconds to fully boot.
        """

        # Exits function if server already online.
        if await server_status() is True:
            await ctx.send("**Server ACTIVE** :green_circle:")
            return False

        if not backend.server_start():
            await ctx.send("**Error:** Could not start Minecraft server.")
            return False
        await ctx.send(f"***Launching Minecraft Server...*** :rocket:\nServer Selected: **{slime_vars.selected_server['server_name']}**\nStartup time: {slime_vars.startup_wait_time}s.")

        # checks if set custom wait time in selected_server list.
        try: wait_time = int(slime_vars.selected_server['startup_wait_time'])
        except: wait_time = slime_vars.startup_wait_time
        await ctx.send(f"***Fetching Status in {wait_time}s...***")
        await asyncio.sleep(wait_time)

        await ctx.invoke(self.bot.get_command('serverstatus'))
        lprint(ctx, "Starting Minecraft Server")

    @commands.command(aliases=['stopserver', 'stop'])
    async def serverstop(self, ctx, now=''):
        """
        Stop Minecraft server, gives players 15s warning.

        Args:
            now optional: Stops server immediately without giving online players 15s warning.

        Usage:
            ?stop
            ?stop now
        """

        if await server_status() is False:
            await ctx.send("Already Offline")
            return

        await ctx.send("***Stopping Minecraft Server...***")
        if 'now' in now:
            await send_command('save-all')
            await asyncio.sleep(3)
            await send_command('stop')
        else:
            await send_command('say ---WARNING--- Server will halt in 15s!')
            await ctx.send("***Halting Minecraft Server in 15s...***")
            await asyncio.sleep(10)
            await send_command('say ---WARNING--- 5s left!')
            await asyncio.sleep(5)
            await send_command('save-all')
            await asyncio.sleep(3)
            await send_command('stop')

        await asyncio.sleep(5)
        await ctx.send("**Halted Minecraft Server** :stop_sign:")
        backend.mc_subprocess = None
        lprint(ctx, "Stopping Server")

    @commands.command(aliases=['restartserver', 'restart'])
    async def serverrestart(self, ctx, now=''):
        """
        Restarts server with 15s warning to players.

        Args:
            now optional: Restarts server immediately without giving online players 15s warning.

        Usage:
            ?restart
            ?reboot now
        """

        await send_command('say ---WARNING--- Server Rebooting...')
        lprint(ctx, "Restarting Server")
        await ctx.send("***Restarting Minecraft Server...*** :repeat:")
        await ctx.invoke(self.bot.get_command('serverstop'), now=now)

        await asyncio.sleep(3)
        await ctx.invoke(self.bot.get_command('serverstart'))

async def setup(bot):
    await bot.add_cog(Server(bot))
