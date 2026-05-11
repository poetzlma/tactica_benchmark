"""Parse the LLM's delimited brief response.

Format:
  === composition ===
  {"mbt": 4, ...}
  === tactic:mbt ===
  <python>
  === tactic:infantry ===
  <python>
  ...
  === scratchpad ===
  <text>
"""

import json
import re


SECTION_RE = re.compile(r"^===\s*(.+?)\s*===\s*$", re.MULTILINE)

VALID_UTYPES = {"mbt", "infantry", "mortar", "medic", "drone"}


class ParseError(Exception):
    pass


def _strip_code_fence(s: str) -> str:
    """If the model wrapped a section in triple-backticks, peel them off."""
    t = s.strip()
    if t.startswith("```"):
        # remove opening fence (with optional language tag)
        first_nl = t.find("\n")
        if first_nl != -1:
            t = t[first_nl + 1:]
        if t.endswith("```"):
            t = t[:-3]
    return t.strip()


def parse_brief_response(text: str) -> dict:
    """Return dict with keys: composition (dict), tactics (dict[str,str]), scratchpad (str)."""
    if not text or not text.strip():
        raise ParseError("Empty LLM response")

    matches = list(SECTION_RE.finditer(text))
    if not matches:
        raise ParseError(
            "No `=== section ===` headers found in response. "
            "Model may have ignored the output format."
        )

    sections = {}
    for i, m in enumerate(matches):
        name = m.group(1).strip().lower()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[name] = text[start:end].strip()

    out = {"composition": None, "tactics": {}, "scratchpad": ""}

    if "composition" not in sections:
        raise ParseError("Missing `composition` section")
    comp_raw = _strip_code_fence(sections["composition"])
    try:
        comp = json.loads(comp_raw)
    except json.JSONDecodeError as e:
        raise ParseError(f"composition is not valid JSON: {e}: {comp_raw[:200]!r}")
    if not isinstance(comp, dict):
        raise ParseError("composition must be a JSON object")
    # Normalize keys to lowercase strings, values to ints
    norm = {}
    for k, v in comp.items():
        kk = str(k).strip().lower()
        try:
            vv = int(v)
        except (TypeError, ValueError):
            raise ParseError(f"composition[{kk!r}] is not an integer: {v!r}")
        norm[kk] = vv
    out["composition"] = norm

    for key, val in sections.items():
        if key.startswith("tactic:"):
            utype = key.split(":", 1)[1].strip().lower()
            out["tactics"][utype] = _strip_code_fence(val)

    out["scratchpad"] = sections.get("scratchpad", "").strip()
    return out
