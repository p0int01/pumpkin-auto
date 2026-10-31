#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shlex
import shutil
import signal
import socket
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

HOME = Path.home()
APP_NAME = "pumpkin-auto"
STATE_DIR = HOME / ".config" / APP_NAME
CACHE_DIR = HOME / ".cache" / APP_NAME
DOWNLOADS_DIR = CACHE_DIR / "downloads"
SERVERS_DIR = HOME / "minecraft-servers"
SECRET_FILE = STATE_DIR / "playit.secret"
PLAYIT_SOCK = STATE_DIR / "playit.sock"
PLAYIT_LOG = STATE_DIR / "playit.log"
PLAYIT_BIN = HOME / ".local" / "bin" / "playit"
PLAYIT_VERSION = "v1.2.0"
PLAYIT_URL = (
    "https://github.com/playit-cloud/playit-agent/releases/download/"
    f"{PLAYIT_VERSION}/playit-linux-amd64"
)
API_BASE = "https://api.playit.gg"
TUNNELS_URL = "https://playit.gg/account/tunnels"
DEFAULT_VERSION = "1.21.11"
DEFAULT_TYPE = "paper"
DEFAULT_PROFILE = "max"
USER_AGENT = f"{APP_NAME}/2.0"
SERVER_TYPES = ("pumpkin", "paper", "fabric", "vanilla")
PROFILES = ("safe", "max", "none")

PUMPKIN_TAGS = {
    "1.21.11": "0.1.0-dev+26.2-26.45",
    "1.21.10": "0.1.0-dev+26.2-26.45",
    "1.21.9": "0.1.0-dev+26.2-26.45",
    "1.21.8": "0.1.0-dev+26.2-26.45",
    "26.1": "0.1.0-dev+26.2-26.45",
    "26.1.1": "0.1.0-dev+26.2-26.45",
    "26.1.2": "0.1.0-dev+26.2-26.45",
    "26.2": "0.1.0-dev+26.2-26.45",
    "26.3": "0.2.1+26.3-26.51",
}
PUMPKIN_LATEST = "0.2.1+26.3-26.51"

FABRIC_SAFE = [
    "fabric-api",
    "lithium",
    "ferrite-core",
    "krypton",
    "servercore",
    "clumps",
    "alternate-current",
    "moreculling",
    "packet-fixer",
    "ksyxis",
    "chunky",
    "spark",
]
FABRIC_MAX = [
    "c2me-fabric",
    "vmp-fabric",
    "threadtweak",
    "tt20",
]
PAPER_SAFE = ["chunky"]
PAPER_MAX = ["farm-limiter-applexial", "blockentitylimiter"]

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
view_distance = __VIEW_DISTANCE__
simulation_distance = __SIMULATION_DISTANCE__
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
view_distance = __VIEW_DISTANCE__
simulation_distance = __SIMULATION_DISTANCE__
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
    print(f"[{APP_NAME}] {message}", flush=True)


def warn(message):
    print(f"[{APP_NAME}] warning: {message}", file=sys.stderr, flush=True)


def die(message, code=1):
    print(f"[{APP_NAME}] error: {message}", file=sys.stderr, flush=True)
    raise SystemExit(code)


def ensure_dirs():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    SERVERS_DIR.mkdir(parents=True, exist_ok=True)


