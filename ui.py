"""Flare Tools desktop workspace, image queue and preset dialogs."""
from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox, ttk
import unicodedata

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

import flare_theme as theme
from presets import FORMATS, QUALITIES, SIZES
from thumbnails import QueueThumbnails
import updater


BG, INK, MUTED = theme.PAGE, theme.INK, theme.MUTED
LIME, BLACK, RED = theme.LIME, theme.BLACK, theme.RED
WHITE, BORDER = theme.SURFACE, theme.BORDER
ASSETS = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'assets'


def frame(parent, **options):
    return ctk.CTkFrame(parent, fg_color='transparent', **options)


def quiet_button(parent, text, command, width, dark=False):
    return ctk.CTkButton(parent, text=text, command=command, width=width, height=32,
                         fg_color='transparent', text_color='#E2E3DE' if dark else INK,
                         hover_color='#373834' if dark else '#EDEEEA', corner_radius=8,
                         font=(theme.FONT, 12))


def combobox(parent, variable, values, command, width=15):
    box = ttk.Combobox(parent, textvariable=variable, values=values, state='readonly',
                       width=width, font=(theme.FONT, 10), style='Flare.TCombobox')
    box.bind('<<ComboboxSelected>>', lambda _: command(variable.get()))
    return box


def keyboard_buttons(parent):
    """Give custom-drawn buttons a single native Tab stop and activation keys."""
    for child in parent.winfo_children():
        if not isinstance(child, ctk.CTkButton):
            keyboard_buttons(child)
            continue
        button = child
        width, color = button.cget('border_width'), button.cget('border_color')
        focusable = button.register(lambda _, b=button: int(b.cget('state') != 'disabled'))
        tk.Frame.configure(button, takefocus=focusable)
        tk.Misc.bind(button, '<FocusIn>',
                     lambda _, b=button: b.configure(border_width=2, border_color='#75951A'))
        tk.Misc.bind(button, '<FocusOut>',
                     lambda _, b=button, w=width, c=color: b.configure(border_width=w, border_color=c))

        def activate(_, b=button):
            b.invoke()
            return 'break'

        tk.Misc.bind(button, '<space>', activate)
        tk.Misc.bind(button, '<Return>', activate)


def divider(parent, row, padx=20):
    ctk.CTkFrame(parent, height=1, corner_radius=0, fg_color=BORDER).grid(
        row=row, column=0, sticky='ew', padx=padx)


