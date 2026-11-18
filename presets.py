"""Persistent, named compression settings for Flare Tools Image Compressor."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import tempfile
import unicodedata


QUALITIES = ('Balanced', 'Best quality', 'Smallest')
FORMATS = ('Keep format', 'WebP')
SIZES = ('Original size', '2560 px', '1920 px', '1280 px')
CUSTOM = 'Custom settings'


@dataclass(frozen=True)
class Profile:
    quality: str = 'Balanced'
    format: str = 'Keep format'
    resize: str = 'Original size'

    def __post_init__(self):
        if self.quality not in QUALITIES or self.format not in FORMATS or self.resize not in SIZES:
            raise ValueError('Choose a supported quality, output format, and image size.')


BUILTINS = {
    'Everyday': Profile(),
    'Product photos': Profile('Best quality', 'Keep format', 'Original size'),
    'Website images': Profile('Balanced', 'WebP', '1920 px'),
    'Email attachments': Profile('Smallest', 'Keep format', '1280 px'),
}


def _name(value):
    if not isinstance(value, str):
        raise ValueError('Enter a preset name.')
    value = unicodedata.normalize('NFKC', value).strip()
    if not value or len(value) > 48 or any(not char.isprintable() for char in value):
        raise ValueError('Use a preset name between 1 and 48 printable characters.')
    return value


def _matching_name(value, choices):
    key = _name(value).casefold()
    return next((name for name in choices if name.casefold() == key), None)


@dataclass
class _State:
    users: dict[str, Profile] = field(default_factory=dict)
    selected: str = 'Everyday'
    current: Profile = field(default_factory=Profile)

    def profiles(self):
        return BUILTINS | self.users


def _legacy(settings):
    data = settings if isinstance(settings, dict) else {}
    profile = Profile(*(data.get(key) if data.get(key) in values else values[0]
                        for key, values in [('preset', QUALITIES), ('format', FORMATS), ('resize', SIZES)]))
    selected = next((name for name, preset in BUILTINS.items() if profile == preset), CUSTOM)
    return _State(selected=selected, current=profile)


@contextmanager
def _lock(path):
    """Serialize short read/modify/write operations across running instances."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix('.lock').open('a+b') as file:
        if os.name == 'nt':
            import msvcrt
            file.seek(0)
            msvcrt.locking(file.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                file.seek(0)
                msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(file.fileno(), fcntl.LOCK_UN)


class PresetStore:
    """Load a user's profiles. Persist successful changes atomically in one file."""

    def __init__(self, path: Path, legacy_settings=None):
        self.path = Path(path)
        self._legacy = legacy_settings
        self._state = self._read()

    @property
    def user_names(self):
        return tuple(sorted(self._state.users, key=str.casefold))

    @property
    def names(self):
        return (*BUILTINS, *self.user_names)

    @property
    def current(self):
        return self._state.current

    @property
    def selected(self):
        return self._state.selected

    def _read(self):
        try:
            data = json.loads(self.path.read_text('utf-8'))
        except FileNotFoundError:
            return _legacy(self._legacy)
        except (UnicodeError, json.JSONDecodeError):
            return _legacy(self._legacy)
        if not isinstance(data, dict) or data.get('version') != 1:
            return _legacy(self._legacy)
        state = _State()
        users = data.get('profiles')
        for raw_name, values in (users.items() if isinstance(users, dict) else ()):
            try:
                name = _name(raw_name)
                if not _matching_name(name, (*state.profiles(), CUSTOM)):
                    state.users[name] = Profile(**values)
            except (ValueError, TypeError):
                continue
        selected = data.get('selected')
        if isinstance(selected, str) and selected in state.profiles():
            state.selected, state.current = selected, state.profiles()[selected]
        elif selected == CUSTOM:
            try:
                state.current = Profile(**data['current'])
                state.selected = CUSTOM
            except (KeyError, ValueError, TypeError):
                pass
        return state

    def _change(self, change):
        with _lock(self.path):
            state = self._read()
            change(state)
            data = {'version': 1, 'profiles': {name: asdict(profile) for name, profile in state.users.items()},
                    'selected': state.selected, 'current': asdict(state.current)}
            temp_name = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent,
                                                 prefix='.presets-', suffix='.tmp', delete=False) as file:
                    temp_name = file.name
                    json.dump(data, file, indent=2, ensure_ascii=False)
                    file.flush()
                    os.fsync(file.fileno())
                os.replace(temp_name, self.path)
            finally:
                if temp_name:
                    Path(temp_name).unlink(missing_ok=True)
            self._state = state
        return self.current

    def select(self, name):
        def change(state):
            if name == CUSTOM and state.selected == CUSTOM:
                return
            key = _matching_name(name, state.profiles())
            if key is None:
                raise ValueError('That preset is no longer available.')
            state.selected, state.current = key, state.profiles()[key]
        return self._change(change)

    def edit(self, profile: Profile):
        """Persist unsaved settings without overwriting the named original."""
        if not isinstance(profile, Profile):
            raise ValueError('Choose valid compression settings.')
        if profile == self.current:
            return profile
        def change(state):
            state.selected, state.current = CUSTOM, profile
        return self._change(change)

    def save(self, name, profile: Profile, *, overwrite=False):
        if not isinstance(profile, Profile):
            raise ValueError('Choose valid compression settings.')
        name = _name(name)
        def change(state):
            if _matching_name(name, (*BUILTINS, CUSTOM)):
                raise ValueError('This name is reserved. Choose another name.')
            old = _matching_name(name, state.users)
            if old and not overwrite:
                raise ValueError('A preset already uses this name.')
            key = old or name
            state.users[key] = profile
            state.selected, state.current = key, profile
        return self._change(change)

    def rename(self, old, new):
        new = _name(new)
        def change(state):
            key = _matching_name(old, state.users)
            if key is None:
                raise ValueError('Only your saved presets can be renamed.')
            collision = _matching_name(new, (*state.profiles(), CUSTOM))
            if collision and collision != key:
                raise ValueError('A preset already uses this name.')
            state.users[new] = state.users.pop(key)
            if state.selected == key:
                state.selected = new
        return self._change(change)

    def delete(self, name):
        def change(state):
            key = _matching_name(name, state.users)
            if key is None:
                raise ValueError('Only your saved presets can be deleted.')
            state.users.pop(key)
            if state.selected == key:
                state.selected, state.current = 'Everyday', BUILTINS['Everyday']
        return self._change(change)
