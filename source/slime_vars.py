import os

# Set this variable if you're also using Debian based system. if not ignore this and manually set your file/folder paths.
user = os.getlogin()

# ========== Discord
# Set location of Discord bot token.
bot_token_file = f'/home/{user}/keys/slime_server.token'

# Set as None if not using a python virtual env.
pyenv_activate_command = f'source /home/{user}/pyenvs/discord2/bin/activate'

# Optionally add channel ID, send message indicating bot is ready on startup.
channel_id = 860361620492255292  # Default: None


# ========== Minecraft Interfacing Options
# Server URL or IP address. In case you're using a DDNS or something.
server_url = 'arcpy.asuscomm.com'
server_port = 25566

# Local file access allows for server files/folders manipulation,for features like backup/restore world saves, editing server.properties file, and read server log.
server_files_access = True

# Uses subprocess.Popen() to run Minecraft server and send commands. If this bot halts, server will halts also. Useful if can't use Tmux.
# Prioritize use_subprocess over Tmux option.
use_subprocess = False

# Use Tmux to send commands to server. You can disable Tmux and RCON to disable server control, and can just use files/folder manipulation features like world backup/restore.
use_tmux = True
tmux_session_name = 'sess'
tmux_bot_pane = '0.6'  # tmux pane for slime_bot
tmux_minecraft_pane = '0.0'  # tmux pane for miencraft server

# Use RCON to send commands to server. You won't be able to use some features like reading server logs.
use_rcon = False
rcon_pass = 'rconpass420'
rcon_port = 25575

# ========== Minecraft Server Config
# Location for Minecraft servers and backups, make sure is full path and is where you want it.
mc_path = f'/home/{user}/Games/Minecraft'

# Second to wait before checking status for ?serverstart. e.g. PaperMC ~10s (w/ decent hardware), Vanilla ~20, Valhesia Volatile ~40-50s.
default_wait_time = 30

# Server profiles, allows you to have different servers and each with their own backups/restores.
# {'server_name': ['server_name', 'description', 'start_Command', 'optional_jar_download_url', optional_wait_time]}
# No spaces allowed in server name. Always put optional_wait_time at tail of list.
# Note: the URL is just for show, the bot uses corresponding API to check and download latest server jar file.
java_params = '-server -Xmx4G -Xms1G -XX:+UseG1GC -XX:MaxGCPauseMillis=100 -XX:ParallelGCThreads=2'
server_list = {'papermc': ["papermc", 'Lightweight PaperMC.', f'java {java_params} -jar server.jar nogui', 'https://papermc.io/downloads', 15],
               'vanilla': ["vanilla", 'Plain old vanilla.', f"java {java_params} -jar server.jar nogui", 'https://www.minecraft.net/en-us/download/server', 20],
               'vvolatile': ["vvolatile", "140 mods!, Note: Takes a long time to start.", f"sh ServerStart.sh", 60],
               'ulibrary': ['ulibrary', 'The Uncensored Library.', f'java -Xmx3G -Xms1G -jar server.jar nogui'],
               }

server_selected = server_list['papermc']
server_path = f"{mc_path}/{server_selected[0]}"
# Where to save world and server backups.
world_backups_path = f"{mc_path}/world_backups/{server_selected[0]}"
server_backups_path = f"{mc_path}/server_backups/{server_selected[0]}"
server_log_file = f"{server_path}/logs/latest.log"
server_log_path = f"{server_path}/logs"

# ========== Bot Config
bot_files_path = os.path.dirname(os.path.abspath(__file__))
slime_vars_file = bot_files_path + '/slime_vars.py'
bot_log_file = f"{bot_files_path}/bot_log.txt"

# The command to use in server to use to check status. server_command() will send something like 'xp 0.64356...'.
status_checker_command = 'xp '

# Max number of log lines to read. Increase if server is really busy (has a lot ouf console logging)
log_lines_limit = 500

# Wait time (in seconds) between sending command to MC server and reading server logs for output.
# Time between receiving command and logging output varies depending on PC specs, MC server type (papermc, vanilla, forge, etc), and how many mods.
command_buffer_time = 1

# Autosave functionality. interval is in minutes.
autosave_status = True
autosave_interval = 60

mc_active_status = False  # If Minecraft server is running.
mc_subprocess = None  # If using subprocess, this is will be the Minecraft server.

# For '?links' command. Shows helpful websites.
useful_websites = {'Minecraft Downlaod': 'https://www.minecraft.net/en-us/download',
                   'Forge Installer': 'https://files.minecraftforge.net/',
                   'CurseForge Download': 'https://curseforge.overwolf.com/',
                   'Modern HD Resource Pack': 'https://minecraftred.com/modern-hd-resource-pack/',
                   'Minecraft Server Commands': 'https://minecraft.gamepedia.com/Commands#List_and_summary_of_commands',
                   'Minecraft /gamerule Commands': 'https://minecraft.gamepedia.com/Game_rule',
                   }

# ========== Misc
updatable_mc = ['vanilla', 'papermc']  # What server has update functionality. See get_latest_version() in backend_functions.py
server_ip = server_url  # Will be updated by get_ip() function in backend_functions.py on bot startup.

if use_rcon is True: import mctools, re
if server_files_access is True: import shutil, fileinput, json
