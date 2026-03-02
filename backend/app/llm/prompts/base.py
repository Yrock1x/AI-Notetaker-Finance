from dataclasses import dataclass, field


@dataclass
class BasePromptTemplate:
    name: str
    system_prompt: str
    user_prompt_template: str
    output_schema: dict = field(default_factory=dict)
    version: str = "v1"

    def render(self, **kwargs) -> tuple[str, str]:
        """Render the prompt with the given variables. Returns (system_prompt, user_prompt)."""
        return self.system_prompt, self.user_prompt_template.format(**kwargs)
