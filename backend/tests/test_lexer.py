import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lexer.lexer import Lexer
from lexer.token import TokenType
from models.compilation import compute_statistics


def token_pairs(tokens):
    return [(t.type, t.lexeme) for t in tokens]


def test_basic_declaration():
    result = Lexer("int total = 10;").tokenize()
    assert result.success
    assert token_pairs(result.tokens) == [
        (TokenType.KEYWORD, "int"),
        (TokenType.IDENTIFIER, "total"),
        (TokenType.OPERATOR, "="),
        (TokenType.INTEGER_LITERAL, "10"),
        (TokenType.DELIMITER, ";"),
        (TokenType.EOF, ""),
    ]


def test_acceptance_program():
    source = (
        "int main() {\n"
        "    int total = 0;\n"
        "\n"
        "    for(int i = 0; i < 10; i++) {\n"
        "        total = total + i;\n"
        "    }\n"
        "\n"
        "    print(total);\n"
        "}\n"
    )
    result = Lexer(source).tokenize()
    assert result.success
    assert len(result.errors) == 0
    # There must be a real, non-fabricated identifier 'total' with real positions.
    total_tokens = [t for t in result.tokens if t.lexeme == "total"]
    assert len(total_tokens) == 4
    for t in total_tokens:
        assert source[t.start:t.end] == "total"
    # Changing 10 -> 100 must change the token stream / statistics.
    result2 = Lexer(source.replace("10", "100")).tokenize()
    stats1 = compute_statistics(result.tokens)
    stats2 = compute_statistics(result2.tokens)
    tok1 = [t.lexeme for t in result.tokens]
    tok2 = [t.lexeme for t in result2.tokens]
    assert tok1 != tok2
    assert "100" in tok2


def test_unknown_character_reports_error():
    result = Lexer("int x = 10 @ 2;").tokenize()
    assert not result.success
    assert len(result.errors) == 1
    err = result.errors[0]
    assert err.character == "@"
    assert err.message == "Unexpected character '@'"
    assert err.line == 1
    # column should point at the '@' (1-based)
    assert result.errors[0].column == 12


def test_unterminated_string():
    result = Lexer('string name = "Kaavya;').tokenize()
    assert not result.success
    assert any("Unterminated string" in e.message for e in result.errors)


def test_empty_source_produces_only_eof():
    result = Lexer("").tokenize()
    assert result.success
    assert len(result.tokens) == 1
    assert result.tokens[0].type == TokenType.EOF


def test_multiline_line_column_tracking():
    source = "int a = 1;\nint b = 2;\n"
    result = Lexer(source).tokenize()
    b_token = next(t for t in result.tokens if t.lexeme == "b")
    assert b_token.line == 2
    assert b_token.column == 5


def test_float_literal():
    result = Lexer("float price = 99.50;").tokenize()
    float_tok = next(t for t in result.tokens if t.type == TokenType.FLOAT_LITERAL)
    assert float_tok.lexeme == "99.50"
    assert float_tok.value == 99.50


def test_multichar_operators():
    result = Lexer("if(a >= 10 && b != 5) {\n}\n").tokenize()
    ops = [t.lexeme for t in result.tokens if t.type == TokenType.OPERATOR]
    assert ops == [">=", "&&", "!="]


def test_comments_line_and_block():
    source = "int a = 1; // trailing comment\n/* block\ncomment */\nint b = 2;"
    result = Lexer(source).tokenize()
    comments = [t for t in result.tokens if t.type == TokenType.COMMENT]
    assert len(comments) == 2
    assert comments[0].lexeme == "// trailing comment"
    assert comments[1].lexeme.startswith("/* block")


def test_boolean_literals_classified_separately_from_keywords():
    result = Lexer("bool flag = true;").tokenize()
    bool_kw = next(t for t in result.tokens if t.lexeme == "bool")
    bool_lit = next(t for t in result.tokens if t.lexeme == "true")
    assert bool_kw.type == TokenType.KEYWORD
    assert bool_lit.type == TokenType.BOOLEAN_LITERAL
    assert bool_lit.value is True


def test_string_literal_value_strips_quotes():
    result = Lexer('print("hello");').tokenize()
    s = next(t for t in result.tokens if t.type == TokenType.STRING_LITERAL)
    assert s.value == "hello"
    assert s.lexeme == '"hello"'


def test_statistics_are_dynamic_not_hardcoded():
    r1 = Lexer("int x = 1;").tokenize()
    r2 = Lexer("int x = 1;\nint y = 2;\nint z = 3;").tokenize()
    s1 = compute_statistics(r1.tokens)
    s2 = compute_statistics(r2.tokens)
    assert s2.totalTokens > s1.totalTokens
    assert s2.identifiers == 3
    assert s1.identifiers == 1


def test_source_positions_are_exact_offsets():
    source = "int total = 10;"
    result = Lexer(source).tokenize()
    for t in result.tokens:
        if t.type == TokenType.EOF:
            continue
        assert source[t.start:t.end] == t.lexeme
