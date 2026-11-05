#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
agent-reaper —— Agent 遗留进程清道夫

背景：
  各类 Agent（Antigravity / Codex / WorkBuddy / Cue / 各种 MCP、终端工具调用）
  经常启动 node / python / shell / headless 浏览器等子进程。任务完成、超时或失败后，
  父进程退出了，子进程却被 macOS 过继给 launchd（PPID=1）继续挂着甚至继续跑，
  时间一长内存和 CPU 被这些"孤儿"慢慢吃光，电脑越来越卡。

处理策略（宁可漏杀，绝不误杀）：
  1. 孤儿工具进程 —— 自动清理
     同时满足以下全部条件才会结束（连同它的子进程树一起）：
       - 属于当前用户、没有终端（tty 为 ??）
       - 父进程已经没了（PPID=1），且不是 launchd 正式托管的服务
       - 可执行文件是 Agent 常用的工具运行时（node / python / shell / uv / npx /
         headless 浏览器等），不是正常的 .app 图形应用或系统进程
       - 不在白名单里（自动读取 ~/Library/LaunchAgents 里所有服务的路径，外加配置文件白名单）
       - 已经变成孤儿并存活超过 orphan_min_age_min 分钟（默认 30 分钟）
  2. 失控进程（比如渲染进程卡进 V8 死循环）—— 只提醒，不自动结束
     连续两次巡检（默认约 20 分钟）都持续占满 ≥85% 单核 CPU 时，弹窗提醒，
     由用户一键决定是否结束。不会再像旧看门狗那样按瞬时 CPU 误杀正在干活的进程。

用法：
  agent-reaper                 # 执行一次巡检（launchd 每 10 分钟调用一次）
  agent-reaper --dry-run       # 只列出会被清理的进程，不动手
  agent-reaper --status        # 查看当前孤儿进程、失控进程和内存占用概况
