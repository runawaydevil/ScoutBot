"""HTML sanitization for Telegram messages"""

import re
from html import escape, unescape


def sanitize_html_for_telegram(text: str) -> str:
    """
    Sanitize HTML text for Telegram's HTML parse mode.

    Telegram supports only these tags: <b>, <i>, <u>, <s>, <code>, <pre>, <a>
    Removes:
    - HTML comments (<!-- -->)
    - Unsupported HTML tags
    - Escapes HTML entities when needed

    Args:
        text: HTML text to sanitize

    Returns:
        Sanitized HTML text safe for Telegram
    """
    if not text:
        return ""

    # Step 1: Remove HTML comments FIRST (most common issue: <!-- -->)
    # This regex matches <!-- ... --> including multi-line comments
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    # Step 2: Remove script and style tags and their content completely
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Step 3: Replace equivalent tags with Telegram-supported ones
    # Telegram supports: <b>, <i>, <u>, <s>, <code>, <pre>, <a href="url">
    # Equivalents: <strong>, <em>, <ins>, <strike>, <del>
    text = re.sub(
        r"</?strong>", lambda m: m.group(0).replace("strong", "b"), text, flags=re.IGNORECASE
    )
    text = re.sub(r"</?em>", lambda m: m.group(0).replace("em", "i"), text, flags=re.IGNORECASE)
    text = re.sub(r"</?ins>", lambda m: m.group(0).replace("ins", "u"), text, flags=re.IGNORECASE)
    text = re.sub(
        r"</?strike>", lambda m: m.group(0).replace("strike", "s"), text, flags=re.IGNORECASE
    )
    text = re.sub(r"</?del>", lambda m: m.group(0).replace("del", "s"), text, flags=re.IGNORECASE)

    # Step 4: Clean up <a> tags - keep only href attribute
    def clean_a_tag(match):
        href_match = re.search(r'href\s*=\s*["\']([^"\']+)["\']', match.group(0), re.IGNORECASE)
        if href_match:
            href = href_match.group(1)
            # Escape special characters in href but keep it valid
            href = href.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            return f'<a href="{href}">'
        return "<a>"

    text = re.sub(r"<a[^>]*>", clean_a_tag, text, flags=re.IGNORECASE)

    # Step 4.5: Remove any orphaned </a> tags that don't have matching opening tags
    # This is a common issue with malformed HTML from Reddit
    text = _remove_orphaned_closing_tags(text, "a")

    # Step 5: Remove attributes from other allowed tags (keep only tag name)
    # Allowed tags: b, i, u, s, code, pre
    for tag in ["b", "i", "u", "s", "code", "pre"]:
        text = re.sub(rf"<{tag}[^>]*>", f"<{tag}>", text, flags=re.IGNORECASE)
        text = re.sub(rf"</{tag}[^>]*>", f"</{tag}>", text, flags=re.IGNORECASE)

    # Step 6: Remove all other HTML tags (not in allowed list)
    # Allowed tags pattern: <b>, </b>, <i>, </i>, <u>, </u>, <s>, </s>, <code>, </code>, <pre>, </pre>, <a href="...">
    # First, protect allowed tags temporarily
    tag_placeholders = {}
    placeholder_counter = 0

    def protect_allowed_tag(match):
        nonlocal placeholder_counter
        tag_content = match.group(0)
        # Check if it's an allowed tag
        if re.match(r"</?(?:b|i|u|s|code|pre|a)", tag_content, re.IGNORECASE):
            placeholder = f"__TAG_PLACEHOLDER_{placeholder_counter}__"
            tag_placeholders[placeholder] = tag_content
            placeholder_counter += 1
            return placeholder
        return ""  # Remove unsupported tags

    # Replace all tags with placeholders or remove them
    text = re.sub(r"<[^>]+>", protect_allowed_tag, text)

    # Step 7: Escape HTML entities in text content (between tags)
    # First unescape to avoid double escaping
    try:
        text = unescape(text)
    except Exception:
        pass

    # Now escape the text content
    text = escape(text)

    # Step 8: Restore protected tags
    for placeholder, tag_content in tag_placeholders.items():
        text = text.replace(placeholder, tag_content)

    # Step 9: Balance HTML tags - ensure all tags are properly closed
    text = _balance_html_tags(text)

    # Step 10: Final cleanup - remove any stray problematic characters
    # Clean up whitespace but preserve intentional line breaks
    text = re.sub(r"[ \t]+", " ", text)  # Multiple spaces to single space
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)  # Multiple newlines to double newline

    return text.strip()


