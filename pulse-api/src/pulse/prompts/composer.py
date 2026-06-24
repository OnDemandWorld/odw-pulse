"""Prompt composer for assembling LLM prompts.

Uses Jinja2-style string formatting (via str.format for now) to compose
system and user prompts from templates and context dictionaries.
"""

from __future__ import annotations

from typing import Any


class PromptComposer:
    """Composes structured prompts from templates and context.

    Takes system and user prompt templates and fills in context variables
    to produce the final prompts sent to the LLM provider.
    """

    def compose(
        self,
        system_template: str,
        user_template: str,
        context: dict[str, Any],
    ) -> dict[str, str]:
        """Compose a system prompt and user prompt from templates and context.

        Uses str.format for variable substitution. Templates should use
        {variable_name} syntax for placeholders.

        Args:
            system_template: System prompt template with {placeholders}
            user_template: User prompt template with {placeholders}
            context: Dictionary of values to substitute into templates

        Returns:
            Dictionary with 'system' and 'user' keys containing the
            rendered prompt strings
        """
        system_prompt = system_template.format(**context)
        user_prompt = user_template.format(**context)
        return {
            "system": system_prompt,
            "user": user_prompt,
        }

    def compose_messages(
        self,
        system_template: str,
        user_template: str,
        context: dict[str, Any],
    ) -> list[dict[str, str]]:
        """Compose prompt as a messages list for chat-style APIs.

        Args:
            system_template: System prompt template with {placeholders}
            user_template: User prompt template with {placeholders}
            context: Dictionary of values to substitute into templates

        Returns:
            List of message dicts with 'role' and 'content' keys
        """
        composed = self.compose(system_template, user_template, context)
        return [
            {"role": "system", "content": composed["system"]},
            {"role": "user", "content": composed["user"]},
        ]
