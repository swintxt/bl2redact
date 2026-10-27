import os, re, tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

PFX = re.compile(r'^\[\d+\.\d+\]\s+Log:\s?')
HDR = re.compile(r"\*\*\* Property dump for object '(\S+) (.+?)' \*\*\*")
PROP = re.compile(r'^\s*([A-Za-z_]\w*(?:\[\d+\]|\(\d+\))?)=(.*)$')


def parse(path):
    """Читает Launch.log, возвращает {путь_объекта: {'class':..., 'props':{имя:значение}}}."""
    objs, cur = {}, None
    for raw in open(path, encoding="utf-8", errors="replace"):
        raw = raw.rstrip("\r\n")
        pre = PFX.match(raw)
        l = PFX.sub("", raw) if pre else raw
        m = HDR.search(l)
        if m:
            cur = objs[m.group(2)] = {"class": m.group(1), "props": {}}
            continue
        if cur is None or l.strip() == "" or l.lstrip().startswith("==="):
            continue
        if pre and not l.startswith(" "):
            cur = None
            continue
        m = PROP.match(l)
        if m:
            cur["props"][m.group(1)] = m.group(2)
    return objs


def cmd(obj, prop, val):
    prop = re.sub(r"\((\d+)\)$", r"[\1]", prop)
    return "set %s %s %s" % (obj, prop, val)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("BL2 Data Explorer")
        self.geometry("1000x600")
        self.objs, self.changes, self.cur = {}, {}, None
        top = ttk.Frame(self); top.pack(fill="x", padx=6, pady=4)
        for t, c in (("Открыть лог", self.open_log), ("Экспорт мода (.txt)", self.export),
                     ("Сохранить в игру", self.to_game), ("Копировать команды", self.copy),
                     ("Сбросить правки", self.reset)):
            ttk.Button(top, text=t, command=c).pack(side="left", padx=2)
        self.info = ttk.Label(top, text="Откройте Launch.log с дампами (obj dump ...)")
        self.info.pack(side="left", padx=8)
        pw = ttk.PanedWindow(self, orient="horizontal"); pw.pack(fill="both", expand=True)
        L = ttk.Frame(pw); R = ttk.Frame(pw); pw.add(L, weight=1); pw.add(R, weight=2)
        self.q1 = tk.StringVar(); self.q1.trace_add("write", lambda *a: self.fill_objs())
        ttk.Entry(L, textvariable=self.q1).pack(fill="x")
        self.lb = tk.Listbox(L, exportselection=False); self.lb.pack(fill="both", expand=True)
        self.lb.bind("<<ListboxSelect>>", self.pick)
        self.q2 = tk.StringVar(); self.q2.trace_add("write", lambda *a: self.fill_props())
        ttk.Entry(R, textvariable=self.q2).pack(fill="x")
        self.tv = ttk.Treeview(R, columns=("p", "v", "m"), show="headings")
        for c, t, w in (("p", "Свойство", 200), ("v", "Значение", 480), ("m", "Изм.", 40)):
            self.tv.heading(c, text=t); self.tv.column(c, width=w)
        self.tv.pack(fill="both", expand=True)
        self.tv.bind("<Double-1>", self.edit)
        self.log_guess()

    def log_guess(self):
        p = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Borderlands 2",
                         "WillowGame", "Logs", "Launch.log")
        if os.path.isfile(p):
            self.load(p)

    def open_log(self):
        p = filedialog.askopenfilename(filetypes=[("Log", "*.log *.txt"), ("Все", "*.*")])
        if p:
            self.load(p)

    def load(self, p):
        try:
            self.objs = parse(p)
        except Exception as e:
            messagebox.showerror("Ошибка", str(e)); return
        self.info.config(text="Объектов: %d" % len(self.objs))
        self.fill_objs()

    def fill_objs(self):
        q = self.q1.get().lower()
        self.names = [n for n in sorted(self.objs) if q in n.lower()][:2000]
        self.lb.delete(0, "end")
        for n in self.names:
            self.lb.insert("end", n)

    def pick(self, _=None):
        s = self.lb.curselection()
        if s:
            self.cur = self.names[s[0]]
            self.fill_props()

    def fill_props(self):
        self.tv.delete(*self.tv.get_children())
        if not self.cur:
            return
        q = self.q2.get().lower()
        for k, v in self.objs[self.cur]["props"].items():
            ch = self.changes.get((self.cur, k))
            if q and q not in k.lower() and q not in (ch or v).lower():
                continue
            self.tv.insert("", "end", iid=k, values=(k, ch if ch is not None else v, "*" if ch is not None else ""))

    def edit(self, _=None):
        s = self.tv.selection()
        if not s or not self.cur:
            return
        k = s[0]
        old = self.changes.get((self.cur, k), self.objs[self.cur]["props"][k])
        n = simpledialog.askstring("Правка", k, initialvalue=old, parent=self)
        if n is not None and n != self.objs[self.cur]["props"][k]:
            self.changes[(self.cur, k)] = n
        elif n is not None:
            self.changes.pop((self.cur, k), None)
        self.fill_props()

    def text(self):
        return "\n".join(cmd(o, p, v) for (o, p), v in self.changes.items()) + "\n"

    def need(self):
        if not self.changes:
            messagebox.showinfo("Нет правок", "Дважды кликните по значению свойства.")
            return False
        return True

    def export(self):
        if self.need():
            p = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="mod.txt")
            if p:
                open(p, "w", encoding="utf-8").write(self.text())

    def to_game(self):
        if not self.need():
            return
        g = filedialog.askdirectory(title="Папка игры")
        if not g:
            return
        for sub in ("Binaries", os.path.join("Binaries", "Win32")):
            d = os.path.join(g, sub); os.makedirs(d, exist_ok=True)
            open(os.path.join(d, "mod.txt"), "w", encoding="utf-8").write(self.text())
        messagebox.showinfo("Готово", "В игре введите в консоли: exec mod.txt")

    def copy(self):
        if self.need():
            self.clipboard_clear(); self.clipboard_append(self.text())

    def reset(self):
        self.changes.clear(); self.fill_props()


if __name__ == "__main__":
    App().mainloop()