def http_json(url, payload=None, headers=None, method=None):
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(
        url, data=data, headers=request_headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise ApiError(f"HTTP {exc.code}: {body[:200]}")
    except Exception as exc:
        raise ApiError(str(exc))
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        raise ApiError(f"unexpected response: {body[:200]}")


def download(url, dest, label, sha256=None, sha1=None):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    info(f"Downloading {label}...")
    tmp = dest.with_name(dest.name + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            last_percent = -1
            last_mb = -1
            with open(tmp, "wb") as handle:
                while True:
                    chunk = response.read(1024 * 256)
                    if not chunk:
                        break
                    handle.write(chunk)
                    done += len(chunk)
                    if total:
                        percent = int(done * 100 / total)
                        if percent != last_percent:
                            print(
                                f"\r    {percent:3d}%  {human_size(done)} / {human_size(total)}",
                                end="",
                                flush=True,
                            )
                            last_percent = percent
                    else:
                        current_mb = done // (1024 * 1024)
                        if current_mb != last_mb:
                            print(
                                f"\r    {human_size(done)}",
                                end="",
                                flush=True,
                            )
                            last_mb = current_mb
            if total:
                print("\r" + " " * 64 + "\r", end="", flush=True)
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        raise ApiError(f"download failed: {exc}")
    if sha256:
        import hashlib

        digest = hashlib.sha256(tmp.read_bytes()).hexdigest()
        if digest.lower() != sha256.lower():
            tmp.unlink(missing_ok=True)
            raise ApiError(f"sha256 mismatch for {label}")
    elif sha1:
        import hashlib

        digest = hashlib.sha1(tmp.read_bytes()).hexdigest()
        if digest.lower() != sha1.lower():
            tmp.unlink(missing_ok=True)
            raise ApiError(f"sha1 mismatch for {label}")
    tmp.replace(dest)
    return dest


def cached_download(url, filename, label, sha256=None, sha1=None):
    return download(url, DOWNLOADS_DIR / filename, label, sha256=sha256, sha1=sha1)


def copy_or_link(source, dest):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() or dest.is_symlink():
        return dest
    try:
        os.link(source, dest)
    except OSError:
        shutil.copy2(source, dest)
    return dest


def port_is_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
        except OSError:
            return False
    return True


def find_free_port(start):
    port = start
    while port < 65535:
        if port_is_free(port):
            return port
        port += 1
    raise RuntimeError("no free port found")


def port_open(port, host="127.0.0.1", timeout=1.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def human_size(num):
    for unit in ("B", "KiB", "MiB", "GiB"):
        if abs(num) < 1024.0:
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} TiB"


def vanilla_server(version):
    manifest = http_json(
        "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
    )
    entry = next((v for v in manifest["versions"] if v["id"] == version), None)
    if not entry:
        raise ApiError(f"Minecraft version {version} not found")
    data = http_json(entry["url"])
    server = data.get("downloads", {}).get("server")
    if not server:
        raise ApiError(f"Minecraft {version} has no server download")
    return {
        "url": server["url"],
        "filename": f"server-{version}.jar",
        "sha1": server.get("sha1"),
        "size": server.get("size"),
    }


def paper_build(version):
    url = f"https://fill.papermc.io/v3/projects/paper/versions/{version}/builds"
    builds = http_json(url)
    if not builds:
        raise ApiError(f"Paper has no builds for {version}")
    stable = [b for b in builds if b.get("channel") == "STABLE"]
    build = max(stable or builds, key=lambda b: b.get("id", 0))
    downloads = build.get("downloads") or {}
    server = downloads.get("server:default") or next(iter(downloads.values()), None)
    if not server:
        raise ApiError(f"Paper build {build.get('id')} has no server download")
    return {
        "build": build.get("id"),
        "channel": build.get("channel"),
        "url": server["url"],
        "filename": server["name"],
        "sha256": (server.get("checksums") or {}).get("sha256"),
        "size": server.get("size"),
    }


def fabric_versions(version):
    loaders = http_json(f"https://meta.fabricmc.net/v2/versions/loader/{version}")
    if not loaders:
        raise ApiError(f"Fabric has no loader for {version}")
    loader = next((x for x in loaders if x.get("loader", {}).get("stable")), loaders[0])
    installer_list = http_json("https://meta.fabricmc.net/v2/versions/installer")
    installer = next((x for x in installer_list if x.get("stable")), installer_list[0])
    loader_version = loader["loader"]["version"]
    installer_version = installer["version"]
    url = (
        f"https://meta.fabricmc.net/v2/versions/loader/{version}/"
        f"{loader_version}/{installer_version}/server/jar"
    )
    return {
        "loader": loader_version,
        "installer": installer_version,
        "url": url,
        "filename": f"fabric-server-{version}-{loader_version}.jar",
    }


def pumpkin_binary(version):
    tag = PUMPKIN_TAGS.get(version, PUMPKIN_LATEST)
    encoded = urllib.parse.quote(tag, safe="")
    url = (
        f"https://github.com/Pumpkin-MC/Pumpkin/releases/download/"
        f"{encoded}/pumpkin-X64-Linux"
    )
    return {"tag": tag, "url": url, "filename": f"pumpkin-{tag}"}


def modrinth_version(slug, version, loader):
    query = urllib.parse.urlencode(
        {
            "game_versions": json.dumps([version]),
            "loaders": json.dumps([loader]),
        }
    )
    url = f"https://api.modrinth.com/v2/project/{slug}/version?{query}"
    try:
        versions = http_json(url)
    except ApiError:
        return None
    for entry in versions:
        files = entry.get("files") or []
        primary = next((f for f in files if f.get("primary")), files[0] if files else None)
        if primary:
            return {
                "slug": slug,
                "version": entry.get("version_number"),
                "filename": primary["filename"],
                "url": primary["url"],
                "sha1": (primary.get("hashes") or {}).get("sha1"),
                "size": primary.get("size"),
            }
    return None


def download_modrinth(slug, version, loader, dest_dir):
    entry = modrinth_version(slug, version, loader)
    if not entry:
        warn(f"{slug} has no {loader} build for {version}; skipping")
        return None
    dest = Path(dest_dir) / entry["filename"]
    try:
        cached_download(
            entry["url"],
            f"{loader}-{version}-{entry['filename']}",
            f"{slug} {entry['version']}",
            sha1=entry.get("sha1"),
        )
    except ApiError as exc:
        warn(f"could not download {slug}: {exc}")
        return None
    copy_or_link(DOWNLOADS_DIR / f"{loader}-{version}-{entry['filename']}", dest)
    return dest


def instance_path(name):
    if name:
        return SERVERS_DIR / name
    return SERVERS_DIR / "survival"


def meta_path(directory):
    return Path(directory) / "instance.json"


def load_meta(directory):
    path = meta_path(directory)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def save_meta(directory, meta):
    path = meta_path(directory)
    path.write_text(json.dumps(meta, indent=2) + "\n")
    path.chmod(0o600)


def list_instances():
    ensure_dirs()
    found = []
    for path in sorted(SERVERS_DIR.iterdir()):
        if path.is_dir() and meta_path(path).exists():
            meta = load_meta(path)
            if meta:
                found.append((path, meta))
    return found


def server_pid(directory):
    directory = Path(directory).resolve()
    pidfile = directory / "server.pid"
    if pidfile.exists():
        try:
            pid = int(pidfile.read_text().strip())
            if process_matches(pid, directory):
                return pid
        except (ValueError, OSError):
            pass
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if process_matches(pid, directory):
            return pid
    return None


def process_matches(pid, directory):
    proc_dir = Path("/proc") / str(pid)
    try:
        cwd = Path(os.readlink(proc_dir / "cwd"))
    except OSError:
        return False
    if cwd != directory:
        return False
    try:
        cmdline = (proc_dir / "cmdline").read_bytes().split(b"\0")
    except OSError:
        return False
    if not cmdline or not cmdline[0]:
        return False
    first = Path(cmdline[0].decode("utf-8", "replace")).name
    return first in ("java", "pumpkin") or "java" in first


def process_info(pid):
    proc_dir = Path("/proc") / str(pid)
    try:
        stat = (proc_dir / "stat").read_text().split()
        start_ticks = int(stat[21])
        uptime_ticks = int(Path("/proc/uptime").read_text().split()[0].replace(".", ""))
        hz = os.sysconf("SC_CLK_TCK")
        uptime = max(0.0, uptime_ticks / 100.0 - start_ticks / hz)
    except (OSError, ValueError, IndexError):
        uptime = 0.0
    rss = None
    try:
        for line in (proc_dir / "status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                rss = int(line.split()[1]) / 1024.0
                break
    except (OSError, ValueError):
        pass
    return uptime, rss


def format_uptime(seconds):
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def rcon_command(port, password, command, timeout=5.0):
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as sock:
        sock.settimeout(timeout)

        def send(packet_id, packet_type, body):
            payload = (
                struct.pack("<ii", packet_id, packet_type)
                + body.encode("utf-8")
                + b"\x00\x00"
            )
            sock.sendall(struct.pack("<i", len(payload)) + payload)

        def recv():
            raw = sock.recv(4)
            if len(raw) < 4:
                raise OSError("rcon closed")
            (length,) = struct.unpack("<i", raw)
            data = b""
            while len(data) < length:
                chunk = sock.recv(length - len(data))
                if not chunk:
                    raise OSError("rcon closed")
                data += chunk
            packet_id, packet_type = struct.unpack("<ii", data[:8])
            return packet_id, packet_type, data[8:-2].decode("utf-8", "replace")

        send(1, 3, password)
        _, _, _ = recv()
        send(2, 2, command)
        _, _, response = recv()
        return response


def server_rcon(meta):
    if not meta.get("rcon_port") or not meta.get("rcon_password"):
        return None
    try:
        return rcon_command(
            int(meta["rcon_port"]), meta["rcon_password"], "list", timeout=3.0
        )
    except OSError:
        return None


def stop_server(directory, timeout=40):
    directory = Path(directory)
    pid = server_pid(directory)
    if not pid:
        (directory / "server.pid").unlink(missing_ok=True)
        return False
    meta = load_meta(directory) or {}
    rcon = server_rcon(meta)
    if rcon is not None:
        try:
            rcon_command(int(meta["rcon_port"]), meta["rcon_password"], "stop", timeout=5.0)
        except OSError:
            pass
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not Path(f"/proc/{pid}").exists():
                (directory / "server.pid").unlink(missing_ok=True)
                return True
            time.sleep(0.5)
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.time() + 10
    while time.time() < deadline:
        if not Path(f"/proc/{pid}").exists():
            (directory / "server.pid").unlink(missing_ok=True)
            return True
        time.sleep(0.5)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    (directory / "server.pid").unlink(missing_ok=True)
    return True


def launch_server(directory, wait=False, timeout=240):
    directory = Path(directory).resolve()
    meta = load_meta(directory)
    if not meta:
        raise RuntimeError(f"no instance metadata in {directory}")
    pid = server_pid(directory)
    if pid:
        return pid
    start_script = directory / "start.sh"
    if not start_script.exists():
        raise RuntimeError(f"missing start.sh in {directory}")
    log_path = directory / "console.log"
    with open(log_path, "ab") as handle:
        process = subprocess.Popen(
            [str(start_script)],
            cwd=directory,
            stdout=handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    (directory / "server.pid").write_text(str(process.pid))
    if not wait:
        return process.pid
    deadline = time.time() + timeout
    port = int(meta["port"])
    while time.time() < deadline:
        if process.poll() is not None:
            (directory / "server.pid").unlink(missing_ok=True)
            raise RuntimeError(
                f"server exited during startup; see {log_path}"
            )
        if port_open(port):
            rcon_port = int(meta.get("rcon_port") or 0)
            if rcon_port:
                rcon_deadline = min(deadline, time.time() + 15)
                while time.time() < rcon_deadline:
                    if process.poll() is not None:
                        break
                    if port_open(rcon_port):
                        break
                    time.sleep(0.25)
            return process.pid
        time.sleep(0.5)
    raise RuntimeError(f"server did not open port {port}; see {log_path}")


def jvm_flags(memory_mb):
    return [
        f"-Xms{memory_mb}M",
        f"-Xmx{memory_mb}M",
        "-XX:+UseG1GC",
        "-XX:+ParallelRefProcEnabled",
        "-XX:MaxGCPauseMillis=200",
        "-XX:+UnlockExperimentalVMOptions",
        "-XX:+DisableExplicitGC",
        "-XX:+AlwaysPreTouch",
        "-XX:G1NewSizePercent=30",
        "-XX:G1MaxNewSizePercent=40",
        "-XX:G1HeapRegionSize=8M",
        "-XX:G1ReservePercent=20",
        "-XX:G1HeapWastePercent=5",
        "-XX:G1MixedGCCountTarget=4",
        "-XX:InitiatingHeapOccupancyPercent=15",
        "-XX:G1MixedGCLiveThresholdPercent=90",
        "-XX:G1RSetUpdatingPauseTimePercent=5",
        "-XX:SurvivorRatio=32",
        "-XX:+PerfDisableSharedMem",
        "-XX:MaxTenuringThreshold=1",
        "-Dusing.aikars.flags=https://mcflags.emc.gs",
        "-Daikars.new.flags=true",
    ]


def write_start_script(directory, meta):
    directory = Path(directory)
    flags = " ".join(shlex.quote(flag) for flag in jvm_flags(meta["memory_mb"]))
    if meta["type"] == "pumpkin":
        command = "exec ./pumpkin"
    elif meta["type"] == "fabric":
        command = f"exec java {flags} -jar fabric-server-launch.jar nogui"
    elif meta["type"] == "paper":
        command = f"exec java {flags} -jar paper.jar nogui"
    else:
        command = f"exec java {flags} -jar server.jar nogui"
    text = "#!/usr/bin/env bash\ncd \"$(dirname \"$0\")\"\n" + command + "\n"
    path = directory / "start.sh"
    path.write_text(text)
    path.chmod(0o755)


def write_eula(directory):
    path = Path(directory) / "eula.txt"
    path.write_text("eula=true\n")


def server_properties(meta):
    profile = meta.get("profile", DEFAULT_PROFILE)
    view = 8 if profile in ("safe", "max") else 12
    simulation = 6 if profile in ("safe", "max") else 8
    props = {
        "online-mode": "true" if meta["online"] else "false",
        "enforce-secure-profile": "true" if meta["online"] else "false",
        "server-port": str(meta["port"]),
        "server-ip": "",
        "motd": meta["motd"].replace("\n", "\\n"),
        "max-players": str(meta["max_players"]),
        "view-distance": str(view),
        "simulation-distance": str(simulation),
        "sync-chunk-writes": "false",
        "network-compression-threshold": "256",
        "entity-broadcast-range-percentage": "75",
        "max-tick-time": "60000",
        "spawn-protection": "0",
        "enable-status": "true",
        "enable-query": "false",
        "allow-flight": "false",
        "allow-nether": "true",
        "allow-end": "true",
        "hardcore": "false",
        "difficulty": meta["difficulty"].lower(),
        "gamemode": meta["gamemode"].lower(),
        "force-gamemode": "false",
        "pvp": "true",
        "enable-command-block": "false",
        "generate-structures": "true",
        "level-name": "world",
        "level-seed": "",
        "spawn-animals": "true",
        "spawn-monsters": "true",
        "spawn-npcs": "true",
        "white-list": "false",
        "enable-rcon": "true",
        "rcon.port": str(meta["rcon_port"]),
        "rcon.password": meta["rcon_password"],
        "broadcast-rcon-to-ops": "false",
        "op-permission-level": "4",
        "function-permission-level": "2",
    }
    return props


def write_server_properties(directory, meta):
    path = Path(directory) / "server.properties"
    text = "\n".join(f"{key}={value}" for key, value in server_properties(meta).items())
    path.write_text(text + "\n")
    path.chmod(0o600)


def write_bukkit_yml(directory):
    path = Path(directory) / "bukkit.yml"
    path.write_text(
        """settings:
  allow-end: true
  warn-on-overload: true
  permissions-file: permissions.yml
  update-folder: update
  plugin-profiling: false
  connection-throttle: 4000
  query-plugins: true
  deprecated-verbose: default
  shutdown-message: Server closed
  minimum-api: none
  use-map-color-cache: true
spawn-limits:
  monsters: 50
  animals: 8
  water-animals: 3
  water-ambient: 1
  water-underground-creature: 3
  axolotls: 3
  ambient: 1
chunk-gc:
  period-in-ticks: 600
ticks-per:
  animal-spawns: 400
  monster-spawns: 4
  water-spawns: 16
  water-ambient-spawns: 16
  water-underground-creature-spawns: 16
  axolotl-spawns: 16
  ambient-spawns: 16
  autosave: 6000
aliases: now-in-commands.yml
"""
    )


def write_spigot_yml(directory, meta):
    profile = meta.get("profile", DEFAULT_PROFILE)
    activation = 24 if profile == "max" else 32
    tracking = 64 if profile == "max" else 96
    merge = 2.5 if profile in ("safe", "max") else 0.5
    path = Path(directory) / "spigot.yml"
    path.write_text(
        f"""settings:
  bungeecord: false
  save-user-cache-on-stop-only: false
  sample-count: 12
  player-shuffle: 0
  user-cache-size: 1000
  moved-wrongly-threshold: 0.0625
  moved-too-quickly-multiplier: 10.0
  timeout-time: 60
  restart-on-crash: true
  restart-script: ./start.sh
  netty-threads: 4
  debug: false
world-settings:
  default:
    view-distance: default
    simulation-distance: default
    mob-spawn-range: 6
    merge-radius:
      item: {merge}
      exp: 3.0
    item-despawn-rate: 6000
    arrow-despawn-rate: 1200
    trident-despawn-rate: 1200
    nerf-spawner-mobs: false
    entity-activation-range:
      animals: {activation}
      monsters: {activation}
      raiders: 48
      misc: 16
      water: 16
      villagers: {activation}
      flying-monsters: {activation}
    entity-tracking-range:
      players: 96
      animals: {tracking}
      monsters: {tracking}
      misc: {tracking}
      other: {tracking}
    ticks-per:
      hopper-transfer: 8
      hopper-check: 8
"""
    )


def write_paper_configs(directory, meta):
    config_dir = Path(directory) / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "paper-global.yml").write_text(
        """chunk-loading-advanced:
  auto-config-send-distance: true
  player-max-concurrent-chunk-generates: 8
  player-max-concurrent-chunk-loads: 4
chunk-loading-basic:
  player-max-chunk-generate-rate: -1.0
  player-max-chunk-load-rate: 100.0
  player-max-chunk-send-rate: 75.0
chunk-system:
  io-threads: -1
  worker-threads: -1
"""
    )
    (config_dir / "paper-world-defaults.yml").write_text(
        """chunks:
  auto-save-interval: 6000
  max-auto-save-chunks-per-tick: 24
  delay-chunk-unloads-by: 10s
collisions:
  max-entity-collisions: 2
entities:
  spawning:
    per-player-mob-spawns: true
    despawn-ranges:
      monster:
        hard: 96
        soft: 32
      creature:
        hard: 96
        soft: 32
"""
    )


def write_pumpkin_config(directory, meta):
    profile = meta.get("profile", DEFAULT_PROFILE)
    view = 8 if profile in ("safe", "max") else 12
    simulation = 6 if profile in ("safe", "max") else 8
    values = {
        "__SEED__": str(secrets.randbits(63)),
        "__DIFFICULTY__": meta["difficulty"],
        "__GAMEMODE__": meta["gamemode"],
        "__PORT__": str(meta["port"]),
        "__RCON_PORT__": str(meta["rcon_port"]),
        "__RCON_PASSWORD__": meta["rcon_password"],
        "__ONLINE__": "true" if meta["online"] else "false",
        "__MAX_PLAYERS__": str(meta["max_players"]),
        "__MOTD__": meta["motd"].replace('"', "'"),
        "__VIEW_DISTANCE__": str(view),
        "__SIMULATION_DISTANCE__": str(simulation),
    }
    text = CONFIG_TEMPLATE
    for token, value in values.items():
        text = text.replace(token, value)
    path = Path(directory) / "pumpkin.toml"
    path.write_text(text)
    path.chmod(0o600)


def install_pumpkin(directory, meta):
    binary = pumpkin_binary(meta["version"])
    cached = cached_download(
        binary["url"], binary["filename"], f"Pumpkin {binary['tag']}"
    )
    binary_path = copy_or_link(cached, Path(directory) / "pumpkin")
    binary_path.chmod(0o755)
    write_pumpkin_config(directory, meta)
    write_start_script(directory, meta)
    meta["pumpkin_tag"] = binary["tag"]
    meta["jar"] = "pumpkin"


def install_vanilla(directory, meta):
    server = vanilla_server(meta["version"])
    cached = cached_download(
        server["url"],
        server["filename"],
        f"Vanilla {meta['version']}",
        sha1=server.get("sha1"),
    )
    copy_or_link(cached, Path(directory) / "server.jar")
    write_eula(directory)
    write_server_properties(directory, meta)
    write_start_script(directory, meta)
    meta["jar"] = "server.jar"


def install_paper(directory, meta):
    build = paper_build(meta["version"])
    cached = cached_download(
        build["url"],
        build["filename"],
        f"Paper {meta['version']} build {build['build']}",
        sha256=build.get("sha256"),
    )
    copy_or_link(cached, Path(directory) / "paper.jar")
    write_eula(directory)
    write_server_properties(directory, meta)
    write_bukkit_yml(directory)
    write_spigot_yml(directory, meta)
    write_paper_configs(directory, meta)
    install_paper_plugins(directory, meta)
    write_start_script(directory, meta)
    meta["paper_build"] = build["build"]
    meta["jar"] = "paper.jar"


def install_fabric(directory, meta):
    fabric = fabric_versions(meta["version"])
    cached = cached_download(
        fabric["url"],
        fabric["filename"],
        f"Fabric loader {fabric['loader']}",
    )
    copy_or_link(cached, Path(directory) / "fabric-server-launch.jar")
    write_eula(directory)
    write_server_properties(directory, meta)
    install_fabric_mods(directory, meta)
    write_start_script(directory, meta)
    meta["fabric_loader"] = fabric["loader"]
    meta["jar"] = "fabric-server-launch.jar"


def install_paper_plugins(directory, meta):
    profile = meta.get("profile", DEFAULT_PROFILE)
    if profile == "none":
        return []
    plugins = list(PAPER_SAFE)
    if profile == "max":
        plugins += PAPER_MAX
    dest = Path(directory) / "plugins"
    dest.mkdir(parents=True, exist_ok=True)
    installed = []
    for slug in plugins:
        result = download_modrinth(slug, meta["version"], "paper", dest)
        if result:
            installed.append(result.name)
    meta["plugins"] = installed
    return installed


def install_fabric_mods(directory, meta):
    profile = meta.get("profile", DEFAULT_PROFILE)
    if profile == "none":
        return []
    mods = list(FABRIC_SAFE)
    if profile == "max":
        mods += FABRIC_MAX
    dest = Path(directory) / "mods"
    dest.mkdir(parents=True, exist_ok=True)
    installed = []
    for slug in mods:
        result = download_modrinth(slug, meta["version"], "fabric", dest)
        if result:
            installed.append(result.name)
    meta["mods"] = installed
    return installed


def create_instance(
    name,
    server_type=DEFAULT_TYPE,
    version=DEFAULT_VERSION,
    port=None,
    online=False,
    profile=DEFAULT_PROFILE,
    motd=None,
    max_players=20,
    difficulty="Normal",
    gamemode="Survival",
    memory_mb=4096,
    playit_enabled=True,
    directory=None,
):
    ensure_dirs()
    if server_type not in SERVER_TYPES:
        raise ValueError(f"unknown server type: {server_type}")
    if profile not in PROFILES:
        raise ValueError(f"unknown optimization profile: {profile}")
    if directory is None:
        directory = instance_path(name)
    else:
        directory = Path(directory).expanduser().resolve()
        name = name or directory.name
    if meta_path(directory).exists():
        raise RuntimeError(f"server '{name}' already exists at {directory}")
    if directory.exists() and any(directory.iterdir()):
        raise RuntimeError(f"directory {directory} is not empty")
    directory.mkdir(parents=True, exist_ok=True)
    if port is None:
        port = find_free_port(25565)
    elif not port_is_free(port):
        raise RuntimeError(f"port {port} is already in use")
    rcon_port = find_free_port(port + 10)
    meta = {
        "name": name or directory.name,
        "type": server_type,
        "version": version,
        "port": port,
        "rcon_port": rcon_port,
        "rcon_password": secrets.token_hex(8),
        "online": bool(online),
        "profile": profile,
        "motd": motd or f"A {server_type} server, tunneled with playit.gg",
        "max_players": int(max_players),
        "difficulty": difficulty,
        "gamemode": gamemode,
        "memory_mb": int(memory_mb),
        "playit_enabled": bool(playit_enabled),
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    save_meta(directory, meta)
    try:
        if server_type == "pumpkin":
            install_pumpkin(directory, meta)
        elif server_type == "paper":
            install_paper(directory, meta)
        elif server_type == "fabric":
            install_fabric(directory, meta)
        else:
            install_vanilla(directory, meta)
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    save_meta(directory, meta)
    return directory, meta


def save_secret(secret):
    ensure_dirs()
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
    headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
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
    raise ApiError(str(data))


def claim_playit():
    code = secrets.token_hex(5)
    url = f"https://playit.gg/claim/{code}"
    info("playit.gg needs to be linked to your account (one time only).")
    info("Open this URL and approve the agent:")
    log()
    log(f"  {url}")
    log()
    info("Waiting for approval (Ctrl+C to cancel)...")
    api_call(
        "/claim/setup",
        {"code": code, "agent_type": "assignable", "version": f"playit {PLAYIT_VERSION.lstrip('v')}"},
    )
    deadline = time.time() + 600
    last_status = None
    while time.time() < deadline:
        try:
            data = api_call("/claim/setup", {"code": code, "agent_type": "assignable", "version": f"playit {PLAYIT_VERSION.lstrip('v')}"})
        except ApiError:
            data = None
        if data is not None:
            status = data if isinstance(data, str) else data.get("status")
            if status and status != last_status:
                info(f"status: {status}")
                last_status = status
            if status == "UserAccepted":
                break
            if status == "UserRejected":
                die("playit.gg link was rejected")
        time.sleep(2)
    else:
        die("timed out waiting for playit.gg approval")
    try:
        result = api_call("/claim/exchange", {"code": code})
    except ApiError as exc:
        die(f"playit.gg link failed: {exc}")
    secret = result.get("secret_key") if isinstance(result, dict) else None
    if not secret:
        die("playit.gg did not return a secret key")
    save_secret(secret)
    info("playit.gg linked.")
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
    cached = cached_download(PLAYIT_URL, f"playit-{PLAYIT_VERSION}", f"playit.gg agent {PLAYIT_VERSION}")
    copy_or_link(cached, PLAYIT_BIN)
    PLAYIT_BIN.chmod(0o755)


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
        if Path(cmdline[0].decode("utf-8", "replace")).name != "playit":
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
        return pid
    other = find_any_playit_pid()
    if other:
        info(f"Another playit.gg agent is already running (PID {other}); using it.")
        return other
    save_secret(secret)
    ensure_dirs()
    with open(PLAYIT_LOG, "ab") as handle:
        process = subprocess.Popen(
            [
                str(PLAYIT_BIN),
                "--secret-path",
                str(SECRET_FILE),
                "--socket-path",
                str(PLAYIT_SOCK),
                "--log-path",
                str(PLAYIT_LOG),
            ],
            stdout=handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    time.sleep(1.5)
    if process.poll() is not None:
        raise RuntimeError(f"playit.gg agent exited; see {PLAYIT_LOG}")
    info(f"Started playit.gg agent (PID {process.pid}).")
    return process.pid


def stop_playit():
    pid = find_playit_pid()
    if not pid:
        info("playit.gg agent is not running.")
        return False
    info(f"Stopping playit.gg agent (PID {pid})...")
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    deadline = time.time() + 10
    while time.time() < deadline:
        if not Path(f"/proc/{pid}").exists():
            info("playit.gg agent stopped.")
            return True
        time.sleep(0.3)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    info("playit.gg agent stopped.")
    return True


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
    return data.get("tunnels", []) if isinstance(data, dict) else []


def tunnel_origin(tunnel):
    origin = tunnel.get("origin") or {}
    return origin.get("data") or {}


def find_tunnel(tunnels, port, agent_id=None):
    for tunnel in tunnels:
        if tunnel.get("port_type") not in (None, "tcp"):
            continue
        data = tunnel_origin(tunnel)
        if int(data.get("local_port") or -1) != int(port):
            continue
        if agent_id and data.get("agent_id") and data.get("agent_id") != agent_id:
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
            if "NotAllowedWithReadOnly" in str(exc):
                log("The saved playit.gg agent key is read-only, so new tunnels")
                log("must be created in the dashboard. Existing tunnels are reused.")
            log("Create it once in the playit.gg dashboard:")
            log(f"  {TUNNELS_URL}")
            log("  Tunnel type: Minecraft Java")
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


def resolve_instance(args):
    if getattr(args, "dir", None):
        return Path(args.dir).expanduser().resolve()
    name = getattr(args, "name", None)
    return instance_path(name)


def print_summary(directory, meta):
    pid = server_pid(directory)
    log()
    log("=" * 64)
    log(f" Server:  {meta['name']}")
    log(f" Type:    {meta['type']} {meta['version']}  profile={meta.get('profile', 'none')}")
    log(f" Path:    {directory}")
    log(f" Java:    {meta['port']}  (online_mode={str(meta['online']).lower()})")
    log(f" Local:   localhost:{meta['port']}")
    log(f" LAN:     {lan_ip()}:{meta['port']}")
    if pid:
        log(f" State:   RUNNING  pid={pid}")
    else:
        log(" State:   STOPPED")
    playit = meta.get("playit") or {}
    if playit.get("address"):
        log(f" Playit:  {playit['address']}")
    else:
        log(" Playit:  not configured")
    log(f" RCON:    127.0.0.1:{meta['rcon_port']}")
    log("=" * 64)
    log()


def cmd_create(args):
    directory, meta = create_instance(
        name=args.name or "survival",
        server_type=args.type,
        version=args.version,
        port=args.port,
        online=args.online,
        profile=args.profile,
        motd=args.motd,
        max_players=args.max_players,
        difficulty=args.difficulty,
        gamemode=args.gamemode,
        memory_mb=args.memory,
        playit_enabled=not args.no_playit,
        directory=Path(args.dir).expanduser().resolve() if args.dir else None,
    )
    info(f"Created {meta['type']} {meta['version']} server at {directory}.")
    print_summary(directory, meta)
    return 0


def cmd_up(args):
    directory = resolve_instance(args)
    if not meta_path(directory).exists():
        directory, meta = create_instance(
            name=args.name or "survival",
            server_type=args.type,
            version=args.version,
            port=args.port,
            online=args.online,
            profile=args.profile,
            motd=args.motd,
            max_players=args.max_players,
            difficulty=args.difficulty,
            gamemode=args.gamemode,
            memory_mb=args.memory,
            playit_enabled=not args.no_playit,
            directory=Path(args.dir).expanduser().resolve() if args.dir else None,
        )
    meta = load_meta(directory)
    if args.port and args.port != meta["port"]:
        info(f"Instance already uses port {meta['port']}; ignoring --port {args.port}.")
    pid = server_pid(directory)
    if pid:
        info(f"Server already running (PID {pid}).")
    else:
        info("Starting server...")
        launch_server(directory, wait=True)
        info(f"Server is listening on 0.0.0.0:{meta['port']}.")
    if not args.no_playit and meta.get("playit_enabled", True):
        secret = resolve_secret(args.secret)
        start_playit(secret)
        name = args.playit_name or f"mc-{meta['name']}"
        public_info = ensure_tunnel(secret, meta["port"], name)
        if public_info:
            meta["playit"] = public_info
            save_meta(directory, meta)
    print_summary(directory, meta)
    return 0


def cmd_start(args):
    directory = resolve_instance(args)
    meta = load_meta(directory)
    if not meta:
        die(f"no server found at {directory}; run `pumpkin-auto create` first")
    pid = server_pid(directory)
    if pid:
        info(f"Server already running (PID {pid}).")
    else:
        info("Starting server...")
        launch_server(directory, wait=True)
        info(f"Server is listening on 0.0.0.0:{meta['port']}.")
    print_summary(directory, meta)
    return 0


def cmd_stop(args):
    directory = resolve_instance(args)
    meta = load_meta(directory)
    if not meta:
        die(f"no server found at {directory}")
    if stop_server(directory):
        info("Server stopped.")
    else:
        info("Server was not running.")
    return 0


def cmd_restart(args):
    cmd_stop(args)
    time.sleep(1)
    return cmd_start(args)


def cmd_status(args):
    directory = resolve_instance(args)
    meta = load_meta(directory)
    if not meta:
        die(f"no server found at {directory}")
    print_summary(directory, meta)
    return 0


def cmd_list(args):
    instances = list_instances()
    if not instances:
        info("No servers found. Run `pumpkin-auto create <name>` or `pumpkin-auto ui`.")
        return 0
    log(f"{'NAME':20} {'TYPE':8} {'VERSION':10} {'PORT':6} {'STATE':9} PUBLIC")
    for directory, meta in instances:
        pid = server_pid(directory)
        state = "RUNNING" if pid else "STOPPED"
        address = (meta.get("playit") or {}).get("address", "-")
        log(
            f"{meta['name']:20} {meta['type']:8} {meta['version']:10} "
            f"{meta['port']:<6} {state:9} {address}"
        )
    return 0


def cmd_delete(args):
    directory = resolve_instance(args)
    meta = load_meta(directory)
    if not meta:
        die(f"no server found at {directory}")
    if not args.yes:
        answer = input(f"Delete {meta['name']} at {directory}? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            info("Cancelled.")
            return 1
    stop_server(directory)
    shutil.rmtree(directory)
    info(f"Deleted {meta['name']}.")
    return 0


def cmd_logs(args):
    directory = resolve_instance(args)
    if not meta_path(directory).exists():
        die(f"no server found at {directory}")
    log_path = directory / "console.log"
    if not log_path.exists():
        die(f"no log yet at {log_path}")
    subprocess.run(["tail", "-n", str(args.lines), "-f", str(log_path)])
    return 0


def cmd_console(args):
    directory = resolve_instance(args)
    meta = load_meta(directory)
    if not meta:
        die(f"no server found at {directory}")
    if not server_pid(directory):
        die("server is not running")
    info("Type a command, or 'exit' to quit.")
    while True:
        try:
            command = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not command or command.lower() in ("exit", "quit"):
            break
        try:
            response = rcon_command(
                int(meta["rcon_port"]), meta["rcon_password"], command
            )
            log(response)
        except OSError as exc:
            warn(f"rcon failed: {exc}")
            break
    return 0


def cmd_players(args):
    directory = resolve_instance(args)
    meta = load_meta(directory)
    if not meta:
        die(f"no server found at {directory}")
    if not server_pid(directory):
        die("server is not running")
    try:
        response = rcon_command(
            int(meta["rcon_port"]), meta["rcon_password"], "list"
        )
        log(response)
    except OSError as exc:
        die(f"rcon failed: {exc}")
    return 0


def cmd_playit(args):
    directory = resolve_instance(args)
    meta = load_meta(directory)
    if not meta:
        die(f"no server found at {directory}")
    secret = resolve_secret(args.secret)
    start_playit(secret)
    name = args.playit_name or f"mc-{meta['name']}"
    public_info = ensure_tunnel(secret, meta["port"], name)
    if public_info:
        meta["playit"] = public_info
        save_meta(directory, meta)
    print_summary(directory, meta)
    return 0


def cmd_playit_stop(args):
    stop_playit()
    return 0


def cmd_playit_reset(args):
    stop_playit()
    SECRET_FILE.unlink(missing_ok=True)
    info("playit.gg secret removed. The next run will ask you to link again.")
    return 0


def cmd_pregen(args):
    directory = resolve_instance(args)
    meta = load_meta(directory)
    if not meta:
        die(f"no server found at {directory}")
    if meta["type"] not in ("paper", "fabric"):
        die("pre-generation is only available for Paper and Fabric (Chunky)")
    if not server_pid(directory):
        die("server must be running to start pre-generation")
    commands = [
        f"chunky radius {args.radius}",
        f"chunky center {args.x} {args.z}",
        "chunky start",
    ]
    for command in commands:
        try:
            response = rcon_command(
                int(meta["rcon_port"]), meta["rcon_password"], command
            )
            log(f"> {command}")
            if response:
                log(response)
        except OSError as exc:
            die(f"rcon failed: {exc}")
    info("Pre-generation started. Check progress with: pumpkin-auto console <name>")
    return 0


def cmd_ui(args):
    from ui import run_ui

    run_ui(getattr(args, "plain", False))
    return 0


def cmd_versions(args):
    log(f"Supported types: {', '.join(SERVER_TYPES)}")
    log(f"Default version: {DEFAULT_VERSION}")
    log("Pumpkin mappings:")
    for version, tag in sorted(PUMPKIN_TAGS.items()):
        log(f"  {version:10} {tag}")
    log(f"  other      {PUMPKIN_LATEST} (latest)")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="pumpkin-auto",
        description="Build optimized Minecraft servers and expose them with playit.gg.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="up",
        help="up (default), create, start, stop, restart, status, list, delete, "
        "logs, console, players, playit, playit-stop, playit-reset, pregen, "
        "versions, ui",
    )
    parser.add_argument("name", nargs="?", help="server name (default: survival)")
    parser.add_argument("--dir", help="use a specific server directory")
    parser.add_argument("--type", choices=SERVER_TYPES, default=DEFAULT_TYPE)
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument("--port", type=int)
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--no-playit", action="store_true")
    parser.add_argument("--secret")
    parser.add_argument("--playit-name")
    parser.add_argument("--motd")
    parser.add_argument("--max-players", type=int, default=20)
    parser.add_argument(
        "--difficulty",
        choices=("Peaceful", "Easy", "Normal", "Hard"),
        default="Normal",
    )
    parser.add_argument(
        "--gamemode",
        choices=("Survival", "Creative", "Adventure", "Spectator"),
        default="Survival",
    )
    parser.add_argument(
        "--profile",
        choices=PROFILES,
        default=DEFAULT_PROFILE,
        help="optimization profile: safe, max, or none",
    )
    parser.add_argument("--memory", type=int, default=4096, help="JVM memory in MiB")
    parser.add_argument("--yes", action="store_true", help="skip confirmation")
    parser.add_argument(
        "--plain", action="store_true", help="use the plain text UI"
    )
    parser.add_argument("--lines", type=int, default=200, help="log lines to show")
    parser.add_argument("--radius", type=int, default=1000, help="pregen radius")
    parser.add_argument("--x", type=int, default=0)
    parser.add_argument("--z", type=int, default=0)
    return parser


def main():
    ensure_dirs()
    parser = build_parser()
    args = parser.parse_args()
    command = args.command
    if command in ("up", "create", "start", "stop", "restart", "status", "list",
                   "delete", "logs", "console", "players", "playit",
                   "playit-stop", "playit-reset", "pregen", "versions", "ui"):
        pass
    elif args.name is None:
        args.name = command
        command = "up"
    commands = {
        "up": cmd_up,
        "create": cmd_create,
        "start": cmd_start,
        "stop": cmd_stop,
        "restart": cmd_restart,
        "status": cmd_status,
        "list": cmd_list,
        "delete": cmd_delete,
        "logs": cmd_logs,
        "console": cmd_console,
        "players": cmd_players,
        "playit": cmd_playit,
        "playit-stop": cmd_playit_stop,
        "playit-reset": cmd_playit_reset,
        "pregen": cmd_pregen,
        "versions": cmd_versions,
        "ui": cmd_ui,
    }
    if command not in commands:
        parser.error(f"unknown command: {command}")
    return commands[command](args)


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
    except (ApiError, RuntimeError, ValueError) as exc:
        die(str(exc))
