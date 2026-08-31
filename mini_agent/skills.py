import logging
import re
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: Path

class SkillRegistry:

    def __init__(self, skills_dir: Path = Path("skills")):
        self.skills_dir = Path(skills_dir)
        self.skills: dict[str, Skill] = {}
        self.load_all()

    def load_all(self) -> None:
        if not self.skills_dir.exists():
            return

        for entry in sorted(self.skills_dir.iterdir()):
            if not entry.is_dir():
                continue
            skill_file = entry / "SKILL.md"

            if not skill_file.exists():
                continue
            try:
                skill = self._parse(skill_file)

            except Exception as e:
                log.warning(
                    "Failed to load skill from %s: %s",
                    skill_file,
                    e,
                )
                continue
            if skill.name != entry.name:
                log.warning(
                    "Skill name '%s' does not match directory '%s' "
                    "(%s); skipping",
                    skill.name,
                    entry.name,
                    skill_file,
                )
                continue
            if skill.name in self.skills:
                log.warning(
                    "Duplicate skill name '%s' in %s; replacing previous",
                    skill.name,
                    skill_file,
                )
            self.skills[skill.name] = skill

    def get(self, name: str) -> Skill | None:
        return self.skills.get(name)

    def catalog_text(self) -> str:
        if not self.skills:
            return ""
        lines = [
            'To activate a skill, output {"skill": "<name>"} as the FIRST '
            "line of your response. Do NOT call skills as functions — they "
            "are procedures you read, not tools you invoke.",
            "",
            "Available skills:",
        ]
        for skill in self.skills.values():
            lines.append(f"- {skill.name}: {skill.description}")
        lines.append("")
        lines.append(
            "Once activated, a skill's instructions remain in effect "
            "for the rest of the session."
        )
        return "\n".join(lines)

    @staticmethod
    def _parse(path: Path) -> Skill:
        text = path.read_text(encoding="utf-8")
        match = re.match(
            r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z",
            text,
            re.DOTALL,
        )
        if not match:
            raise ValueError("SKILL.md missing YAML frontmatter")
        front, body = match.group(1), match.group(2)
        meta: dict[str, str] = {}
        for line in front.splitlines():
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip('"').strip("'")
        if "name" not in meta or "description" not in meta:
            raise ValueError(
                "SKILL.md frontmatter must contain name and description"
            )
        return Skill(
            name=meta["name"],
            description=meta["description"],
            body=body.strip(),
            path=path,
        )

        
