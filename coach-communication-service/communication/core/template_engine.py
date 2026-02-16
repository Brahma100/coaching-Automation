from __future__ import annotations

from jinja2 import Environment, StrictUndefined


def _telegram_format(text: str) -> str:
    return text


def _whatsapp_format(text: str) -> str:
    return text.replace("\n", "\\n")


class TemplateEngine:
    def __init__(self) -> None:
        self.env = Environment(undefined=StrictUndefined, autoescape=False)
        self.formatters = {
            "telegram": _telegram_format,
            "whatsapp": _whatsapp_format,
        }

    def render(self, body: str, context: dict[str, object], provider: str) -> str:
        tpl = self.env.from_string(body)
        rendered = tpl.render(**context)
        return self.formatters.get(provider, lambda x: x)(rendered)

    def preview(self, body: str, sample: dict[str, object], provider: str) -> str:
        return self.render(body, sample, provider)
