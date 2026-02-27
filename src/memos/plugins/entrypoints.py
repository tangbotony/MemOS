from __future__ import annotations

import logging
import os

from importlib import metadata
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from collections.abc import Iterable


logger = logging.getLogger(__name__)

APP_PLUGIN_GROUP = "memos.plugins"
CLI_PLUGIN_GROUP = "memos.cli_plugins"


def _truthy_env(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "y", "on"}


def _iter_entry_points(group: str) -> Iterable[metadata.EntryPoint]:
    eps = metadata.entry_points()
    select = getattr(eps, "select", None)
    if callable(select):
        return eps.select(group=group)
    return eps.get(group, [])


def _load_group(group: str, *, context: dict[str, Any]) -> list[str]:
    enabled = _truthy_env("MEMOS_PLUGINS_ENABLED", "true")
    if not enabled:
        return []

    strict = _truthy_env("MEMOS_PLUGINS_STRICT", "false")

    loaded: list[str] = []
    for ep in _iter_entry_points(group):
        try:
            plugin_obj = ep.load()

            if callable(plugin_obj):
                plugin_obj(**context)
            else:
                register = getattr(plugin_obj, "register", None)
                if not callable(register):
                    raise TypeError(
                        f"Entry point '{ep.name}' in group '{group}' is not callable and has no .register()"
                    )
                register(**context)

            loaded.append(ep.name)
            logger.info("Loaded plugin '%s' from group '%s'", ep.name, group)
        except Exception:
            logger.exception("Failed to load plugin '%s' from group '%s'", ep.name, group)
            if strict:
                raise

    return loaded


def load_plugins(*, app: Any) -> list[str]:
    return _load_group(APP_PLUGIN_GROUP, context={"app": app})


def load_cli_plugins(*, subparsers: Any) -> list[str]:
    return _load_group(CLI_PLUGIN_GROUP, context={"subparsers": subparsers})
