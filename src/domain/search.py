"""Structured inventory search — pure query parsing functions (HT-020)."""
import re
from dataclasses import dataclass, field


# Operators handled by this implementation.
# parent: and network: are intentionally omitted — those features are not shipped.
# Unknown operators fall through to free_text (graceful degradation).
_KNOWN_OPERATORS = frozenset({"type", "tag", "ip", "os", "location", "service"})

# Tokenizer: matches op:"quoted value" OR op:unquoted OR anything-else
_TOKENIZER_RE = re.compile(r'[a-zA-Z_\-]+:"[^"]*"|[a-zA-Z_\-]+:\S+|\S+')


@dataclass
class ParsedQuery:
    """Structured representation of an inventory search query.

    All list fields accumulate multiple values for the same operator (OR within
    operator, AND across operators). free_text is the remainder after operator
    extraction and is matched against name, IP, OS, notes, and location name.
    """
    free_text: str = ""
    types: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    ip_patterns: list[str] = field(default_factory=list)
    os_patterns: list[str] = field(default_factory=list)
    location_patterns: list[str] = field(default_factory=list)
    service_patterns: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        """Return True when the query would match all devices (no filtering)."""
        return (
            not self.free_text
            and not self.types
            and not self.tags
            and not self.ip_patterns
            and not self.os_patterns
            and not self.location_patterns
            and not self.service_patterns
        )


def parse_query(raw: str) -> ParsedQuery:
    """Tokenise a structured query string into a ParsedQuery.

    Tokenisation rules:
    1. Split by whitespace (quoted values not specially handled in v1).
    2. Each token matching `operator:value` where operator is known is extracted.
    3. Tokens with an unknown operator prefix fall through to free_text.
    4. Tokens with no `:` go to free_text.
    5. Empty token values (e.g. `type:`) are ignored.
    """
    result = ParsedQuery()
    free_parts: list[str] = []

    for token in _TOKENIZER_RE.findall(raw.strip()):
        if ":" in token:
            op, _, val = token.partition(":")
            op_lower = op.lower()
            # Strip surrounding quotes from value
            if val.startswith('"') and val.endswith('"') and len(val) >= 2:
                val = val[1:-1]
            if op_lower in _KNOWN_OPERATORS:
                if val:
                    if op_lower == "type":
                        result.types.append(val)
                    elif op_lower == "tag":
                        result.tags.append(val)
                    elif op_lower == "ip":
                        result.ip_patterns.append(val)
                    elif op_lower == "os":
                        result.os_patterns.append(val)
                    elif op_lower == "location":
                        result.location_patterns.append(val)
                    elif op_lower == "service":
                        result.service_patterns.append(val)
                # else: known operator with empty value — silently skip
            else:
                free_parts.append(token)  # unknown operator → free text
        else:
            free_parts.append(token)

    result.free_text = " ".join(free_parts)
    return result


def to_sql_like(pattern: str) -> str:
    """Convert a glob pattern to a SQL LIKE-compatible string.

    Escapes SQL meta-characters (% and _) in user input before replacing
    glob * with %. This prevents accidental wildcard injection.

    Example: "192.168._*" → "192.168.\\_%" (backslash escapes _ and * → %)
    """
    escaped = pattern.replace("%", r"\%").replace("_", r"\_")
    return escaped.replace("*", "%")
