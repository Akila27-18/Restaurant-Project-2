"""
Restaurant POS System (Tkinter + SQLite)
Features:
- Table management (create fixed number of tables)
- Order entry per table: add items, change qty, remove
- Send orders to kitchen (orders.status = 'pending')
- Kitchen screen: view pending items, mark prepared
- Billing: generate PDF receipt, store sales, free table
- SQLite offline storage (database/pos.db)
- Receipts saved to receipts/
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
import os
from datetime import datetime
from fpdf import FPDF

# -------------------------
# Setup folders & database
# -------------------------
os.makedirs("database", exist_ok=True)
os.makedirs("receipts", exist_ok=True)

DB_PATH = "database/pos.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # tables: restaurant tables
    c.execute("""
    CREATE TABLE IF NOT EXISTS tables (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_no INTEGER UNIQUE,
        status TEXT DEFAULT 'free'
    )""")
    # menu items
    c.execute("""
    CREATE TABLE IF NOT EXISTS menu (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price REAL,
        category TEXT
    )""")
    # orders: current (pending/served) items
    c.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_no INTEGER,
        item_id INTEGER,
        item_name TEXT,
        qty INTEGER,
        price REAL,
        status TEXT DEFAULT 'pending',
        timestamp TEXT
    )""")
    # sales: completed bills
    c.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_no INTEGER,
        total REAL,
        date TEXT,
        receipt_file TEXT
    )""")
    conn.commit()

    # create default tables if not present (for example 8 tables)
    c.execute("SELECT COUNT(*) FROM tables")
    count = c.fetchone()[0]
    if count == 0:
        for t in range(1, 9):
            c.execute("INSERT INTO tables (table_no, status) VALUES (?, ?)", (t, "free"))
        conn.commit()

    # insert sample menu if table empty
    c.execute("SELECT COUNT(*) FROM menu")
    mcount = c.fetchone()[0]
    if mcount == 0:
        sample_menu = [
            ("Margherita Pizza", 8.50, "Pizza"),
            ("Farmhouse Pizza", 9.50, "Pizza"),
            ("Veg Burger", 5.00, "Burger"),
            ("Chicken Burger", 6.50, "Burger"),
            ("Pasta Alfredo", 7.50, "Pasta"),
            ("Coke", 1.50, "Beverage"),
            ("Orange Juice", 2.00, "Beverage"),
            ("French Fries", 3.00, "Sides"),
            ("Caesar Salad", 4.50, "Salad")
        ]
        c.executemany("INSERT INTO menu (name, price, category) VALUES (?, ?, ?)", sample_menu)
        conn.commit()

    conn.close()

init_db()

# -------------------------
# DB helper functions
# -------------------------
def db_connect():
    return sqlite3.connect(DB_PATH)

def get_tables():
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT table_no, status FROM tables ORDER BY table_no")
    rows = c.fetchall()
    conn.close()
    return rows

def set_table_status(table_no, status):
    conn = db_connect()
    c = conn.cursor()
    c.execute("UPDATE tables SET status=? WHERE table_no=?", (status, table_no))
    conn.commit()
    conn.close()

def get_menu_items():
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT id, name, price, category FROM menu ORDER BY category, name")
    rows = c.fetchall()
    conn.close()
    return rows

def add_order_item(table_no, item_id, item_name, qty, price):
    conn = db_connect()
    c = conn.cursor()
    ts = datetime.now().isoformat()
    c.execute("INSERT INTO orders (table_no, item_id, item_name, qty, price, status, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (table_no, item_id, item_name, qty, price, "pending", ts))
    conn.commit()
    conn.close()
    set_table_status(table_no, "occupied")

def get_orders_for_table(table_no):
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT id, item_name, qty, price, status FROM orders WHERE table_no=? ORDER BY id", (table_no,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_pending_orders():
    conn = db_connect()
    c = conn.cursor()
    c.execute("SELECT id, table_no, item_name, qty, price, timestamp FROM orders WHERE status='pending' ORDER BY timestamp")
    rows = c.fetchall()
    conn.close()
    return rows

def mark_order_prepared(order_id):
    conn = db_connect()
    c = conn.cursor()
    c.execute("UPDATE orders SET status='prepared' WHERE id=?", (order_id,))
    conn.commit()
    conn.close()

def delete_orders_for_table(table_no):
    conn = db_connect()
    c = conn.cursor()
    c.execute("DELETE FROM orders WHERE table_no=?", (table_no,))
    conn.commit()
    conn.close()

def complete_bill_and_save(table_no, total, receipt_file):
    conn = db_connect()
    c = conn.cursor()
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO sales (table_no, total, date, receipt_file) VALUES (?, ?, ?, ?)", (table_no, total, date, receipt_file))
    conn.commit()
    conn.close()
    # remove orders for table and free it
    delete_orders_for_table(table_no)
    set_table_status(table_no, "free")

# -------------------------
# PDF Receipt Generation
# -------------------------
def generate_receipt_pdf(table_no, items, subtotal, tax_percent=5.0):
    # items: list of tuples (name, qty, price, total_line)
    invoice_no = int(datetime.now().timestamp())
    filename = f"receipts/receipt_table{table_no}_{invoice_no}.pdf"
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.set_text_color(0, 80, 160)
    pdf.cell(0, 10, f"Restaurant Receipt - Table {table_no}", ln=True, align="C")
    pdf.ln(4)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 6, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.ln(4)
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(90, 8, "Item", 1, 0, 'C', 1)
    pdf.cell(20, 8, "Qty", 1, 0, 'C', 1)
    pdf.cell(30, 8, "Price", 1, 0, 'C', 1)
    pdf.cell(40, 8, "Total", 1, 1, 'C', 1)
    total_amount = 0.0
    for name, qty, price, line_total in items:
        pdf.cell(90, 8, str(name), 1)
        pdf.cell(20, 8, str(qty), 1, 0, 'C')
        pdf.cell(30, 8, f"{price:.2f}", 1, 0, 'R')
        pdf.cell(40, 8, f"{line_total:.2f}", 1, 1, 'R')
        total_amount += line_total
    pdf.ln(4)
    pdf.cell(130, 8, "Subtotal", 0)
    pdf.cell(40, 8, f"{subtotal:.2f}", 0, 1, 'R')
    tax = subtotal * tax_percent / 100.0
    pdf.cell(130, 8, f"Tax ({tax_percent:.1f}%)", 0)
    pdf.cell(40, 8, f"{tax:.2f}", 0, 1, 'R')
    grand_total = subtotal + tax
    pdf.set_font("Arial", "B", 12)
    pdf.cell(130, 10, "Grand Total", 0)
    pdf.cell(40, 10, f"{grand_total:.2f}", 0, 1, 'R')
    pdf.ln(8)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 8, "Thank you for dining with us!", ln=True, align='C')
    pdf.output(filename)
    return filename, grand_total

# -------------------------
# Tkinter GUI
# -------------------------
class POSApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🍽️ Restaurant POS System")
        self.root.geometry("1100x700")
        self.root.config(bg="#fafafa")
        self.selected_table = None
        self.menu_items = {}  # id -> (name, price, category)
        self.load_menu()
        self.create_ui()

    def load_menu(self):
        rows = get_menu_items()
        self.menu_items = {r[0]: (r[1], r[2], r[3]) for r in rows}  # id: (name, price, category)

    def create_ui(self):
        # Left frame: tables
        left = tk.Frame(self.root, bg="#f3f6fb", bd=2, relief="groove")
        left.place(x=10, y=10, width=300, height=680)
        tk.Label(left, text="Tables", bg="#f3f6fb", font=("Arial", 14, "bold")).pack(pady=8)
        self.table_frame = tk.Frame(left, bg="#f3f6fb")
        self.table_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.render_tables()

        # Top bar buttons
        topbar = tk.Frame(self.root, bg="#ffffff")
        topbar.place(x=320, y=10, width=770, height=60)
        btn_kitchen = tk.Button(topbar, text="🍳 Kitchen Screen", bg="#ff9900", fg="white",
                                font=("Arial", 12, "bold"), command=self.open_kitchen_screen)
        btn_kitchen.pack(side="left", padx=8, pady=8)
        btn_refresh = tk.Button(topbar, text="🔄 Refresh Tables", bg="#2196f3", fg="white",
                                font=("Arial", 12, "bold"), command=self.render_tables)
        btn_refresh.pack(side="left", padx=8)
        btn_reports = tk.Button(topbar, text="📈 Sales Report", bg="#6a1b9a", fg="white",
                                font=("Arial", 12, "bold"), command=self.open_sales_report)
        btn_reports.pack(side="left", padx=8)

        # Right: Order entry and summary
        right = tk.Frame(self.root, bg="#fff", bd=2, relief="groove")
        right.place(x=320, y=80, width=770, height=610)

        # --- Order entry frame ---
        entry_frame = tk.LabelFrame(right, text="Order Entry", font=("Arial", 12, "bold"))
        entry_frame.place(x=10, y=10, width=740, height=320)

        tk.Label(entry_frame, text="Menu:", font=("Arial", 11)).place(x=10, y=8)
        # Category filter
        categories = sorted(set(v[2] for v in self.menu_items.values()))
        categories.insert(0, "All")
        self.cat_var = tk.StringVar(value="All")
        cat_menu = ttk.Combobox(entry_frame, textvariable=self.cat_var, values=categories, state="readonly", width=12)
        cat_menu.place(x=60, y=8)
        cat_menu.bind("<<ComboboxSelected>>", lambda e: self.populate_menu_listbox())

        # Menu listbox
        self.menu_listbox = tk.Listbox(entry_frame, font=("Arial", 11), height=10)
        self.menu_listbox.place(x=10, y=40, width=320, height=240)
        self.populate_menu_listbox()

        # Quantity and add button
        tk.Label(entry_frame, text="Qty:", font=("Arial", 11)).place(x=350, y=40)
        self.qty_var = tk.IntVar(value=1)
        qty_spin = tk.Spinbox(entry_frame, from_=1, to=100, textvariable=self.qty_var, width=5)
        qty_spin.place(x=390, y=40)
        btn_add = tk.Button(entry_frame, text="➕ Add to Order", bg="#4caf50", fg="white", font=("Arial", 11, "bold"),
                            command=self.add_selected_item_to_order)
        btn_add.place(x=350, y=80, width=140, height=35)

        # Order treeview
        order_cols = ("id", "Item", "Qty", "Price", "Total")
        self.order_tree = ttk.Treeview(entry_frame, columns=order_cols, show="headings", height=9)
        for col in order_cols:
            self.order_tree.heading(col, text=col)
            if col == "Item":
                self.order_tree.column(col, width=220)
            else:
                self.order_tree.column(col, width=70, anchor="center")
        self.order_tree.place(x=350, y=130, width=370, height=150)

        btn_remove = tk.Button(entry_frame, text="🗑 Remove Selected", bg="#f44336", fg="white",
                               command=self.remove_selected_order_item)
        btn_remove.place(x=500, y=80, width=140, height=35)

        # --- Billing / Summary frame ---
        summary_frame = tk.LabelFrame(right, text="Summary & Actions", font=("Arial", 12, "bold"))
        summary_frame.place(x=10, y=340, width=740, height=250)

        tk.Label(summary_frame, text="Selected Table:", font=("Arial", 11)).place(x=10, y=10)
        self.lbl_table = tk.Label(summary_frame, text="None", font=("Arial", 12, "bold"), fg="#d32f2f")
        self.lbl_table.place(x=130, y=8)

        tk.Label(summary_frame, text="Subtotal:", font=("Arial", 11)).place(x=10, y=50)
        self.lbl_subtotal = tk.Label(summary_frame, text="0.00", font=("Arial", 12, "bold"))
        self.lbl_subtotal.place(x=130, y=48)

        tk.Label(summary_frame, text="Tax (%):", font=("Arial", 11)).place(x=10, y=90)
        self.tax_var = tk.DoubleVar(value=5.0)
        tax_spin = tk.Spinbox(summary_frame, from_=0, to=100, increment=0.5, textvariable=self.tax_var, width=6)
        tax_spin.place(x=130, y=90)

        tk.Label(summary_frame, text="Grand Total:", font=("Arial", 11)).place(x=10, y=130)
        self.lbl_total = tk.Label(summary_frame, text="0.00", font=("Arial", 14, "bold"), fg="#2e7d32")
        self.lbl_total.place(x=130, y=126)

        btn_send_kitchen = tk.Button(summary_frame, text="🍳 Send to Kitchen", bg="#ffb300", fg="black",
                                     font=("Arial", 12, "bold"), command=self.send_to_kitchen)
        btn_send_kitchen.place(x=10, y=170, width=200, height=50)

        btn_print_bill = tk.Button(summary_frame, text="🧾 Print Bill (Cashier)", bg="#1976d2", fg="white",
                                   font=("Arial", 12, "bold"), command=self.print_bill)
        btn_print_bill.place(x=240, y=170, width=220, height=50)

        btn_free = tk.Button(summary_frame, text="🔓 Free Table", bg="#9e9e9e", fg="white",
                             font=("Arial", 11), command=self.free_table)
        btn_free.place(x=480, y=170, width=120, height=50)

        # Load initial table selection if any
        self.refresh_order_view()

    # UI helpers
    def render_tables(self):
        # Clear frame
        for w in self.table_frame.winfo_children():
            w.destroy()
        rows = get_tables()
        # create grid of table buttons
        r = 0
        c = 0
        for table_no, status in rows:
            color = "#66bb6a" if status == "free" else "#ef5350"
            btn = tk.Button(self.table_frame, text=f"Table {table_no}\n({status})", bg=color, fg="white",
                            font=("Arial", 11, "bold"), width=12, height=3,
                            command=lambda tn=table_no: self.open_table(tn))
            btn.grid(row=r, column=c, padx=6, pady=6)
            c += 1
            if c >= 2:
                c = 0
                r += 1

    def open_table(self, table_no):
        self.selected_table = table_no
        self.lbl_table.config(text=str(table_no))
        self.refresh_order_view()

    def populate_menu_listbox(self):
        self.menu_listbox.delete(0, tk.END)
        selected_cat = self.cat_var.get()
        for mid, (name, price, cat) in self.menu_items.items():
            if selected_cat == "All" or selected_cat == cat:
                self.menu_listbox.insert(tk.END, f"{mid} - {name} ({cat}) - ₹{price:.2f}")

    def add_selected_item_to_order(self):
        if self.selected_table is None:
            messagebox.showerror("No table selected", "Please select a table first.")
            return
        sel = self.menu_listbox.curselection()
        if not sel:
            messagebox.showerror("No item selected", "Please select a menu item to add.")
            return
        line = self.menu_listbox.get(sel[0])
        # parse id from line: "id - name (cat) - ₹price"
        parts = line.split(" - ", 1)
        item_id = int(parts[0])
        name, price, cat = self.menu_items[item_id]
        qty = int(self.qty_var.get() or 1)
        add_order_item(self.selected_table, item_id, name, qty, price)
        self.refresh_order_view()
        self.render_tables()

    def refresh_order_view(self):
        # clear tree
        for row in self.order_tree.get_children():
            self.order_tree.delete(row)
        subtotal = 0.0
        if self.selected_table is not None:
            orders = get_orders_for_table(self.selected_table)
            # orders rows: (id, item_name, qty, price, status)
            for o in orders:
                oid, item_name, qty, price, status = o
                line_total = qty * price
                self.order_tree.insert("", "end", values=(oid, item_name, qty, f"{price:.2f}", f"{line_total:.2f}"))
                subtotal += line_total
        self.lbl_subtotal.config(text=f"{subtotal:.2f}")
        tax = subtotal * (self.tax_var.get() / 100.0)
        grand = subtotal + tax
        self.lbl_total.config(text=f"{grand:.2f}")

    def remove_selected_order_item(self):
        selected = self.order_tree.selection()
        if not selected:
            messagebox.showerror("No selection", "Please select an order item to remove.")
            return
        oid = self.order_tree.item(selected[0])['values'][0]
        # remove from DB
        conn = db_connect()
        c = conn.cursor()
        c.execute("DELETE FROM orders WHERE id=?", (oid,))
        conn.commit()
        conn.close()
        self.refresh_order_view()
        self.render_tables()

    def send_to_kitchen(self):
        if self.selected_table is None:
            messagebox.showerror("No table", "Select a table first.")
            return
        # mark all current table orders as pending (they already should be pending)
        # (optionally we could change status here if we had drafts)
        messagebox.showinfo("Sent", f"Orders for table {self.selected_table} sent to kitchen.")
        self.render_tables()
        # open kitchen screen to show the new orders
        # self.open_kitchen_screen()

    def print_bill(self):
        if self.selected_table is None:
            messagebox.showerror("No table selected", "Please select a table.")
            return
        orders = get_orders_for_table(self.selected_table)
        if not orders:
            messagebox.showerror("No orders", "No orders for this table to bill.")
            return
        # prepare items list for receipt
        items_for_receipt = []
        subtotal = 0.0
        for o in orders:
            oid, item_name, qty, price, status = o
            line_total = qty * price
            items_for_receipt.append((item_name, qty, price, line_total))
            subtotal += line_total
        # generate receipt
        receipt_file, grand_total = generate_receipt_pdf(self.selected_table, items_for_receipt, subtotal, tax_percent=self.tax_var.get())
        # save sale to sales table and clear orders
        complete_bill_and_save(self.selected_table, grand_total, receipt_file)
        messagebox.showinfo("Billed", f"Bill printed and saved to:\n{receipt_file}")
        self.selected_table = None
        self.lbl_table.config(text="None")
        self.refresh_order_view()
        self.render_tables()

    def free_table(self):
        if self.selected_table is None:
            messagebox.showerror("No table selected", "Select a table first.")
            return
        # optionally confirm
        if messagebox.askyesno("Confirm", f"Are you sure you want to free Table {self.selected_table}? This will remove all orders."):
            delete_orders_for_table(self.selected_table)
            set_table_status(self.selected_table, "free")
            self.selected_table = None
            self.lbl_table.config(text="None")
            self.refresh_order_view()
            self.render_tables()

    # Kitchen screen
    def open_kitchen_screen(self):
        ks = tk.Toplevel(self.root)
        ks.title("🍽️ Kitchen Screen - Pending Orders")
        ks.geometry("700x500")
        ks.config(bg="#fff")
        tk.Label(ks, text="Pending Orders", font=("Arial", 14, "bold")).pack(pady=8)
        tree = ttk.Treeview(ks, columns=("Order ID", "Table", "Item", "Qty", "Price", "Time"), show="headings")
        for col in ("Order ID", "Table", "Item", "Qty", "Price", "Time"):
            tree.heading(col, text=col)
            tree.column(col, width=100)
        tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        def load_pending():
            for r in tree.get_children():
                tree.delete(r)
            rows = get_pending_orders()
            for r in rows:
                oid, table_no, item_name, qty, price, ts = r
                tree.insert("", "end", values=(oid, table_no, item_name, qty, f"{price:.2f}", ts.split("T")[0]+" "+ts.split("T")[1][:8]))

        def mark_prepared():
            sel = tree.selection()
            if not sel:
                messagebox.showerror("No selection", "Select an order to mark prepared.")
                return
            oid = tree.item(sel[0])["values"][0]
            mark_order_prepared(oid)
            load_pending()

        btn_frame = tk.Frame(ks, bg="#fff")
        btn_frame.pack(pady=6)
        tk.Button(btn_frame, text="✅ Mark Prepared", bg="#4caf50", fg="white", command=mark_prepared).pack(side="left", padx=6)
        tk.Button(btn_frame, text="🔄 Refresh", bg="#2196f3", fg="white", command=load_pending).pack(side="left", padx=6)

        load_pending()

    # Sales report (simple)
    def open_sales_report(self):
        rs = tk.Toplevel(self.root)
        rs.title("📈 Sales Report")
        rs.geometry("900x600")
        tk.Label(rs, text="Sales Report", font=("Arial", 14, "bold")).pack(pady=8)
        tree = ttk.Treeview(rs, columns=("Sale ID", "Table", "Total", "Date", "Receipt"), show="headings")
        for col in ("Sale ID", "Table", "Total", "Date", "Receipt"):
            tree.heading(col, text=col)
            tree.column(col, width=150)
        tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        conn = db_connect()
        c = conn.cursor()
        c.execute("SELECT id, table_no, total, date, receipt_file FROM sales ORDER BY date DESC")
        rows = c.fetchall()
        conn.close()
        total_sum = 0.0
        for r in rows:
            sid, tno, total, date, receipt = r
            tree.insert("", "end", values=(sid, tno, f"{total:.2f}", date, receipt))
            try:
                total_sum += float(total)
            except:
                pass
        tk.Label(rs, text=f"Total Sales: {total_sum:.2f}", font=("Arial", 12, "bold")).pack(pady=6)

# Run the application
if __name__ == "__main__":
    root = tk.Tk()
    app = POSApp(root)
    root.mainloop()
