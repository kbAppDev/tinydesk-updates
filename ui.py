"""Soft, compact desktop layout matching the Flare app family."""
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
import updater

import flare_theme as theme
from pathlib import Path
from PIL import Image
import sys

BG, INK, MUTED = theme.PAGE, theme.INK, theme.MUTED
LIME, BLACK, RED = theme.LIME, theme.BLACK, theme.RED


def build_ui(self):
    style = ttk.Style(self)
    style.theme_use('clam')
    style.configure('Treeview', background='white', fieldbackground='white', foreground=INK,
                    rowheight=44, borderwidth=0, font=('Segoe UI', 10))
    style.configure('Treeview.Heading', background='#F6F6F4', foreground=MUTED,
                    font=('Segoe UI', 9), relief='flat', padding=(8, 9))
    style.map('Treeview', background=[('selected', theme.SOFT_LIME)], foreground=[('selected', INK)])
    style.configure('Horizontal.TProgressbar', background=LIME, troughcolor='#e9ecf0', borderwidth=0)
    self.grid_columnconfigure(1, weight=1)
    self.grid_rowconfigure(0, weight=1)

    sidebar = ctk.CTkFrame(self, fg_color=BLACK, corner_radius=0, width=184)
    sidebar.grid(row=0, column=0, sticky='ns')
    sidebar.grid_propagate(False)
    sidebar.grid_columnconfigure(0, weight=1)
    sidebar.grid_rowconfigure(5, weight=1)
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
    self.brand_image = ctk.CTkImage(Image.open(root / 'assets' / 'FlareTools.png'), size=(60, 60))
    ctk.CTkLabel(sidebar, text='', image=self.brand_image).grid(row=0, column=0, sticky='w', padx=20, pady=(24, 8))
    self.label(sidebar, 'FLARE', 19, 'white', True).grid(row=1, column=0, sticky='w', padx=24)
    self.label(sidebar, 'TOOLS', 11, LIME, True).grid(row=2, column=0, sticky='w', padx=25, pady=(0, 30))
    nav = ctk.CTkFrame(sidebar, fg_color='#242424', corner_radius=12)
    nav.grid(row=3, column=0, sticky='ew', padx=12)
    ctk.CTkFrame(nav, fg_color=RED, corner_radius=2, width=3, height=26).pack(side='left', padx=(10, 9), pady=12)
    self.label(nav, 'Image Compressor', 9, 'white', True).pack(side='left', padx=(0, 10))
    local = ctk.CTkFrame(sidebar, fg_color='transparent')
    local.grid(row=6, column=0, sticky='ew', padx=20, pady=(10, 10))
    self.label(local, 'Flare Fireplaces', 8, '#F5F5F5', True).pack(anchor='w')
    self.label(local, 'Works offline.\nYour images stay on this PC.', 8, '#B6B6B6', justify='left').pack(anchor='w', pady=(4, 0))
    self.update_button = ctk.CTkButton(sidebar, text='Check for updates', command=lambda: self.check_updates(True),
        fg_color='transparent', hover_color='#272727', text_color='#DADADA', anchor='w', height=34,
        corner_radius=9, font=('Segoe UI', 11))
    self.update_button.grid(row=7, column=0, sticky='ew', padx=12)
    self.label(sidebar, 'v' + updater.VERSION, 8, '#8A8A8A').grid(row=8, column=0, sticky='w', padx=22, pady=(2, 18))

    main = ctk.CTkFrame(self, fg_color='transparent', corner_radius=0)
    main.grid(row=0, column=1, sticky='nsew', padx=26, pady=(24, 18))
    main.grid_columnconfigure(0, weight=1)
    main.grid_rowconfigure(1, weight=1)
    header = ctk.CTkFrame(main, fg_color='transparent')
    header.grid(row=0, column=0, sticky='ew', pady=(0, 20))
    self.label(header, 'Image Compressor', 21, bold=True).pack(anchor='w')
    self.label(header, 'Smaller files. More room for what matters.', 10, MUTED).pack(anchor='w', pady=(4, 0))

    card = ctk.CTkFrame(main, fg_color='white', corner_radius=20, border_width=1, border_color=theme.BORDER)
    card.grid(row=1, column=0, sticky='nsew')
    card.grid_columnconfigure(0, weight=1)
    card.grid_rowconfigure(1, weight=1)
    toolbar = ctk.CTkFrame(card, fg_color='transparent')
    toolbar.grid(row=0, column=0, sticky='ew', padx=20, pady=(18, 12))
    self.label(toolbar, 'Your images', 12, bold=True).pack(side='left')
    self.add_button = self.button(toolbar, '+ Add images', self.add_images)
    self.add_button.pack(side='right')
    self.mutable.append(self.add_button)
    folder = self.button(toolbar, 'Add folder', self.add_folder)
    folder.pack(side='right', padx=(0, 8))
    self.mutable.append(folder)

    list_frame = tk.Frame(card, bg='white', bd=0)
    list_frame.grid(row=1, column=0, sticky='nsew', padx=15)
    list_frame.grid_columnconfigure(0, weight=1)
    list_frame.grid_rowconfigure(0, weight=1)
    self.tree = ttk.Treeview(list_frame, columns=('name', 'before', 'after', 'saved', 'status'), show='headings', selectmode='extended')
    for name, title, width, anchor in [('name', 'Image', 230, 'w'), ('before', 'Before', 80, 'e'), ('after', 'After', 80, 'e'),
                                       ('saved', 'Saved', 60, 'e'), ('status', 'Status', 125, 'w')]:
        self.tree.heading(name, text=title, anchor=anchor)
        self.tree.column(name, width=width, minwidth=50, anchor=anchor, stretch=name == 'name')
    self.tree.grid(row=0, column=0, sticky='nsew')
    scroll = ttk.Scrollbar(list_frame, orient='vertical', command=self.tree.yview)
    scroll.grid(row=0, column=1, sticky='ns')
    self.tree.configure(yscrollcommand=scroll.set)
    self.tree.tag_configure('error', foreground=RED)
    self.tree.tag_configure('done', foreground=INK, background=theme.SOFT_LIME)
    self.tree.bind('<<TreeviewSelect>>', self.selection_changed)
    self.tree.bind('<Delete>', lambda _: self.remove_selected())
    self.tree.bind('<Double-1>', self.open_result)
    # Empty state covers the grid until there are images. No dashboard to learn.
    self.empty = ctk.CTkFrame(list_frame, fg_color='white', corner_radius=0)
    self.empty.place(x=0, y=0, relwidth=1, relheight=1)
    empty_content = ctk.CTkFrame(self.empty, fg_color='transparent')
    empty_content.place(relx=.5, rely=.48, anchor='center')
    icon = ctk.CTkFrame(empty_content, fg_color=theme.SOFT_LIME, corner_radius=20, width=76, height=76)
    icon.pack(pady=(0, 18))
    icon.pack_propagate(False)
    self.label(icon, '\u2193', 30, BLACK).place(relx=.5, rely=.46, anchor='center')
    self.label(empty_content, 'Ready to lighten things up?', 15, bold=True).pack()
    self.label(empty_content, 'Drop images or a folder here. We’ll take it from there.', 10, MUTED).pack(pady=(7, 18))
    choose = self.button(empty_content, 'Choose images', self.add_images, True, 25)
    choose.pack()
    self.mutable.append(choose)
    self.label(empty_content, 'JPG, PNG, WebP and more', 9, MUTED).pack(pady=(12, 0))

    self.queue_footer = ctk.CTkFrame(card, fg_color='transparent')
    self.queue_footer.grid(row=2, column=0, sticky='ew', padx=20, pady=(8, 16))
    self.stat_labels = []
    for title in ('images', 'original', 'saved'):
        group = ctk.CTkFrame(self.queue_footer, fg_color='transparent')
        group.pack(side='left', padx=(0, 18))
        value = self.label(group, '0', 11, INK, True)
        value.pack(side='left', padx=(0, 5))
        self.label(group, title, 9, MUTED).pack(side='left')
        self.stat_labels.append(value)
    for text, command in [('Clear', self.clear), ('Remove', self.remove_selected)]:
        button = ctk.CTkButton(self.queue_footer, text=text, command=command, width=66, height=30,
                             fg_color='transparent', hover_color='#F1F1EF', text_color=MUTED,
                             corner_radius=8, font=('Segoe UI', 11))
        button.pack(side='right', padx=(7, 0))
        self.mutable.append(button)
    self.queue_footer.grid_remove()

    # Preview is a small on-demand window, so the main view stays uncluttered.
    self.preview = None
    self.preview_canvas = None
    self.preview_name = None
    self.preview_details = None

    lower = ctk.CTkFrame(main, fg_color='transparent')
    lower.grid(row=2, column=0, sticky='ew', pady=(18, 0))
    lower.grid_columnconfigure(0, weight=1)
    row = ctk.CTkFrame(lower, fg_color='transparent')
    row.grid(row=0, column=0, sticky='ew')
    self.label(row, 'Quality', 10, bold=True).pack(side='left', padx=(0, 12))
    quality = ctk.CTkOptionMenu(row, variable=self.preset, values=['Balanced', 'Best quality', 'Smallest'],
        command=lambda _: self.options_changed(), fg_color='white', button_color='#E8E8E5',
        button_hover_color='#DDDDDA', text_color=INK, dropdown_fg_color='white', dropdown_text_color=INK,
        corner_radius=10, width=154, height=38, font=('Segoe UI', 12))
    quality.pack(side='left')
    self.mutable.append(quality)
    self.advanced_button = ctk.CTkButton(row, text='More options  ›', command=lambda: toggle_advanced(self),
        fg_color='transparent', hover_color='#EAEAE7', text_color=MUTED, width=125, height=36,
        corner_radius=10, font=('Segoe UI', 12))
    self.advanced_button.pack(side='left', padx=8)
    self.mutable.append(self.advanced_button)
    self.compress_button = self.button(row, 'Compress images', self.start_batch, True, 19)
    self.compress_button.pack(side='right')
    self.advanced = ctk.CTkFrame(lower, fg_color='#EDEDE9', corner_radius=12)
    self.advanced.grid(row=1, column=0, sticky='ew', pady=(10, 0))
    for title, variable, values in [('Format', self.format, ['Keep format', 'WebP']),
                                    ('Resize', self.resize, ['Original size', '2560 px', '1920 px', '1280 px'])]:
        self.label(self.advanced, title, 9, MUTED).pack(side='left', padx=(14, 8))
        menu = ctk.CTkOptionMenu(self.advanced, variable=variable, values=values,
            command=lambda _: self.options_changed(), width=145, height=32,
            fg_color='white', button_color='#DFDFDB', button_hover_color='#D1D1CC', text_color=INK,
            dropdown_fg_color='white', dropdown_text_color=INK, corner_radius=8)
        menu.pack(side='left', pady=12)
        self.mutable.append(menu)
    self.advanced.grid_remove()
    self.hint = self.label(lower, '', 9, MUTED, anchor='w')
    self.hint.grid(row=2, column=0, sticky='ew', pady=(8, 8))
    output = ctk.CTkFrame(lower, fg_color='transparent')
    output.grid(row=3, column=0, sticky='ew')
    self.label(output, 'Save to', 9, MUTED).pack(side='left', padx=(0, 8))
    self.output_label = self.label(output, '', 9, INK, anchor='w')
    self.output_label.pack(side='left', expand=True, fill='x')
    for title, command in [('Open folder', self.open_folder), ('Change', self.change_output)]:
        button = ctk.CTkButton(output, text=title, command=command, width=83, height=30,
            fg_color='transparent', hover_color='#EAEAE7', text_color=MUTED, corner_radius=8,
            font=('Segoe UI', 11))
        button.pack(side='right')
        if title == 'Change':
            self.mutable.append(button)
    self.progress = ttk.Progressbar(lower, maximum=100)
    self.progress.grid(row=4, column=0, sticky='ew', pady=(10, 7))
    self.progress.grid_remove()
    self.status = self.label(lower, 'Originals stay safe. Compressed copies go into your output folder.', 9, MUTED, anchor='w')
    self.status.grid(row=5, column=0, sticky='ew')
    self.options_changed()
    self.refresh_output()


def toggle_advanced(self):
    if self.advanced.winfo_ismapped():
        self.advanced.grid_remove()
        self.advanced_button.configure(text='More options  ›')
    else:
        self.advanced.grid()
        self.advanced_button.configure(text='Fewer options  ‹')


def preview_dialog(self):
    if self.preview is not None and self.preview.winfo_exists():
        return
    self.preview = ctk.CTkToplevel(self)
    self.preview.title('Flare Tools - Image Details')
    self.preview.geometry('360x430')
    self.preview.resizable(False, False)
    self.preview.transient(self)
    self.preview.configure(fg_color=BG)
    self.preview_canvas = tk.Label(self.preview, bg='#ECECE8', fg=MUTED, text='Loading preview…', font=('Segoe UI', 10))
    self.preview_canvas.pack(padx=24, pady=(24, 14), fill='x')
    self.preview_name = self.label(self.preview, '', 11, bold=True, wraplength=312)
    self.preview_name.pack(padx=24)
    self.preview_details = self.label(self.preview, '', 9, MUTED, wraplength=312, justify='left')
    self.preview_details.pack(padx=24, pady=10)
