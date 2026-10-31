#!/usr/bin/env python3
from __future__ import annotations

import curses
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pumpkin_auto as core

KEY_ENTER = (10, 13)
KEY_ESC = 27
KEY_BACKSPACE = (8, 127, curses.KEY_BACKSPACE)

SERVER_TYPE_CHOICES = ["paper", "fabric", "vanilla", "pumpkin"]
PROFILE_CHOICES = ["max", "safe", "none"]


class Dashboard:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.servers = []
        self.index = 0
        self.message = ""
        self.players_cache = {}
        self.refresh()

    def init_colors(self):
        self.header_attr = curses.A_BOLD
        self.selected_attr = curses.A_REVERSE | curses.A_BOLD
        self.running_attr = curses.A_BOLD
        self.stopped_attr = curses.A_DIM
        self.accent_attr = curses.A_BOLD
        self.dim_attr = curses.A_DIM
        self.error_attr = curses.A_BOLD
        if not curses.has_colors():
            return
        try:
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)
            curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_WHITE)
            curses.init_pair(3, curses.COLOR_GREEN, -1)
            curses.init_pair(4, curses.COLOR_YELLOW, -1)
            curses.init_pair(5, curses.COLOR_RED, -1)
            curses.init_pair(6, curses.COLOR_CYAN, -1)
            self.header_attr = curses.color_pair(1) | curses.A_BOLD
            self.selected_attr = curses.color_pair(2) | curses.A_BOLD
            self.running_attr = curses.color_pair(3) | curses.A_BOLD
            self.stopped_attr = curses.color_pair(4)
            self.accent_attr = curses.color_pair(6) | curses.A_BOLD
            self.error_attr = curses.color_pair(5) | curses.A_BOLD
        except curses.error:
            pass

    def refresh(self):
        self.servers = core.list_instances()
        if self.index >= len(self.servers):
            self.index = max(0, len(self.servers) - 1)

    def selected(self):
        if not self.servers:
            return None
        return self.servers[self.index]

    def set_cursor(self, visible):
        try:
            curses.curs_set(1 if visible else 0)
        except curses.error:
            pass

    def add(self, y, x, text, attr=0):
        height, width = self.stdscr.getmaxyx()
        if y < 0 or y >= height or x >= width:
            return
        try:
            self.stdscr.addnstr(y, x, text, max(0, width - x - 1), attr)
        except curses.error:
            pass

    def draw(self):
        self.stdscr.erase()
        height, width = self.stdscr.getmaxyx()
        if height < 14 or width < 60:
            self.add(0, 0, "Terminal too small. Resize to at least 60x14.", self.accent_attr)
            self.stdscr.refresh()
            return
        linked = "linked" if core.load_secret() else "not linked"
        header = (
            f" Pumpkin Auto  |  LAN {core.lan_ip()}  |  "
            f"playit.gg {linked}  |  {len(self.servers)} server(s)"
        )
        self.add(0, 0, header.ljust(width - 1), self.header_attr)
        try:
            self.stdscr.hline(1, 0, curses.ACS_HLINE, width)
        except curses.error:
            pass
        columns = f"{'NAME':20} {'TYPE':8} {'VERSION':10} {'PORT':6} {'STATE':9} {'PLAYERS':8}"
        self.add(2, 1, columns, self.accent_attr)
        max_rows = max(1, height - 12)
        start = max(0, self.index - max_rows + 1)
        if not self.servers:
            self.add(4, 2, "No servers yet. Press N to create one.", self.dim_attr)
        for row, (path, meta) in enumerate(self.servers[start:start + max_rows]):
            y = 3 + row
            actual_index = start + row
            pid = core.server_pid(path)
            state = "RUNNING" if pid else "STOPPED"
            players = self.players_label(path, meta) if pid else "-"
            line = (
                f"{meta['name'][:20]:20} {meta['type'][:8]:8} "
                f"{meta['version'][:10]:10} {meta['port']:<6} "
                f"{state:9} {players:8}"
            )
            attr = 0
            if actual_index == self.index:
                attr = self.selected_attr
            elif pid:
                attr = self.running_attr
            else:
                attr = self.stopped_attr
            self.add(y, 1, line, attr)
        try:
            self.stdscr.hline(height - 8, 0, curses.ACS_HLINE, width)
        except curses.error:
            pass
        self.draw_details(height, width)
        footer1 = " N new   S start   X stop   R restart   C console   L logs"
        footer2 = " P players   D delete   I info   T playit   G pregen   Q back"
        self.add(height - 2, 0, footer1.ljust(width - 1), self.accent_attr)
        self.add(height - 1, 0, footer2.ljust(width - 1), self.accent_attr)
        if self.message:
            self.add(height - 3, 1, self.message[:width - 2], self.error_attr)
        self.stdscr.refresh()

    def players_label(self, path, meta):
        key = str(path)
        now = time.time()
        cached = self.players_cache.get(key)
        if cached and now - cached[0] < 5:
            return cached[1]
        label = "-"
        try:
            response = core.rcon_command(
                int(meta["rcon_port"]), meta["rcon_password"], "list", timeout=2.0
            )
            label = self.parse_players(response)
        except OSError:
            pass
        self.players_cache[key] = (now, label)
        return label

    def parse_players(self, response):
        match = None
        for pattern in (
            r"There are (\d+) of a max of (\d+) players online",
            r"There are (\d+)/(\d+) players online",
        ):
            import re

            match = re.search(pattern, response or "")
            if match:
                return f"{match.group(1)}/{match.group(2)}"
        return "?"

    def draw_details(self, height, width):
        selected = self.selected()
        if not selected:
            self.add(height - 7, 1, "Select a server or press N to create one.", self.dim_attr)
            return
        path, meta = selected
        pid = core.server_pid(path)
        profile = meta.get("profile", "none")
        details = [
            f"Selected: {meta['name']}  [{meta['type']} {meta['version']}]  "
            f"profile={profile}  memory={meta.get('memory_mb', 4096)} MiB",
        ]
        public = (meta.get("playit") or {}).get("address")
        details.append(
            f"Public:   {public or 'not configured'}"
        )
        extras = f"Path: {path}"
        if pid:
            uptime, rss = core.process_info(pid)
            extras += f"   Uptime: {core.format_uptime(uptime)}"
            if rss is not None:
                extras += f"   RAM: {rss:.0f} MB"
        details.append(extras)
        for offset, line in enumerate(details):
            self.add(height - 7 + offset, 1, line[:width - 2], self.dim_attr)

    def run(self):
        self.set_cursor(False)
        self.stdscr.keypad(True)
        self.stdscr.timeout(1000)
        self.init_colors()
        while True:
            choice = self.main_menu()
            if choice is None:
                break
            if choice == "create":
                self.create_wizard()
            elif choice == "manage":
                self.dashboard_loop()
            elif choice in ("start", "stop", "delete", "playit"):
                titles = {
                    "start": "Start a server",
                    "stop": "Stop a server",
                    "delete": "Delete a server",
                    "playit": "playit.gg setup",
                }
                index = self.choose_server(titles[choice])
                if index is None:
                    continue
                self.index = index
                if choice == "start":
                    self.start_selected()
                elif choice == "stop":
                    self.stop_selected()
                elif choice == "delete":
                    self.delete_selected()
                else:
                    self.playit_selected()

    def main_menu(self):
        options = [
            ("create", "Create a server"),
            ("manage", "Manage servers"),
            ("start", "Start a server"),
            ("stop", "Stop a server"),
            ("delete", "Delete a server"),
            ("playit", "playit.gg setup"),
            ("quit", "Quit"),
        ]
        selected = 0
        self.stdscr.timeout(-1)
        self.set_cursor(False)
        while True:
            self.refresh()
            height, width = self.stdscr.getmaxyx()
            self.stdscr.erase()
            if height < 16 or width < 60:
                self.add(0, 0, "Terminal too small. Resize to at least 60x16.", self.error_attr)
                self.stdscr.refresh()
                key = self.stdscr.getch()
                if key in (ord("q"), ord("Q"), KEY_ESC):
                    self.stdscr.timeout(1000)
                    self.stdscr.clear()
                    return None
                continue
            box_height = len(options) + 7
            box_width = min(width - 2, 64)
            top = max(0, (height - box_height) // 2)
            left = max(0, (width - box_width) // 2)
            try:
                win = curses.newwin(box_height, box_width, top, left)
                win.box()
                win.addnstr(0, 2, " Pumpkin Auto ", box_width - 4, self.header_attr)
                linked = "linked" if core.load_secret() else "not linked"
                win.addnstr(
                    2,
                    2,
                    f" playit.gg {linked}  |  {len(self.servers)} server(s) ",
                    box_width - 4,
                    self.dim_attr,
                )
                for row, (_, label) in enumerate(options):
                    line = f" {row + 1}. {label}"
                    attr = self.selected_attr if row == selected else 0
                    win.addnstr(4 + row, 2, line, box_width - 4, attr)
                if self.message:
                    win.addnstr(
                        box_height - 3,
                        2,
                        self.message,
                        box_width - 4,
                        self.error_attr,
                    )
                win.addnstr(
                    box_height - 2,
                    2,
                    " Up/Down + Enter, or press 1-7   Q quit ",
                    box_width - 4,
                    self.dim_attr,
                )
                win.refresh()
            except curses.error:
                pass
            key = self.stdscr.getch()
            if key in (ord("q"), ord("Q"), KEY_ESC):
                self.stdscr.timeout(1000)
                self.stdscr.clear()
                return None
            if key in (curses.KEY_UP, ord("k")):
                selected = (selected - 1) % len(options)
            elif key in (curses.KEY_DOWN, ord("j")):
                selected = (selected + 1) % len(options)
            elif key in KEY_ENTER:
                choice = options[selected][0]
                self.stdscr.timeout(1000)
                self.stdscr.clear()
                return None if choice == "quit" else choice
            elif ord("1") <= key <= ord("7"):
                choice = options[key - ord("1")][0]
                self.stdscr.timeout(1000)
                self.stdscr.clear()
                return None if choice == "quit" else choice

    def choose_server(self, title):
        self.refresh()
        if not self.servers:
            self.modal(title, ["No servers found.", "Create one first."])
            return None
        selected = 0
        self.stdscr.timeout(-1)
        self.set_cursor(False)
        while True:
            height, width = self.stdscr.getmaxyx()
            self.stdscr.erase()
            if height < 12 or width < 60:
                self.add(0, 0, "Terminal too small. Resize to at least 60x12.", self.error_attr)
                self.stdscr.refresh()
                key = self.stdscr.getch()
                if key in (ord("q"), ord("Q"), KEY_ESC):
                    self.stdscr.timeout(1000)
                    self.stdscr.clear()
                    return None
                continue
            box_height = min(height - 2, min(len(self.servers), 12) + 6)
            box_width = min(width - 2, 76)
            top = max(0, (height - box_height) // 2)
            left = max(0, (width - box_width) // 2)
            visible = max(1, box_height - 5)
            start = max(0, selected - visible + 1)
            try:
                win = curses.newwin(box_height, box_width, top, left)
                win.box()
                win.addnstr(0, 2, f" {title} ", box_width - 4, self.header_attr)
                win.addnstr(
                    2,
                    2,
                    " #  NAME                 TYPE     PORT   STATE",
                    box_width - 4,
                    self.accent_attr,
                )
                for row, (path, meta) in enumerate(self.servers[start:start + visible]):
                    actual = start + row
                    state = "RUNNING" if core.server_pid(path) else "STOPPED"
                    line = (
                        f" {actual + 1:2}. {meta['name'][:20]:20} "
                        f"{meta['type'][:8]:8} {meta['port']:<6} {state}"
                    )
                    attr = self.selected_attr if actual == selected else 0
                    win.addnstr(3 + row, 2, line, box_width - 4, attr)
                win.addnstr(
                    box_height - 2,
                    2,
                    " Up/Down + Enter, or number   Esc cancel ",
                    box_width - 4,
                    self.dim_attr,
                )
                win.refresh()
            except curses.error:
                pass
            key = self.stdscr.getch()
            if key in (ord("q"), ord("Q"), KEY_ESC):
                self.stdscr.timeout(1000)
                self.stdscr.clear()
                return None
            if key in (curses.KEY_UP, ord("k")):
                selected = (selected - 1) % len(self.servers)
            elif key in (curses.KEY_DOWN, ord("j")):
                selected = (selected + 1) % len(self.servers)
            elif key in KEY_ENTER:
                self.stdscr.timeout(1000)
                self.stdscr.clear()
                return selected
            elif ord("1") <= key <= ord("9"):
                index = key - ord("1")
                if index < len(self.servers):
                    self.stdscr.timeout(1000)
                    self.stdscr.clear()
                    return index

    def dashboard_loop(self):
        self.stdscr.timeout(1000)
        while True:
            self.refresh()
            self.draw()
            key = self.stdscr.getch()
            if key == -1:
                continue
            if key == curses.KEY_RESIZE:
                self.stdscr.clear()
                continue
            if key in (ord("q"), ord("Q"), KEY_ESC):
                break
            if key in (curses.KEY_UP, ord("k")):
                self.move(-1)
            elif key in (curses.KEY_DOWN, ord("j")):
                self.move(1)
            elif key in (ord("n"), ord("N")):
                self.create_wizard()
            elif key in (ord("s"), ord("S")):
                self.start_selected()
            elif key in (ord("x"), ord("X")):
                self.stop_selected()
            elif key in (ord("r"), ord("R")):
                self.restart_selected()
            elif key in (ord("c"), ord("C")):
                self.console_selected()
            elif key in (ord("l"), ord("L")):
                self.logs_selected()
            elif key in (ord("p"), ord("P")):
                self.players_selected()
            elif key in (ord("d"), ord("D")):
                self.delete_selected()
            elif key in (ord("i"), ord("I")):
                self.info_selected()
            elif key in (ord("t"), ord("T")):
                self.playit_selected()
            elif key in (ord("g"), ord("G")):
                self.pregen_selected()

    def move(self, delta):
        if not self.servers:
            return
        self.index = (self.index + delta) % len(self.servers)

    def blocking(self, title, func):
        curses.def_prog_mode()
        curses.endwin()
        print(f"=== {title} ===")
        result = None
        try:
            result = func()
        except Exception as exc:
            print(f"Error: {exc}")
        print("\nPress Enter to return to the dashboard...")
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            pass
        curses.reset_prog_mode()
        self.stdscr.clear()
        self.stdscr.refresh()
        self.refresh()
        return result

    def edit_line(self, prompt, value=""):
        height, width = self.stdscr.getmaxyx()
        buf = list(value)
        pos = len(buf)
        limit = max(1, width - len(prompt) - 3)
        self.set_cursor(True)
        self.stdscr.timeout(-1)
        while True:
            text = prompt + "".join(buf)
            self.add(height - 1, 0, " " * (width - 1))
            self.add(height - 1, 0, text[:width - 2], self.accent_attr)
            cursor_x = min(len(prompt) + pos, width - 2)
            try:
                self.stdscr.move(height - 1, cursor_x)
            except curses.error:
                pass
            self.stdscr.refresh()
            key = self.stdscr.getch()
            if key in KEY_ENTER:
                break
            if key == KEY_ESC:
                buf = []
                pos = 0
                value = None
                break
            if key in KEY_BACKSPACE:
                if pos > 0:
                    buf.pop(pos - 1)
                    pos -= 1
            elif key == curses.KEY_DC:
                if pos < len(buf):
                    buf.pop(pos)
            elif key == curses.KEY_LEFT:
                pos = max(0, pos - 1)
            elif key == curses.KEY_RIGHT:
                pos = min(len(buf), pos + 1)
            elif key == curses.KEY_HOME:
                pos = 0
            elif key == curses.KEY_END:
                pos = len(buf)
            elif 32 <= key < 127 and len(buf) < limit:
                buf.insert(pos, chr(key))
                pos += 1
        curses.curs_set(0)
        self.stdscr.timeout(1000)
        if value is None:
            return None
        return "".join(buf)

    def modal(self, title, lines, wait=True):
        height, width = self.stdscr.getmaxyx()
        body = [str(line) for line in lines]
        box_height = min(height - 2, max(5, len(body) + 4))
        box_width = min(width - 2, max(40, max([len(title)] + [len(x) for x in body]) + 6))
        top = max(0, (height - box_height) // 2)
        left = max(0, (width - box_width) // 2)
        try:
            win = curses.newwin(box_height, box_width, top, left)
            win.box()
            win.addnstr(0, 2, f" {title} ", box_width - 4, self.accent_attr)
            for offset, line in enumerate(body[:box_height - 3]):
                win.addnstr(1 + offset, 2, line, box_width - 4)
            win.addnstr(box_height - 1, 2, " Press any key ", box_width - 4, self.dim_attr)
            win.refresh()
            if wait:
                win.timeout(-1)
                win.getch()
        except curses.error:
            pass
        self.stdscr.clear()
        self.stdscr.refresh()
        self.stdscr.timeout(1000)

    def confirm(self, title, message):
        height, width = self.stdscr.getmaxyx()
        box_height = 7
        box_width = min(width - 2, max(44, len(message) + 6))
        top = max(0, (height - box_height) // 2)
        left = max(0, (width - box_width) // 2)
        try:
            win = curses.newwin(box_height, box_width, top, left)
            win.box()
            win.addnstr(0, 2, f" {title} ", box_width - 4, self.accent_attr)
            win.addnstr(2, 2, message, box_width - 4)
            win.addnstr(4, 2, " y = yes    n / Esc = no ", box_width - 4, self.dim_attr)
            win.refresh()
            win.timeout(-1)
            while True:
                key = win.getch()
                if key in (ord("y"), ord("Y")):
                    return True
                if key in (ord("n"), ord("N"), KEY_ESC):
                    return False
        except curses.error:
            return False
        finally:
            self.stdscr.clear()
            self.stdscr.refresh()
            self.stdscr.timeout(1000)

    def start_selected(self):
        selected = self.selected()
        if not selected:
            self.message = "No server selected."
            return
        path, meta = selected
        if core.server_pid(path):
            self.message = f"{meta['name']} is already running."
            return
        result = self.blocking(
            f"Starting {meta['name']} ({meta['type']} {meta['version']})",
            lambda: core.launch_server(path, wait=True),
        )
        self.message = f"Started {meta['name']}." if result else f"Could not start {meta['name']}."

    def stop_selected(self):
        selected = self.selected()
        if not selected:
            self.message = "No server selected."
            return
        path, meta = selected
        if not core.server_pid(path):
            self.message = f"{meta['name']} is already stopped."
            return
        self.message = f"Stopping {meta['name']}..."
        self.draw()
        core.stop_server(path)
        self.message = f"Stopped {meta['name']}."

    def restart_selected(self):
        selected = self.selected()
        if not selected:
            self.message = "No server selected."
            return
        path, meta = selected

        def do_restart():
            core.stop_server(path)
            time.sleep(1)
            return core.launch_server(path, wait=True)

        result = self.blocking(f"Restarting {meta['name']}", do_restart)
        self.message = f"Restarted {meta['name']}." if result else f"Could not restart {meta['name']}."

    def console_selected(self):
        selected = self.selected()
        if not selected:
            self.message = "No server selected."
            return
        path, meta = selected
        if not core.server_pid(path):
            self.message = "Start the server before using the console."
            return
        command = self.edit_line(f"{meta['name']}> ")
        if not command:
            return
        try:
            response = core.rcon_command(
                int(meta["rcon_port"]), meta["rcon_password"], command
            )
        except OSError as exc:
            self.modal("Console error", [str(exc)])
            return
        lines = response.splitlines() or ["(no output)"]
        self.modal(f"{meta['name']} console", lines)

    def logs_selected(self):
        selected = self.selected()
        if not selected:
            self.message = "No server selected."
            return
        path, meta = selected
        log_path = path / "console.log"
        if not log_path.exists():
            self.modal("Logs", [f"No log yet: {log_path}"])
            return
        self.log_viewer(meta["name"], log_path)

    def log_viewer(self, name, log_path):
        self.stdscr.timeout(-1)
        self.set_cursor(False)
        offset = 0
        lines = []
        while True:
            try:
                with open(log_path, "r", errors="replace") as handle:
                    lines = handle.read().splitlines()
            except OSError as exc:
                lines = [str(exc)]
            height, width = self.stdscr.getmaxyx()
            visible = max(1, height - 3)
            max_offset = max(0, len(lines) - visible)
            offset = min(offset, max_offset)
            start = max(0, len(lines) - visible - offset)
            self.stdscr.erase()
            self.add(0, 0, f" Logs: {name}  ({len(lines)} lines)  R reload  PgUp/PgDn  Q close ".ljust(width - 1), self.header_attr)
            try:
                self.stdscr.hline(1, 0, curses.ACS_HLINE, width)
            except curses.error:
                pass
            for row, line in enumerate(lines[start:start + visible]):
                self.add(2 + row, 0, line[:width - 1])
            self.stdscr.refresh()
            key = self.stdscr.getch()
            if key in (ord("q"), ord("Q"), KEY_ESC):
                break
            if key in (curses.KEY_UP, ord("k")):
                offset = min(max_offset, offset + 1)
            elif key in (curses.KEY_DOWN, ord("j")):
                offset = max(0, offset - 1)
            elif key == curses.KEY_PPAGE:
                offset = min(max_offset, offset + visible)
            elif key == curses.KEY_NPAGE:
                offset = max(0, offset - visible)
            elif key == curses.KEY_HOME:
                offset = max_offset
            elif key == curses.KEY_END:
                offset = 0
            elif key in (ord("r"), ord("R")):
                continue
        self.stdscr.timeout(1000)
        self.stdscr.clear()
        self.stdscr.refresh()

    def players_selected(self):
        selected = self.selected()
        if not selected:
            self.message = "No server selected."
            return
        path, meta = selected
        if not core.server_pid(path):
            self.modal("Players", ["Server is not running."])
            return
        try:
            response = core.rcon_command(
                int(meta["rcon_port"]), meta["rcon_password"], "list"
            )
        except OSError as exc:
            self.modal("Players", [str(exc)])
            return
        self.modal("Players", response.splitlines() or ["(no output)"])

    def info_selected(self):
        selected = self.selected()
        if not selected:
            self.message = "No server selected."
            return
        path, meta = selected
        lines = [
            f"Name:      {meta['name']}",
            f"Type:      {meta['type']} {meta['version']}",
            f"Profile:   {meta.get('profile', 'none')}",
            f"Port:      {meta['port']}",
            f"RCON:      127.0.0.1:{meta['rcon_port']}",
            f"Online:    {meta['online']}",
            f"Memory:    {meta.get('memory_mb', 4096)} MiB",
            f"Path:      {path}",
            f"Public:    {(meta.get('playit') or {}).get('address', 'not configured')}",
        ]
        if meta.get("plugins"):
            lines.append(f"Plugins:   {len(meta['plugins'])}")
        if meta.get("mods"):
            lines.append(f"Mods:      {len(meta['mods'])}")
        if meta.get("paper_build"):
            lines.append(f"Paper:     build {meta['paper_build']}")
        if meta.get("fabric_loader"):
            lines.append(f"Fabric:    loader {meta['fabric_loader']}")
        if meta.get("pumpkin_tag"):
            lines.append(f"Pumpkin:   {meta['pumpkin_tag']}")
        self.modal(f"{meta['name']} info", lines)

    def delete_selected(self):
        selected = self.selected()
        if not selected:
            self.message = "No server selected."
            return
        path, meta = selected
        if not self.confirm(
            "Delete server",
            f"Delete {meta['name']} and its world at {path}?",
        ):
            return
        result = self.blocking(
            f"Deleting {meta['name']}",
            lambda: (core.stop_server(path), shutil.rmtree(path)),
        )
        if result is None:
            self.message = f"Could not delete {meta['name']}."
        else:
            self.message = f"Deleted {meta['name']}."
        self.refresh()

    def playit_selected(self):
        selected = self.selected()
        if not selected:
            self.message = "No server selected."
            return
        path, meta = selected

        def do_playit():
            secret = core.resolve_secret()
            core.start_playit(secret)
            public = core.ensure_tunnel(
                secret, int(meta["port"]), f"mc-{meta['name']}"
            )
            if public:
                meta["playit"] = public
                core.save_meta(path, meta)
                print(f"Public address: {public['address']}")
            else:
                print("No public address yet. Check the playit.gg dashboard.")
            return public

        self.blocking(f"playit.gg tunnel for {meta['name']}", do_playit)
        self.message = f"playit.gg updated for {meta['name']}."

    def pregen_selected(self):
        selected = self.selected()
        if not selected:
            self.message = "No server selected."
            return
        path, meta = selected
        if meta["type"] not in ("paper", "fabric"):
            self.modal("Pre-generation", ["Chunky is only available for Paper and Fabric."])
            return
        if not core.server_pid(path):
            self.modal("Pre-generation", ["Start the server first."])
            return
        radius = self.edit_line("Chunky radius (blocks): ", "1000")
        if radius is None or not radius.strip().isdigit():
            return

        def do_pregen():
            commands = [f"chunky radius {int(radius)}", "chunky start"]
            for command in commands:
                print(f"> {command}")
                try:
                    response = core.rcon_command(
                        int(meta["rcon_port"]), meta["rcon_password"], command
                    )
                    print(response)
                except OSError as exc:
                    print(f"rcon failed: {exc}")
                    return
            print("Pre-generation started. Use console to check progress.")

        self.blocking(f"Pre-generating {meta['name']}", do_pregen)
        self.message = f"Pre-generation started for {meta['name']}."

    def field_choices(self, key):
        if key == "type":
            return SERVER_TYPE_CHOICES
        if key == "profile":
            return PROFILE_CHOICES
        if key == "online":
            return ["off", "on"]
        if key == "playit":
            return ["on", "off"]
        if key == "start":
            return ["on", "off"]
        return None

    def create_wizard(self):
        fields = [
            ["name", "Name", "survival"],
            ["type", "Type", core.DEFAULT_TYPE],
            ["version", "Version", core.DEFAULT_VERSION],
            ["port", "Port (blank = auto)", ""],
            ["profile", "Optimization", core.DEFAULT_PROFILE],
            ["online", "Online mode", "off"],
            ["playit", "playit.gg", "on"],
            ["start", "Start after create", "on"],
            ["memory", "Memory (MiB)", "4096"],
            ["motd", "MOTD", "A Minecraft server, tunneled with playit.gg"],
            ["max_players", "Max players", "20"],
        ]
        types = SERVER_TYPE_CHOICES
        profiles = PROFILE_CHOICES
        index = 1
        cancelled = False
        self.stdscr.timeout(-1)
        while True:
            height, width = self.stdscr.getmaxyx()
            box_height = min(height - 2, len(fields) + 8)
            box_width = min(width - 2, 76)
            top = max(0, (height - box_height) // 2)
            left = max(0, (width - box_width) // 2)
            self.stdscr.erase()
            try:
                win = curses.newwin(box_height, box_width, top, left)
                win.box()
                win.addnstr(0, 2, " Create a Minecraft server ", box_width - 4, self.accent_attr)
                for row, field in enumerate(fields):
                    key, label, value = field
                    if key in ("type", "profile", "online", "playit", "start"):
                        display = f"< {value} >"
                    elif key == "port" and not value:
                        display = "auto"
                    else:
                        display = value
                    line = f"{label:20} {display}"
                    attr = self.selected_attr if row == index else 0
                    win.addnstr(2 + row, 2, line, box_width - 4, attr)
                create_line = "  Create server  "
                attr = self.selected_attr if index == len(fields) else self.accent_attr
                win.addnstr(2 + len(fields), 2, create_line, box_width - 4, attr)
                if index < len(fields):
                    choices = self.field_choices(fields[index][0])
                else:
                    choices = None
                if choices:
                    hint = " " + " ".join(
                        f"{i + 1}={choice}" for i, choice in enumerate(choices)
                    ) + "  Up/Down move  Esc cancel "
                elif index < len(fields):
                    hint = " Enter edit   Up/Down move   Esc cancel "
                else:
                    hint = " Enter create   Up/Down move   Esc cancel "
                win.addnstr(
                    box_height - 2,
                    2,
                    hint,
                    box_width - 4,
                    self.dim_attr,
                )
                win.refresh()
            except curses.error:
                win = None
            key = self.stdscr.getch()
            if key == KEY_ESC:
                cancelled = True
                break
            if key in (curses.KEY_UP, ord("k")):
                index = (index - 1) % (len(fields) + 1)
            elif key in (curses.KEY_DOWN, ord("j")):
                index = (index + 1) % (len(fields) + 1)
            elif index == len(fields):
                if key in KEY_ENTER:
                    break
            elif ord("1") <= key <= ord("9"):
                field = fields[index]
                choices = self.field_choices(field[0])
                if choices:
                    choice_index = key - ord("1")
                    if choice_index < len(choices):
                        field[2] = choices[choice_index]
            elif key in (curses.KEY_LEFT, curses.KEY_RIGHT):
                field = fields[index]
                if field[0] == "type":
                    field[2] = types[(types.index(field[2]) + (1 if key == curses.KEY_RIGHT else -1)) % len(types)]
                elif field[0] == "profile":
                    field[2] = profiles[(profiles.index(field[2]) + (1 if key == curses.KEY_RIGHT else -1)) % len(profiles)]
                elif field[0] in ("online", "playit", "start"):
                    field[2] = "off" if field[2] == "on" else "on"
            elif key in KEY_ENTER:
                field = fields[index]
                if field[0] in ("online", "playit", "start"):
                    field[2] = "off" if field[2] == "on" else "on"
                elif field[0] == "type":
                    field[2] = types[(types.index(field[2]) + 1) % len(types)]
                elif field[0] == "profile":
                    field[2] = profiles[(profiles.index(field[2]) + 1) % len(profiles)]
                else:
                    edited = self.edit_line(f"{field[1]}: ", field[2])
                    if edited is not None:
                        field[2] = edited
                    self.stdscr.timeout(-1)
            elif key == curses.KEY_RESIZE:
                continue
        self.stdscr.timeout(1000)
        self.stdscr.clear()
        self.stdscr.refresh()
        if cancelled or index != len(fields) or not fields:
            return
        values = {field[0]: field[2] for field in fields}
        try:
            port = int(values["port"]) if values["port"].strip() else None
            memory = int(values["memory"])
            max_players = int(values["max_players"])
            name = values["name"].strip()
            version = values["version"].strip()
            if not name:
                raise ValueError("name cannot be empty")
            if not version:
                raise ValueError("version cannot be empty")
        except ValueError as exc:
            self.modal("Create server", [f"Invalid value: {exc}"])
            return
        start_after = values["start"] == "on"
        playit = values["playit"] == "on"

        def do_create():
            directory, meta = core.create_instance(
                name=name,
                server_type=values["type"],
                version=version,
                port=port,
                online=values["online"] == "on",
                profile=values["profile"],
                motd=values["motd"],
                max_players=max_players,
                memory_mb=memory,
                playit_enabled=playit,
            )
            print(f"Created {directory}")
            if start_after:
                print("Starting server...")
                core.launch_server(directory, wait=True)
                print("Server started.")
            if playit:
                secret = core.resolve_secret()
                core.start_playit(secret)
                public = core.ensure_tunnel(
                    secret, int(meta["port"]), f"mc-{meta['name']}"
                )
                if public:
                    meta["playit"] = public
                    core.save_meta(directory, meta)
                    print(f"Public address: {public['address']}")
            core.print_summary(directory, meta)
            return directory

        result = self.blocking(f"Creating {values['type']} {version} server", do_create)
        if result:
            self.message = f"Created {values['name']}."
            self.refresh()
            for i, (path, meta) in enumerate(self.servers):
                if meta["name"] == name:
                    self.index = i
                    break
        else:
            self.message = "Server creation failed."


def plain_input(prompt):
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def plain_choice(label, choices, default=1):
    print(f"\n{label}")
    for index, choice in enumerate(choices, 1):
        print(f"  {index}. {choice}")
    value = plain_input(f"Choice [{default}]: ")
    if value is None:
        return None
    value = value.strip()
    if not value:
        return choices[default - 1]
    if value.isdigit() and 1 <= int(value) <= len(choices):
        return choices[int(value) - 1]
    if value in choices:
        return value
    print("Invalid choice; using default.")
    return choices[default - 1]


def plain_cli(*args):
    command = [sys.executable, str(Path(core.__file__).resolve()), *map(str, args)]
    try:
        return subprocess.call(command)
    except OSError as exc:
        print(f"Could not run command: {exc}")
        return 1


def plain_choose_server(title):
    servers = core.list_instances()
    if not servers:
        print("\nNo servers found. Create one first.")
        return None
    print(f"\n{title}")
    for index, (path, meta) in enumerate(servers, 1):
        state = "RUNNING" if core.server_pid(path) else "STOPPED"
        print(
            f"  {index}. {meta['name']}  {meta['type']} {meta['version']}  "
            f"port {meta['port']}  {state}"
        )
    value = plain_input("Select server (blank to cancel): ")
    if value is None:
        return None
    value = value.strip()
    if not value.isdigit():
        return None
    index = int(value) - 1
    if not 0 <= index < len(servers):
        print("Invalid selection.")
        return None
    return servers[index]


def plain_create():
    print("\nCreate a server")
    name = plain_input("Name [survival]: ")
    if name is None:
        return
    name = name.strip() or "survival"
    server_type = plain_choice("Type", ["paper", "fabric", "vanilla", "pumpkin"], 1)
    if server_type is None:
        return
    version = plain_input(f"Version [{core.DEFAULT_VERSION}]: ")
    if version is None:
        return
    version = version.strip() or core.DEFAULT_VERSION
    port = plain_input("Port (blank = auto): ")
    if port is None:
        return
    port = port.strip()
    profile = plain_choice("Optimization", ["max", "safe", "none"], 1)
    if profile is None:
        return
    online = plain_choice("Online mode", ["off", "on"], 1)
    if online is None:
        return
    playit = plain_choice("playit.gg", ["on", "off"], 1)
    if playit is None:
        return
    start = plain_choice("Start after create", ["on", "off"], 1)
    if start is None:
        return
    memory = plain_input("Memory (MiB) [4096]: ")
    if memory is None:
        return
    memory = memory.strip() or "4096"
    motd = plain_input(
        f"MOTD [A {server_type} server, tunneled with playit.gg]: "
    )
    if motd is None:
        return
    motd = motd.strip() or f"A {server_type} server, tunneled with playit.gg"
    max_players = plain_input("Max players [20]: ")
    if max_players is None:
        return
    max_players = max_players.strip() or "20"
    args = [
        "create",
        name,
        "--type",
        server_type,
        "--version",
        version,
        "--profile",
        profile,
        "--memory",
        memory,
        "--max-players",
        max_players,
        "--motd",
        motd,
    ]
    if port:
        args += ["--port", port]
    if online == "on":
        args += ["--online"]
    if playit == "off":
        args += ["--no-playit"]
    if plain_cli(*args) != 0:
        print("Create failed.")
        return
    if start == "on" and plain_cli("start", name) != 0:
        print("Start failed.")
        return
    if playit == "on":
        plain_cli("playit", name)


def plain_manage():
    selected = plain_choose_server("Manage servers")
    if selected is None:
        return
    path, meta = selected
    while True:
        meta = core.load_meta(path) or meta
        pid = core.server_pid(path)
        state = "RUNNING" if pid else "STOPPED"
        print(
            f"\n{meta['name']} | {meta['type']} {meta['version']} | "
            f"port {meta['port']} | {state}"
        )
        print(" 1. Start       2. Stop        3. Restart")
        print(" 4. Logs        5. Console     6. Players")
        print(" 7. Info        8. Delete      9. Pregen")
        print("10. playit.gg  11. Back")
        choice = plain_input("Choose: ")
        if choice is None:
            return
        choice = choice.strip().lower()
        if choice in ("", "11", "b", "back", "q"):
            return
        if choice in ("1", "start"):
            plain_cli("start", meta["name"], "--dir", path)
        elif choice in ("2", "stop"):
            plain_cli("stop", meta["name"], "--dir", path)
        elif choice in ("3", "restart"):
            plain_cli("restart", meta["name"], "--dir", path)
        elif choice in ("4", "logs"):
            plain_cli("logs", meta["name"], "--dir", path, "--lines", "50")
        elif choice in ("5", "console"):
            plain_cli("console", meta["name"], "--dir", path)
        elif choice in ("6", "players"):
            plain_cli("players", meta["name"], "--dir", path)
        elif choice in ("7", "info", "status"):
            plain_cli("status", meta["name"], "--dir", path)
        elif choice in ("8", "delete"):
            confirm = plain_input(f"Type {meta['name']} to delete: ")
            if confirm is None:
                continue
            if confirm.strip() != meta["name"]:
                print("Cancelled.")
                continue
            plain_cli("delete", meta["name"], "--dir", path, "--yes")
            return
        elif choice in ("9", "pregen"):
            radius = plain_input("Radius [1000]: ")
            if radius is None:
                continue
            radius = radius.strip() or "1000"
            plain_cli("pregen", meta["name"], "--dir", path, "--radius", radius)
        elif choice in ("10", "playit"):
            plain_cli("playit", meta["name"], "--dir", path)
        else:
            print("Invalid choice.")


def run_plain_ui():
    print("Pumpkin Auto")
    while True:
        servers = core.list_instances()
        linked = "linked" if core.load_secret() else "not linked"
        print("\n" + "=" * 60)
        print(f" playit.gg: {linked} | {len(servers)} server(s)")
        print(" 1. Create a server")
        print(" 2. Manage servers")
        print(" 3. Start a server")
        print(" 4. Stop a server")
        print(" 5. Delete a server")
        print(" 6. playit.gg setup")
        print(" 7. Quit")
        choice = plain_input("Choose 1-7: ")
        if choice is None:
            return
        choice = choice.strip().lower()
        if choice in ("", "7", "q", "quit"):
            return
        if choice in ("1", "create"):
            plain_create()
        elif choice in ("2", "manage"):
            plain_manage()
        elif choice in ("3", "4", "5", "6"):
            titles = {
                "3": "Start a server",
                "4": "Stop a server",
                "5": "Delete a server",
                "6": "playit.gg setup",
            }
            commands = {"3": "start", "4": "stop", "5": "delete", "6": "playit"}
            selected = plain_choose_server(titles[choice])
            if selected is None:
                continue
            path, meta = selected
            command = commands[choice]
            if command == "delete":
                confirm = plain_input(f"Type {meta['name']} to delete: ")
                if confirm is None or confirm.strip() != meta["name"]:
                    print("Cancelled.")
                    continue
                plain_cli("delete", meta["name"], "--dir", path, "--yes")
            else:
                plain_cli(command, meta["name"], "--dir", path)
        else:
            print("Invalid choice.")


def run_ui(plain=False):
    force_plain = (
        plain
        or "--plain" in sys.argv[1:]
        or os.environ.get("PUMPKIN_UI_PLAIN") == "1"
    )
    term = os.environ.get("TERM", "")
    if force_plain or term in ("", "dumb"):
        run_plain_ui()
        return
    os.environ.setdefault("ESCDELAY", "25")
    try:
        curses.wrapper(lambda stdscr: Dashboard(stdscr).run())
    except (curses.error, OSError) as exc:
        print(f"\nFull-screen UI unavailable: {exc}")
        print("Falling back to the plain menu.\n")
        run_plain_ui()


if __name__ == "__main__":
    run_ui()
