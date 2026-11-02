# SPDX-License-Identifier: GPL-3.0-or-later
"""Minimal Chinese/English localisation for paim.

The user's session language is read the same way gettext does: LANGUAGE
first, then LC_ALL/LC_MESSAGES/LANG.  PAIM_LANG can explicitly override the
choice for testing or portable launches.
"""
from __future__ import annotations

import os

try:
    import gi
    gi.require_version('GLib', '2.0')
    from gi.repository import GLib
except Exception:  # pragma: no cover - only used in unusual headless contexts
    GLib = None

_OVERRIDE = None


def set_language(value):
    """Set ``zh``, ``en`` or ``None`` (automatic)."""
    global _OVERRIDE
    value = (value or '').lower()
    _OVERRIDE = 'zh' if value.startswith('zh') else ('en' if value else None)


def _locale_candidates():
    override = os.environ.get('PAIM_LANG', '').strip()
    if override:
        yield override
    for var in ('LANGUAGE', 'LC_ALL', 'LC_MESSAGES', 'LANG'):
        value = os.environ.get(var, '').strip()
        if value:
            for part in value.split(':'):
                if part.strip():
                    yield part.strip()
    if GLib is not None:
        try:
            for name in GLib.get_language_names():
                yield name
        except Exception:
            pass


def language_is_zh():
    if _OVERRIDE is not None:
        return _OVERRIDE == 'zh'
    for value in _locale_candidates():
        value = value.lower().replace('-', '_')
        if value.startswith('zh'):
            return True
        if value.startswith(('en', 'c', 'posix')):
            return False
    return False


def tr(zh, en):
    return zh if language_is_zh() else en
