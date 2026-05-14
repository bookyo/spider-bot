"""后台任务运行器"""

import asyncio
import os
import shlex
import signal
import sys
from datetime import datetime, timezone


BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_PY = os.path.join(BACKEND_ROOT, 'run.py')
RUNTIME_LOG_DIR = os.path.join(BACKEND_ROOT, 'runtime_logs')
MAX_OUTPUT_TAIL_BYTES = 64 * 1024


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _format_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def describe_process_exit(returncode: int | None) -> str:
    if returncode is None:
        return 'exit_state=unknown'
    if returncode >= 0:
        return f'exit_code={returncode}'

    signal_number = abs(returncode)
    try:
        signal_name = signal.Signals(signal_number).name
    except ValueError:
        signal_name = 'UNKNOWN'
    return f'signal={signal_name} signal_number={signal_number}'


def build_backend_log_path(args: list[str], started_at: datetime | None = None) -> str:
    started_at = started_at or _utcnow()
    os.makedirs(RUNTIME_LOG_DIR, exist_ok=True)

    command_name = 'task'
    if args:
        command_name = ''.join(
            ch if ch.isalnum() or ch in {'-', '_'} else '-'
            for ch in str(args[0]).strip().lower()
        ).strip('-') or 'task'

    filename = f"{started_at.strftime('%Y%m%d-%H%M%S-%f')}_{command_name}.log"
    return os.path.join(RUNTIME_LOG_DIR, filename)


def _format_command(args: list[str]) -> str:
    return ' '.join(shlex.quote(part) for part in [sys.executable, RUN_PY, *args])


def _write_log_header(log_path: str, args: list[str], started_at: datetime) -> None:
    with open(log_path, 'w', encoding='utf-8') as log_file:
        log_file.write(f'[runner] started_at={_format_utc(started_at)}\n')
        log_file.write(f'[runner] cwd={BACKEND_ROOT}\n')
        log_file.write(f'[runner] command={_format_command(args)}\n\n')


def _append_log_footer(log_path: str, finished_at: datetime, returncode: int | None) -> None:
    with open(log_path, 'a', encoding='utf-8') as log_file:
        log_file.write('\n')
        log_file.write(f'[runner] finished_at={_format_utc(finished_at)}\n')
        log_file.write(f'[runner] {describe_process_exit(returncode)}\n')


def _build_output_summary(
    *,
    args: list[str],
    started_at: datetime,
    finished_at: datetime,
    log_path: str,
    returncode: int | None,
    output_tail: str,
) -> str:
    metadata_lines = [
        f'[runner] started_at={_format_utc(started_at)}',
        f'[runner] finished_at={_format_utc(finished_at)}',
        f'[runner] cwd={BACKEND_ROOT}',
        f'[runner] command={_format_command(args)}',
        f'[runner] log_path={log_path}',
        f'[runner] {describe_process_exit(returncode)}',
    ]
    if output_tail.strip():
        return '\n'.join([output_tail.strip(), '', *metadata_lines])
    return '\n'.join(metadata_lines)


async def _read_process_output(process: asyncio.subprocess.Process, log_path: str) -> str:
    tail = b''
    with open(log_path, 'ab') as log_file:
        if process.stdout is not None:
            while True:
                chunk = await process.stdout.read(4096)
                if not chunk:
                    break
                log_file.write(chunk)
                tail += chunk
                if len(tail) > MAX_OUTPUT_TAIL_BYTES:
                    tail = tail[-MAX_OUTPUT_TAIL_BYTES:]
    return tail.decode('utf-8', errors='ignore')


async def run_backend_command(args: list[str], env: dict[str, str] | None = None) -> tuple[int, str]:
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    started_at = _utcnow()
    log_path = build_backend_log_path(args, started_at)
    _write_log_header(log_path, args, started_at)
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        RUN_PY,
        *args,
        cwd=BACKEND_ROOT,
        env=process_env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output_tail = await _read_process_output(process, log_path)
    code = await process.wait()
    finished_at = _utcnow()
    _append_log_footer(log_path, finished_at, code)
    output = _build_output_summary(
        args=args,
        started_at=started_at,
        finished_at=finished_at,
        log_path=log_path,
        returncode=code,
        output_tail=output_tail,
    )
    return code, output


async def spawn_backend_command(args: list[str], env: dict[str, str] | None = None) -> dict:
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    started_at = _utcnow()
    log_path = build_backend_log_path(args, started_at)
    _write_log_header(log_path, args, started_at)
    log_file = open(log_path, 'ab')
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        RUN_PY,
        *args,
        cwd=BACKEND_ROOT,
        env=process_env,
        stdout=log_file,
        stderr=asyncio.subprocess.STDOUT,
    )
    log_file.close()
    return {
        'pid': process.pid,
        'args': args,
        'started_at': started_at,
        'log_path': log_path,
    }


async def run_backend_command_stream(args: list[str], env: dict[str, str] | None = None) -> tuple[int, str]:
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    started_at = _utcnow()
    log_path = build_backend_log_path(args, started_at)
    _write_log_header(log_path, args, started_at)
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        RUN_PY,
        *args,
        cwd=BACKEND_ROOT,
        env=process_env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output_tail = await _read_process_output(process, log_path)
    code = await process.wait()
    finished_at = _utcnow()
    _append_log_footer(log_path, finished_at, code)
    output = _build_output_summary(
        args=args,
        started_at=started_at,
        finished_at=finished_at,
        log_path=log_path,
        returncode=code,
        output_tail=output_tail,
    )
    return code, output
