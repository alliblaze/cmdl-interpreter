#!/usr/bin/env python3
"""
Simple CMD-style interpreter for .cmdl scripts.

Notes:
- Supports text, set, math, clear, labels, goto, loop, if/elif/else, color, pause, exit.
- pause() or pause  -> waits for Enter
- pause(n) or pause n -> sleeps for n seconds (accepts integers/floats or numeric variable)
- Use --hold when running a script to keep the window open after the script finishes.
"""

import sys
import re
import math
import os
import time

# -------------------------
# Utilities
# -------------------------
def is_number(s):
    try:
        float(s)
        return True
    except:
        return False

def to_number(s):
    try:
        if '.' in str(s):
            return float(s)
        return int(s)
    except:
        return float(s)

def clear_console():
    os.system('cls' if os.name == 'nt' else 'clear')

# very small ANSI color helper (best-effort)
ANSI_COLORS = {
    "black":"30","red":"31","green":"32","yellow":"33","blue":"34","purple":"35",
    "magenta":"35","cyan":"36","white":"37","brown":"33","orange":"33","pink":"95"
}
def set_color_ansi(name_or_rgb):
    if isinstance(name_or_rgb, tuple):
        r,g,b = name_or_rgb
        print(f"\x1b[38;2;{r};{g};{b}m", end="")
        return
    n = name_or_rgb.lower()
    code = ANSI_COLORS.get(n)
    if code:
        print(f"\x1b[{code}m", end="")
    else:
        print("\x1b[0m", end="")

# -------------------------
# Parser: build a tree based on indentation
# -------------------------
INDENT_UNIT = 4  # spaces or a tab counted as one indent

def indent_level(line):
    if line.startswith("\t"):
        return len(re.match(r'^\t*', line).group(0))
    m = re.match(r'^( *)', line)
    spaces = len(m.group(1))
    return spaces // INDENT_UNIT

def tokenize_text_args(argstr):
    parts = []
    cur = ""
    in_quote = False
    quote_char = None
    i = 0
    while i < len(argstr):
        ch = argstr[i]
        if in_quote:
            cur += ch
            if ch == quote_char:
                in_quote = False
            i += 1
            continue
        if ch in ('"', "'"):
            in_quote = True
            quote_char = ch
            cur += ch
            i += 1
            continue
        if ch == ',':
            parts.append(cur.strip())
            cur = ""
            i += 1
            continue
        cur += ch
        i += 1
    if cur.strip() != "":
        parts.append(cur.strip())
    return parts

def strip_quotes(s):
    s = s.strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    return s

def parse_lines(lines):
    root = []
    stack = [( -1, root )]
    i = 0
    while i < len(lines):
        raw = lines[i].rstrip("\n")
        if raw.strip() == "" or raw.strip().startswith("#"):
            i += 1
            continue
        ind = indent_level(raw)
        while ind <= stack[-1][0] and len(stack) > 1:
            stack.pop()
        cur_list = stack[-1][1]
        stripped = raw.lstrip()
        m_label = re.match(r'^([A-Za-z_]\w*)\(\):\s*$', stripped)
        if m_label:
            node = {"type":"label", "name": m_label.group(1), "raw": stripped, "children": [], "parent": cur_list}
            cur_list.append(node)
            i += 1
            continue
        m_loop = re.match(r'^loop(?:\(([^)]*)\))?:\s*$', stripped)
        if m_loop:
            param = m_loop.group(1)
            node = {"type":"loop", "param": param.strip() if param else None, "raw": stripped, "children": [], "parent": cur_list}
            cur_list.append(node)
            stack.append((ind, node["children"]))
            i += 1
            continue
        m_if = re.match(r'^(if|elif)\s+(.+?):\s*$', stripped)
        m_else = re.match(r'^else:\s*$', stripped)
        if m_if:
            kind = m_if.group(1)
            cond = m_if.group(2).strip()
            node = {"type":"ifpart", "kind": kind, "cond": cond, "children": [], "raw": stripped, "parent": cur_list}
            if kind == "if":
                wrapper = {"type":"if", "parts":[node], "raw": stripped, "parent": cur_list}
                cur_list.append(wrapper)
            else:
                found = None
                for n in reversed(cur_list):
                    if n.get("type") == "if":
                        found = n
                        break
                if not found:
                    cur_list.append(node)
                    i += 1
                    continue
                found["parts"].append(node)
            stack.append((ind, node["children"]))
            i += 1
            continue
        if m_else:
            node = {"type":"ifpart", "kind":"else", "cond": None, "children": [], "raw": stripped, "parent": cur_list}
            found = None
            for n in reversed(cur_list):
                if n.get("type") == "if":
                    found = n
                    break
            if not found:
                cur_list.append(node); i += 1; continue
            found["parts"].append(node)
            stack.append((ind, node["children"]))
            i += 1
            continue
        node = {"type":"stmt", "raw": stripped, "parent": cur_list}
        cur_list.append(node)
        i += 1
    return root

# -------------------------
# Execution engine
# -------------------------
class RuntimeErrorInter(Exception):
    pass

