"""댓글 자동 답글 실행 진입점."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, reply_bot


def main() -> int:
    missing = config.validate(require_threads=not config.DRY_RUN, require_claude=True)
    if missing:
        print(f"환경변수 누락: {missing}")
        return 2
    reply_bot.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
