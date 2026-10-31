#!/usr/bin/env python3
import argparse
import json
import os
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

HOME = Path.home()
STATE_DIR = HOME / ".config" / "pumpkin-auto"
SECRET_FILE = STATE_DIR / "playit.secret"
PLAYIT_SOCK = STATE_DIR / "playit.sock"
PLAYIT_LOG = STATE_DIR / "playit.log"
PLAYIT_BIN = HOME / ".local" / "bin" / "playit"
SERVERS_DIR = HOME / "pumpkin-servers"
DEFAULT_DIR = HOME / "pumpkin-server"
CACHE_DIR = HOME / ".cache" / "pumpkin-auto"

PUMPKIN_VERSION = "0.1.0-dev+26.2-26.45"
PUMPKIN_URL = (
    "https://github.com/Pumpkin-MC/Pumpkin/releases/download/"
    "0.1.0-dev%2B26.2-26.45/pumpkin-X64-Linux"
)
PLAYIT_VERSION = "v1.2.0"
PLAYIT_URL = (
    f"https://github.com/playit-cloud/playit-agent/releases/download/"
    f"{PLAYIT_VERSION}/playit-linux-amd64"
)
API_BASE = "https://api.playit.gg"
TUNNELS_URL = "https://playit.gg/account/tunnels"

CONFIG_TEMPLATE = """seed = "__SEED__"
default_difficulty = "__DIFFICULTY__"
op_permission_level = 4
allow_nether = true
allow_end = true
hardcore = false
tps = 20.0
default_gamemode = "__GAMEMODE__"
force_gamemode = false
scrub_ips = true
use_favicon = true
default_level_name = "world"
allow_chat_reports = false
white_list = false
enforce_whitelist = false

[logging]
enabled = true
level = "info"
threads = false
thread_ids = false
target = false
color = true
timestamp = true
timestamp_format = "[hour]:[minute]:[second]"
file = "latest.log"

[resource_pack.java]
enabled = false
url = ""
sha1 = ""
prompt_message = ""
force = false

[resource_pack.bedrock]
enabled = false
force = false
packs = []

[world]
lighting = "default"
autosave_ticks = 6000

[world.chunk]
type = "anvil"
write_in_place = false

[world.chunk.compression]
algorithm = "LZ4"
level = 6

[networking.query]
enabled = false
address = "0.0.0.0:__PORT__"

[networking.rcon]
enabled = true
address = "127.0.0.1:__RCON_PORT__"
password = "__RCON_PASSWORD__"
max_connections = 10

[networking.rcon.logging]
logged_successfully = false
wrong_password = true
commands = false
quit = false

[networking.proxy]
enabled = false

[networking.proxy.velocity]
enabled = false
secret = ""

[networking.proxy.bungeecord]
enabled = false
secret = ""

[networking.lan_broadcast]
enabled = false

[networking.java]
enabled = true
address = "0.0.0.0:__PORT__"
encryption = true
online_mode = __ONLINE__
max_players = __MAX_PLAYERS__
view_distance = 16
simulation_distance = 10
keep_alive_time = 15
motd = "__MOTD__"

[networking.java.compression]
enabled = true
threshold = 256
level = 4

[networking.java.authentication]
enabled = true
fallbacks = []
profile_by_name_fallbacks = []
profile_by_uuid_fallbacks = []
connect_timeout = 5000
read_timeout = 5000
prevent_proxy_connections = false

[networking.java.authentication.player_profile]
allow_banned_players = false
allowed_actions = ["FORCED_NAME_CHANGE", "USING_BANNED_SKIN"]

[networking.java.authentication.textures]
enabled = true
allowed_url_schemes = ["http", "https"]
allowed_url_domains = [".minecraft.net", ".mojang.com"]

[networking.java.authentication.textures.types]
skin = true
cape = true
elytra = true

[networking.java.packet_limiter]
enabled = true
max_packet_rate = 500.0
burst_capacity = 500.0
kick_message = "Kicked for spamming packets"

[networking.bedrock]
enabled = false
online_mode = false
max_players = 1000
view_distance = 16
simulation_distance = 10
motd = "__MOTD__"
username_prefix = ""
replace_username_spaces = true
chunk_caching = true

[networking.bedrock.compression]
enabled = true
threshold = 256
level = 4

[networking.bedrock.authentication]
enabled = true
connect_timeout = 5000
read_timeout = 5000

[networking.bedrock.nethernet]
enabled = false
address = "0.0.0.0:19132"
identity_key = "nethernet-key.der"
stun_servers = []

[networking.bedrock.packet_limiter]
enabled = true
max_packet_rate = 500.0
burst_capacity = 500.0
kick_message = "Kicked for spamming packets"

[commands]
use_console = true
use_tty = true
log_console = true
broadcast_console_to_ops = true
default_op_level = 0

[commands.overrides]

[chat]
format = "<{DISPLAYNAME}> {MESSAGE}"

[chat.anti_spam]
enabled = true
spam_threshold = 200
message_cost = 20
decay_per_tick = 1
ops_bypass = true

[pvp]
enabled = true
hurt_animation = true
protect_creative = true
knockback = true
swing = true

[server_links]
enabled = true
bug_report = "https://github.com/Pumpkin-MC/Pumpkin/issues"
support = ""
status = ""
feedback = ""
community = ""
website = ""
forums = ""
news = ""
announcements = ""

[server_links.custom]

[player_data]
save_player_data = true
save_player_cron_interval = 300

[fun]
april_fools = false

[recipe]
send_recipes = true

[plugins]
enabled = true
hot_reload = false
ask_permission_confirmation = true
allow_unsigned = true
allowed_permissions = []
blocked_permissions = []
inherit_env = false
loopback_only = false
verify_signatures = true

[plugins.overrides]

[advancement]
save_advancements = true
"""