class Interpreter:
    def __init__(self, root):
        self.root = root
        self.vars = {}
        self.labels = {}
        self._index_labels(self.root)
        self.call_stack_limit = 10000

    def _index_labels(self, node_list):
        for idx, n in enumerate(node_list):
            if n["type"] == "label":
                parent = n["parent"]
                try:
                    i = parent.index(n)
                except ValueError:
                    i = idx
                target_index = i + 1
                self.labels[n["name"]] = (parent, target_index)
            if "children" in n:
                self._index_labels(n["children"])
            if n.get("type") == "if":
                for p in n["parts"]:
                    self._index_labels(p["children"])

    def eval_expr(self, expr):
        def repl_var(m):
            name = m.group(0)
            if name in ("and","or","not"):
                return name
            if name in self.vars:
                v = self.vars[name]
                if isinstance(v, str) and is_number(v):
                    return v
                if isinstance(v, (int,float)):
                    return str(v)
                return repr(v)
            return "0"
        safe = re.sub(r'\b[A-Za-z_]\w*\b', repl_var, expr)
        try:
            return eval(safe, {"__builtins__":None}, {})
        except Exception as e:
            raise RuntimeErrorInter(f"Bad expression: {expr} -> {e}")

    def resolve_value(self, token):
        token = token.strip()
        if (token.startswith('"') and token.endswith('"')) or (token.startswith("'") and token.endswith("'")):
            return token[1:-1]
        if is_number(token):
            n = to_number(token)
            return n
        return self.vars.get(token, "")

    def run_stmt_list(self, lst, start_idx=0):
        i = start_idx
        while i < len(lst):
            n = lst[i]
            res = self.run_node(n)
            if isinstance(res, dict) and res.get("action") == "goto":
                label = res["label"]
                if label not in self.labels:
                    raise RuntimeErrorInter(f"Unknown label: {label}")
                parent, idx = self.labels[label]
                return ("jump", parent, idx)
            if isinstance(res, dict) and res.get("action") == "return_to_caller":
                return ("return",)
            i += 1
        return ("done",)

    def run_node(self, node):
        typ = node["type"]
        if typ == "label":
            return None
        if typ == "stmt":
            raw = node["raw"]

            # support "cmd(arg)" and "cmd arg..." forms
            m = re.match(r'^([A-Za-z_]\w*)(?:\(([^)]*)\))?(?:\s+(.*))?$', raw)
            if not m:
                return None
            cmd = m.group(1).lower()
            paren_args = m.group(2)
            rest = m.group(3) or ""
            if paren_args and rest.strip() == "":
                rest = paren_args

            if cmd == "text":
                parts = tokenize_text_args(rest)
                out_parts = []
                for p in parts:
                    p = p.strip()
                    if p == "": continue
                    if (p.startswith('"') and p.endswith('"')) or (p.startswith("'") and p.endswith("'")):
                        out_parts.append(p[1:-1])
                    else:
                        val = self.vars.get(p, "")
                        out_parts.append(str(val))
                print("".join(out_parts))
            elif cmd == "echo":
                print(rest)
            elif cmd == "set":
                mset = re.match(r'^([A-Za-z_]\w*)\s*=\s*(.+)$', rest)
                if not mset:
                    raise RuntimeErrorInter(f"Bad set syntax: {raw}")
                name = mset.group(1)
                val_raw = mset.group(2).strip()
                if (val_raw.startswith('"') and val_raw.endswith('"')) or (val_raw.startswith("'") and val_raw.endswith("'")):
                    self.vars[name] = val_raw[1:-1]
                elif is_number(val_raw):
                    self.vars[name] = to_number(val_raw)
                else:
                    if re.search(r'[\+\-\*/()]', val_raw):
                        v = self.eval_expr(val_raw)
                        self.vars[name] = v
                    else:
                        self.vars[name] = self.vars.get(val_raw, val_raw)
            elif cmd == "math":
                mm = re.match(r'^([A-Za-z_]\w*)\s*=\s*(.+)$', rest)
                if not mm:
                    raise RuntimeErrorInter(f"Bad math syntax: {raw}")
                name = mm.group(1)
                expr = mm.group(2)
                v = self.eval_expr(expr)
                self.vars[name] = v
            elif cmd == "clear":
                clear_console()
            elif cmd == "goto":
                label = rest.strip()
                label = re.sub(r'\(\)\s*$', '', label)
                return {"action":"goto","label":label}
            elif cmd == "pause":
                t = rest.strip()
                if t == "":
                    # wait for Enter
                    input("Press Enter to continue...")
                elif is_number(t):
                    time.sleep(float(t))
                else:
                    # allow a numeric variable name
                    if t in self.vars and is_number(self.vars[t]):
                        time.sleep(float(self.vars[t]))
                    else:
                        input("Press Enter to continue...")
            elif cmd == "exit":
                sys.exit(0)
            elif cmd == "color":
                r = rest.strip()
                m_rgb = re.match(r'rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)', r, re.IGNORECASE)
                if m_rgb:
                    rr,gg,bb = map(int, m_rgb.groups())
                    set_color_ansi((rr,gg,bb))
                else:
                    set_color_ansi(r)
            else:
                print(f"Unknown command: {cmd} (raw: {raw})")
            return None

        if typ == "loop":
            param = node.get("param")
            if param is None or param == "":
                while True:
                    res = self.run_stmt_list(node["children"], 0)
                    if res[0] == "jump":
                        return {"action":"goto","label": None, "jump": res}
                    if res[0] == "done":
                        continue
                    if res[0] == "return":
                        return {"action":"return_to_caller"}
            else:
                p = param.strip()
                if is_number(p):
                    times = int(to_number(p))
                else:
                    times = int(to_number(self.vars.get(p, 0)))
                for _ in range(times):
                    r = self.run_stmt_list(node["children"], 0)
                    if r[0] == "jump":
                        parent, idx = r[1], r[2]
                        return {"action":"goto","label": None, "jump": r}
                    if r[0] == "return":
                        return {"action":"return_to_caller"}
            return None

        if typ == "if":
            for part in node["parts"]:
                kind = part["kind"]
                if kind == "else":
                    r = self.run_stmt_list(part["children"], 0)
                    if r[0] == "jump":
                        parent, idx = r[1], r[2]
                        return {"action":"goto","label": None, "jump": r}
                    if r[0] == "return":
                        return {"action":"return_to_caller"}
                    return None
                else:
                    cond = part["cond"]
                    try:
                        cond_eval = cond
                        cond_eval = re.sub(r'(?<![=!<>])\s=\s(?!=)', '==', cond_eval)
                        def rv(m):
                            name = m.group(0)
                            if name in self.vars:
                                v = self.vars[name]
                                if isinstance(v, str):
                                    return repr(v)
                                return str(v)
                            return "0"
                        cond_safe = re.sub(r'\b[A-Za-z_]\w*\b', rv, cond_eval)
                        ok = bool(eval(cond_safe, {"__builtins__":None}, {}))
                    except Exception as e:
                        raise RuntimeErrorInter(f"Bad condition '{cond}': {e}")
                    if ok:
                        r = self.run_stmt_list(part["children"], 0)
                        if r[0] == "jump":
                            parent, idx = r[1], r[2]
                            return {"action":"goto","label": None, "jump": r}
                        if r[0] == "return":
                            return {"action":"return_to_caller"}
                        return None
            return None

        return None

    def run(self):
        cur_list = self.root
        idx = 0
        steps = 0
        while True:
            if idx >= len(cur_list):
                break
            node = cur_list[idx]
            res = self.run_node(node)
            if isinstance(res, dict) and res.get("action") == "goto":
                label = res.get("label")
                if label is not None:
                    if label not in self.labels:
                        raise RuntimeErrorInter(f"Unknown label: {label}")
                    parent, new_idx = self.labels[label]
                    cur_list = parent
                    idx = new_idx
                    continue
                j = res.get("jump")
                if j and j[0] == "jump":
                    parent, new_idx = j[1], j[2]
                    cur_list = parent
                    idx = new_idx
                    continue
            idx += 1
            steps += 1
            if steps > self.call_stack_limit:
                raise RuntimeErrorInter("Step limit exceeded (possible infinite loop).")

