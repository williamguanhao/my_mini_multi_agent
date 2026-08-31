from dataclasses import dataclass
from typing import Any
import re
from pathlib import Path

from .skills import SkillRegistry

SKILL_INTENT_RE = re.compile(
    r'\A\s*\{"skill":\s*"([^"]+)"\}\s*(?:\n|\Z)'
)

@dataclass
class AgentContext:
    messages: list[Any]
    skill_intent: str | None = None


class ContextProvider:

    def __init__(
            self,
            session,
            retriever,
            skills_dir: Path | None = None,
            skill_registry: SkillRegistry | None = None,
            default_system_prompt: str | None = None,
            ):
        self.session = session
        self.retriever = retriever
        if default_system_prompt is not None:
            self._default_system_prompt = default_system_prompt
        else:
            self._default_system_prompt = None

        if skill_registry is not None:
            self.skills = skill_registry
        else:
            self.skills = SkillRegistry(skills_dir or Path("skills"))

        self._active_skill_name: str | None = None

    def build(
            self,
            user_input: str
        ) -> AgentContext:
        messages = self._retrieve_messages(user_input)
        self._maybe_activate_from_history(messages)

        system = self._build_system_message()

        if system is not None:
            messages = [system, *messages]

        return AgentContext(messages=messages)


    def _retrieve_messages(self, user_input: str) -> list[dict]:
        return self.retriever.retrieve(
            self.session,
            user_input
        )

    def _maybe_activate_from_history(self, messages: list[dict]) -> None:
        for m in reversed(messages):
            if m.get("role") == "assistant":
                content = m.get("content") or ""
                first_line = content.split("\n", 1)[0]
                match = SKILL_INTENT_RE.match(first_line)
                if match:
                    name = match.group(1)
                    if self.skills.get(name) is not None:
                        self._active_skill_name = name
                return

    def _build_system_message(self) -> dict | None:
        parts: list[str] = []

        if self._default_system_prompt is not None:
            parts.append(self._default_system_prompt)
        catalog = self.skills.catalog_text()
        if catalog:
            parts.append(catalog)
        if self._active_skill_name:
            print(f"<Skill {self._active_skill_name} loaded> ")
            skill = self.skills.get(self._active_skill_name)
            if skill is not None:
                parts.append(f"# Active skill: {skill.name}\n{skill.body}")

        if not parts:
            return None

        return {"role": "system", "content": "\n\n".join(parts)}
            