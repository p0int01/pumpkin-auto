# pumpkin-auto

Build and manage optimized Minecraft servers from the terminal.

`pumpkin-auto` supports **Paper**, **Fabric**, **Vanilla**, and **Pumpkin** servers. It downloads the server software, writes tuned configuration, starts and stops servers, provides RCON console access, and can expose servers through **playit.gg**. It includes both a full-screen terminal UI and a plain-text menu fallback.

It is designed for Linux, uses only the Python standard library, and keeps each server in its own directory with its own logs, PID file, RCON password, and metadata.

## Table of Contents

- [Features](#features)
- [Supported Server Types](#supported-server-types)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Terminal UI](#terminal-ui)
- [CLI Reference](#cli-reference)
- [Server Types and Optimization Profiles](#server-types-and-optimization-profiles)
- [playit.gg](#playitgg)
- [Instance Layout](#instance-layout)
- [Networking](#networking)
- [Security and Legal Notes](#security-and-legal-notes)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [Development and Testing](#development-and-testing)
- [Contributing](#contributing)
- [License](#license)

## Features

- Four server types: Paper, Fabric, Vanilla, and Pumpkin
- Optimization profiles: `safe`, `max`, and `none`
- Full-screen terminal UI with numbered menus and guided choices
- Plain-text UI fallback for terminals where curses does not work
- CLI for scripting and automation
- Automatic server downloads with checksum verification where available
- Cached downloads shared between servers
- Tuned JVM flags, `server.properties`, Paper/Spigot configs, and Pumpkin config
- RCON console, player list, and Chunky pre-generation
- Optional playit.gg tunnel setup and reuse
- Per-instance metadata, logs, PID tracking, and safe shutdown
- No Python packages required beyond the standard library

## Supported Server Types

| Type | Runtime | Server file | Optimization content |
| --- | --- | --- | --- |
| `paper` | Java | `paper.jar` | Chunky; `max` adds FarmLimiter and BlockEntityLimiter |
| `fabric` | Java | `fabric-server-launch.jar` | Fabric API and performance mods; `max` adds more aggressive mods |
| `vanilla` | Java | `server.jar` | Tuned server properties and JVM flags only |
| `pumpkin` | Native binary | `pumpkin` | Tuned `pumpkin.toml` and server settings only |

## Requirements

- Linux
- Python 3.9 or newer
- Java 21 or newer for Minecraft 1.21.x Java servers
- Bash and standard Linux utilities such as `tail`
- Internet access for the first download of server software, mods, plugins, or the playit.gg agent
- A playit.gg account only if you want a public tunnel

Pumpkin is a native binary and does not require Java.

Tested with Python 3.14.7 and OpenJDK 21.0.12.1.

## Installation

### 1. Get the project

Clone the repository:

```bash
git clone https://github.com/p0int01/pumpkin-auto.git "$HOME/pumpkin-auto"
cd "$HOME/pumpkin-auto"
```
You can also download and extract the repository ZIP from GitHub.

### 2. Make the Python files executable

```bash
chmod +x pumpkin_auto.py ui.py
```

### 3. Create the launchers

The launchers must point to the real files in the repository. Do not use symlinks, because `ui.py` imports `pumpkin_auto` from its own directory.

```bash
mkdir -p "$HOME/.local/bin"

cat > "$HOME/.local/bin/pumpkin-auto" <<'EOF'
#!/usr/bin/env bash
exec python3 "$HOME/pumpkin-auto/pumpkin_auto.py" "$@"
EOF

cat > "$HOME/.local/bin/pumpkin-ui" <<'EOF'
#!/usr/bin/env bash
exec python3 "$HOME/pumpkin-auto/ui.py" "$@"
EOF

chmod +x "$HOME/.local/bin/pumpkin-auto" "$HOME/.local/bin/pumpkin-ui"
```

If you cloned the project somewhere other than `$HOME/pumpkin-auto`, update the paths in both launchers.

### 4. Ensure `~/.local/bin` is on your PATH

Add this to your shell profile if needed:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Then reload your shell:

```bash
source "$HOME/.bashrc"
```

### 5. Verify the installation

```bash
pumpkin-auto versions
pumpkin-auto --help
pumpkin-ui --plain
```

The plain UI is a good first check because it does not depend on curses terminal support. Press `7` to quit.

### Run without installing

You can run directly from the repository directory:

```bash
cd "$HOME/pumpkin-auto"
python3 pumpkin_auto.py --help
python3 pumpkin_auto.py versions
python3 ui.py --plain
```

Run `ui.py` from the repository directory, or use the launcher, so Python can find `pumpkin_auto.py`.

### Upgrade

```bash
cd "$HOME/pumpkin-auto"
git pull
```

There are no pip dependencies to reinstall. Existing servers and the launchers continue to work.

### Uninstall

Remove the launchers:

```bash
rm -f "$HOME/.local/bin/pumpkin-auto" "$HOME/.local/bin/pumpkin-ui"
```

Remove the project:

```bash
rm -rf "$HOME/pumpkin-auto"
```

Optionally remove application state and caches:

```bash
rm -rf "$HOME/.config/pumpkin-auto" "$HOME/.cache/pumpkin-auto"
```

Deleting servers is destructive. Only remove them when you mean to:

```bash
rm -rf "$HOME/minecraft-servers"
```

## Quick Start

### Use the UI

```bash
pumpkin-ui
```

Or use the plain-text UI:

```bash
pumpkin-ui --plain
```

### Use the CLI

Create and start a Paper server with the maximum optimization profile:

```bash
pumpkin-auto create survival --type paper --profile max
pumpkin-auto start survival
pumpkin-auto status survival
```

Running `pumpkin-auto` with no arguments is the same as `pumpkin-auto up`. It creates and starts a server named `survival` on the first free port starting at `25565`, then configures playit.gg unless `--no-playit` is used:

```bash
pumpkin-auto
```

For a local-only server without playit.gg:

```bash
pumpkin-auto up survival --no-playit
```

The first create or start may take time while server software, plugins, mods, or the playit.gg agent are downloaded.

## Terminal UI

Launch the full-screen UI:

```bash
pumpkin-ui
# or
pumpkin-auto ui
```

The main menu provides:

1. Create a server
2. Manage servers
3. Start a server
4. Stop a server
5. Delete a server
6. playit.gg setup
7. Quit

If the full-screen UI does not appear, use the plain menu:

```bash
pumpkin-ui --plain
# or
pumpkin-auto ui --plain
```

The plain menu uses simple numbered prompts and does not use the full-screen curses interface. It is selected automatically when `TERM` is missing or set to `dumb`, or when curses cannot start.

### Create wizard

The create screen starts on **Type** and shows numbered choices:

- Type: `1=paper`, `2=fabric`, `3=vanilla`, `4=pumpkin`
- Optimization: `1=max`, `2=safe`, `3=none`
- Online mode: `1=off`, `2=on`
- playit.gg: `1=on`, `2=off`
- Start after create: `1=on`, `2=off`

Use `Up`/`Down` or `j`/`k` to move between fields. Press `Enter` to edit text fields or toggle choices. Press `Esc` to cancel. The terminal must be at least **60x16**; **80x24** or larger is recommended.

### Manage dashboard

The dashboard shows server state, ports, player counts, paths, uptime, and memory usage.

| Key | Action |
| --- | --- |
| `Up` / `Down` or `k` / `j` | Move selection |
| `N` | Create a new server |
| `S` | Start selected server |
| `X` | Stop selected server |
| `R` | Restart selected server |
| `C` | Open RCON console |
| `L` | Follow logs |
| `P` | Show players |
| `D` | Delete selected server |
| `I` | Show server info |
| `T` | Set up playit.gg |
| `G` | Start Chunky pre-generation |
| `Q` or `Esc` | Return to main menu |

In the main menu, `Q`, `Esc`, or `7` quits.

## CLI Reference

### Syntax

```text
pumpkin-auto [command] [name] [options]
```

A bare server name is treated as `up`:

```bash
pumpkin-auto survival
```

### Commands

| Command | Description |
| --- | --- |
| `up` | Create if needed, start the server, and configure playit.gg. This is the default command. |
| `create` | Download and configure a new server without starting it. |
| `start` | Start an existing server. |
| `stop` | Stop a server through RCON, then SIGTERM/SIGKILL if needed. |
| `restart` | Stop and start a server. |
| `status` | Show paths, ports, state, and public address. |
| `list` | List all servers with type, version, port, state, and public address. |
| `delete` | Stop and remove a server directory. |
| `logs` | Follow `console.log`. Use `--lines N` to set the initial line count. |
| `console` | Open an interactive RCON command prompt. Type `exit` to quit. |
| `players` | Show the online player list through RCON. |
| `playit` | Start playit.gg and ensure a tunnel for the server port. |
| `playit-stop` | Stop the playit.gg agent. |
| `playit-reset` | Stop playit.gg and remove the saved secret. |
| `pregen` | Start Chunky pre-generation for Paper or Fabric. |
| `versions` | Show supported server types, the default version, and Pumpkin mappings. |
| `ui` | Launch the terminal UI. |

### Options

| Option | Default | Description |
| --- | --- | --- |
| `--dir DIR` | | Use a specific server directory instead of `~/minecraft-servers/<name>`. |
| `--type TYPE` | `paper` | `pumpkin`, `paper`, `fabric`, or `vanilla`. |
| `--version VERSION` | `1.21.11` | Minecraft version. |
| `--port PORT` | auto | Java port. The default search starts at `25565`. |
| `--profile PROFILE` | `max` | `safe`, `max`, or `none`. |
| `--memory MIB` | `4096` | JVM heap size; sets both `-Xms` and `-Xmx`. |
| `--online` | off | Enable Mojang online-mode authentication. |
| `--no-playit` | off | Skip playit.gg setup. |
| `--secret SECRET` | | Save and use a specific playit.gg secret. |
| `--playit-name NAME` | `mc-<server>` | Tunnel name when creating a tunnel. |
| `--motd TEXT` | generated | Server MOTD. |
| `--max-players N` | `20` | Player limit. |
| `--difficulty LEVEL` | `Normal` | `Peaceful`, `Easy`, `Normal`, or `Hard`. |
| `--gamemode MODE` | `Survival` | `Survival`, `Creative`, `Adventure`, or `Spectator`. |
| `--yes` | off | Skip the delete confirmation. |
| `--plain` | off | Use the plain-text UI instead of curses. |
| `--lines N` | `200` | Initial lines shown by `logs`. |
| `--radius N` | `1000` | Chunky pre-generation radius. |
| `--x N`, `--z N` | `0` | Chunky pre-generation center. |

### Examples

```bash
# Create and start a Paper server with the maximum optimization profile
pumpkin-auto up survival --type paper --profile max --memory 6144

# Create a Fabric server without starting it or configuring playit
pumpkin-auto create creative --type fabric --port 25566 --no-playit

# Start a server in a custom directory
pumpkin-auto start --dir /srv/minecraft/survival

# Show logs and open the console
pumpkin-auto logs survival --lines 100
pumpkin-auto console survival

# Show players
pumpkin-auto players survival

# Pre-generate a 2000-block radius around spawn
pumpkin-auto pregen survival --radius 2000

# Configure playit.gg for an existing server
pumpkin-auto playit survival

# Stop or reset the playit.gg agent
pumpkin-auto playit-stop
pumpkin-auto playit-reset

# Delete without a prompt
pumpkin-auto delete survival --yes

# Launch the plain UI
pumpkin-auto ui --plain
```

## Server Types and Optimization Profiles

### Profiles

- `none` — no optimization plugins or mods. Uses more conservative view and simulation distances.
- `safe` — stable optimization set. Paper adds Chunky. Fabric adds Fabric API, Lithium, Ferrite Core, Krypton, ServerCore, Clumps, Alternate Current, MoreCulling, Packet Fixer, Ksyxis, Chunky, and Spark.
- `max` — `safe` plus more aggressive optimizations. Paper adds FarmLimiter and BlockEntityLimiter. Fabric adds C2ME, VMP, ThreadTweak, and TT20.

The `max` profile is intentionally aggressive. Test it with your world, player count, and plugin/mod set before using it in production.

Paper plugins and Fabric mods are downloaded from Modrinth for the selected Minecraft version. If no compatible release is found, that item is skipped with a warning instead of failing the whole build.

### Versions

- The default Minecraft version is `1.21.11`.
- Vanilla versions are resolved from Mojang's version manifest.
- Paper builds are resolved from the Paper API, preferring the latest stable build.
- Fabric loader and installer versions are resolved automatically.
- Pumpkin uses a version mapping table; run `pumpkin-auto versions` to see it.

Use `--version` to choose a different version:

```bash
pumpkin-auto create old-school --type paper --version 1.20.6
```

Use the Java version required by your selected Minecraft version. Minecraft 1.21.x requires Java 21 or newer.

### Downloads and cache

Server software, mods, plugins, and the playit.gg agent are cached in:

```text
~/.cache/pumpkin-auto/downloads/
```

Files are linked into each server directory when possible, which saves disk space. Checksums are verified where the upstream source provides them.

## playit.gg

playit.gg is optional. Use `--no-playit` for a local or LAN-only server.

### First-time linking

On first use, `pumpkin-auto` asks you to link a playit.gg agent and saves the secret to:

```text
~/.config/pumpkin-auto/playit.secret
```

The secret file is created with mode `0600`. The playit.gg agent binary is downloaded to:

```text
~/.local/bin/playit
```

### Tunnel behavior

- Existing tunnels are reused when their local port matches the server port.
- New tunnels are created automatically when the saved agent key allows it.
- The public address is stored in the instance metadata and shown by `status` and `list`.
- One playit.gg agent is shared across servers; tunnels are created per local port.

### Read-only agent keys

Some playit.gg agent keys are **read-only**. With a read-only key, `pumpkin-auto` cannot create new tunnels automatically. Create the tunnel once in the [playit.gg dashboard](https://playit.gg/account/tunnels) and point it at:

```text
127.0.0.1:<server-port>
```

`pumpkin-auto` will reuse the existing tunnel.

### playit.gg commands

```bash
pumpkin-auto playit survival
pumpkin-auto playit-stop
pumpkin-auto playit-reset
```

- `playit` starts the agent and ensures a tunnel for the server port.
- `playit-stop` stops the agent without deleting the secret.
- `playit-reset` stops the agent and removes the saved secret. The next run will ask you to link again.

## Instance Layout

By default, servers live in `~/minecraft-servers/<name>/`:

```text
~/minecraft-servers/<name>/
  instance.json       # server settings, RCON password, playit address
  start.sh            # launch script
  console.log         # combined stdout/stderr
  server.pid          # PID while running
  eula.txt            # eula=true
  server.properties   # Java server settings
  ...
```

Additional files depend on the type:

- Paper: `paper.jar`, `plugins/`, `config/`, `bukkit.yml`, `spigot.yml`
- Fabric: `fabric-server-launch.jar`, `mods/`
- Vanilla: `server.jar`
- Pumpkin: `pumpkin`, `pumpkin.toml`

Application state and caches are stored separately:

```text
~/.config/pumpkin-auto/    # playit secret, socket, and log
~/.cache/pumpkin-auto/     # downloaded server software, mods, and plugins
```

### Backups

Stop the server before copying its directory:

```bash
pumpkin-auto stop survival
cp -a "$HOME/minecraft-servers/survival" "$HOME/minecraft-servers/survival-backup"
```

The world data is inside the server directory under `world/` unless you changed `level-name`.

### Existing worlds

You can copy an existing world folder into the instance directory before the first start. The default `level-name` is `world`, so the folder should normally be:

```text
~/minecraft-servers/<name>/world/
```

Back up the world before changing server software or mods.

## Networking

- Servers bind to `0.0.0.0` on their Java port.
- The default Java port search starts at `25565`.
- RCON uses the first free port at or after the Java port plus 10.
- RCON passwords are randomly generated per instance.
- The tool connects to RCON on `127.0.0.1`.
- LAN access uses the machine's local IP; `status` shows it.
- Open the Java port in your firewall if you want direct LAN or internet access.
- Do not expose the RCON port to the internet.

Multiple servers can run at the same time. Each one gets its own Java port, RCON port, directory, and metadata.

## Security and Legal Notes

- **Offline mode is the default.** Use `--online` to enable Mojang authentication.
- RCON is password-protected, but the password is stored in `instance.json` and `server.properties`. Restrict the RCON port with your firewall.
- `instance.json` and the playit.gg secret are written with restrictive permissions.
- The Minecraft EULA is accepted automatically by writing `eula=true`. Review the EULA before running a public server.
- Server software, mods, plugins, and the playit.gg agent are downloaded from third-party sources. Review what you install before running a public server.
- Do not commit `instance.json`, playit secrets, world data, logs, or server binaries to a public repository.
- Minecraft is a trademark of Mojang Studios and Microsoft. playit.gg is a third-party service. This project is not affiliated with or endorsed by them.

## Troubleshooting

### The UI shows nothing

Use the plain menu:

```bash
pumpkin-ui --plain
# or
pumpkin-auto ui --plain
```

The plain menu bypasses curses and uses numbered text prompts. The full-screen UI automatically falls back when `TERM` is missing or set to `dumb`, or when curses cannot start.

### `pumpkin-ui: command not found`

Make sure `~/.local/bin` is on your `PATH`:

```bash
echo "$PATH"
export PATH="$HOME/.local/bin:$PATH"
```

Recreate the launchers if they are missing. See [Installation](#installation).

### `ModuleNotFoundError: No module named 'pumpkin_auto'`

Run `ui.py` from the repository directory, or use the `pumpkin-ui` launcher:

```bash
cd "$HOME/pumpkin-auto"
python3 ui.py --plain
```

### The UI says the terminal is too small

Resize the terminal to at least **60 columns by 16 rows**. **80x24** or larger is recommended.

### The server does not start

```bash
pumpkin-auto logs <name>
```

Check that Java 21+ is installed for Java-based servers, the port is free, and the server has enough memory. A failed startup leaves the reason in `console.log`.

### `java: command not found`

Install a Java 21+ runtime and ensure `java` is on your `PATH`:

```bash
java -version
```

Pumpkin servers do not require Java.

### The port is already in use

Choose another port:

```bash
pumpkin-auto create survival --port 25570
```

Or let the tool choose automatically by omitting `--port`.

### Console or player commands fail

The server must be running and RCON must be reachable on localhost. Check the RCON port shown by:

```bash
pumpkin-auto status <name>
```

### playit.gg does not connect

```bash
pumpkin-auto status <name>
tail -n 100 "$HOME/.config/pumpkin-auto/playit.log"
```

If the key is read-only, create or edit the tunnel in the playit.gg dashboard. If the saved secret is invalid, run:

```bash
pumpkin-auto playit-reset
pumpkin-auto playit <name>
```

### A server directory is left after a failed create

The tool removes the directory when installation fails. If a directory remains because the target already existed or was not empty, inspect it and remove it manually before retrying.

### Permission denied

Make the Python files executable:

```bash
chmod +x "$HOME/pumpkin-auto/pumpkin_auto.py" "$HOME/pumpkin-auto/ui.py"
```

Also make sure the launchers are executable:

```bash
chmod +x "$HOME/.local/bin/pumpkin-auto" "$HOME/.local/bin/pumpkin-ui"
```

## FAQ

### Do I need root?

No. Everything installs under your home directory by default.

### Does this work on Windows or macOS?

No. It is Linux-only because it relies on `/proc`, Bash, Unix signals, and Linux-oriented terminal behavior.

### Can I run multiple servers?

Yes. Each server gets its own directory, Java port, RCON port, logs, and metadata. Use `pumpkin-auto list` to see them.

### Is online mode enabled by default?

No. Servers start in offline mode. Use `--online` when creating a server if you want Mojang authentication.

### How do I change memory after creation?

Set it when creating the server:

```bash
pumpkin-auto create survival --memory 6144
```

After creation, edit the `-Xms` and `-Xmx` values in the server's `start.sh` and restart the server.

### Can I use an existing world?

Yes. Copy the world folder into the server directory before the first start. The default `level-name` is `world`.

### How do I back up a server?

Stop it and copy the entire server directory. See [Backups](#backups).

### How do I update the server software?

There is no automatic update command. Recreate the server, or replace the server jar/binary manually after backing up the world. Always test updates with a backup.

### Does it support Bedrock?

No. This project manages Java Edition servers.

### Can I add my own plugins or mods?

Yes. Put Paper plugins in `plugins/` and Fabric mods in `mods/`. The `safe` and `max` profiles install a default optimization set, but you can add or remove files manually.

### Does playit.gg require an account?

Yes, for a public tunnel. Local and LAN-only servers do not need playit.gg. Use `--no-playit`.

### Why can't playit.gg create a new tunnel?

The saved agent key may be read-only. Create the tunnel in the playit.gg dashboard, or link an agent key that has permission to create tunnels.

## Development and Testing

### Project layout

```text
pumpkin-auto/
  pumpkin_auto.py          # core CLI, downloads, server lifecycle, RCON, playit
  ui.py                    # curses UI and plain-text UI
  README.md
  pumpkin_auto_legacy.py   # optional legacy prototype, not used by the launchers
```

### Compile check

```bash
cd "$HOME/pumpkin-auto"
python3 -m py_compile pumpkin_auto.py ui.py
```

### CLI smoke checks

```bash
pumpkin-auto --help
pumpkin-auto versions
pumpkin-auto list
```

### End-to-end smoke test

This creates a temporary Vanilla server in `/tmp`, starts it, checks RCON, stops it, and deletes it:

```bash
rm -rf /tmp/pumpkin-auto-smoke
pumpkin-auto create smoke --dir /tmp/pumpkin-auto-smoke --type vanilla \
  --port 25573 --no-playit
pumpkin-auto start smoke --dir /tmp/pumpkin-auto-smoke
pumpkin-auto status smoke --dir /tmp/pumpkin-auto-smoke
pumpkin-auto players smoke --dir /tmp/pumpkin-auto-smoke
pumpkin-auto stop smoke --dir /tmp/pumpkin-auto-smoke
pumpkin-auto delete smoke --dir /tmp/pumpkin-auto-smoke --yes
```

Change `25573` if that port is already in use.

### UI smoke test

```bash
pumpkin-ui --plain
```

Open the create wizard, choose a type with a number key, then quit with `7`. For the full-screen UI, run `pumpkin-ui` in a terminal at least 60x16.

### Static checks

There is no formal test framework yet. The checks above cover compilation, CLI parsing, UI startup, server creation, startup, RCON, shutdown, and deletion.

## Contributing

Issues and pull requests are welcome.

- Keep the project Linux-focused.
- Prefer the Python standard library; avoid adding runtime dependencies.
- Run the compile and smoke checks before submitting changes.
- Do not include secrets, world data, logs, or generated server binaries in commits.
- Test changes with at least one server type, and ideally all four.

## License

No license file is included yet. Add a `LICENSE` file before distributing this project or accepting contributions if you want to grant others permission to use, modify, and redistribute it.
