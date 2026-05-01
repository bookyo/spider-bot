"""后台任务运行器"""

import asyncio
import os
import sys
from datetime import datetime


BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_PY = os.path.join(BACKEND_ROOT, 'run.py')


async def run_backend_command(args: list[str]) -> tuple[int, str]:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        RUN_PY,
        *args,
        cwd=BACKEND_ROOT,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await process.communicate()
    output = stdout.decode('utf-8', errors='ignore') if stdout else ''
    return process.returncode, output


async def spawn_backend_command(args: list[str]) -> dict:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        RUN_PY,
        *args,
        cwd=BACKEND_ROOT,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    return {
        'pid': process.pid,
        'args': args,
        'started_at': datetime.utcnow(),
    }
