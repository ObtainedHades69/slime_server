import subprocess, requests, datetime, random, asyncio, time, csv, os, re
from file_read_backwards import FileReadBackwards
from bs4 import BeautifulSoup
from slime_vars import *


# Removes unwanted ANSI escape characters.
def remove_ansi(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

# Outputs and logs used bot commands and which Discord user invoked them.
def lprint(arg1=None, arg2=None):
    if type(arg1) is str:
        msg, user = arg1, 'Script'  # If did not receive ctx object.
    else:
        try:
            user = arg1.message.author
        except:
            user = 'N/A'
        msg = arg2

    output = f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ({user}): {msg}"
    print(output)

    # Logs output.
    with open(bot_log_file, 'a') as file:
        file.write(output + '\n')

lprint("Server selected: " + server_selected[0])


# ========== Server commands: start, send command, read log, etc
def mc_start():
    """
    Start Minecraft server depending on whether you're using Tmux subprocess method.

    Note: Priority is given to subprocess method over Tmux if both corresponding booleans are True.

    Returns:
        bool: If successful boot.
    """

    global mc_subprocess

    os.chdir(server_path)
    if use_subprocess is True:
        # Runs MC server as subprocess. Note, If this script stops, the server will stop.
        try:
            mc_subprocess = subprocess.Popen(server_selected[2].split(), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        except:
            lprint("Error server starting subprocess")

        if type(mc_subprocess) == subprocess.Popen:
            return True

    elif use_tmux is True:
        os.system('tmux send-keys -t mcserver:1.0 "cd /" ENTER')  # Fix: 'java.lang.Error: Properties init: Could not determine current working' error
        os.system(f'tmux send-keys -t mcserver:1.0 "cd {server_path}" ENTER')

        # Tries starting new detached tmux session.
        if not os.system(f'tmux send-keys -t mcserver:1.0 "{server_selected[2]}" ENTER'):
            return True
    else:
        return "Error starting server."

# Sends command to tmux window running server.
async def mc_command(command, return_bool=True):
    """
    Sends command to Minecraft server. Depending on whether server is a subprocess or in Tmux session or using RCON.
    Sends command to server, then reads from latest.log file for output.
    If using RCON, will only return RCON returned data, can't read from server log.

    Args:
        command: Command to send.
        match_output [Optional]: Look for specific string from server output.
        return_bool: Return True/False whether or not command ran successfully.

    Returns:
        bool: If error sending command to server, sends False boolean.
        str: Returns matched string if match found.
    """

    global mc_subprocess

    if use_rcon is True:
        return mc_rcon(command)

    elif use_subprocess is True:
        if mc_subprocess is not None:
            mc_subprocess.stdin.write(bytes(command + '\n', 'utf-8'))
            mc_subprocess.stdin.flush()
        else:
            return False

    elif use_tmux is True:
        if os.system(f'tmux send-keys -t mcserver:1.0 "{command}" ENTER') != 0:
            return True
    else:
        return "Error sending command to server."

    time.sleep(1)
    return mc_log(command, return_bool=return_bool)

# Send commands to server using RCON.
def mc_rcon(command=''):
    """
    Send command to server with RCON.

    Args:
        command: Minecraft command.

    Returns:
        bool: Returns False if error connecting to RCON.
        str: Output from RCON.
    """

    mc_rcon_client = mctools.RCONClient(server_ip, port=rcon_port)
    try:
        mc_rcon_client.login(rcon_pass)
    except ConnectionError:
        lprint(f"Error Connecting to RCON: {server_ip} : {rcon_port}")
        return False
    else:
        return mc_rcon_client.command(command)

# Gets server output by reading log file, can also find response from command in log by finding matching string.
def mc_log(match='placeholder match', file_path=f"{server_path}/logs/latest.log", lines=15, normal_read=False, return_bool=False, log_mode=False, filter_mode=False):
    """
    Read latest.log file under server/logs folder.

    Args:
        match [str]: Check for matching string.
        file_path [str:latest.log]: File to read.
        lines [int:15]: Number of most recent lines to return.
        return_bool [bool:False]: Return True/False boolean if match was found.
        log_mode [bool:False]: Return x lines from log file, skips matching.
        normal_read [bool:False]: Reads file top down, defaults to bottom up using file-read-backwards module.
        filter_mode [bool:False]: Don't stop at first match.

    Returns:

    """
    if not os.path.isfile(file_path):
        return False

    log_data = ''
    if normal_read is True:
        with open(file_path, 'r') as file:
            for line in file:
                if match in line:
                    return line
    else:
        with FileReadBackwards(file_path) as file:
            for i in range(lines):
                line = file.readline()
                if 'banlist' in match:
                    if 'was banned by' in line:  # finds log lines that shows banned players.
                        log_data += line
                    elif ']: There are' in line:  # finds the end so it doesn't return everything from log other then banned users.
                        log_data += line
                        break
                elif log_mode:
                    log_data += line
                elif match in line:
                    log_data += line
                    if filter_mode is False:
                        break

    if log_data:
        return log_data


# ========== Getting Info: output, ping, reading files.

# Get server active status, motd, and version information. Either using PINGClient or reading from local server files.
async def mc_status():
    """
    Gets server active status, by sending command to server and checking server log.

    Returns:
        bool: returns True if server is online.

    """

    status_checker = 'debug status_checker' + str(random.random())
    log_data = await mc_command(status_checker)
    if status_checker in str(log_data):
        return True

# Gets server stats from mctools PINGClient. Returned dictionary data contains ansi escape chars.
def mc_ping():
    """
    Gets server information using mctools.PINGClient()

    Returns:
        dict: Dictionary containing 'version', and 'description' (motd).

    """
    try:
        stats = mctools.PINGClient(server_ip).get_stats()
    except ConnectionRefusedError:
        lprint("Ping Error: Connection Refused.")
    else:
        return stats

def get_mc_motd():
    """
    Gets current message of the day from server, either by reading from server.properties file or using PINGClient.

    Returns:
        str: Server motd.
    """

    if server_files_access is True:
        return edit_file('motd')[1]
    elif use_rcon is True:
        return remove_ansi(mc_ping()['description'])
    else:
        return "N/A"


def get_server_ip():
    server_ip = requests.get('http://ip.42.pl/raw').text
    return server_ip
server_ip = get_server_ip()

# Gets server version from log file or gets latest version number from website.
def mc_version():
    """
    Gets server version, either by reading server log or using PINGClient.

    Returns:
        str: Server version number.
    """

    if use_rcon is True:
        return mc_ping()['version']['name']
    elif server_files_access is True:
        if version := mc_log('server version', normal_read=True):
            version = version.split()[-1]
            with open(f"{server_path}/version.txt", 'w') as f:
                f.write(version)
            return version
        else:
            with open(f"{server_path}/version.txt", 'r') as f:
                return f.readline()
    else:
        return 'N/A'

def get_latest_version():
    """
    Gets latest Minecraft server version number from official website using bs4.

    Returns:
        str: Latest version number.
    """

    soup = BeautifulSoup(requests.get(new_server_url).text, 'html.parser')
    for i in soup.findAll('a'):
        if i.string and 'minecraft_server' in i.string:
            return '.'.join(i.string.split('.')[1:][:-1])  # Extract version number.

# Used so Discord command arguments don't need qoutes.
def format_args(args, return_empty_str=False):
    """
    Formats passed in *args from Discord command functions.
    This is so quotes aren't necessary for Discord command arguments.

    Args:
        args: Passed in args to combine and return.
        return_empty [bool:False]: returns empty str if passed in arguments aren't usable for Discord command.

    Returns:
        str: Arguments combines with spaces.
    """

    if len(str(args)) >= 1:
        return ' '.join(args)
    else:
        if return_empty_str is True:
            return ''
        return "No reason given"

# Gets data from json local file.
def read_json(json_file):
    os.chdir(bot_files_path)
    with open(server_path + '/' + json_file) as file:
        return [i for i in json.load(file)]

def read_csv(csv_file):
    os.chdir(bot_files_path)
    with open(csv_file) as file:
        return [i for i in csv.reader(file, delimiter=',', skipinitialspace=True)]


# ========== Extra: edit file, backup, restore
def download_new_server():
    """
    Downloads latest server.jar file from Minecraft website. Also updates eula.txt.

    Returns:
        bool: If download was successful.
    """

    os.chdir(mc_path)
    jar_download_url = ''

    minecraft_website = requests.get(new_server_url)
    soup = BeautifulSoup(minecraft_website.text, 'html.parser')
    # Finds Minecraft server.jar urls in div class.
    div_agenda = soup.find_all('div', class_='minecraft-version')
    for i in div_agenda[0].find_all('a'):
        jar_download_url = f"{i.get('href')}"

    if not jar_download_url:
        return False

    # Saves new server.jar in current server.
    new_jar_data = requests.get(jar_download_url).content

    try:
        with open(server_path + '/eula.txt', 'w+') as f:
            f.write(new_jar_data)
    except IOError:
        lprint(f"Error updatine eula.txt file: {server_path}")

    try:
        with open(server_path + '/server.jar', 'wb+') as f:
            f.write(new_jar_data)
        return True
    except IOError:
        lprint(f"Error saving new jar file: {server_path}")

    return False

# Reads, find, or replace properties in a .properties file, edits inplace using fileinput.
def edit_file(target_property=None, value='', file_path=f"{server_path}/server.properties"):
    """
    Edits server.properties file if received target_property and value.
    If receive no value, will return current set value if property exists.

    Args:
        target_property [str:None]: Find Minecraft server property.
        value [str:'']: If received argument, will change value.
        file_path [str:server.properties]: File to edit. Must be in .properties file format. Default is server.properties file under /server folder containing server.jar.

    Returns:
        str: If target_property was not found.
        tuple: First item is line from file that matched target_property. Second item is just the current value.
    """

    os.chdir(server_path)
    return_line = discord_return = ''  # Discord has it's own return variable, because the data might be formatted for Discord.

    with fileinput.FileInput(file_path, inplace=True, backup='.bak') as file:
        for line in file:
            split_line = line.split('=', 1)

            if target_property == 'all':  # Return all lines of file.
                discord_return += F"`{line.rstrip()}`\n"
                return_line += line.strip() + '\n'
                print(line, end='')

            # If found match, and user passed in new value to update it.
            elif target_property in split_line[0] and len(split_line) > 1:
                if len(str(value)) >= 1:
                    split_line[1] = value
                    new_line = '='.join(split_line)
                    discord_return = f"Updated Property:`{line}` > `{new_line}`.\nRestart to apply changes."
                    return_line = line
                    print(new_line, end='\n')
                # If user did not pass a new value to update property, just return the line from file.
                else:
                    discord_return = f"`{'='.join(split_line)}`"
                    return_line = '='.join(split_line)
                    print(line, end='')
            else:
                print(line, end='')

    if return_line:
        return return_line, return_line.split('=')[1]
    else:
        return "404 Match not found."

def get_from_index(path, index):
    """
    Get server or world backup folder name from passed in index number

    Args:
        path str: Location to find world or server backups.
        index int: Select specific folder, get index from other functions like ?worldbackupslist, ?serverbackupslist

    Returns:
            str: file path of selected folder.
    """

    return os.listdir(path)[index]

def fetch_backups(path, amount=5):
    """
    Gets x amount of backups. Usually to show in list.

    Args:
        path str: Path of world or server backups location.
        amount int: Number of backups to show in list.
    """

    backups = []
    if not os.path.isdir(path):
        return False

    for item in os.listdir(path)[-amount:]:
        if os.path.isdir(path + '/' + item):
            backups.append(item)
    return backups

def create_backup(name, src, dst):
    """
    Create a new world or server backup, by copying and renaming folder.

    Args:
        name str: Name of new backup. Final name will have date and time prefixed.
        src str: Folder to backup, whether it's a world folder or a entire server folder.
        dst str: Destination for backup.
    """

    if not os.path.isdir(dst):
        os.makedirs(dst)

    folder_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H-%M')
    new_name = f"({folder_timestamp}) {mc_version()} {name}"
    new_backup_path = dst + '/' + new_name
    shutil.copytree(src, new_backup_path)

    if os.path.isdir(new_backup_path):
        lprint("Backed up to: " + new_backup_path)
        return new_name
    else:
        lprint("Error creating backup at: " + new_backup_path)
        return False

def restore_backup(src, dst, reset=False):
    """
    Restores world or server backup. Overwrites existing files.

    Args:
        src str: Backed up folder to copy to current server.
        dst str: Location to copy backup to.
        reset [bool:False]: Leave src folder empty and not copy backup to dst.
    """

    try:
        shutil.rmtree(dst)
    except:
        pass

    # Used in ?worldreset and ?serverreset Discord command to clear all world or server files.
    if reset is True:
        return True

    try:
        shutil.copytree(src, dst)
        return True
    except:
        lprint("Error restoring: " + str(src + ' > ' + dst))

def delete_backup(backup):
    """
    Delete world or server backup.

    Args:
        backup str: Path of backup to delete.
    """

    try:
        shutil.rmtree(backup)
        return True
    except:
        lprint("Error deleting: " + str(backup))


# ========== Discord commands.
def get_server_from_index(index):
    """Returns server backup full path from passed in index number."""
    return get_from_index(server_backups_path, index)

def get_world_from_index(index):
    return get_from_index(world_backups_path, index)

def fetch_servers(amount=5):
    """Returns list of x number of backed up server."""
    return fetch_backups(server_backups_path, amount)

def fetch_worlds(amount=5):
    return fetch_backups(world_backups_path, amount)

def backup_server(name='server_backup'):
    """Create new server backup with specified name."""
    return create_backup(name, server_path, server_backups_path)

def backup_world(name="world_backup"):
    return create_backup(name, server_path + '/world', world_backups_path)

def delete_server(server):
    """Delete specified server with specified index."""
    return delete_backup(server_backups_path + '/' + server)

def delete_world(world):
    return delete_backup(world_backups_path + '/' + world)

def restore_server(server=None, reset=False):
    """Restore server with specified index."""
    os.chdir(server_backups_path)
    return restore_backup(server, server_path, reset)

def restore_world(world=None, reset=False):
    os.chdir(world_backups_path)
    return restore_backup(world, server_path + '/world', reset)
