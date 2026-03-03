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
        safe_kwargs = {
            k: v.replace("{", "{{").replace("}", "}}") if isinstance(v, str) else v
            for k, v in kwargs.items()
        }
        system = self.system_prompt
        if self.output_schema:
            import json
            schema_str = json.dumps(self.output_schema, indent=2)
            system += f"\n\n## Output Schema\nReturn valid JSON matching this schema exactly:\n```json\n{schema_str}\n```"
        return system, self.user_prompt_template.format(**safe_kwargs)