# -------------------------
# Helper / CLI
# -------------------------
SAMPLE = """# demo script
text "Starting demo..."
text "This line should appear."

loop(3):
    text "Inside loop, counting"

set x = 5
math x = x + 2
text "x is now: ", x

if x = 7:
    text "If statement works!"
else:
    text "If failed!"

text "Pausing 1.5 seconds..."
pause(1.5)

text "Clearing screen in 1 second..."
pause(1)
clear
text "Screen was cleared!"
text "Demo finished."
"""

def run_script_text(script_text):
    lines = script_text.splitlines()
    root = parse_lines(lines)
    interp = Interpreter(root)
    interp.run()

def run_file_path(path):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    root = parse_lines(lines)
    interp = Interpreter(root)
    interp.run()

if __name__ == "__main__":
    args = sys.argv[1:]
    hold = False

    # convenience flags
    if "--demo" in args or "-d" in args or len(args) == 0:
        print("Running demo script...\n")
        run_script_text(SAMPLE)
        sys.exit(0)

    # detect and remove --hold flag
    if "--hold" in args:
        hold = True
        args = [a for a in args if a != "--hold"]

    if len(args) == 0:
        print("Usage: python cmdl_interpreter_with_pause.py <script.cmdl> [--hold]")
        sys.exit(1)

    fp = args[0]
    if not os.path.exists(fp):
        print(f"File not found: {fp}")
        print("Usage: python cmdl_interpreter_with_pause.py yourscript.cmdl [--hold]")
        sys.exit(1)

    try:
        run_file_path(fp)
    except Exception as e:
        print("ERROR:", e)
        raise

    if hold:
        try:
            input("\nScript finished. Press Enter to exit...")
        except:
            pass