def configure_styles(app):
    style = ttk.Style(app)
    style.theme_use('clam')
    scale = app._apply_window_scaling
    style.layout('Flare.Treeview', [('Treeview.treearea', {'sticky': 'nswe'})])
    style.configure('Flare.Treeview', background=WHITE, fieldbackground=WHITE, foreground=INK,
                    rowheight=scale(42), borderwidth=0, font=(theme.FONT, 10))
    style.configure('Flare.Treeview.Heading', background='#F4F5F2', foreground='#575953',
                    font=(theme.FONT, 9), relief='flat', padding=(8, 6))
    style.map('Flare.Treeview', background=[('selected', '#E7F1C9')], foreground=[('selected', BLACK)])

    # Nine-sliced outlines give native, keyboard-operable comboboxes the same
    # rounded shape as the other controls, including a visible focus state.
    app.style_images = []
    def native_image(pixels):
        image = ImageTk.PhotoImage(pixels, master=app)
        app.style_images.append(image)
        return image

    def field(edge, stroke):
        side = scale(24)
        pixels = Image.new('RGBA', (side, side))
        ImageDraw.Draw(pixels).rounded_rectangle((0, 0, side-1, side-1), radius=scale(6),
                                                 fill=WHITE, outline=edge, width=scale(stroke))
        return native_image(pixels)

    arrow = Image.new('RGBA', (scale(27), scale(16)))
    ImageDraw.Draw(arrow).line([(scale(x), scale(y)) for x,y in [(8, 6), (12, 10), (16, 6)]],
                              fill='#4A4D45', width=max(1, scale(2)), joint='curve')
    style.element_create('FlareCombo.field', 'image', field('#D8DBD2',1),
                         ('focus', field('#839D43',2)), border=scale(7), sticky='nswe')
    style.element_create('FlareCombo.downarrow', 'image', native_image(arrow), sticky='')
    style.layout('Flare.TCombobox', [('FlareCombo.field', {
        'sticky': 'nswe', 'children': [
            ('FlareCombo.downarrow', {'side': 'right', 'sticky': 'ns'}),
            ('Combobox.padding', {'sticky': 'nswe', 'children': [
                ('Combobox.textarea', {'sticky': 'nswe'})]})]})])
    style.configure('Flare.TCombobox', padding=(5, 1), foreground=INK, background=WHITE)
    style.map('Flare.TCombobox', fieldbackground=[('readonly', WHITE)],
              foreground=[('disabled', MUTED), ('readonly', INK)], selectbackground=[('readonly', WHITE)],
              selectforeground=[('readonly', INK)])

    # These image elements stretch as a two-color four-pixel line at any DPI.
    for tail, color in [('trough', '#E0E3DA'), ('pbar', LIME)]:
        pixels = Image.new('RGB', (1, max(1, scale(4))), color)
        style.element_create('Flare.Horizontal.Progressbar.' + tail, 'image', native_image(pixels),
                             border=0, sticky='nswe')
    style.layout('Flare.Horizontal.TProgressbar', [('Flare.Horizontal.Progressbar.trough', {
        'sticky': 'nswe', 'children': [('Flare.Horizontal.Progressbar.pbar',
                                      {'side': 'left', 'sticky': 'ns'})]})])