"""

import json
import os
import re
import signal
import subprocess
import sys
import time

HOME = os.path.expanduser("~")
UID = os.getuid()
SELF_PID = os.getpid()

CONFIG_PATH = os.environ.get("AGENT_REAPER_CONFIG") or os.path.join(HOME, ".config/agent-reaper/config.json")
STATE_PATH = os.environ.get("AGENT_REAPER_STATE") or os.path.join(HOME, ".local/state/agent-reaper/state.json")
LOG_PATH = os.path.join(HOME, "Library/Logs/agent-reaper.log")
LAUNCH_AGENTS_DIR = os.path.join(HOME, "Library/LaunchAgents")

DEFAULT_CONFIG = {
    "orphan_min_age_min": 30,
    "runaway_cpu_ratio": 0.85,
    "runaway_consecutive": 2,
    "runaway_notify_cooldown_min": 120,
    "runaway_action": "ask",
    "whitelist_patterns": [
        "/.local/share/spider/",
        "/.dsh/mihomo/",
        "mihomo",
        "/.local/share/agent-reaper/",
        "vscode-server",
        "cursor-server",
        "jetbrains",
    ],
}

# Agent 常用的工具运行时（按可执行文件名匹配）
TOOL_NAMES = re.compile(
    r"^(node|nodejs|python|python3|python3\.\d+|Python|bash|zsh|sh|dash|fish|"
    r"uv|uvx|npx|npm|pnpm|yarn|corepack|bun|bunx|deno|tsx|ts-node|esbuild|vite|"
    r"tail|sleep|caffeinate|ffmpeg|rg|chromedriver|chrome-headless-shell|"
    r"playwright|puppeteer)$"
)
# 由 Agent 拉起的 headless 浏览器（即使是 .app 也算工具进程）
HEADLESS_HINT = re.compile(r"(--headless|ms-playwright|puppeteer|chrome-headless|Google Chrome for Testing)", re.I)
# 这些前缀下的程序永远不碰
PROTECTED_PREFIXES = ("/System/", "/usr/libexec/", "/usr/sbin/", "/sbin/", "/Library/Apple/")
# 服务配置里常见的"解释器"参数，不能拿来当白名单（否则所有 node/bash 都被白名单了）
GENERIC_ARGS = {
    "/bin/bash", "/bin/sh", "/bin/zsh", "/usr/bin/python3", "/usr/bin/env",
    "/usr/bin/open", "/bin/launchctl", "-a", "-c", "--args", "--hidden",
    "run", "start", "daemon", "--daemon", "--watch",
}


def log(msg):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    try:
        if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > 1024 * 1024:
            os.replace(LOG_PATH, LOG_PATH + ".1")
    except OSError:
        pass
    line = "%s  %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_config():
    if not os.path.exists(CONFIG_PATH):
        save_json(CONFIG_PATH, DEFAULT_CONFIG)
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(load_json(CONFIG_PATH, {}))
    return cfg


def to_seconds(t):
    """把 ps 的 etime / time（[[dd-]hh:]mm:ss[.xx]）转换成秒。"""
    t = t.strip()
    days = 0
    if "-" in t:
        d, t = t.split("-", 1)
        days = int(d)
    parts = t.split(":")
    try:
        nums = [float(x) for x in parts]
    except ValueError:
        return 0
    while len(nums) < 3:
        nums.insert(0, 0.0)
    h, m, s = nums[-3], nums[-2], nums[-1]
    return int(days * 86400 + h * 3600 + m * 60 + s)


def snapshot():
    out = subprocess.run(
        ["/bin/ps", "-axo", "pid=,ppid=,uid=,etime=,time=,rss=,stat=,tty=,command="],
        capture_output=True, text=True, errors="replace",
    ).stdout
    procs = {}
    for line in out.splitlines():
        parts = line.split(None, 8)
        if len(parts) < 9:
            continue
        pid, ppid, uid, etime, cputime, rss, stat, tty, cmd = parts
        try:
            procs[int(pid)] = {
                "pid": int(pid), "ppid": int(ppid), "uid": int(uid),
                "age": to_seconds(etime), "cpu": to_seconds(cputime),
                "rss_mb": int(rss) // 1024, "stat": stat, "tty": tty, "cmd": cmd,
            }
        except ValueError:
            continue
    return procs


def launchd_job_pids():
    out = subprocess.run(["/bin/launchctl", "list"], capture_output=True, text=True).stdout
    pids = set()
    for line in out.splitlines():
        first = line.split("\t", 1)[0].strip()
        if first.isdigit():
            pids.add(int(first))
    return pids


def launch_agent_whitelist():
    """把 ~/Library/LaunchAgents 中所有服务的脚本/程序路径加入白名单。"""
    pats = set()
    try:
        names = os.listdir(LAUNCH_AGENTS_DIR)
    except OSError:
        return pats
    for name in names:
        if not name.endswith(".plist"):
            continue
        path = os.path.join(LAUNCH_AGENTS_DIR, name)
        r = subprocess.run(
            ["/usr/bin/plutil", "-convert", "json", "-o", "-", path],
            capture_output=True, text=True,
        )
        try:
            data = json.loads(r.stdout)
        except Exception:
            continue
        args = list(data.get("ProgramArguments") or [])
        if data.get("Program"):
            args.insert(0, data["Program"])
        for a in args:
            if not isinstance(a, str) or a in GENERIC_ARGS:
                continue
            if a.startswith("/") and len(a) > 12:
                # 解释器本体（如 .../bin/node）不能当白名单，只取脚本/程序路径
                if re.search(r"/bin/(node|python3?|bash|sh|zsh)$", a):
                    continue
                pats.add(a)
    return pats


def exe_of(cmd):
    """取命令行里的可执行文件路径（兼容带空格的 .app 路径）。"""
    m = re.match(r"^(/.*?\.app/Contents/MacOS/[^ ]+)", cmd)
    if m:
        return m.group(1)
    return cmd.split(" ", 1)[0]


def is_tool_process(cmd):
    exe = exe_of(cmd)
    if exe.startswith(PROTECTED_PREFIXES):
        return False
    if ".app/Contents/" in exe:
        return bool(HEADLESS_HINT.search(cmd))
    name = os.path.basename(exe).lstrip("-")
    return bool(TOOL_NAMES.match(name)) or bool(HEADLESS_HINT.search(cmd))


def descendants(children, root):
    result, stack = [], [root]
    while stack:
        cur = stack.pop()
        for c in children.get(cur, []):
            result.append(c)
            stack.append(c)
    return result


def ancestors(procs, pid):
    chain = set()
    while pid in procs and pid > 1 and pid not in chain:
        chain.add(pid)
        pid = procs[pid]["ppid"]
    return chain


def find_orphans(procs, cfg):
    job_pids = launchd_job_pids()
    whitelist = set(cfg.get("whitelist_patterns", [])) | launch_agent_whitelist()
    protected = ancestors(procs, SELF_PID)
    min_age = int(cfg["orphan_min_age_min"]) * 60

    children = {}
    for p in procs.values():
        children.setdefault(p["ppid"], []).append(p["pid"])

    found = []
    for p in procs.values():
        if p["uid"] != UID or p["ppid"] != 1:
            continue
        if p["pid"] in job_pids or p["pid"] in protected:
            continue
        if p["tty"] not in ("??", "?"):
            continue
        if not is_tool_process(p["cmd"]):
            continue
        if any(w in p["cmd"] for w in whitelist):
            continue
        tree = descendants(children, p["pid"])

        # False-kill protection: do not reap if any descendant is a non-tool process
        # that is not in the tool name regex and not a headless browser.
        all_descendants_tools = True
        for c in tree:
            if c in procs and not is_tool_process(procs[c]["cmd"]):
                all_descendants_tools = False
                break
        if not all_descendants_tools:
            continue

        found.append({
            "proc": p,
            "tree": tree,
            "tree_mb": p["rss_mb"] + sum(procs[c]["rss_mb"] for c in tree if c in procs),
            "old_enough": p["age"] >= min_age,
        })
    return found


def kill_tree(procs, item):
    pids = list(reversed(item["tree"])) + [item["proc"]["pid"]]
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    time.sleep(3)
    survivors = []
    for pid in pids:
        try:
            os.kill(pid, 0)
            os.kill(pid, signal.SIGKILL)
            survivors.append(pid)
        except (ProcessLookupError, PermissionError):
            pass
    return survivors


def short(cmd, n=110):
    cmd = cmd.replace(HOME, "~")
    return cmd if len(cmd) <= n else cmd[: n - 1] + "…"


def check_runaway(procs, cfg, state, notify=True):
    """连续多次巡检都持续高 CPU 的进程：弹窗询问，不自动结束。"""
    now = time.time()
    prev = state.get("cpu_samples", {})
    prev_time = state.get("sample_time")
    streaks = state.get("runaway_streak", {})
    notified = state.get("notified", {})
    new_samples, new_streaks, runaway = {}, {}, []
    protected = ancestors(procs, SELF_PID)
    for p in procs.values():
        if p["uid"] != UID or p["pid"] in protected:
            continue
        if exe_of(p["cmd"]).startswith(PROTECTED_PREFIXES):
            continue
        key = str(p["pid"])
        new_samples[key] = [p["cpu"], p["age"]]
        if prev_time and key in prev:
            wall = now - prev_time
            old_cpu, old_age = prev[key]
            if p["age"] >= old_age and wall > 60:
                ratio = (p["cpu"] - old_cpu) / wall
                if ratio >= float(cfg["runaway_cpu_ratio"]):
                    new_streaks[key] = streaks.get(key, 0) + 1
                    if new_streaks[key] >= int(cfg["runaway_consecutive"]):
                        runaway.append((p, ratio))
    cooldown = int(cfg["runaway_notify_cooldown_min"]) * 60
    for p, ratio in runaway:
        key = str(p["pid"])
        if now - notified.get(key, 0) < cooldown:
            continue
        notified[key] = now
        name = os.path.basename(exe_of(p["cmd"]))
        log("失控提醒 pid=%d cpu=%.0f%% 运行=%ds 内存=%dMB | %s"
            % (p["pid"], ratio * 100, p["age"], p["rss_mb"], short(p["cmd"])))
        if notify and cfg.get("runaway_action", "ask") == "ask":
            ask_kill(p["pid"], name, ratio)
    notified = {k: v for k, v in notified.items() if now - v < 86400}
    state.update({"cpu_samples": new_samples, "sample_time": now,
                  "runaway_streak": new_streaks, "notified": notified})
    return runaway


def ask_kill(pid, name, ratio):
    msg = ("进程「%s」(PID %d) 已持续约 20 分钟占用 %.0f%% CPU，可能卡死了。\\n"
           "结束它通常只会让对应窗口重新加载，不会关掉整个应用。" % (name, pid, ratio * 100))
    script = (
        'set r to button returned of (display dialog "%s" with title "Agent 清道夫" '
        'buttons {"忽略", "结束进程"} default button "忽略" giving up after 300)\n'
        'if r is "结束进程" then do shell script "kill %d; sleep 2; kill -9 %d 2>/dev/null; true"'
        % (msg.replace('"', "'"), pid, pid)
    )
    subprocess.Popen(["/usr/bin/osascript", "-e", script],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def clean_bloated_helpers(procs, dry=False):
    """自动回收后台膨胀的 WebKit.WebContent (>500MB) 与无用系统分析进程 (mediaanalysisd/photoanalysisd/wpscloudsvr)。"""
    cleaned = []
    for p in procs.values():
        if p["uid"] != UID or p["pid"] == SELF_PID:
            continue
        cmd = p["cmd"]
        mb = p["rss_mb"]
        reason = None
        if "com.apple.WebKit.WebContent" in cmd and mb >= 500:
            reason = "膨胀的 WebKit 渲染进程 (%dMB)" % mb
        elif ("/mediaanalysisd" in cmd or "/photoanalysisd" in cmd) and mb >= 180:
            reason = "后台媒体分析守护进程 (%dMB)" % mb
        elif "/wpscloudsvr" in cmd and mb >= 180:
            reason = "WPS 后台云盘冗余服务 (%dMB)" % mb
        if reason:
            cleaned.append((p, reason))
            if not dry:
                try:
                    os.kill(p["pid"], signal.SIGKILL)
                except OSError:
                    pass
    return cleaned


def main():
    args = set(sys.argv[1:])
    dry = "--dry-run" in args or "--status" in args
    cfg = load_config()
    state = load_json(STATE_PATH, {})
    procs = snapshot()

    orphans = find_orphans(procs, cfg)
    ready = [o for o in orphans if o["old_enough"]]
    bloated = clean_bloated_helpers(procs, dry=dry)

    if "--status" in args or "--dry-run" in args:
        print("孤儿工具进程（父进程已退出）：%d 个，其中超过 %d 分钟、会被清理的：%d 个"
              % (len(orphans), cfg["orphan_min_age_min"], len(ready)))
        for o in orphans:
            p = o["proc"]
            tag = "将清理" if o["old_enough"] else "观察中"
            print("  [%s] pid=%d 存活=%dmin 子进程=%d 内存=%dMB | %s"
                  % (tag, p["pid"], p["age"] // 60, len(o["tree"]), o["tree_mb"], short(p["cmd"])))
        if bloated:
            print("膨胀后台辅助进程：%d 个" % len(bloated))
            for p, reason in bloated:
                print("  [将回收] pid=%d %s" % (p["pid"], reason))
        zombies = [p for p in procs.values() if p["uid"] == UID and "Z" in p["stat"]]
        print("僵尸进程：%d 个" % len(zombies))
        runaway = check_runaway(procs, cfg, dict(state), notify=False)
        if runaway:
            print("持续高 CPU 进程：")
            for p, ratio in runaway:
                print("  pid=%d cpu=%.0f%% | %s" % (p["pid"], ratio * 100, short(p["cmd"])))
        return

    freed_mb, killed = 0, 0
    for o in ready:
        p = o["proc"]
        survivors = kill_tree(procs, o)
        killed += 1 + len(o["tree"])
        freed_mb += o["tree_mb"]
        log("清理孤儿 pid=%d 存活=%dmin 子进程=%d 内存=%dMB%s | %s"
            % (p["pid"], p["age"] // 60, len(o["tree"]), o["tree_mb"],
               " (已强制结束)" if survivors else "", short(p["cmd"])))
    for p, reason in bloated:
        killed += 1
        freed_mb += p["rss_mb"]
        log("回收膨胀辅助进程 pid=%d | %s" % (p["pid"], reason))
    if killed:
        log("本轮共清理 %d 个进程，释放约 %dMB 内存" % (killed, freed_mb))

    check_runaway(snapshot() if killed else procs, cfg, state, notify=not dry)
    save_json(STATE_PATH, state)


if __name__ == "__main__":
    main()
