# Diagnostic Codes

Produced by `backend/compiler/semantic/analyzer.py`. Errors (`E***`) make a
program invalid and stop the pipeline at the Semantic Analysis stage.
Warnings (`W***`) do not.

| Code | Severity | Meaning |
|------|----------|---------|
| E000 | error | Internal: an AST node type reached semantic analysis with no handler (should be unreachable for anything the parser can produce; indicates a compiler bug, not a user error) |
| E001 | error | Undeclared identifier |
| E002 | error | Duplicate declaration in the same scope |
| E003 | error | Type mismatch on assignment or initialization |
| E004 | error | Operator applied to incompatible operand type(s) |
| E005 | error | Assignment target is a function, not a variable |
| E006 | error | Call to something that is not a function (undeclared, or a variable) |
| E007 | error | Wrong number of arguments in a call |
| E008 | error | Wrong argument type in a call |
| E009 | error | Invalid or inconsistent `return` (missing value, extra value, type mismatch, outside a function) |
| E010 | error | Condition of `if`/`while`/`for` is not `bool` |
| E011 | error | Division or modulo by the constant `0` |
| E012 | error | A void call's non-result used as a value |
| E013 | error | Integer literal out of 32-bit range |
| E014 | error | `main` declared with parameters |
| E015 | error | Self-recursive `function` (untyped) declaration with no explicit return type to fall back on |
| E016 | error | `++`/`--` applied to a non-numeric variable |
| W001 | warning | Variable declared but never read |
| W002 | warning | Unreachable code after `return` |
| W003 | warning | Non-void function may fall off its end without returning |
| W004 | warning | Local declaration shadows an outer one |
