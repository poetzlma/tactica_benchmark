"""AST-whitelisted sandbox for loading unit tactic code.

Loaded source must define `class Tactic` with `__init__(self)` and
`tick(self, me, world)`. Imports, dunder attribute access, eval/exec/open/etc.
are rejected at parse time. Builtins are replaced with a curated subset.
"""

import ast


ALLOWED_NODES = {
    ast.Module,
    ast.ClassDef, ast.FunctionDef,
    ast.Return, ast.If, ast.For, ast.While, ast.Break, ast.Continue, ast.Pass,
    ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Expr,
    ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.LShift, ast.RShift, ast.BitOr, ast.BitAnd, ast.BitXor,
    ast.USub, ast.UAdd, ast.Not, ast.Invert,
    ast.And, ast.Or,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.Is, ast.IsNot, ast.In, ast.NotIn,
    ast.Call, ast.Attribute, ast.Subscript, ast.Name, ast.Constant,
    ast.List, ast.Tuple, ast.Dict, ast.Set,
    ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.comprehension,
    ast.Slice, ast.Starred, ast.keyword, ast.arguments, ast.arg,
    ast.Lambda, ast.IfExp,
    ast.Load, ast.Store, ast.Del,
    ast.Try, ast.ExceptHandler, ast.Raise,
    ast.JoinedStr, ast.FormattedValue,
}


FORBIDDEN_NAMES = {
    "eval", "exec", "compile", "open", "input", "__import__",
    "globals", "locals", "vars", "dir",
    "getattr", "setattr", "delattr",
    "breakpoint", "help", "exit", "quit",
    "memoryview", "object", "super",
    "classmethod", "staticmethod", "property",
}


_SAFE_BUILTINS = {
    # Required for `class` statements to compile/execute. The validator
    # forbids user code from *referencing* dunders by name, so exposing
    # this in the builtins dict is safe.
    "__build_class__": __build_class__,
    "abs": abs, "min": min, "max": max, "sum": sum, "len": len,
    "range": range, "enumerate": enumerate, "zip": zip,
    "map": map, "filter": filter,
    "sorted": sorted, "reversed": reversed,
    "list": list, "tuple": tuple, "dict": dict, "set": set,
    "frozenset": frozenset, "str": str, "int": int, "float": float,
    "bool": bool, "round": round, "pow": pow, "divmod": divmod,
    "any": any, "all": all, "isinstance": isinstance, "type": type,
    "hasattr": hasattr,
    "print": lambda *a, **kw: None,
    "None": None, "True": True, "False": False,
}


class SandboxError(Exception):
    pass


class _Validator(ast.NodeVisitor):
    def __init__(self):
        self.errors = []

    def generic_visit(self, node):
        if type(node) not in ALLOWED_NODES:
            self.errors.append(
                f"Disallowed syntax: {type(node).__name__} "
                f"at line {getattr(node, 'lineno', '?')}"
            )
            return
        super().generic_visit(node)

    def visit_Import(self, node):
        self.errors.append(f"Imports are not allowed (line {node.lineno})")

    def visit_ImportFrom(self, node):
        self.errors.append(f"Imports are not allowed (line {node.lineno})")

    def visit_Attribute(self, node):
        if isinstance(node.attr, str) and node.attr.startswith("_"):
            self.errors.append(
                f"Underscore attribute access '{node.attr}' "
                f"is not allowed (line {node.lineno})"
            )
        self.generic_visit(node)

    def visit_Name(self, node):
        if node.id in FORBIDDEN_NAMES:
            self.errors.append(
                f"Use of '{node.id}' is not allowed (line {node.lineno})"
            )
        if node.id.startswith("__") and node.id.endswith("__"):
            self.errors.append(
                f"Dunder name '{node.id}' is not allowed (line {node.lineno})"
            )
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        if (
            node.name.startswith("__")
            and node.name.endswith("__")
            and node.name != "__init__"
        ):
            self.errors.append(
                f"Dunder method '{node.name}' is not allowed (line {node.lineno})"
            )
        self.generic_visit(node)


def load_tactic(source: str, name: str = "<tactic>"):
    """Parse + validate + exec the source. Return the `Tactic` class."""
    try:
        tree = ast.parse(source, filename=name)
    except SyntaxError as e:
        raise SandboxError(f"Syntax error in {name}: {e}")

    validator = _Validator()
    validator.visit(tree)
    if validator.errors:
        raise SandboxError(
            f"Tactic {name} rejected: " + "; ".join(validator.errors)
        )

    has_tactic = any(
        isinstance(node, ast.ClassDef) and node.name == "Tactic"
        for node in tree.body
    )
    if not has_tactic:
        raise SandboxError(f"Tactic {name} must define `class Tactic`")

    namespace = {
        "__builtins__": _SAFE_BUILTINS,
        # Python's class-body machinery looks these up implicitly when
        # building a class. User code can't reference them because the
        # validator rejects dunder names in user source.
        "__name__": name,
    }
    try:
        exec(compile(tree, name, "exec"), namespace)
    except Exception as e:
        raise SandboxError(f"Tactic {name} failed at load time: {e!r}")

    Tactic = namespace.get("Tactic")
    if Tactic is None:
        raise SandboxError(f"Tactic {name} did not produce a `Tactic` class")
    return Tactic
