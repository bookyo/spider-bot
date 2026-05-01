"""环境变量加载。"""

from pathlib import Path

from dotenv import load_dotenv


def load_backend_env() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    project_root = backend_root.parent

    # 先加载通用 .env，再用 .env.local 覆盖。
    for path in (
        project_root / '.env',
        project_root / '.env.local',
        backend_root / '.env',
        backend_root / '.env.local',
    ):
        if path.exists():
            load_dotenv(path, override=True)
