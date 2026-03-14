"""Утилиты: экранирование HTML."""
import html


def escape_html(text: str) -> str:
    """Экранировать <, >, & для безопасного отображения в Telegram HTML."""
    if not text:
        return ""
    return html.escape(str(text), quote=False)
