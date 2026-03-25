"""
CryptoDesk — Tkinter Crypto Trading App
Requirements: pip install requests matplotlib
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import requests
import time
from datetime import datetime
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter

# ── Palette ──────────────────────────────────────────────────────────────────
BG1    = "#0d0f14"   # deepest background
BG2    = "#13151c"   # panel background
BG3    = "#1a1d27"   # input / card background
BORDER = "#1f2230"   # separator lines
FG     = "#e8eaf0"   # primary text
MUTED  = "#6b7280"   # secondary text
ACCENT = "#6366f1"   # indigo accent
GREEN  = "#22c55e"
RED    = "#ef4444"
FONT   = ("Segoe UI", 10)
FONT_B = ("Segoe UI", 10, "bold")
MONO   = ("Consolas", 10)
MONO_B = ("Consolas", 10, "bold")

# ── CoinGecko Config ──────────────────────────────────────────────────────────
BASE = "https://api.coingecko.com/api/v3"
COINS = [
    {"id": "bitcoin",      "symbol": "BTC", "name": "Bitcoin"},
    {"id": "ethereum",     "symbol": "ETH", "name": "Ethereum"},
    {"id": "solana",       "symbol": "SOL", "name": "Solana"},
    {"id": "binancecoin",  "symbol": "BNB", "name": "BNB"},
    {"id": "ripple",       "symbol": "XRP", "name": "XRP"},
    {"id": "cardano",      "symbol": "ADA", "name": "Cardano"},
]
RANGES = [
    {"label": "1H",  "days": "0.042", "interval": "minutely"},
    {"label": "24H", "days": "1",     "interval": "hourly"},
    {"label": "7D",  "days": "7",     "interval": "daily"},
    {"label": "30D", "days": "30",    "interval": "daily"},
]

# ── Helpers ───────────────────────────────────────────────────────────────────
def fmt_price(n):
    if n is None: return "—"
    if n >= 1000: return f"${n:,.2f}"
    if n >= 1:    return f"${n:.4f}"
    return f"${n:.6f}"

def fmt_usd(n): return f"${n:,.2f}" if n is not None else "—"
def fmt_pct(n): return f"{n:+.2f}%" if n is not None else "—"

# ── API Layer ─────────────────────────────────────────────────────────────────
class CoinGecko:
    HEADERS = {"accept": "application/json"}

    @staticmethod
    def markets():
        ids = ",".join(c["id"] for c in COINS)
        url = f"{BASE}/coins/markets"
        params = {
            "vs_currency": "usd",
            "ids": ids,
            "order": "market_cap_desc",
            "sparkline": "false",
            "price_change_percentage": "24h",
        }
        r = requests.get(url, params=params, headers=CoinGecko.HEADERS, timeout=8)
        r.raise_for_status()
        return {m["id"]: m for m in r.json()}

    @staticmethod
    def chart(coin_id, days, interval):
        url = f"{BASE}/coins/{coin_id}/market_chart"
        params = {"vs_currency": "usd", "days": days, "interval": interval}
        r = requests.get(url, params=params, headers=CoinGecko.HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
        prices = data.get("prices", [])
        return [(ts / 1000, float(p)) for ts, p in prices]

# ── Main Application ──────────────────────────────────────────────────────────
class CryptoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CryptoDesk")
        self.geometry("1200x720")
        self.minsize(900, 600)
        self.configure(bg=BG1)

        # State
        self.market_data   = {}
        self.selected_coin = COINS[0]
        self.selected_range = RANGES[1]
        self.chart_data    = []
        self.portfolio     = {
            "BTC": {"qty": 0.25, "avg_cost": 58000},
            "ETH": {"qty": 2.1,  "avg_cost": 2800},
            "SOL": {"qty": 15,   "avg_cost": 120},
        }
        self.trades = []
        self._loading_chart = False
        self._loading_markets = False

        self._build_ui()
        self._start_market_refresh()
        self._load_chart()

    # ── UI Builder ────────────────────────────────────────────────────────────
    def _build_ui(self):
        self._style_ttk()

        # Top header
        hdr = tk.Frame(self, bg=BG2, height=52)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  ◈ CryptoDesk", bg=BG2, fg=FG,
                 font=("Segoe UI", 13, "bold")).pack(side="left", padx=8)
        self.lbl_portfolio_val = tk.Label(hdr, text="Portfolio: —", bg=BG2,
                                          fg=GREEN, font=FONT_B)
        self.lbl_portfolio_val.pack(side="right", padx=16)
        self.lbl_pnl = tk.Label(hdr, text="P&L: —", bg=BG2, fg=MUTED, font=FONT)
        self.lbl_pnl.pack(side="right", padx=4)

        sep = tk.Frame(self, bg=BORDER, height=1)
        sep.pack(fill="x")

        # Body (sidebar | center | right panel)
        body = tk.Frame(self, bg=BG1)
        body.pack(fill="both", expand=True)

        self._build_sidebar(body)
        self._build_right_panel(body)
        self._build_center(body)

    def _style_ttk(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview",
            background=BG3, foreground=FG, fieldbackground=BG3,
            rowheight=30, font=FONT, borderwidth=0)
        style.configure("Treeview.Heading",
            background=BG2, foreground=MUTED, font=("Segoe UI", 9, "bold"),
            borderwidth=0, relief="flat")
        style.map("Treeview",
            background=[("selected", ACCENT)],
            foreground=[("selected", "#fff")])

    # ── Sidebar ───────────────────────────────────────────────────────────────
    def _build_sidebar(self, parent):
        sb = tk.Frame(parent, bg=BG2, width=200)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)

        tk.Frame(sb, bg=BORDER, height=1).pack(fill="x")
        tk.Label(sb, text="MARKETS", bg=BG2, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=14, pady=(10, 6))

        self.market_buttons = {}
        for coin in COINS:
            frm = tk.Frame(sb, bg=BG2, cursor="hand2")
            frm.pack(fill="x")

            indicator = tk.Frame(frm, bg=BG2, width=3)
            indicator.pack(side="left", fill="y")

            inner = tk.Frame(frm, bg=BG2, padx=10, pady=8)
            inner.pack(side="left", fill="x", expand=True)

            top_row = tk.Frame(inner, bg=BG2)
            top_row.pack(fill="x")

            lbl_sym = tk.Label(top_row, text=coin["symbol"], bg=BG2, fg=FG, font=FONT_B)
            lbl_sym.pack(side="left")

            lbl_chg = tk.Label(top_row, text="—", bg=BG2, fg=MUTED, font=("Segoe UI", 9))
            lbl_chg.pack(side="right")

            lbl_price = tk.Label(inner, text="Loading…", bg=BG2, fg=MUTED, font=MONO)
            lbl_price.pack(anchor="w")

            self.market_buttons[coin["id"]] = {
                "frame": frm, "inner": inner, "indicator": indicator,
                "lbl_price": lbl_price, "lbl_chg": lbl_chg, "lbl_sym": lbl_sym,
            }

            def on_click(c=coin):
                self.selected_coin = c
                self._refresh_sidebar_selection()
                self._load_chart()
                self._update_pair_header()

            for w in (frm, inner, top_row, lbl_sym, lbl_chg, lbl_price):
                w.bind("<Button-1>", lambda e, c=coin: on_click(c))

        self._refresh_sidebar_selection()

    def _refresh_sidebar_selection(self):
        for cid, widgets in self.market_buttons.items():
            active = cid == self.selected_coin["id"]
            bg = "#1a1c2e" if active else BG2
            ind = ACCENT if active else BG2
            for w in (widgets["frame"], widgets["inner"]):
                w.configure(bg=bg)
            widgets["indicator"].configure(bg=ind)
            widgets["lbl_sym"].configure(bg=bg)
            widgets["lbl_chg"].configure(bg=bg)
            widgets["lbl_price"].configure(bg=bg)

    # ── Center ────────────────────────────────────────────────────────────────
    def _build_center(self, parent):
        center = tk.Frame(parent, bg=BG1)
        center.pack(side="left", fill="both", expand=True)

        # Pair header bar
        pair_bar = tk.Frame(center, bg=BG2, height=64)
        pair_bar.pack(fill="x")
        pair_bar.pack_propagate(False)
        tk.Frame(center, bg=BORDER, height=1).pack(fill="x")

        ph = tk.Frame(pair_bar, bg=BG2)
        ph.pack(side="left", padx=16, pady=8)

        self.lbl_pair = tk.Label(ph, text="BTC/USDT", bg=BG2, fg=FG,
                                  font=("Segoe UI", 14, "bold"))
        self.lbl_pair.pack(anchor="w")
        self.lbl_coin_name = tk.Label(ph, text="Bitcoin", bg=BG2, fg=MUTED, font=FONT)
        self.lbl_coin_name.pack(anchor="w")

        pstats = tk.Frame(pair_bar, bg=BG2)
        pstats.pack(side="left", padx=20, pady=8)

        self.lbl_current_price = tk.Label(pstats, text="—", bg=BG2, fg=FG,
                                           font=("Consolas", 20, "bold"))
        self.lbl_current_price.pack(anchor="w")

        self.lbl_change = tk.Label(pstats, text="—", bg=BG2, fg=MUTED, font=FONT)
        self.lbl_change.pack(anchor="w")

        for key, label in [("high", "24H High"), ("low", "24H Low"), ("vol", "Volume")]:
            box = tk.Frame(pair_bar, bg=BG2, padx=14)
            box.pack(side="left")
            tk.Label(box, text=label, bg=BG2, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w")
            lbl = tk.Label(box, text="—", bg=BG2, fg=FG, font=MONO)
            lbl.pack(anchor="w")
            setattr(self, f"lbl_{key}", lbl)

        # Tabs
        tab_bar = tk.Frame(center, bg=BG2)
        tab_bar.pack(fill="x")
        tk.Frame(center, bg=BORDER, height=1).pack(fill="x")

        self.tab_frames = {}
        self.tab_buttons = {}
        self.active_tab = tk.StringVar(value="chart")

        for tab_id, tab_name in [("chart", "Price Chart"), ("history", "Trade History")]:
            btn = tk.Label(tab_bar, text=tab_name, bg=BG2, fg=MUTED,
                           font=("Segoe UI", 10), padx=16, pady=10, cursor="hand2")
            btn.pack(side="left")
            btn.bind("<Button-1>", lambda e, t=tab_id: self._switch_tab(t))
            self.tab_buttons[tab_id] = btn

        # Tab content area
        content = tk.Frame(center, bg=BG1)
        content.pack(fill="both", expand=True)

        # Chart tab
        chart_frm = tk.Frame(content, bg=BG1)
        self.tab_frames["chart"] = chart_frm

        # Range buttons
        range_bar = tk.Frame(chart_frm, bg=BG1, pady=10)
        range_bar.pack(fill="x", padx=16)
        self.range_buttons = {}
        for rng in RANGES:
            btn = tk.Label(range_bar, text=rng["label"], bg=BG3, fg=MUTED,
                           font=FONT, padx=12, pady=4, cursor="hand2",
                           relief="flat", bd=0)
            btn.pack(side="left", padx=3)
            btn.bind("<Button-1>", lambda e, r=rng: self._set_range(r))
            self.range_buttons[rng["label"]] = btn
        self._update_range_buttons()

        # Matplotlib chart
        chart_container = tk.Frame(chart_frm, bg=BG2, padx=1, pady=1)
        chart_container.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        self.fig = Figure(figsize=(6, 3.5), facecolor=BG2)
        self.ax  = self.fig.add_subplot(111)
        self._style_chart()

        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_container)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.canvas.draw()

        # History tab
        hist_frm = tk.Frame(content, bg=BG1)
        self.tab_frames["history"] = hist_frm

        cols = ("Time", "Side", "Pair", "Qty", "Price", "Total")
        self.hist_tree = ttk.Treeview(hist_frm, columns=cols,
                                       show="headings", selectmode="browse")
        for col in cols:
            self.hist_tree.heading(col, text=col)
            self.hist_tree.column(col, width=110, anchor="w")
        self.hist_tree.tag_configure("buy",  foreground=GREEN)
        self.hist_tree.tag_configure("sell", foreground=RED)

        sb_hist = ttk.Scrollbar(hist_frm, orient="vertical",
                                command=self.hist_tree.yview)
        self.hist_tree.configure(yscrollcommand=sb_hist.set)
        sb_hist.pack(side="right", fill="y")
        self.hist_tree.pack(fill="both", expand=True)

        self._switch_tab("chart")

    def _switch_tab(self, tab_id):
        self.active_tab.set(tab_id)
        for tid, frm in self.tab_frames.items():
            frm.pack_forget()
        self.tab_frames[tab_id].pack(fill="both", expand=True)
        for tid, btn in self.tab_buttons.items():
            active = tid == tab_id
            btn.configure(fg=FG if active else MUTED)

    def _style_chart(self):
        self.ax.set_facecolor(BG2)
        self.fig.patch.set_facecolor(BG2)
        for spine in self.ax.spines.values():
            spine.set_color(BORDER)
        self.ax.tick_params(colors=MUTED, labelsize=8)
        self.ax.xaxis.label.set_color(MUTED)
        self.ax.yaxis.label.set_color(MUTED)
        self.fig.tight_layout(pad=1.5)

    def _set_range(self, rng):
        self.selected_range = rng
        self._update_range_buttons()
        self._load_chart()

    def _update_range_buttons(self):
        for lbl, btn in self.range_buttons.items():
            active = lbl == self.selected_range["label"]
            btn.configure(bg=ACCENT if active else BG3,
                          fg="#fff" if active else MUTED)

    # ── Right Panel ───────────────────────────────────────────────────────────
    def _build_right_panel(self, parent):
        rp = tk.Frame(parent, bg=BG2, width=260)
        rp.pack(side="right", fill="y")
        rp.pack_propagate(False)
        tk.Frame(rp, bg=BORDER, height=1).pack(fill="x")

        # Order panel
        op = tk.Frame(rp, bg=BG2, padx=14, pady=10)
        op.pack(fill="x")
        tk.Label(op, text="PLACE ORDER", bg=BG2, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 8))

        # Buy / Sell toggle
        toggle = tk.Frame(op, bg=BG2)
        toggle.pack(fill="x", pady=(0, 10))
        self.side_var = tk.StringVar(value="buy")

        self.btn_buy  = tk.Label(toggle, text="Buy",  bg=GREEN, fg="#fff",
                                  font=FONT_B, padx=10, pady=6, cursor="hand2")
        self.btn_sell = tk.Label(toggle, text="Sell", bg=BG3,  fg=MUTED,
                                  font=FONT_B, padx=10, pady=6, cursor="hand2")
        self.btn_buy.pack(side="left", fill="x", expand=True)
        self.btn_sell.pack(side="left", fill="x", expand=True)
        self.btn_buy.bind("<Button-1>",  lambda e: self._set_side("buy"))
        self.btn_sell.bind("<Button-1>", lambda e: self._set_side("sell"))

        # Market price display
        mkt_row = tk.Frame(op, bg=BG3, padx=10, pady=6)
        mkt_row.pack(fill="x", pady=(0, 8))
        tk.Label(mkt_row, text="Market Price", bg=BG3, fg=MUTED, font=FONT).pack(side="left")
        self.lbl_order_price = tk.Label(mkt_row, text="—", bg=BG3, fg=FG, font=MONO_B)
        self.lbl_order_price.pack(side="right")

        # Amount input
        tk.Label(op, text="Amount", bg=BG2, fg=MUTED,
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(0, 2))
        amt_frm = tk.Frame(op, bg=BG3, bd=1, relief="flat")
        amt_frm.pack(fill="x", pady=(0, 8))
        self.amount_var = tk.StringVar()
        self.amount_var.trace_add("write", lambda *a: self._update_total())
        self.entry_amount = tk.Entry(amt_frm, textvariable=self.amount_var,
                                      bg=BG3, fg=FG, font=MONO, relief="flat",
                                      bd=6, insertbackground=FG)
        self.entry_amount.pack(fill="x")
        self.lbl_symbol_suffix = tk.Label(amt_frm, text="BTC", bg=BG3, fg=MUTED,
                                           font=("Segoe UI", 8), padx=6)
        self.lbl_symbol_suffix.place(relx=1.0, rely=0.5, anchor="e")

        # Total preview
        total_row = tk.Frame(op, bg=BG3, padx=10, pady=6)
        total_row.pack(fill="x", pady=(0, 12))
        tk.Label(total_row, text="Total USDT", bg=BG3, fg=MUTED, font=FONT).pack(side="left")
        self.lbl_total = tk.Label(total_row, text="—", bg=BG3, fg=FG, font=MONO_B)
        self.lbl_total.pack(side="right")

        # Submit button
        self.btn_submit = tk.Button(op, text="Buy BTC", bg=GREEN, fg="#fff",
                                     font=FONT_B, relief="flat", bd=0,
                                     activebackground="#16a34a", activeforeground="#fff",
                                     cursor="hand2", command=self._place_order)
        self.btn_submit.pack(fill="x", ipady=6)

        tk.Frame(rp, bg=BORDER, height=1).pack(fill="x", pady=(8, 0))

        # Portfolio
        pf = tk.Frame(rp, bg=BG2, padx=14, pady=10)
        pf.pack(fill="both", expand=True)

        hdr_row = tk.Frame(pf, bg=BG2)
        hdr_row.pack(fill="x", pady=(0, 6))
        tk.Label(hdr_row, text="PORTFOLIO", bg=BG2, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        self.lbl_pf_total = tk.Label(hdr_row, text="$0.00", bg=BG2, fg=FG, font=MONO_B)
        self.lbl_pf_total.pack(side="right")

        self.pf_canvas  = tk.Canvas(pf, bg=BG2, highlightthickness=0)
        pf_scroll       = ttk.Scrollbar(pf, orient="vertical", command=self.pf_canvas.yview)
        self.pf_inner   = tk.Frame(self.pf_canvas, bg=BG2)
        self.pf_inner.bind("<Configure>",
                           lambda e: self.pf_canvas.configure(
                               scrollregion=self.pf_canvas.bbox("all")))
        self.pf_canvas.create_window((0, 0), window=self.pf_inner, anchor="nw")
        self.pf_canvas.configure(yscrollcommand=pf_scroll.set)
        pf_scroll.pack(side="right", fill="y")
        self.pf_canvas.pack(side="left", fill="both", expand=True)

    def _set_side(self, side):
        self.side_var.set(side)
        sym = self.selected_coin["symbol"]
        if side == "buy":
            self.btn_buy.configure(bg=GREEN, fg="#fff")
            self.btn_sell.configure(bg=BG3, fg=MUTED)
            self.btn_submit.configure(text=f"Buy {sym}", bg=GREEN,
                                       activebackground="#16a34a")
        else:
            self.btn_sell.configure(bg=RED, fg="#fff")
            self.btn_buy.configure(bg=BG3, fg=MUTED)
            self.btn_submit.configure(text=f"Sell {sym}", bg=RED,
                                       activebackground="#b91c1c")

    def _update_total(self):
        try:
            qty = float(self.amount_var.get())
            cid = self.selected_coin["id"]
            price = self.market_data.get(cid, {}).get("current_price")
            if price:
                self.lbl_total.configure(text=fmt_usd(qty * price))
            else:
                self.lbl_total.configure(text="—")
        except ValueError:
            self.lbl_total.configure(text="—")

    # ── Market Data Refresh ───────────────────────────────────────────────────
    def _start_market_refresh(self):
        self._fetch_markets_async()
        self.after(30000, self._start_market_refresh)

    def _fetch_markets_async(self):
        def worker():
            try:
                data = CoinGecko.markets()
                self.market_data = data
                self.after(0, self._apply_market_data)
            except Exception as e:
                self.after(0, lambda: self._set_sidebar_error())
        threading.Thread(target=worker, daemon=True).start()

    def _apply_market_data(self):
        for coin in COINS:
            cid = coin["id"]
            m   = self.market_data.get(cid, {})
            widgets = self.market_buttons.get(cid, {})
            price = m.get("current_price")
            chg   = m.get("price_change_percentage_24h")
            if widgets.get("lbl_price"):
                widgets["lbl_price"].configure(
                    text=fmt_price(price) if price else "—")
            if widgets.get("lbl_chg") and chg is not None:
                color = GREEN if chg >= 0 else RED
                widgets["lbl_chg"].configure(
                    text=fmt_pct(chg), fg=color)

        self._update_pair_header()
        self._update_portfolio_panel()
        self._update_total()

    def _set_sidebar_error(self):
        for cid, widgets in self.market_buttons.items():
            if widgets.get("lbl_price"):
                widgets["lbl_price"].configure(text="Error", fg=RED)

    def _update_pair_header(self):
        cid  = self.selected_coin["id"]
        sym  = self.selected_coin["symbol"]
        name = self.selected_coin["name"]
        m    = self.market_data.get(cid, {})
        price = m.get("current_price")
        chg   = m.get("price_change_percentage_24h")

        self.lbl_pair.configure(text=f"{sym}/USDT")
        self.lbl_coin_name.configure(text=name)
        self.lbl_current_price.configure(text=fmt_price(price) if price else "—")
        self.lbl_order_price.configure(text=fmt_price(price) if price else "—")
        self.lbl_symbol_suffix.configure(text=sym)

        if chg is not None:
            color = GREEN if chg >= 0 else RED
            arrow = "▲" if chg >= 0 else "▼"
            self.lbl_change.configure(text=f"{arrow} {abs(chg):.2f}% (24H)", fg=color)
        else:
            self.lbl_change.configure(text="—", fg=MUTED)

        self.lbl_high.configure(text=fmt_price(m.get("high_24h")))
        self.lbl_low.configure(text=fmt_price(m.get("low_24h")))
        vol = m.get("total_volume")
        self.lbl_vol.configure(text=f"${vol/1e6:.1f}M" if vol else "—")

        self._set_side(self.side_var.get())

    # ── Chart ─────────────────────────────────────────────────────────────────
    def _load_chart(self):
        if self._loading_chart:
            return
        self._loading_chart = True
        cid      = self.selected_coin["id"]
        days     = self.selected_range["days"]
        interval = self.selected_range["interval"]

        def worker():
            try:
                data = CoinGecko.chart(cid, days, interval)
                self.chart_data = data
                self.after(0, self._draw_chart)
            except Exception:
                self.after(0, self._chart_error)
            finally:
                self._loading_chart = False

        threading.Thread(target=worker, daemon=True).start()

    def _draw_chart(self):
        if not self.chart_data:
            self._chart_error()
            return

        timestamps = [t for t, _ in self.chart_data]
        prices     = [p for _, p in self.chart_data]
        dates      = [datetime.fromtimestamp(t) for t in timestamps]

        # Determine line color from direction
        color = GREEN if prices[-1] >= prices[0] else RED

        self.ax.clear()
        self._style_chart()

        self.ax.plot(dates, prices, color=color, linewidth=1.4)
        self.ax.fill_between(dates, prices, min(prices),
                              color=color, alpha=0.08)

        # Reference line at current price
        cid   = self.selected_coin["id"]
        cprice = self.market_data.get(cid, {}).get("current_price")
        if cprice:
            self.ax.axhline(y=cprice, color=color, linestyle="--",
                            linewidth=0.7, alpha=0.5)

        # Axis formatting
        days_float = float(self.selected_range["days"])
        if days_float <= 0.042:
            fmt = mdates.DateFormatter("%H:%M")
        elif days_float <= 1:
            fmt = mdates.DateFormatter("%H:%M")
        else:
            fmt = mdates.DateFormatter("%b %d")
        self.ax.xaxis.set_major_formatter(fmt)

        def price_fmt(x, pos):
            if x >= 1000: return f"${x:,.0f}"
            if x >= 1:    return f"${x:.2f}"
            return f"${x:.4f}"

        self.ax.yaxis.set_major_formatter(FuncFormatter(price_fmt))
        self.fig.autofmt_xdate(rotation=30, ha="right")
        self.fig.tight_layout(pad=1.2)
        self.canvas.draw()

    def _chart_error(self):
        self.ax.clear()
        self._style_chart()
        self.ax.text(0.5, 0.5, "Could not load chart data",
                     ha="center", va="center", transform=self.ax.transAxes,
                     color=MUTED, fontsize=11)
        self.canvas.draw()

    # ── Order Placement ───────────────────────────────────────────────────────
    def _place_order(self):
        try:
            qty = float(self.amount_var.get())
            if qty <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Invalid Amount", "Please enter a valid quantity.")
            return

        cid   = self.selected_coin["id"]
        sym   = self.selected_coin["symbol"]
        price = self.market_data.get(cid, {}).get("current_price")
        if not price:
            messagebox.showwarning("No Price", "Price data not available.")
            return

        side = self.side_var.get()

        # Update portfolio
        if side == "buy":
            if sym in self.portfolio:
                old  = self.portfolio[sym]
                new_qty  = old["qty"] + qty
                new_cost = (old["avg_cost"] * old["qty"] + price * qty) / new_qty
                self.portfolio[sym] = {"qty": new_qty, "avg_cost": new_cost}
            else:
                self.portfolio[sym] = {"qty": qty, "avg_cost": price}
        else:  # sell
            if sym not in self.portfolio or self.portfolio[sym]["qty"] < qty:
                messagebox.showwarning("Insufficient Balance",
                                       f"You don't have {qty} {sym} to sell.")
                return
            new_qty = self.portfolio[sym]["qty"] - qty
            if new_qty < 1e-8:
                del self.portfolio[sym]
            else:
                self.portfolio[sym]["qty"] = new_qty

        # Record trade
        trade = {
            "time":  datetime.now().strftime("%H:%M:%S"),
            "side":  side,
            "pair":  f"{sym}/USDT",
            "qty":   qty,
            "price": price,
            "total": qty * price,
        }
        self.trades.insert(0, trade)
        self._refresh_history()
        self._update_portfolio_panel()

        self.amount_var.set("")
        color = GREEN if side == "buy" else RED
        action = "Bought" if side == "buy" else "Sold"
        messagebox.showinfo("Order Filled",
                            f"{action} {qty} {sym} @ {fmt_price(price)}\n"
                            f"Total: {fmt_usd(qty * price)}")

    # ── History Table ─────────────────────────────────────────────────────────
    def _refresh_history(self):
        self.hist_tree.delete(*self.hist_tree.get_children())
        for t in self.trades[:50]:
            tag = t["side"]
            self.hist_tree.insert("", "end", values=(
                t["time"], t["side"].upper(), t["pair"],
                f"{t['qty']:.6f}", fmt_price(t["price"]), fmt_usd(t["total"])
            ), tags=(tag,))

    # ── Portfolio Panel ───────────────────────────────────────────────────────
    def _update_portfolio_panel(self):
        for w in self.pf_inner.winfo_children():
            w.destroy()

        total_value = 0
        total_pnl   = 0

        for sym, pos in self.portfolio.items():
            m_id  = next((c["id"] for c in COINS if c["symbol"] == sym), None)
            curr  = self.market_data.get(m_id, {}).get("current_price", pos["avg_cost"]) if m_id else pos["avg_cost"]
            value = pos["qty"] * curr
            pnl   = (curr - pos["avg_cost"]) * pos["qty"]
            pnl_pct = ((curr - pos["avg_cost"]) / pos["avg_cost"]) * 100
            total_value += value
            total_pnl   += pnl

            card = tk.Frame(self.pf_inner, bg=BG3, padx=10, pady=8,
                            bd=0, relief="flat")
            card.pack(fill="x", pady=(0, 6))

            row1 = tk.Frame(card, bg=BG3)
            row1.pack(fill="x")
            tk.Label(row1, text=sym, bg=BG3, fg=FG, font=FONT_B).pack(side="left")
            tk.Label(row1, text=fmt_usd(value), bg=BG3, fg=FG,
                     font=MONO_B).pack(side="right")

            row2 = tk.Frame(card, bg=BG3)
            row2.pack(fill="x", pady=(2, 0))
            tk.Label(row2,
                     text=f"{pos['qty']:.4f} @ {fmt_price(pos['avg_cost'])}",
                     bg=BG3, fg=MUTED, font=("Consolas", 9)).pack(side="left")
            pnl_color = GREEN if pnl >= 0 else RED
            tk.Label(row2, text=f"{pnl_pct:+.2f}%", bg=BG3,
                     fg=pnl_color, font=("Segoe UI", 9, "bold")).pack(side="right")

        self.lbl_pf_total.configure(text=fmt_usd(total_value))
        pnl_color = GREEN if total_pnl >= 0 else RED
        self.lbl_portfolio_val.configure(text=f"Portfolio: {fmt_usd(total_value)}")
        self.lbl_pnl.configure(text=f"P&L: {total_pnl:+,.2f}", fg=pnl_color)


if __name__ == "__main__":
    app = CryptoApp()
    app.mainloop()
