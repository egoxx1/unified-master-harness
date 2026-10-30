#!/usr/bin/env python3
"""Append-only, secret-free log of V4 hook decisions (the Growth Engine's raw input).

Only calls the shared policy did not allow are logged (adapter-level asks for
unknown-but-harmless commands are not). Commands are reduced to a *shape* (program,
subcommand and option names, never argument values) plus a short digest, so the log
can be kept and analysed without exposing paths, tokens or other secrets.

Set V4_HOOK_LOG to a file path to redirect the log, or to "off" to disable it.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MAX_BYTES = 2 * 1024 * 1024


def log_path() -> Path | None:
    override = os.environ.get('V4_HOOK_LOG', '')
    if override.lower() == 'off':
        return None
    return Path(override) if override else ROOT / '.agent-state' / 'hook-log.jsonl'


def command_shape(command: str) -> str:
    """Program + subcommand + option names for each segment; values and paths are dropped."""
    from policy import GIT_VALUE_OPTIONS, _segments, _unwrap  # local import keeps adapters' import order simple

    parts = []
    for segment in _segments(command or ''):
        tokens = _unwrap(segment)
        if not tokens:
            continue
        program = Path(tokens[0]).name
        words, subcommand, skip_value = [program], None, False
        for token in tokens[1:]:
            if skip_value:
                skip_value = False
                continue
            if token.startswith('-'):
                words.append(token.split('=', 1)[0][:24])
                skip_value = program == 'git' and subcommand is None and token in GIT_VALUE_OPTIONS
            elif subcommand is None and re.fullmatch(r'[a-z][a-z-]{0,19}', token):
                # Only plain lowercase words (push / reset / checkout) can be a logged subcommand;
                # anything with digits, case or punctuation may be a value or secret and is dropped.
                subcommand = token
                words.append(token)
        parts.append(' '.join(words[:8]))
    return ' ; '.join(parts)[:200]


def subject_of(tool: str, tool_input: dict[str, Any]) -> tuple[str, str]:
    """Return (shape, raw) for the logged tool call; raw is only used for the digest."""
    from policy import patch_targets, shell_patch, strip_heredoc_bodies  # local import keeps adapters' import order simple
    command = ''
    for key in ('command', 'CommandLine', 'cmd', 'script'):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            command = value
            break
    if tool == 'apply_patch' or (command and shell_patch(command) and patch_targets(command)):
        # A patch body is file content: log only the names of the files it touches.
        names = [Path(t).name for t in patch_targets(command)][:5]
        return ' '.join(['apply_patch', *names])[:200], command
    if command:
        return command_shape(strip_heredoc_bodies(command)), command
    for key in ('file_path', 'path', 'AbsolutePath', 'TargetFile', 'glob'):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return f'{tool} {Path(value).name}', value
    return tool, json.dumps(tool_input, sort_keys=True)


def record(provider: str, tool: str, tool_input: dict[str, Any], decision: str, verdict: Any) -> None:
    """Never raises: logging must not change the hook's decision."""
    try:
        path = log_path()
        if path is None or getattr(verdict, 'action', 'allow') == 'allow':
            return
        shape, raw = subject_of(tool, tool_input or {})
        entry = {
            'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'provider': provider,
            'tool': tool,
            'decision': decision,
            'kind': getattr(verdict, 'kind', '') or '',
            'reason': (getattr(verdict, 'reason', '') or '')[:200],
            'shape': shape,
            'digest': hashlib.sha256(raw.encode('utf-8', 'replace')).hexdigest()[:16],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > MAX_BYTES:
            path.replace(path.with_name(path.name + '.1'))
        with path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception:
        return