def build_ui(self):
    configure_styles(self)
    self.grid_columnconfigure(0, weight=1)
    self.grid_rowconfigure(1, weight=1)
    self.preview = self.preview_canvas = self.preview_name = self.preview_details = None

    header = ctk.CTkFrame(self, fg_color=BLACK, corner_radius=theme.RADIUS_CARD)
    header.grid(row=0, column=0, sticky='ew', padx=24, pady=(20, 12))
    header.grid_columnconfigure(1, weight=1)
    with Image.open(ASSETS / 'FlareTools.png') as mark:
        self.brand_image = ctk.CTkImage(light_image=mark.copy(), size=(51, 51))
    ctk.CTkLabel(header, text='', image=self.brand_image).grid(
        row=0, column=0, sticky='nw', padx=(19, 12), pady=(15, 12))
    title = frame(header)
    title.grid(row=0, column=1, sticky='w', pady=(15, 12))
    self.label(title, 'FLARE TOOLS', 9, LIME, True, height=16).pack(anchor='w')
    self.label(title, 'Image Compressor', 21, WHITE, True, height=32).pack(anchor='w')
    updates = frame(header)
    updates.grid(row=0, column=2, sticky='ne', padx=(10, 19), pady=(18, 0))
    self.label(updates, 'v' + updater.VERSION, 9, '#B8B9B4').pack(side='left', padx=(0, 10))
    self.update_button = quiet_button(updates, 'Check for updates', lambda: self.check_updates(True), 118, True)
    self.update_button.pack(side='left')
    ctk.CTkFrame(header, height=1, fg_color='#363733', corner_radius=0).grid(
        row=1, column=0, columnspan=3, sticky='ew', padx=22)
    output = frame(header)
    output.grid(row=2, column=0, columnspan=3, sticky='ew', padx=22, pady=(3, 5))
    output.grid_columnconfigure(1, weight=1)
    self.label(output, 'Save copies to', 9, '#B8B9B4').grid(row=0, column=0, sticky='w', padx=(0, 9))
    self.output_label = self.label(output, '', 9, '#F1F2EC', anchor='w')
    self.output_label.grid(row=0, column=1, sticky='ew')
    change = quiet_button(output, 'Change…', self.change_output, 74, True)
    change.grid(row=0, column=2)
    self.mutable.append(change)
    quiet_button(output, 'Open folder', self.open_folder, 84, True).grid(row=0, column=3)

    workspace = ctk.CTkFrame(self, fg_color=WHITE, corner_radius=theme.RADIUS_CARD,
                             border_color=BORDER, border_width=1)
    workspace.grid(row=1, column=0, sticky='nsew', padx=24)
    workspace.grid_columnconfigure(0, weight=1)
    workspace.grid_rowconfigure(1, weight=1)
    queue_header = frame(workspace)
    queue_header.grid(row=0, column=0, sticky='ew', padx=20, pady=(12, 7))
    queue_header.grid_columnconfigure(1, weight=1)
    self.label(queue_header, 'Image queue', 13, bold=True).grid(row=0, column=0, sticky='w')
    self.queue_footer = frame(queue_header)
    self.queue_footer.grid(row=0, column=1, sticky='ew', padx=(16, 0))
    self.stat_labels = []
    for title in ('images', 'original', 'saved'):
        group = frame(self.queue_footer)
        group.pack(side='left', padx=(0, 12))
        value = self.label(group, '0', 9, INK, True)
        value.pack(side='left', padx=(0, 4))
        self.label(group, title, 9, MUTED).pack(side='left')
        self.stat_labels.append(value)
    for title, action in [('Clear list', self.clear), ('Remove selected', self.remove_selected)]:
        button = quiet_button(self.queue_footer, title, action, 68 if title == 'Clear list' else 112)
        button.pack(side='right')
        self.mutable.append(button)
    self.queue_footer.grid_remove()

    pane = tk.Frame(workspace, bg=WHITE, bd=0)
    pane.grid(row=1, column=0, sticky='nsew', padx=20, pady=(0, 12))
    pane.grid_columnconfigure(0, weight=1)
    pane.grid_rowconfigure(0, weight=1)
    self.tree = ttk.Treeview(pane, columns=('name', 'before', 'after', 'saved', 'status'),
                             show='tree headings', selectmode='extended', height=2, style='Flare.Treeview')
    scale = self._apply_window_scaling
    for key, title, width, anchor in [
        ('#0', '', 54, 'center'), ('name', 'File name', 220, 'w'), ('before', 'Original', 92, 'e'),
        ('after', 'Compressed', 102, 'e'), ('saved', 'Saved', 76, 'e'), ('status', 'Status', 132, 'w')
    ]:
        self.tree.heading(key, text=title, anchor=anchor)
        self.tree.column(key, width=round(scale(width)), minwidth=round(scale(45)),
                         anchor=anchor, stretch=key == 'name')
    self.tree.grid(row=0, column=0, sticky='nsew')
    scroll = ctk.CTkScrollbar(pane, orientation='vertical', command=self.tree.yview, width=11,
                              fg_color=WHITE, button_color='#C7CBC1', button_hover_color='#9DA393',
                              border_spacing=2)
    scroll.grid(row=0, column=1, sticky='ns')
    self.thumbnails = QueueThumbnails(self.tree, scroll, round(scale(32)))
    self.tree.tag_configure('error', foreground=RED)
    self.tree.bind('<<TreeviewSelect>>', self.selection_changed)
    self.tree.bind('<Delete>', lambda _: self.remove_selected())
    self.tree.bind('<Double-1>', self.open_result)
    self.tree.bind('<Return>', self.open_result)

    self.empty = ctk.CTkFrame(pane, fg_color='#F8F9F5', corner_radius=14,
                              border_color='#E4E6DD', border_width=1)
    self.empty.place(x=0, y=0, relwidth=1, relheight=1)
    empty_content = frame(self.empty)
    empty_content.place(relx=.5, rely=.5, anchor='center')
    self.drop_icon = drop_icon()
    ctk.CTkLabel(empty_content, text='', image=self.drop_icon, height=49).pack(pady=(0, 5))
    self.label(empty_content, 'Drop images here', 15, bold=True, height=28).pack()
    self.label(empty_content, 'Drag in files or a folder, or click to browse.', 10, MUTED,
               height=22).pack(pady=(2, 0))

    # Tk does not bubble pointer events through children. Give the entire drop
    # surface one binding so the icon, text and padding have the same behavior.
    def browse(_):
        self.add_images()

    self.bind_class('FlareDropArea', '<Button-1>', browse)
    def clickable(widget):
        widget.bindtags(('FlareDropArea', *widget.bindtags()))
        for child in widget.winfo_children():
            clickable(child)
    self.empty.configure(cursor='hand2')
    clickable(self.empty)

    divider(workspace, 2)
    settings = frame(workspace)
    settings.grid(row=3, column=0, sticky='ew', padx=20, pady=(11, 10))
    settings.grid_columnconfigure(2, weight=1)
    self.label(settings, 'Preset', 10, bold=True).grid(row=0, column=0, padx=(0, 10))
    self.profile_picker = combobox(settings, self.profile_var, self.profiles.names, self.select_profile, 21)
    self.profile_picker.grid(row=0, column=1, sticky='w')
    self.summary = self.label(settings, '', 9, MUTED, anchor='w')
    self.summary.grid(row=0, column=2, sticky='ew', padx=(12, 6))
    for variable in (self.preset, self.format, self.resize):
        variable.trace_add('write', lambda *_: update_summary(self))
    update_summary(self)
    self.advanced_button = quiet_button(settings, 'Edit settings', lambda: toggle_advanced(self), 90)
    self.advanced_button.grid(row=0, column=3)
    save_button = quiet_button(settings, 'Save as…', lambda: save_dialog(self), 70)
    save_button.grid(row=0, column=4)
    manage_button = quiet_button(settings, 'Manage…', lambda: manage_dialog(self), 74)
    manage_button.grid(row=0, column=5)
    self.mutable.extend([self.profile_picker, self.advanced_button, save_button, manage_button])

    self.advanced = ctk.CTkFrame(workspace, fg_color='#F6F7F3', corner_radius=12)
    self.advanced.grid(row=4, column=0, sticky='ew', padx=20, pady=(0, 12))
    options = frame(self.advanced)
    options.pack(fill='x', padx=12, pady=(9, 2))
    for title_text, variable, values, width in [
        ('Quality', self.preset, QUALITIES, 13), ('Format', self.format, FORMATS, 12),
        ('Longest edge', self.resize, SIZES, 13)
    ]:
        self.label(options, title_text, 9, INK).pack(side='left', padx=(0, 8))
        option = combobox(options, variable, values, lambda _: self.options_changed(), width)
        option.pack(side='left', padx=(0, 14))
        self.mutable.append(option)
    self.hint = self.label(self.advanced, '', 9, MUTED, height=20, anchor='w')
    self.hint.pack(fill='x', padx=12, pady=(1, 8))
    self.advanced.grid_remove()

    divider(workspace, 5)
    actions = frame(workspace)
    actions.grid(row=6, column=0, sticky='ew', padx=20, pady=(12, 15))
    self.add_button = self.button(actions, 'Add images…', self.add_images, width=14)
    self.add_button.pack(side='left', padx=(0, 8))
    folder = self.button(actions, 'Add folder…', self.add_folder, width=13)
    folder.pack(side='left')
    self.mutable.extend([self.add_button, folder])
    self.compress_button = self.button(actions, 'Compress images', self.start_batch, True, 19)
    self.compress_button.pack(side='right')
    footer = frame(self)
    footer.grid(row=2, column=0, sticky='ew', padx=28, pady=(7, 9))
    footer.grid_columnconfigure(0, weight=1)
    self.progress = ttk.Progressbar(footer, maximum=100, style='Flare.Horizontal.TProgressbar')
    self.progress.grid(row=0, column=0, sticky='ew', pady=(1, 3))
    self.progress.grid_remove()
    self.status = self.label(footer, 'Ready', 9, MUTED, height=20, anchor='w')
    self.status.grid(row=1, column=0, sticky='ew')
    self.refresh_output()
    keyboard_buttons(self)


