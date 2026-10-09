import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200


def test_lex_endpoint_valid_program():
    source = (
        "int main() {\n"
        "    int total = 0;\n"
        "    for(int i = 0; i < 10; i++) {\n"
        "        total = total + i;\n"
        "    }\n"
        "    print(total);\n"
        "}\n"
    )
    r = client.post("/api/lex", json={"source": source})
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["errors"] == []
    assert data["statistics"]["totalTokens"] == len(data["tokens"])
    assert data["statistics"]["totalTokens"] > 0
    # Real traceability: every non-EOF token's lexeme must match the raw slice.
    for tok in data["tokens"]:
        if tok["type"] == "EOF":
            continue
        assert source[tok["start"]:tok["end"]] == tok["lexeme"]


def test_lex_endpoint_error_program():
    r = client.post("/api/lex", json={"source": "int x = 10 @ 2;"})
    data = r.json()
    assert data["success"] is False
    assert len(data["errors"]) == 1
    assert data["errors"][0]["character"] == "@"
    assert data["errors"][0]["line"] == 1
    assert data["errors"][0]["column"] == 12


def test_lex_endpoint_stats_change_with_source():
    r1 = client.post("/api/lex", json={"source": "int x = 10;"})
    r2 = client.post("/api/lex", json={"source": "int x = 10;\nint y = 20;"})
    s1 = r1.json()["statistics"]["totalTokens"]
    s2 = r2.json()["statistics"]["totalTokens"]
    assert s2 > s1


def test_lex_endpoint_empty_source():
    r = client.post("/api/lex", json={"source": ""})
    data = r.json()
    assert data["success"] is True
    assert len(data["tokens"]) == 1
    assert data["tokens"][0]["type"] == "EOF"
