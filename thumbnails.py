"""Load only visible image thumbnails without decoding files on Tk's thread."""
from collections import OrderedDict
from queue import Empty, Queue
import threading

from PIL import Image, ImageOps, ImageTk


class QueueThumbnails:
    def __init__(self, tree, scroll, size):
        self.tree = tree
        self.size = size
        self.cache = OrderedDict()
        self.tasks = Queue(maxsize=2)
        self.results = Queue()
        self.worker = None
        self.active = None
        self.visible = ()
        self.debounce = None
        self.poll = None
        self.closed = False

        def scrolled(first, last):
            scroll.set(float(first), float(last))
            overflow = float(first) > 0 or float(last) < 1
            if overflow and not scroll.winfo_manager():
                scroll.grid()
            elif not overflow and scroll.winfo_manager():
                scroll.grid_remove()
            self.refresh()

        tree.configure(yscrollcommand=scrolled)
        tree.bind('<Configure>', self.refresh, add=True)
        tree.bind('<Map>', self.refresh, add=True)
        tree.bind('<Destroy>', self._close, add=True)

    def refresh(self, _=None):
        if not self.closed and self.debounce is None:
            self.debounce = self.tree.after(55, self._viewport)

    def _viewport(self):
        self.debounce = None
        height = self.tree.winfo_height()
        step = max(4, self.size // 2)
        rows = [self.tree.identify_row(y) for y in range(0, height, step)]
        rows.append(self.tree.identify_row(max(0, height - 1)))
        self.visible = tuple(dict.fromkeys(row for row in rows if row))
        for key in self.visible:
            if key in self.cache:
                self.cache.move_to_end(key)
                image = self.cache[key]
                if image is not None and not self.tree.item(key, 'image'):
                    self.tree.item(key, image=image)
        self._next()

    def _next(self):
        if self.active or self.closed:
            return
        key = next((row for row in self.visible if row not in self.cache and self.tree.exists(row)), None)
        if not key:
            return
        if self.worker is None:
            self.worker = threading.Thread(target=_decode, args=(self.tasks, self.results, self.size),
                                           daemon=True, name='Flare thumbnails')
            self.worker.start()
        self.active = key
        self.tasks.put_nowait(key)
        self.poll = self.tree.after(25, self._receive)

    def _receive(self):
        self.poll = None
        try:
            key, thumb = self.results.get_nowait()
        except Empty:
            self.poll = self.tree.after(35, self._receive)
            return
        self.active = None
        if self.tree.exists(key):
            image = ImageTk.PhotoImage(thumb, master=self.tree) if thumb is not None else None
            self.cache[key] = image
            if image is not None:
                self.tree.item(key, image=image)
            # Accommodate unusually tall windows and retain a small scroll-back buffer.
            while len(self.cache) > max(64, len(self.visible) * 2):
                old, _ = self.cache.popitem(last=False)
                if self.tree.exists(old):
                    self.tree.item(old, image='')
        self._next()

    def _close(self, _=None):
        self.closed = True
        for timer in (self.debounce, self.poll):
            if timer is not None:
                self.tree.after_cancel(timer)
        if self.worker is not None:
            self.tasks.put_nowait(None)
        self.cache.clear()


def _decode(tasks, results, size):
    while (key := tasks.get()) is not None:
        try:
            with Image.open(key) as source:
                if source.width * source.height > Image.MAX_IMAGE_PIXELS:
                    raise ValueError('Image is too large for a thumbnail')
                source.draft('RGB', (size, size))
                source.thumbnail((size, size), Image.Resampling.BILINEAR)
                thumb = ImageOps.exif_transpose(source).convert('RGBA')
        except Exception:
            # Broken files still appear in the queue and are reported during compression.
            thumb = None
        results.put((key, thumb))
