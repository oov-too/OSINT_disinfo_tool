"""A small TOML writer for the files the acquire layer writes (mapping.toml); reading is tomllib's (Python 3.11+, else tomli).
Supports what those files use: strings, integers, floats, booleans, lists of scalars, inline tables of scalars, tables and arrays of
tables, with comments carried as `# ...` lines through the special key "__comment__" of any table."""
import json, math, re

BARE = re.compile(r"^[A-Za-z0-9_-]+$")


def _key(k):
    return k if BARE.match(k) else json.dumps(k, ensure_ascii=False)


def _scalar(v):
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, int): return str(v)
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v): raise ValueError("TOML: nan and inf are not written")
        return repr(v)
    if isinstance(v, str): return json.dumps(v, ensure_ascii=False)     # a JSON string is a valid TOML basic string
    if v is None: raise ValueError("TOML has no null: drop the key")
    if isinstance(v, (list, tuple)): return "[" + ", ".join(_scalar(x) for x in v) + "]"
    if isinstance(v, dict): return "{" + ", ".join(f"{_key(k)} = {_scalar(x)}" for k, x in v.items() if x is not None) + "}"
    raise TypeError(f"TOML: cannot write {type(v).__name__}")


def _is_table(v): return isinstance(v, dict) and not getattr(v, "inline", False)
def _is_aot(v): return isinstance(v, list) and v and all(isinstance(x, dict) for x in v)


class Inline(dict):
    """A dict written as an inline table."""
    inline = True


def dumps(doc):
    out = []

    def table(d, path):
        com = d.get("__comment__")
        simple = [(k, v) for k, v in d.items() if k != "__comment__" and v is not None and not (_is_table(v) or _is_aot(v))]
        nested = [(k, v) for k, v in d.items() if k != "__comment__" and v is not None and (_is_table(v) or _is_aot(v))]
        if path:
            if out: out.append("")
            if com: out.extend("# " + c for c in str(com).split("\n"))
            out.append("[" + ".".join(_key(p) for p in path) + "]")
        elif com:
            out.extend("# " + c for c in str(com).split("\n"))
        for k, v in simple: out.append(f"{_key(k)} = {_scalar(v)}")
        for k, v in nested:
            if _is_aot(v):
                for item in v:
                    out.append("")
                    if item.get("__comment__"): out.extend("# " + c for c in str(item["__comment__"]).split("\n"))
                    out.append("[[" + ".".join(_key(p) for p in path + [k]) + "]]")
                    for k2, v2 in item.items():
                        if k2 == "__comment__" or v2 is None: continue
                        if _is_table(v2) or _is_aot(v2): raise ValueError("TOML writer: nested tables inside an array of tables are not supported")
                        out.append(f"{_key(k2)} = {_scalar(v2)}")
            else:
                table(v, path + [k])

    table(doc, [])
    return "\n".join(out).strip("\n") + "\n"


def loads(text):
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    return tomllib.loads(text)