class ApiError(Exception):
    pass


def log(message=""):
    print(message, flush=True)


def info(message):
    print(f"[pumpkin-auto] {message}", flush=True)


def die(message, code=1):
    print(f"[pumpkin-auto] error: {message}", file=sys.stderr, flush=True)
    raise SystemExit(code)


def download_file(url, dest, label):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    info(f"Downloading {label}...")
    request = urllib.request.Request(url, headers={"User-Agent": "pumpkin-auto/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, open(tmp, "wb") as handle:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            last = -10
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                done += len(chunk)
                if total:
                    pct = int(done * 100 / total)
                    if pct >= last + 10:
                        print(
                            f"  {pct:3d}%  {done // (1024 * 1024)}/{total // (1024 * 1024)} MiB",
                            end="\r",
                            flush=True,
                        )
                        last = pct
        print(" " * 40, end="\r", flush=True)
    except Exception as exc:
        try:
            tmp.unlink()
        except OSError:
            pass
        die(f"download failed for {label}: {exc}")
    tmp.replace(dest)
    dest.chmod(0o755)
    info(f"Saved {dest}")


def ensure_pumpkin_binary():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = CACHE_DIR / f"pumpkin-{PUMPKIN_VERSION}"
    if not cached.exists() or cached.stat().st_size < 1_000_000:
        download_file(PUMPKIN_URL, cached, f"Pumpkin {PUMPKIN_VERSION}")
    return cached


def link_binary(source, instance_dir):
    dest = instance_dir / "pumpkin"
    if dest.exists() or dest.is_symlink():
        return
    try:
        os.link(source, dest)
    except OSError:
        try:
            dest.symlink_to(source)
        except OSError:
            shutil.copy2(source, dest)
            dest.chmod(0o755)


def port_is_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def find_free_port(start):
    port = start
    while port < start + 500:
        if port_is_free(port):
            return port
        port += 1
    die(f"could not find a free port starting at {start}")


def port_open(port, host="127.0.0.1"):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


def lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def read_instance_config(instance_dir):
    config_path = instance_dir / "pumpkin.toml"
    with open(config_path, "rb") as handle:
        config = tomllib.load(handle)
    java = config.get("networking", {}).get("java", {})
    address = str(java.get("address", "0.0.0.0:25565"))
    try:
        port = int(address.rsplit(":", 1)[1])
    except (IndexError, ValueError):
        port = 25565
    rcon = config.get("networking", {}).get("rcon", {})
    rcon_address = str(rcon.get("address", "127.0.0.1:25575"))
    try:
        rcon_port = int(rcon_address.rsplit(":", 1)[1])
    except (IndexError, ValueError):
        rcon_port = port + 10
    return {
        "port": port,
        "online": bool(java.get("online_mode", True)),
        "motd": str(java.get("motd", "")),
        "rcon_port": rcon_port,
        "rcon_password": str(rcon.get("password", "")),
    }


def write_instance_config(instance_dir, port, rcon_port, online, motd, max_players,
                          difficulty, gamemode):
    values = {
        "__SEED__": str(secrets.randbits(63)),
        "__DIFFICULTY__": difficulty,
        "__GAMEMODE__": gamemode,
        "__PORT__": str(port),
        "__RCON_PORT__": str(rcon_port),
        "__RCON_PASSWORD__": secrets.token_hex(8),
        "__ONLINE__": "true" if online else "false",
        "__MAX_PLAYERS__": str(max_players),
        "__MOTD__": motd.replace('"', "'"),
    }
    text = CONFIG_TEMPLATE
    for token, value in values.items():
        text = text.replace(token, value)
    config_path = instance_dir / "pumpkin.toml"
    config_path.write_text(text)
    config_path.chmod(0o600)


def find_server_pid(instance_dir):
    instance_dir = instance_dir.resolve()
    pidfile = instance_dir / "server.pid"
    if pidfile.exists():
        try:
            pid = int(pidfile.read_text().strip())
            if process_matches(pid, instance_dir):
                return pid
        except (ValueError, OSError):
            pass
    proc = Path("/proc")
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if process_matches(pid, instance_dir):
            return pid
    return None


def process_matches(pid, instance_dir):
    proc_dir = Path("/proc") / str(pid)
    try:
        cwd = Path(os.readlink(proc_dir / "cwd"))
    except OSError:
        return False
    if cwd != instance_dir:
        return False
    try:
        cmdline = (proc_dir / "cmdline").read_bytes().split(b"\0")
    except OSError:
        return False
    if not cmdline or not cmdline[0]:
        return False
    first = cmdline[0].decode("utf-8", "replace")
    return os.path.basename(first) == "pumpkin"


def process_info(pid):
    uptime = None
    rss = None
    try:
        fields = (Path("/proc") / str(pid) / "stat").read_text().split()
        sys_uptime = float(Path("/proc/uptime").read_text().split()[0])
        hz = os.sysconf("SC_CLK_TCK")
        uptime = sys_uptime - int(fields[21]) / hz
    except Exception:
        pass
    try:
        for line in (Path("/proc") / str(pid) / "status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                rss = int(line.split()[1]) / 1024
                break
    except Exception:
        pass
    return uptime, rss


def format_uptime(seconds):
    if seconds is None:
        return "-"
    seconds = int(seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days:
        return f"{days}d {hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def start_server(instance_dir, port, timeout=45):
    pid = find_server_pid(instance_dir)
    if pid:
        info(f"Server already running (PID {pid}).")
        return pid
    log_path = instance_dir / "console.log"
    with open(log_path, "ab") as handle:
        proc = subprocess.Popen(
            ["./pumpkin"],
            cwd=instance_dir,
            stdin=subprocess.DEVNULL,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    (instance_dir / "server.pid").write_text(str(proc.pid))
    info(f"Starting server (PID {proc.pid})...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            tail = log_path.read_text(errors="replace").splitlines()[-15:]
            die("server exited during startup:\n" + "\n".join(tail))
        if port_open(port):
            info(f"Server is listening on 0.0.0.0:{port}.")
            return proc.pid
        time.sleep(0.3)
    die(f"server did not open port {port} within {timeout}s; see {log_path}")


def stop_server(instance_dir, timeout=25):
    pid = find_server_pid(instance_dir)
    if not pid:
        info("Server is not running.")
        return False
    info(f"Stopping server (PID {pid})...")
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not (Path("/proc") / str(pid)).exists():
            info("Server stopped.")
            try:
                (instance_dir / "server.pid").unlink()
            except OSError:
                pass
            return True
        time.sleep(0.2)
    info(f"Server did not stop in {timeout}s; sending SIGKILL.")
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    return True


def save_secret(secret):
    SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    SECRET_FILE.write_text(secret.strip())
    SECRET_FILE.chmod(0o600)


def load_secret():
    try:
        value = SECRET_FILE.read_text().strip()
        return value or None
    except OSError:
        return None


def api_call(path, payload, secret=None):
    url = API_BASE + path
    headers = {"Content-Type": "application/json", "User-Agent": "pumpkin-auto/1.0"}
    if secret:
        headers["Authorization"] = f"Agent-Key {secret.strip()}"
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            body = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            raise ApiError(f"HTTP {exc.code}: {body[:200]}")
        status = parsed.get("status")
        data = parsed.get("data")
        if status == "error" and isinstance(data, dict):
            raise ApiError(data.get("message") or data.get("type") or str(data))
        if status == "fail":
            raise ApiError(str(data))
        raise ApiError(f"HTTP {exc.code}: {body[:200]}")
    except Exception as exc:
        raise ApiError(str(exc))
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        raise ApiError(f"unexpected response: {body[:200]}")
    status = parsed.get("status")
    data = parsed.get("data")
    if status == "success":
        return data
    if status == "fail":
        raise ApiError(str(data))
    if status == "error" and isinstance(data, dict):
        raise ApiError(data.get("message") or data.get("type") or str(data))
    raise ApiError(f"unexpected response: {parsed}")


def claim_playit():
    code = secrets.token_hex(5)
    url = f"https://playit.gg/claim/{code}"
    log()
    log("playit.gg needs to be linked to your account (one time only).")
    log("Open this URL and approve the agent:")
    log()
    log(f"  {url}")
    log()
    log("Waiting for approval (Ctrl+C to cancel)...")
    last = None
    started = time.time()
    while True:
        try:
            status = api_call(
                "/claim/setup",
                {"code": code, "agent_type": "assignable", "version": "playit 1.2.0"},
            )
        except ApiError as exc:
            log(f"  claim error: {exc} (retrying)")
            time.sleep(2)
            continue
        if status == "UserAccepted":
            break
        if status == "UserRejected":
            die("claim was rejected in the browser")
        if status != last:
            log(f"  status: {status}")
            last = status
        if time.time() - started > 900:
            die("timed out waiting for playit.gg approval")
        time.sleep(1)
    log("Approved. Fetching agent secret...")
    data = api_call("/claim/exchange", {"code": code})
    secret = data.get("secret_key") if isinstance(data, dict) else None
    if not secret:
        die(f"claim exchange returned no secret: {data!r}")
    save_secret(secret)
    info("playit.gg agent linked and secret saved.")
    return secret


def resolve_secret(explicit=None):
    if explicit:
        save_secret(explicit)
        return explicit.strip()
    env = os.environ.get("PLAYIT_SECRET")
    if env:
        save_secret(env)
        return env.strip()
    existing = load_secret()
    if existing:
        return existing
    return claim_playit()


def ensure_playit_binary():
    if PLAYIT_BIN.exists() and PLAYIT_BIN.stat().st_size > 1_000_000:
        return
    download_file(PLAYIT_URL, PLAYIT_BIN, f"playit.gg agent {PLAYIT_VERSION}")


def find_playit_pid():
    sock_arg = str(PLAYIT_SOCK).encode()
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmdline = (entry / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if not cmdline or not cmdline[0]:
            continue
        if b"playit" not in Path(cmdline[0].decode("utf-8", "replace")).name.encode():
            continue
        if sock_arg in cmdline:
            return int(entry.name)
    return None


def find_any_playit_pid():
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmdline = (entry / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if not cmdline or not cmdline[0]:
            continue
        if Path(cmdline[0].decode("utf-8", "replace")).name == "playit":
            return int(entry.name)
    return None


def start_playit(secret):
    ensure_playit_binary()
    pid = find_playit_pid()
    if pid:
        info(f"playit.gg agent already running (PID {pid}).")
        return pid
    other = find_any_playit_pid()
    if other:
        info(f"Another playit.gg agent is already running (PID {other}); using it.")
        return other
    save_secret(secret)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(PLAYIT_LOG, "ab") as logfile:
        proc = subprocess.Popen(
            [
                str(PLAYIT_BIN),
                "--secret-path",
                str(SECRET_FILE),
                "--socket-path",
                str(PLAYIT_SOCK),
                "--log-path",
                str(PLAYIT_LOG),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    time.sleep(1.5)
    if proc.poll() is not None:
        tail = PLAYIT_LOG.read_text(errors="replace").splitlines()[-15:]
        die("playit.gg agent exited during startup:\n" + "\n".join(tail))
    info(f"Started playit.gg agent (PID {proc.pid}).")
    return proc.pid


def stop_playit():
    pid = find_playit_pid()
    if not pid:
        info("playit.gg agent is not running.")
        return
    info(f"Stopping playit.gg agent (PID {pid})...")
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.time() + 10
    while time.time() < deadline:
        if not (Path("/proc") / str(pid)).exists():
            info("playit.gg agent stopped.")
            return
        time.sleep(0.2)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def get_agent_data(secret, timeout=40):
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            return api_call("/v1/agents/rundata", {}, secret)
        except ApiError as exc:
            last_error = exc
            text = str(exc)
            if "InvalidAgentKey" in text or "NoLongerValid" in text:
                die(
                    "playit.gg rejected the saved secret. Run "
                    "`pumpkin-auto playit-reset` and link again."
                )
            try:
                return api_call("/agents/rundata", {}, secret)
            except ApiError:
                pass
            time.sleep(1.5)
    die(f"playit.gg agent did not come online: {last_error}")


def list_tunnels(secret):
    data = api_call("/tunnels/list", {"tunnel_id": None, "agent_id": None}, secret)
    if not isinstance(data, dict):
        return []
    return data.get("tunnels") or []


def tunnel_origin(tunnel):
    origin = tunnel.get("origin") or {}
    if origin.get("type") == "agent":
        return origin.get("data") or {}
    return {}


def find_tunnel(tunnels, port, agent_id=None):
    for tunnel in tunnels:
        if tunnel.get("port_type") not in ("tcp", "both"):
            continue
        origin = tunnel_origin(tunnel)
        if origin.get("local_port") != port:
            continue
        if agent_id and origin.get("agent_id") != agent_id:
            continue
        return tunnel
    return None


def find_tunnel_by_id(tunnels, tunnel_id):
    for tunnel in tunnels:
        if tunnel.get("id") == tunnel_id:
            return tunnel
    return None


def create_tunnel(secret, agent_id, port, name):
    base = {
        "name": name,
        "port_type": "tcp",
        "port_count": 1,
        "origin": {
            "type": "agent",
            "data": {
                "agent_id": agent_id,
                "local_ip": "127.0.0.1",
                "local_port": port,
            },
        },
        "enabled": True,
        "alloc": None,
        "firewall_id": None,
        "proxy_protocol": None,
    }
    errors = []
    for tunnel_type in ("minecraft-java", None):
        body = dict(base)
        body["tunnel_type"] = tunnel_type
        try:
            result = api_call("/tunnels/create", body, secret)
            tunnel_id = result.get("id") if isinstance(result, dict) else None
            info(f"Created {'Minecraft Java' if tunnel_type else 'TCP'} tunnel.")
            if tunnel_id:
                tunnels = list_tunnels(secret)
                tunnel = find_tunnel_by_id(tunnels, tunnel_id)
                if tunnel:
                    return tunnel
                return {"id": tunnel_id}
            return None
        except ApiError as exc:
            errors.append(f"{tunnel_type or 'tcp'}: {exc}")
    raise ApiError("; ".join(errors))


def tunnel_address(tunnel):
    alloc = tunnel.get("alloc") or {}
    status = alloc.get("status")
    if status == "allocated":
        data = alloc.get("data") or {}
        host = (
            data.get("assigned_domain")
            or data.get("ip_hostname")
            or data.get("static_ip4")
        )
        port = data.get("port_start", 25565)
        if not host:
            return None, "allocated but no hostname", None
        address = host if port == 25565 else f"{host}:{port}"
        return address, None, data
    if status == "disabled":
        reason = (alloc.get("data") or {}).get("reason", "disabled")
        return None, f"disabled ({reason})", None
    return None, "waiting for allocation", None


def ensure_tunnel(secret, port, name):
    agent_data = get_agent_data(secret)
    agent_id = agent_data.get("agent_id")
    if not agent_id:
        die("playit.gg did not return an agent id")
    tunnels = list_tunnels(secret)
    tunnel = find_tunnel(tunnels, port, agent_id)
    if tunnel:
        info(f"Using existing playit tunnel for 127.0.0.1:{port}.")
    else:
        info(f"Creating playit tunnel for 127.0.0.1:{port}...")
        try:
            tunnel = create_tunnel(secret, agent_id, port, name)
        except ApiError as exc:
            log()
            log(f"Could not create the tunnel automatically: {exc}")
            log("Create it once in the playit.gg dashboard:")
            log(f"  {TUNNELS_URL}")
            log(f"  Tunnel type: Minecraft Java")
            log(f"  Local address: 127.0.0.1:{port}")
            log()
            return None
    if not tunnel:
        return None
    deadline = time.time() + 90
    last_reason = None
    while time.time() < deadline:
        tunnels = list_tunnels(secret)
        current = find_tunnel_by_id(tunnels, tunnel.get("id")) or find_tunnel(
            tunnels, port, agent_id
        )
        if current:
            tunnel = current
        address, reason, data = tunnel_address(tunnel)
        if address:
            info(f"Public address: {address}")
            return {
                "address": address,
                "tunnel_id": tunnel.get("id"),
                "agent_id": agent_id,
                "local_port": port,
                "port_start": data.get("port_start") if data else None,
                "assigned_domain": data.get("assigned_domain") if data else None,
                "assigned_srv": data.get("assigned_srv") if data else None,
            }
        if reason and reason != last_reason:
            info(f"Tunnel status: {reason}")
            last_reason = reason
        time.sleep(2)
    info("Timed out waiting for playit.gg to allocate the tunnel.")
    return None


def instance_from_args(args, create=True):
    if args.dir:
        return Path(args.dir).expanduser().resolve()
    if args.name:
        return SERVERS_DIR / args.name
    if DEFAULT_DIR.exists() and (DEFAULT_DIR / "pumpkin").exists():
        return DEFAULT_DIR
    return SERVERS_DIR / "survival"


def ensure_instance(args, instance_dir):
    instance_dir.mkdir(parents=True, exist_ok=True)
    config_path = instance_dir / "pumpkin.toml"
    binary = instance_dir / "pumpkin"
    created = False
    if not binary.exists() and not binary.is_symlink():
        source = ensure_pumpkin_binary()
        link_binary(source, instance_dir)
        created = True
    if not config_path.exists():
        source = ensure_pumpkin_binary()
        link_binary(source, instance_dir)
        if args.port and not port_is_free(args.port):
            die(f"port {args.port} is already in use")
        port = args.port or find_free_port(25565)
        rcon_port = find_free_port(port + 10)
        motd = args.motd or "A Pumpkin server, tunneled with playit.gg"
        write_instance_config(
            instance_dir,
            port=port,
            rcon_port=rcon_port,
            online=args.online,
            motd=motd,
            max_players=args.max_players,
            difficulty=args.difficulty,
            gamemode=args.gamemode,
        )
        created = True
        info(f"Created server at {instance_dir} on port {port}.")
    if created:
        for script, body in (
            (
                "start.sh",
                '#!/usr/bin/env bash\ncd "$(dirname "$0")" || exit 1\n'
                'exec ./pumpkin\n',
            ),
            (
                "stop.sh",
                '#!/usr/bin/env bash\ncd "$(dirname "$0")" || exit 1\n'
                'pid=$(cat server.pid 2>/dev/null) || exit 0\n'
                'kill "$pid" 2>/dev/null || true\n',
            ),
        ):
            path = instance_dir / script
            path.write_text(body)
            path.chmod(0o755)
    return created


def save_playit_info(instance_dir, info_data):
    path = instance_dir / "playit.json"
    path.write_text(json.dumps(info_data, indent=2) + "\n")
    if info_data and info_data.get("address"):
        (instance_dir / "PUBLIC_ADDRESS").write_text(info_data["address"] + "\n")


def load_playit_info(instance_dir):
    try:
        return json.loads((instance_dir / "playit.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None


def print_summary(instance_dir, config, public_info):
    lan = lan_ip()
    log()
    log("=" * 64)
    log(f" Server:  {instance_dir.name}")
    log(f" Path:    {instance_dir}")
    log(f" Java:    {config['port']}  (online_mode={str(config['online']).lower()})")
    log(f" Local:   localhost:{config['port']}")
    log(f" LAN:     {lan}:{config['port']}")
    if public_info and public_info.get("address"):
        log(f" Playit:  {public_info['address']}")
        if public_info.get("assigned_srv"):
            log(f" SRV:     {public_info['assigned_srv']}")
    else:
        log(" Playit:  not active (use --no-playit to skip)")
    log(f" RCON:    127.0.0.1:{config['rcon_port']}")
    log("=" * 64)
    log()


def cmd_up(args):
    instance_dir = instance_from_args(args)
    ensure_instance(args, instance_dir)
    config = read_instance_config(instance_dir)
    if args.port and args.port != config["port"]:
        info(
            f"Instance already uses port {config['port']}; ignoring --port {args.port}."
        )
    start_server(instance_dir, config["port"])
    public_info = load_playit_info(instance_dir)
    if not args.no_playit:
        secret = resolve_secret(args.secret)
        start_playit(secret)
        name = args.playit_name or f"pumpkin-{instance_dir.name}"
        public_info = ensure_tunnel(secret, config["port"], name)
        if public_info:
            save_playit_info(instance_dir, public_info)
    print_summary(instance_dir, config, public_info)
    return 0


def cmd_start(args):
    instance_dir = instance_from_args(args)
    if not (instance_dir / "pumpkin.toml").exists():
        die(f"no server found at {instance_dir}; run `pumpkin-auto` first")
    config = read_instance_config(instance_dir)
    start_server(instance_dir, config["port"])
    print_summary(instance_dir, config, load_playit_info(instance_dir))
    return 0


def cmd_stop(args):
    instance_dir = instance_from_args(args)
    stop_server(instance_dir)
    return 0


def cmd_status(args):
    instance_dir = instance_from_args(args)
    if not (instance_dir / "pumpkin.toml").exists():
        die(f"no server found at {instance_dir}")
    config = read_instance_config(instance_dir)
    pid = find_server_pid(instance_dir)
    public_info = load_playit_info(instance_dir)
    log()
    log(f"Server: {instance_dir}")
    if pid:
        uptime, rss = process_info(pid)
        ram = f"{rss:.0f} MB" if rss is not None else "-"
        log(f"State:  RUNNING  pid={pid}  uptime={format_uptime(uptime)}  ram={ram}")
    else:
        log("State:  STOPPED")
    log(f"Java:   {config['port']}  online_mode={str(config['online']).lower()}")
    log(f"RCON:   127.0.0.1:{config['rcon_port']}")
    if public_info and public_info.get("address"):
        log(f"Playit: {public_info['address']}")
    else:
        log("Playit: not configured")
    log(f"Log:    {instance_dir / 'console.log'}")
    log()
    return 0


def cmd_list(args):
    dirs = []
    if DEFAULT_DIR.exists() and (DEFAULT_DIR / "pumpkin").exists():
        dirs.append(DEFAULT_DIR)
    if SERVERS_DIR.exists():
        for path in sorted(SERVERS_DIR.iterdir()):
            if path.is_dir() and (path / "pumpkin.toml").exists():
                dirs.append(path)
    if not dirs:
        info("No servers found. Run `pumpkin-auto` to create one.")
        return 0
    for path in dirs:
        try:
            config = read_instance_config(path)
        except Exception:
            continue
        pid = find_server_pid(path)
        state = "RUNNING" if pid else "stopped"
        public = load_playit_info(path)
        address = public.get("address") if public else ""
        log(
            f"{path.name:20s} {state:8s} port={config['port']:<5d} "
            f"{address or ''}"
        )
    return 0


def cmd_playit(args):
    instance_dir = instance_from_args(args)
    if not (instance_dir / "pumpkin.toml").exists():
        die(f"no server found at {instance_dir}")
    config = read_instance_config(instance_dir)
    secret = resolve_secret(args.secret)
    start_playit(secret)
    name = args.playit_name or f"pumpkin-{instance_dir.name}"
    public_info = ensure_tunnel(secret, config["port"], name)
    if public_info:
        save_playit_info(instance_dir, public_info)
    print_summary(instance_dir, config, public_info)
    return 0


def cmd_playit_stop(args):
    stop_playit()
    return 0


def cmd_playit_reset(args):
    stop_playit()
    try:
        SECRET_FILE.unlink()
    except OSError:
        pass
    info("playit.gg secret removed. The next run will ask you to link again.")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="pumpkin-auto",
        description="Build a Pumpkin Minecraft server and expose it through playit.gg.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="up",
        help="up (default), start, stop, status, list, playit, playit-stop, playit-reset",
    )
    parser.add_argument("name", nargs="?", help="server name (default: existing server or 'survival')")
    parser.add_argument("--dir", help="use a specific server directory")
    parser.add_argument("--port", type=int, help="Java port for a new server")
    parser.add_argument("--online", action="store_true", help="enable Mojang authentication")
    parser.add_argument("--no-playit", action="store_true", help="do not start playit.gg")
    parser.add_argument("--secret", help="playit.gg agent secret key")
    parser.add_argument("--playit-name", help="name for the playit tunnel")
    parser.add_argument("--motd", help="server MOTD")
    parser.add_argument("--max-players", type=int, default=20)
    parser.add_argument(
        "--difficulty",
        default="Normal",
        choices=["Peaceful", "Easy", "Normal", "Hard"],
    )
    parser.add_argument(
        "--gamemode",
        default="Survival",
        choices=["Survival", "Creative", "Adventure", "Spectator"],
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    known = {
        "up",
        "start",
        "stop",
        "status",
        "list",
        "playit",
        "playit-stop",
        "playit-reset",
    }
    if args.command not in known:
        if args.name is None:
            args.name = args.command
            args.command = "up"
        else:
            parser.error(f"unknown command: {args.command}")
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    commands = {
        "up": cmd_up,
        "start": cmd_start,
        "stop": cmd_stop,
        "status": cmd_status,
        "list": cmd_list,
        "playit": cmd_playit,
        "playit-stop": cmd_playit_stop,
        "playit-reset": cmd_playit_reset,
    }
    return commands[args.command](args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130)
    except BrokenPipeError:
        try:
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())
        except OSError:
            pass
        raise SystemExit(0)