def drop_icon():
    # Draw a high-resolution photo glyph so its edges stay clean at desktop DPI.
    img = Image.new('RGBA', (216, 168))
    pen = ImageDraw.Draw(img)
    pen.rounded_rectangle((12, 25, 151, 157), radius=18, fill='#E0E3D8')
    pen.rounded_rectangle((38, 8, 202, 137), radius=18, fill=WHITE, outline=BLACK, width=6)
    pen.ellipse((61, 30, 85, 54), fill=LIME)
    pen.polygon([(49, 115), (94, 69), (118, 90), (145, 58), (191, 113), (191, 125), (49, 125)],
                fill='#DCEBAD')
    pen.line([(49, 115), (94, 69), (118, 90), (145, 58), (191, 113)], fill=BLACK, width=5, joint='curve')
    return ctk.CTkImage(light_image=img, size=(63, 49))


def update_summary(app):
    fmt = 'Original format' if app.format.get() == 'Keep format' else app.format.get()
    app.summary.configure(text='  ·  '.join([app.preset.get(), fmt, app.resize.get()]))


def toggle_advanced(app):
    if app.advanced.winfo_manager():
        app.advanced.grid_remove()
        app.advanced_button.configure(text='Edit settings')
    else:
        app.advanced.grid()
        app.advanced_button.configure(text='Hide settings')


