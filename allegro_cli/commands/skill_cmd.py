from __future__ import annotations

import shutil
from pathlib import Path

_SKILLS_DIR = Path.home() / ".claude" / "skills"
_PACKAGE_SKILLS = Path(__file__).resolve().parent.parent.parent / "skills" / "allegro-cli"


def handle_skill(args) -> int:
    target = Path(getattr(args, "target_dir", None) or _SKILLS_DIR) / "allegro-cli"
    target.mkdir(parents=True, exist_ok=True)

    # ponytail: copy whole dir, don't enumerate individual files
    for src in _PACKAGE_SKILLS.iterdir():
        if src.is_file():
            shutil.copy2(src, target / src.name)

    print(f"Skill installed to {target}")
    print("Restart Claude Code for the skill to take effect.")
    return 0
