"""Typed AST nodes for EvoLang.

The parser constructs these nodes while recognising productions. The AST
stage (``compiler.ast.builder``) then finalises the tree: it assigns stable
preorder ids, parent links, depths and verifies structural invariants.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Tuple


@dataclass
class Span:
    """Source span. Lines/columns are 1-based; start/end are char offsets;
    first_token/last_token are indices into the *lexer* token list."""
    line: int = 0
    column: int = 0
    end_line: int = 0
    end_column: int = 0
    start: int = 0
    end: int = 0
    first_token: int = 0
    last_token: int = 0

    def to_dict(self) -> dict:
        return {
            "line": self.line, "column": self.column,
            "endLine": self.end_line, "endColumn": self.end_column,
            "start": self.start, "end": self.end,
            "firstToken": self.first_token, "lastToken": self.last_token,
        }


@dataclass
class Node:
    node_type: ClassVar[str] = "Node"
    # names of dataclass fields that hold children (Node or List[Node])
    child_fields: ClassVar[Tuple[str, ...]] = ()
    span: Span = field(default_factory=Span, repr=False)
    id: int = field(default=-1, repr=False)

    def children(self) -> List[Tuple[str, "Node"]]:
        out: List[Tuple[str, Node]] = []
        for name in self.child_fields:
            v = getattr(self, name)
            if v is None:
                continue
            if isinstance(v, list):
                for i, c in enumerate(v):
                    out.append((f"{name}[{i}]", c))
            else:
                out.append((name, v))
        return out

    def attributes(self) -> Dict[str, Any]:
        return {}

    def label(self) -> str:
        return self.node_type


@dataclass
class Program(Node):
    node_type = "Program"
    child_fields = ("body",)
    body: List[Node] = field(default_factory=list)


@dataclass
class Parameter(Node):
    node_type = "Parameter"
    name: str = ""
    type: str = ""

    def attributes(self):
        return {"name": self.name, "type": self.type}

    def label(self):
        return f"Parameter {self.type} {self.name}"


@dataclass
class FunctionDeclaration(Node):
    node_type = "FunctionDeclaration"
    child_fields = ("params", "body")
    name: str = ""
    return_type: Optional[str] = None  # None => inferred (``function`` form)
    params: List[Parameter] = field(default_factory=list)
    body: Optional["BlockStatement"] = None
    form: str = "typed"  # 'typed' (int f()) or 'function' (function f())

    def attributes(self):
        return {"name": self.name, "returnType": self.return_type or "(inferred)",
                "form": self.form, "arity": len(self.params)}

    def label(self):
        return f"FunctionDeclaration {self.name}"


@dataclass
class VariableDeclaration(Node):
    node_type = "VariableDeclaration"
    child_fields = ("init",)
    var_type: str = ""
    name: str = ""
    init: Optional[Node] = None

    def attributes(self):
        return {"type": self.var_type, "name": self.name,
                "initialized": self.init is not None}

    def label(self):
        return f"VariableDeclaration {self.var_type} {self.name}"


@dataclass
class Assignment(Node):
    node_type = "Assignment"
    child_fields = ("target", "value")
    target: Optional["Identifier"] = None
    operator: str = "="
    value: Optional[Node] = None

    def attributes(self):
        return {"operator": self.operator}

    def label(self):
        return f"Assignment ({self.operator})"


@dataclass
class IncDecStatement(Node):
    node_type = "IncDecStatement"
    child_fields = ("target",)
    target: Optional["Identifier"] = None
    operator: str = "++"

    def attributes(self):
        return {"operator": self.operator}

    def label(self):
        return f"IncDecStatement ({self.operator})"


@dataclass
class IfStatement(Node):
    node_type = "IfStatement"
    child_fields = ("condition", "then_branch", "else_branch")
    condition: Optional[Node] = None
    then_branch: Optional[Node] = None
    else_branch: Optional[Node] = None

    def attributes(self):
        return {"hasElse": self.else_branch is not None}


@dataclass
class WhileStatement(Node):
    node_type = "WhileStatement"
    child_fields = ("condition", "body")
    condition: Optional[Node] = None
    body: Optional[Node] = None


@dataclass
class ForStatement(Node):
    node_type = "ForStatement"
    child_fields = ("init", "condition", "update", "body")
    init: Optional[Node] = None
    condition: Optional[Node] = None
    update: Optional[Node] = None
    body: Optional[Node] = None


@dataclass
class ReturnStatement(Node):
    node_type = "ReturnStatement"
    child_fields = ("value",)
    value: Optional[Node] = None

    def attributes(self):
        return {"hasValue": self.value is not None}


@dataclass
class PrintStatement(Node):
    node_type = "PrintStatement"
    child_fields = ("value",)
    value: Optional[Node] = None


@dataclass
class ExpressionStatement(Node):
    node_type = "ExpressionStatement"
    child_fields = ("expression",)
    expression: Optional[Node] = None


@dataclass
class BlockStatement(Node):
    node_type = "BlockStatement"
    child_fields = ("statements",)
    statements: List[Node] = field(default_factory=list)

    def attributes(self):
        return {"statementCount": len(self.statements)}


@dataclass
class BinaryExpression(Node):
    node_type = "BinaryExpression"
    child_fields = ("left", "right")
    operator: str = ""
    left: Optional[Node] = None
    right: Optional[Node] = None

    def attributes(self):
        return {"operator": self.operator}

    def label(self):
        return f"BinaryExpression ({self.operator})"


@dataclass
class UnaryExpression(Node):
    node_type = "UnaryExpression"
    child_fields = ("operand",)
    operator: str = ""
    operand: Optional[Node] = None

    def attributes(self):
        return {"operator": self.operator}

    def label(self):
        return f"UnaryExpression ({self.operator})"


@dataclass
class Literal(Node):
    node_type = "Literal"
    lit_type: str = ""
    value: Any = None
    raw: str = ""

    def attributes(self):
        return {"type": self.lit_type, "value": self.value, "raw": self.raw}

    def label(self):
        return f"Literal {self.raw}"


@dataclass
class Identifier(Node):
    node_type = "Identifier"
    name: str = ""

    def attributes(self):
        return {"name": self.name}

    def label(self):
        return f"Identifier {self.name}"


@dataclass
class FunctionCall(Node):
    node_type = "FunctionCall"
    child_fields = ("args",)
    name: str = ""
    name_span: Span = field(default_factory=Span, repr=False)
    args: List[Node] = field(default_factory=list)

    def attributes(self):
        return {"callee": self.name, "argCount": len(self.args)}

    def label(self):
        return f"FunctionCall {self.name}"


ALL_NODE_TYPES = [
    "Program", "FunctionDeclaration", "Parameter", "VariableDeclaration",
    "Assignment", "IncDecStatement", "IfStatement", "WhileStatement",
    "ForStatement", "ReturnStatement", "PrintStatement", "ExpressionStatement",
    "BlockStatement", "BinaryExpression", "UnaryExpression", "Literal",
    "Identifier", "FunctionCall",
]


def walk(node: Node):
    """Preorder traversal."""
    yield node
    for _, c in node.children():
        yield from walk(c)