def modal(app, title):
    window = ctk.CTkToplevel(app)
    window.withdraw()
    window.title(title)
    window.configure(fg_color=WHITE)
    window.transient(app)
    window.resizable(False, False)
    window.bind('<Escape>', lambda _: window.destroy())
    body = frame(window)
    body.pack(fill='both', expand=True, padx=20, pady=18)
    body.grid_columnconfigure(0, weight=1)
    app.label(body, title, 15, bold=True).grid(row=0, column=0, sticky='w', pady=(0, 10))
    return window, body


def show_modal(app, window, first):
    keyboard_buttons(window)
    window.update_idletasks()
    width, height = window.winfo_reqwidth(), window.winfo_reqheight()
    x = max(0, app.winfo_rootx() + (app.winfo_width() - width) // 2)
    y = max(0, app.winfo_rooty() + (app.winfo_height() - height) // 2)
    window.geometry(f'+{x}+{y}')
    window.deiconify()
    window.grab_set()
    if isinstance(first, ctk.CTkButton):
        tk.Misc.focus_set(first)
    else:
        first.focus_set()


def save_dialog(app):
    window, body = modal(app, 'Save preset')
    app.label(body, app.summary.cget('text'), 10, MUTED).grid(row=1, column=0, sticky='w', pady=(0, 12))
    app.label(body, 'Preset name', 10, bold=True).grid(row=2, column=0, sticky='w')
    entry = ctk.CTkEntry(body, width=360, height=36, corner_radius=8, border_color=BORDER)
    entry.grid(row=3, column=0, sticky='ew')
    error = app.label(body, '', 9, RED, wraplength=350, anchor='w', justify='left')
    error.grid(row=4, column=0, sticky='w', pady=(2, 4))

    def save(event=None):
        name = unicodedata.normalize('NFKC', entry.get()).strip()
        existing = next((n for n in app.profiles.user_names if n.casefold() == name.casefold()), None)
        if existing and not messagebox.askyesno('Replace preset',
                f'Replace “{existing}” with the current compression settings?', parent=window):
            return
        try:
            app.save_profile(name, overwrite=bool(existing))
        except (OSError, ValueError) as failure:
            error.configure(text=str(failure))
            return
        window.destroy()

    actions = frame(body)
    actions.grid(row=5, column=0, sticky='e')
    quiet_button(actions, 'Cancel', window.destroy, 72).pack(side='left', padx=(0, 8))
    app.button(actions, 'Save preset', save, True).pack(side='left')
    window.bind('<Return>', save)
    show_modal(app, window, entry)


def manage_dialog(app):
    window, body = modal(app, 'Manage presets')
    names = list(app.profiles.user_names)
    if not names:
        app.label(body, 'Use Save as… to create your first preset.', 10, MUTED).grid(
            row=1, column=0, sticky='w', pady=(2, 14))
        done = app.button(body, 'Done', window.destroy)
        done.grid(row=2, column=0, sticky='e')
        show_modal(app, window, done)
        return
    selected = tk.StringVar(window, value=app.profiles.selected if app.profiles.selected in names else names[0])
    new_name = tk.StringVar(window, value=selected.get())
    app.label(body, 'Saved preset', 10, bold=True).grid(row=1, column=0, sticky='w')
    picker = combobox(body, selected, names, lambda name: new_name.set(name), 35)
    picker.grid(row=2, column=0, sticky='ew', pady=(0, 10))
    app.label(body, 'Preset name', 10, bold=True).grid(row=3, column=0, sticky='w')
    line = frame(body)
    line.grid(row=4, column=0, sticky='ew')
    entry = ctk.CTkEntry(line, textvariable=new_name, height=34, width=245,
                         corner_radius=8, border_color=BORDER)
    entry.pack(side='left', expand=True, fill='x')
    error = app.label(body, '', 9, RED, wraplength=350, anchor='w', justify='left')
    error.grid(row=5, column=0, sticky='w', pady=(0, 3))

    def rename():
        try:
            app.rename_profile(selected.get(), new_name.get())
        except (ValueError, OSError) as failure:
            error.configure(text=str(failure))
            return
        window.destroy()

    def delete():
        if not messagebox.askyesno('Delete preset', f'Delete “{selected.get()}”?', parent=window):
            return
        try:
            app.delete_profile(selected.get())
        except (ValueError, OSError) as failure:
            error.configure(text=str(failure))
            return
        window.destroy()

    def replace():
        if not messagebox.askyesno('Update preset',
                f'Replace “{selected.get()}” with the current settings?\n\n{app.summary.cget("text")}', parent=window):
            return
        try:
            app.save_profile(selected.get(), overwrite=True)
        except (ValueError, OSError) as failure:
            error.configure(text=str(failure))
            return
        window.destroy()

    quiet_button(line, 'Rename', rename, 80).pack(side='left', padx=(6, 0))
    actions = frame(body)
    actions.grid(row=6, column=0, sticky='ew')
    update = quiet_button(actions, 'Use current settings', replace, 138)
    update.pack(side='left')
    remove = quiet_button(actions, 'Delete', delete, 64)
    remove.configure(text_color=RED)
    remove.pack(side='left')
    app.button(actions, 'Done', window.destroy, width=9).pack(side='right', padx=(12, 0))
    show_modal(app, window, picker)


def preview_dialog(app):
    if app.preview is not None and app.preview.winfo_exists():
        app.preview.lift()
        return
    app.preview = ctk.CTkToplevel(app)
    app.preview.title('Image details')
    app.preview.resizable(False, False)
    app.preview.transient(app)
    app.preview.configure(fg_color=BG)
    panel = tk.Frame(app.preview, bg='#ECEEE7', width=296, height=205)
    panel.pack(padx=20, pady=(20, 10), fill='x')
    panel.pack_propagate(False)
    app.preview_canvas = tk.Label(panel, bg='#ECEEE7', fg=MUTED, text='Loading preview…')
    app.preview_canvas.pack(expand=True, fill='both')
    app.preview_name = app.label(app.preview, '', 12, bold=True, wraplength=296)
    app.preview_name.pack(padx=20)
    app.preview_details = app.label(app.preview, '', 9, MUTED, wraplength=296)
    app.preview_details.pack(padx=20, pady=(4, 18))

