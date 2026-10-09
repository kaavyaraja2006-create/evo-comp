# EvoLang Grammar

This is the exact grammar implemented by `backend/compiler/parser/parser.py`
(recursive descent, one method per production below). It is descriptive, not
aspirational — every rule listed here is parsed, and nothing not listed here
is accepted. Terminals are quoted or `ALL_CAPS` token classes from the Phase 1
lexer; `COMMENT` tokens never reach the parser (filtered beforehand, per the
Phase 1 lexer design).

```ebnf
program          = { functionDecl | statement } ;

functionDecl     = ( "function" | type ) IDENTIFIER "(" params ")" block ;
                    (* "function f(...)" -> return type inferred from its
                       return statements; "int f(...)" -> explicit return
                       type. Only allowed at the top level, never nested. *)
params           = [ param { "," param } ] ;
param            = type IDENTIFIER ;
type             = "int" | "float" | "string" | "bool" ;

block            = "{" { statement } "}" ;

statement        = block
                  | varDecl ";"
                  | simpleStatement ";"
                  | ifStmt
                  | whileStmt
                  | forStmt
                  | returnStmt
                  | printStmt ;

varDecl          = type IDENTIFIER [ "=" expression ] ;
simpleStatement  = assignment | incDec | call ;
assignment       = IDENTIFIER ( "=" | "+=" | "-=" | "*=" | "/=" ) expression ;
incDec           = IDENTIFIER ( "++" | "--" ) ;
call             = IDENTIFIER "(" [ expression { "," expression } ] ")" ;

ifStmt           = "if" "(" expression ")" statement [ "else" statement ] ;
whileStmt        = "while" "(" expression ")" statement ;
forStmt          = "for" "(" [ varDecl | simpleStatement ] ";"
                              [ expression ] ";"
                              [ simpleStatement ] ")" statement ;
returnStmt       = "return" [ expression ] ";" ;
printStmt        = "print" "(" expression ")" ";" ;

(* expression precedence, lowest to highest *)
expression       = logicalOr ;
logicalOr        = logicalAnd { "||" logicalAnd } ;
logicalAnd       = equality { "&&" equality } ;
equality         = relational { ( "==" | "!=" ) relational } ;
relational       = additive { ( "<" | "<=" | ">" | ">=" ) additive } ;
additive         = multiplicative { ( "+" | "-" ) multiplicative } ;
multiplicative   = unary { ( "*" | "/" | "%" ) unary } ;
unary            = ( "-" | "!" ) unary | callOrPrimary ;
callOrPrimary    = call | primary ;
primary          = INTEGER_LITERAL | FLOAT_LITERAL | STRING_LITERAL
                  | BOOLEAN_LITERAL | IDENTIFIER | "(" expression ")" ;
```

## Deliberately not in the grammar

Arrays (`a[i]`), member access (`a.b`), pointers, structs/classes, multiple
assignment targets, ternary `?:`, bitwise operators, `switch`, `do-while`,
`break`/`continue`, and string escape-interpolation are all **not** part of
EvoLang. The parser recognizes `[`, `]`, and `.` at statement/expression start
specifically to give a clear "not part of the supported grammar" error rather
than a generic "expected expression" one; elsewhere they produce the ordinary
"expected X, found Y" error.

## Semantic rules layered on top of the grammar

The grammar above is necessary but not sufficient for a valid program —
`compiler/semantic/analyzer.py` additionally enforces (see its diagnostic
codes E001–E016, W001–W004 in `docs/DIAGNOSTICS.md`):

- every identifier must be declared before use, in a visible scope;
- no duplicate declarations in the same scope;
- binary/unary operators must be applied to compatible types
  (`int`→`float` widens implicitly; nothing narrows implicitly);
- a function's argument count and types must match its parameters;
- `main` must exist implicitly reachable at the top level and take no
  parameters;
- a `function` (untyped) declaration that calls itself must be given an
  explicit return type, since the type cannot be inferred before the body
  has been analyzed.
