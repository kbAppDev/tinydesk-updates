from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import ctypes
import json
import logging
import os
import queue
import subprocess
import sys
import threading
import time
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import customtkinter as ctk

from PIL import Image, ImageOps, ImageTk
from tkinterdnd2 import DND_FILES, TkinterDnD

from engine import Options, compress, discover, human_bytes
import updater
import flare_theme as theme

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))


def known_folder(identifier, fallback):
    if sys.platform == 'win32':
        value = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.shell32.SHGetFolderPathW(None, identifier, None, 0, value) == 0:
            return Path(value.value)
    return Path(fallback)


DATA = Path(os.environ.get('FLARE_IMAGE_DATA_DIR') or
            known_folder(28, os.environ.get('LOCALAPPDATA') or tempfile.gettempdir()) / 'Flare Tools' / 'Image Compressor')
BG, INK, MUTED = theme.PAGE, theme.INK, theme.MUTED


def desktop():
    return known_folder(16, Path(os.environ.get('USERPROFILE') or tempfile.gettempdir()) / 'Desktop')


def load_settings():
    try:
        value = json.loads((DATA / 'settings.json').read_text('utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


class TinyDeskApp(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        ctk.set_appearance_mode('light')
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)
        self.title('TinyDesk — Image Compressor')
        self.geometry('1060x740')
        self.minsize(960, 680)
        self.configure(fg_color=BG)
        self.iconbitmap(str(ROOT / 'assets' / 'FlareTools.ico'))
        self.settings = load_settings()
        self.files = {}
        self.results = {}
        self.events = queue.Queue()
        self.cancel_event = threading.Event()
        self.busy = False
        self.importing = False
        self.updating = False
        self.update_checking = False
        self.update_info = None
        self.preview_token = 0
        self.preview_image = None
        self.total_before = 0
        self.run_before = 0
        self.run_after = 0
        self.run_ok = 0
        self.run_errors = 0
        self.completed = 0
        self.close_when_idle = False
        self.mutable = []
        self.preset = tk.StringVar(value=self.settings.get('preset', 'Balanced'))
        self.format = tk.StringVar(value=self.settings.get('format', 'Keep format'))
        self.resize = tk.StringVar(value=self.settings.get('resize', 'Original size'))
        if self.preset.get() not in ('Balanced', 'Best quality', 'Smallest'):
            self.preset.set('Balanced')
        if self.format.get() not in ('Keep format', 'WebP'):
            self.format.set('Keep format')
        if self.resize.get() not in ('Original size', '2560 px', '1920 px', '1280 px'):
            self.resize.set('Original size')
        self.output = Path(self.settings.get('output', str(desktop() / 'Flare Compressed Images')))
        self.build_ui()
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.on_drop)
        self.bind('<Control-o>', lambda _: self.add_images())
        self.bind('<Control-O>', lambda _: self.add_folder())
        self.bind('<Control-Return>', lambda _: self.start_batch())
        self.bind('<Escape>', lambda _: self.cancel_batch())
        self.protocol('WM_DELETE_WINDOW', self.on_close)
        self.after(70, self.poll)
        self.after(1800, lambda: self.check_updates(False))
        if len(sys.argv) > 1:
            self.after(150, lambda: self.import_paths(sys.argv[1:]))

    def label(self, parent, text='', size=10, color=INK, bold=False, **kw):
        return ctk.CTkLabel(parent, text=text, font=('Segoe UI', int(size * 1.32), 'bold' if bold else 'normal'),
                           text_color=color, **kw)

    def button(self, parent, text, command, primary=False, width=None):
        button = ctk.CTkButton(parent, text=text, command=command, font=('Segoe UI', 13, 'bold'),
                              fg_color=theme.LIME if primary else 'white', text_color=theme.BLACK if primary else INK,
                              hover_color=theme.LIME_HOVER if primary else '#F0F0EE', corner_radius=12,
                              height=42, border_width=0 if primary else 1, border_color=theme.BORDER,
                              text_color_disabled='#99a1a9', width=110)
        if width:
            button.configure(width=width * 9)
        return button

    def build_ui(self):
        from ui import build_ui
        build_ui(self)

    def refresh_output(self):
        text = str(self.output)
        self.output_label.configure(text=text if len(text) < 58 else '…' + text[-55:])

    def options_changed(self):
        hints = {'Balanced': 'A smaller file, with great quality. PNG colors stay unchanged.',
                 'Best quality': 'Keeps more fine detail. Files will be a little larger.',
                 'Smallest': 'The smallest files. PNG colors may look less detailed.'}
        self.hint.configure(text=hints[self.preset.get()])
        self.save_settings()

    def save_settings(self):
        self.settings.update(preset=self.preset.get(), format=self.format.get(), resize=self.resize.get(), output=str(self.output))
        try:
            DATA.mkdir(parents=True, exist_ok=True)
            temporary = DATA / 'settings.tmp'
            temporary.write_text(json.dumps(self.settings, indent=2), 'utf-8')
            temporary.replace(DATA / 'settings.json')
        except OSError:
            logging.exception('Could not save preferences')

    def add_images(self):
        if self.busy or self.importing or self.updating:
            return
        paths = filedialog.askopenfilenames(parent=self, title='Add images', filetypes=[
            ('Images', '*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff'), ('All files', '*.*')])
        if paths:
            self.import_paths(paths)

    def add_folder(self):
        if self.busy or self.importing or self.updating:
            return
        path = filedialog.askdirectory(parent=self, title='Add all images in a folder')
        if path:
            self.import_paths([path])

    def on_drop(self, event):
        if not self.busy and not self.updating:
            self.import_paths(self.tk.splitlist(event.data))
        return event.action

    def import_paths(self, paths):
        if self.busy or self.importing or self.updating:
            return
        self.importing = True
        self.set_controls(False)
        self.status.configure(text='Finding images…')
        def work():
            added = []
            try:
                for path in discover(paths):
                    try:
                        added.append((str(path), path.stat().st_size))
                    except OSError:
                        continue
                    if len(added) >= 100:
                        self.events.put(('import', added))
                        added = []
                    if self.events.qsize() > 100:
                        break
                if added:
                    self.events.put(('import', added))
            except Exception as error:
                self.events.put(('import_error', str(error)))
            finally:
                self.events.put(('import_done', None))
        threading.Thread(target=work, daemon=True).start()

    def set_controls(self, enabled):
        for widget in self.mutable:
            state = 'readonly' if isinstance(widget, ttk.Combobox) and enabled else ('normal' if enabled else 'disabled')
            widget.configure(state=state)
        self.compress_button.configure(state='normal' if enabled else 'disabled')

    def refresh_stats(self):
        self.stat_labels[0].configure(text=f'{len(self.files):,}')
        self.stat_labels[1].configure(text=human_bytes(self.total_before))
        saved = max(0, self.run_before - self.run_after)
        percent = saved * 100 / self.run_before if self.run_before else 0
        self.stat_labels[2].configure(text=f'{human_bytes(saved)}  ({percent:.0f}%)' if self.run_ok else '0 B')
        if self.files:
            self.empty.place_forget()
            self.queue_footer.grid()
        else:
            self.queue_footer.grid_remove()
            self.empty.place(x=0, y=0, relwidth=1, relheight=1)

    def remove_selected(self):
        if self.busy or self.importing or self.updating:
            return
        for key in self.tree.selection():
            self.total_before -= self.files.pop(key, 0)
            self.results.pop(key, None)
            self.tree.delete(key)
        self.refresh_stats()

    def clear(self):
        if self.busy or self.importing or self.updating:
            return
        self.tree.delete(*self.tree.get_children())
        self.files.clear()
        self.results.clear()
        self.total_before = self.run_before = self.run_after = self.run_ok = 0
        self.progress['value'] = 0
        self.progress.grid()
        self.refresh_stats()
        self.status.configure(text='Queue cleared. Saved images are still in your output folder.')

    def change_output(self):
        folder = filedialog.askdirectory(parent=self, title='Choose output folder', initialdir=self.output if self.output.exists() else desktop())
        if folder:
            self.output = Path(folder)
            self.refresh_output()
            self.save_settings()

    def open_folder(self):
        try:
            self.output.mkdir(parents=True, exist_ok=True)
            os.startfile(self.output)
        except OSError as error:
            messagebox.showerror('Could not open folder', str(error), parent=self)

    def selection_changed(self, event=None):
        selection = self.tree.selection()
        self.preview_token += 1
        token = self.preview_token
        if not selection:
            return
        key = selection[0]
        if event is not None:
            if not self.busy:
                result = self.results.get(key)
                detail = result.error if result and result.error else str(Path(key))
                self.status.configure(text=detail if len(detail) < 120 else detail[:117] + '...')
            return
        from ui import preview_dialog
        preview_dialog(self)
        self.preview_name.configure(text=Path(key).name)
        result = self.results.get(key)
        detail = result.error if result and result.error else str(Path(key).parent)
        self.preview_details.configure(text=detail)
        self.preview_canvas.configure(image='', text='Loading preview…', width=196, height=190)
        def work():
            try:
                with Image.open(key) as image:
                    size = image.size
                    image.draft('RGB', (196, 190))
                    image = ImageOps.exif_transpose(image)
                    image.thumbnail((196, 190))
                    image = image.convert('RGBA')
                    self.events.put(('preview', (token, image.copy(), size)))
            except Exception:
                self.events.put(('preview_error', token))
        # Only the selected file is decoded; the queue never caches full images.
        threading.Thread(target=work, daemon=True).start()

    def open_result(self, _=None):
        selection = self.tree.selection()
        if selection:
            result = self.results.get(selection[0])
            if result and result.output and result.output.exists():
                os.startfile(result.output)
            else:
                self.selection_changed()

    def start_batch(self):
        if self.busy or self.importing or self.updating:
            return
        if not self.files:
            self.add_images()
            return
        self.cancel_event.clear()
        self.busy = True
        self.run_before = self.run_after = self.run_ok = self.run_errors = self.completed = 0
        self.results.clear()
        self.set_controls(False)
        self.compress_button.configure(text='Cancel batch', command=self.cancel_batch, state='normal')
        self.progress['value'] = 0
        self.progress.grid()
        for key in self.files:
            self.tree.set(key, 'after', '—')
            self.tree.set(key, 'saved', '—')
            self.tree.set(key, 'status', 'Queued')
            self.tree.item(key, tags=())
        options = Options(self.preset.get(), self.format.get(), 0 if self.resize.get() == 'Original size' else int(self.resize.get().split()[0]))
        files = [Path(key) for key in self.files]
        output = self.output
        self.status.configure(text=f'Compressing {len(files)} images…')
        self.start_time = time.monotonic()
        def work():
            try:
                # Two workers overlap disk and codec work without large RAM spikes.
                with ThreadPoolExecutor(max_workers=2, thread_name_prefix='FlareImages') as pool:
                    futures = [pool.submit(compress, path, output, options, self.cancel_event) for path in files]
                    for future in as_completed(futures):
                        self.events.put(('result', future.result()))
            except Exception as error:
                self.events.put(('batch_error', str(error)))
            finally:
                self.events.put(('done', None))
        threading.Thread(target=work, daemon=True).start()

    def cancel_batch(self):
        if self.busy:
            self.cancel_event.set()
            self.compress_button.configure(text='Canceling…', state='disabled')
            self.status.configure(text='Finishing current operations. Completed copies stay in your output folder.')

    def on_close(self):
        if self.busy:
            if messagebox.askyesno('Finish and close?', 'Cancel remaining images and close Image Compressor? Completed copies will be kept.', parent=self):
                self.close_when_idle = True
                self.cancel_batch()
        elif self.updating:
            messagebox.showinfo('Downloading update', 'Please wait for the update download to finish.', parent=self)
        else:
            self.save_settings()
            self.destroy()

    def check_updates(self, manual=False):
        if self.update_checking or self.updating:
            return
        if self.update_info:
            self.install_update()
            return
        if not manual and time.time() - self.settings.get('last_update_check', 0) < 86400:
            return
        self.update_checking = True
        self.update_button.configure(text='Checking…', state='disabled')
        def work():
            try:
                self.events.put(('update', (updater.check(), manual, '')))
            except Exception as error:
                self.events.put(('update', (None, manual, str(error))))
        threading.Thread(target=work, daemon=True).start()

    def install_update(self):
        if self.busy or self.importing:
            messagebox.showinfo('Finish your batch', 'Finish or cancel the current batch before installing an update.', parent=self)
            return
        if not messagebox.askyesno('Flare Tools update', f'Image Compressor {self.update_info["version"]} is ready. Download and install it now?\n\nImage Compressor will close and the installer will open.', parent=self):
            return
        self.updating = True
        self.set_controls(False)
        self.update_button.configure(state='disabled', text='Downloading…')
        self.status.configure(text='Downloading update and verifying its checksum…')
        def work():
            try:
                path = updater.download(self.update_info, DATA / 'updates', lambda value: self.events.put(('update_progress', value)))
                self.events.put(('install_ready', path))
            except Exception as error:
                self.events.put(('install_error', str(error)))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            for _ in range(100):
                kind, value = self.events.get_nowait()
                if kind == 'import':
                    for key, size in value:
                        if key not in self.files and len(self.files) < 10000:
                            self.files[key] = size
                            self.total_before += size
                            self.tree.insert('', 'end', iid=key, values=(Path(key).name, human_bytes(size), '—', '—', 'Ready'))
                    self.refresh_stats()
                elif kind == 'import_done':
                    self.importing = False
                    self.set_controls(True)
                    self.status.configure(text=f'{len(self.files):,} images ready.' + (' Queue limit: 10,000 images.' if len(self.files) == 10000 else ''))
                elif kind in {'import_error', 'batch_error'}:
                    self.status.configure(text=value)
                elif kind == 'result':
                    result = value
                    key = str(result.source)
                    self.results[key] = result
                    self.completed += 1
                    if result.output:
                        self.run_ok += 1
                        self.run_before += result.before
                        self.run_after += result.after
                        percent = max(0, (result.before - result.after) * 100 / result.before) if result.before else 0
                        self.tree.set(key, 'after', human_bytes(result.after))
                        self.tree.set(key, 'saved', f'{percent:.0f}%')
                        self.tree.item(key, tags=('done',))
                    elif result.error:
                        self.run_errors += 1
                        self.tree.item(key, tags=('error',))
                    self.tree.set(key, 'status', result.status)
                    self.progress['value'] = self.completed * 100 / max(1, len(self.files))
                    self.status.configure(text=f'{self.completed}/{len(self.files)} processed · {self.run_errors} errors')
                    self.refresh_stats()
                elif kind == 'done':
                    self.busy = False
                    self.set_controls(True)
                    self.compress_button.configure(text='Compress images', command=self.start_batch)
                    elapsed = time.monotonic() - self.start_time
                    text = f'{"Canceled" if self.cancel_event.is_set() else "Done"} · {self.run_ok} saved · {self.run_errors} errors · {elapsed:.1f}s'
                    self.status.configure(text=text + (' · Select a red row for details.' if self.run_errors else ' · Double-click a row to open its copy.'))
                    if self.close_when_idle:
                        self.destroy()
                        return
                elif kind == 'preview':
                    token, image, size = value
                    if token == self.preview_token and self.preview is not None and self.preview.winfo_exists():
                        self.preview_image = ImageTk.PhotoImage(image)
                        self.preview_canvas.configure(image=self.preview_image, text='', width=196, height=190)
                        detail = self.preview_details.cget('text')
                        self.preview_details.configure(text=f'{size[0]:,} × {size[1]:,} px\n\n{detail}')
                elif kind == 'preview_error' and value == self.preview_token and self.preview is not None and self.preview.winfo_exists():
                    self.preview_canvas.configure(image='', text='Preview unavailable', width=26, height=11)
                elif kind == 'update':
                    info, manual, error = value
                    self.update_checking = False
                    self.update_info = info
                    self.update_button.configure(text='Install update' if info else 'Check for updates', state='normal')
                    if not error:
                        self.settings['last_update_check'] = time.time()
                        self.save_settings()
                    if manual:
                        if error:
                            messagebox.showinfo('Could not check updates', 'Flare Tools could not reach its update service. Try again when you are online.\n\n' + error, parent=self)
                        elif info:
                            self.install_update()
                        else:
                            messagebox.showinfo('You are up to date', f'Flare Tools - Image Compressor {updater.VERSION} is the latest version.', parent=self)
                elif kind == 'update_progress':
                    self.progress['value'] = value * 100
                elif kind == 'install_ready':
                    try:
                        subprocess.Popen([str(value), '/SP-', '/CLOSEAPPLICATIONS', '/RESTARTAPPLICATIONS'])
                        self.save_settings()
                        self.destroy()
                        return
                    except OSError as error:
                        self.events.put(('install_error', str(error)))
                elif kind == 'install_error':
                    self.updating = False
                    self.set_controls(True)
                    self.update_button.configure(state='normal', text='Install update')
                    self.status.configure(text='Update could not be installed. Your current version is still available.')
                    messagebox.showerror('Update not installed', value, parent=self)
        except queue.Empty:
            pass
        self.after(70, self.poll)


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=DATA / 'ImageCompressor.log', level=logging.WARNING,
                        format='%(asctime)s %(levelname)s %(message)s')
    if sys.platform == 'win32':
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(theme.APP_ID)
    app = TinyDeskApp()
    app.mainloop()


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--self-check':
        import selfcheck
        sys.exit(selfcheck.run(sys.modules[__name__], sys.argv[2]))
    try:
        main()
    except Exception as error:
        logging.exception('TinyDesk startup error')
        messagebox.showerror('Flare Tools could not start', str(error))