def _remove_orphaned_closing_tags(text: str, tag_name: str) -> str:
    """
    Remove orphaned closing tags that don't have matching opening tags.

    Args:
        text: HTML text
        tag_name: Tag name to check (e.g., 'a', 'i', 'b')

    Returns:
        HTML text with orphaned closing tags removed
    """
    if not text:
        return ""

    # Count opening and closing tags
    opening_pattern = rf"<{tag_name}(?:\s[^>]*)?>|<{tag_name}>"
    closing_pattern = rf"</{tag_name}>"

    # Find all tags with their positions
    tags = []
    for match in re.finditer(opening_pattern, text, re.IGNORECASE):
        tags.append(("open", match.start(), match.end()))
    for match in re.finditer(closing_pattern, text, re.IGNORECASE):
        tags.append(("close", match.start(), match.end()))

    # Sort by position
    tags.sort(key=lambda x: x[1])

    # Track which closing tags are orphaned
    orphaned_positions = []
    open_count = 0

    for tag_type, start, end in tags:
        if tag_type == "open":
            open_count += 1
        else:  # close
            if open_count > 0:
                open_count -= 1
            else:
                # This is an orphaned closing tag
                orphaned_positions.append((start, end))

    # Remove orphaned tags from text (in reverse order to maintain positions)
    for start, end in reversed(orphaned_positions):
        text = text[:start] + text[end:]

    return text


def _balance_html_tags(text: str) -> str:
    """
    Ensure all HTML tags are properly balanced (opened and closed).
    Closes unclosed tags or removes unmatched closing tags.

    Args:
        text: HTML text to balance

    Returns:
        HTML text with balanced tags
    """
    if not text:
        return ""

    # Tags that need to be paired (opened and closed)
    paired_tags = {"b", "i", "u", "s", "code", "pre"}
    # Tags that can be self-closing
    self_closing_tags = {"a"}

    # Find all tags in the text
    tag_pattern = r"<(/?)([a-zA-Z]+)(?:\s[^>]*)?>"
    tags = []

    for match in re.finditer(tag_pattern, text, re.IGNORECASE):
        is_closing = bool(match.group(1))
        tag_name = match.group(2).lower()
        start_pos = match.start()
        end_pos = match.end()

        if tag_name in paired_tags or tag_name in self_closing_tags:
            tags.append(
                {
                    "name": tag_name,
                    "is_closing": is_closing,
                    "start": start_pos,
                    "end": end_pos,
                    "full_match": match.group(0),
                }
            )

    # If no tags found, return as-is
    if not tags:
        return text

    # Build result by processing tags in order
    tag_stack = []
    result_parts = []
    last_pos = 0

    for tag_info in tags:
        # Add text before this tag
        result_parts.append(text[last_pos : tag_info["start"]])

        tag_name = tag_info["name"]
        is_closing = tag_info["is_closing"]

        if tag_name in self_closing_tags:
            # Self-closing tags (like <a>) - just include them
            result_parts.append(tag_info["full_match"])
        elif is_closing:
            # Closing tag - find matching opening tag in stack
            found_match = False
            # Search from top of stack (most recent) backwards
            for i in range(len(tag_stack) - 1, -1, -1):
                if tag_stack[i]["name"] == tag_name:
                    # Found matching opening tag - remove it from stack
                    # Close any tags that were opened after this one
                    while len(tag_stack) > i + 1:
                        closed_tag = tag_stack.pop()
                        result_parts.append(f'</{closed_tag["name"]}>')
                    # Remove the matched tag from stack
                    tag_stack.pop()
                    # Add the closing tag
                    result_parts.append(tag_info["full_match"])
                    found_match = True
                    break

            if not found_match:
                # Unmatched closing tag - remove it (don't add to result)
                pass
        else:
            # Opening tag - add to stack
            tag_stack.append(tag_info)
            result_parts.append(tag_info["full_match"])

        last_pos = tag_info["end"]

    # Add remaining text after last tag
    result_parts.append(text[last_pos:])

    # Close any remaining open tags
    while tag_stack:
        closed_tag = tag_stack.pop()
        result_parts.append(f'</{closed_tag["name"]}>')

    return "".join(result_parts)


def strip_html_tags(text: str) -> str:
    """
    Remove all HTML tags from text, returning plain text.
    Used as fallback when HTML sanitization fails.

    Args:
        text: HTML text

    Returns:
        Plain text without HTML tags
    """
    if not text:
        return ""

    # Remove HTML comments
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    # Remove all HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Unescape HTML entities
    try:
        text = unescape(text)
    except Exception:
        pass

    # Clean up whitespace
    text = re.sub(r"\s+", " ", text)
    text = text.strip()

    return text
