from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_stages_metadata_endpoint():
    r = client.get("/api/stages")
    assert r.status_code == 200
    d = r.json()
    assert d["order"][0] == "lexer" and d["order"][-1] == "validation"
    assert set(d["stages"].keys()) == set(d["order"])


def test_session_lifecycle_stage_by_stage():
    r = client.post("/api/session", json={"source": "int main() { print(1); }"})
    assert r.status_code == 200
    sid = r.json()["sessionId"]
    r = client.post(f"/api/session/{sid}/run/lexer")
    assert r.status_code == 200 and r.json()["status"] == "completed"
    r = client.get(f"/api/session/{sid}/stage/lexer")
    assert r.status_code == 200 and r.json()["data"] is not None
    r = client.delete(f"/api/session/{sid}")
    assert r.status_code == 200
    r = client.get(f"/api/session/{sid}")
    assert r.status_code == 404


def test_out_of_order_stage_is_blocked_with_409():
    r = client.post("/api/session", json={"source": "int main() { print(1); }"})
    sid = r.json()["sessionId"]
    r = client.post(f"/api/session/{sid}/run/ir")
    assert r.status_code == 409
    assert r.json()["detail"]["blockedBy"] == "semantic"  # nearest unmet dependency


def test_compile_one_shot_success():
    src = ("function add(int a, int b) { return a + b; }\n"
          "int main() { int t = 0; for(int i = 0; i < 10; i++) { t = t + add(i, 2*4); } print(t); }")
    r = client.post("/api/compile", json={"source": src,
                    "options": {"seed": 1, "population": 8, "generations": 5, "step_limit": 50000}})
    assert r.status_code == 200
    d = r.json()
    assert d["failedAt"] is None
    assert d["report"]["validation"]["equivalent"] is True


def test_compile_one_shot_reports_honest_failure():
    r = client.post("/api/compile", json={"source": "int x = ;"})
    d = r.json()
    assert d["failedAt"] == "parser"
    assert d["stages"]["parser"]["status"] == "failed"


def test_invalid_options_rejected_with_422():
    r = client.post("/api/session", json={"source": "int main(){}", "options": {"population": 999}})
    assert r.status_code == 422
