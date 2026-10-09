import type { LexResponse } from "../types/compiler";

// All backend calls go through this single service. Components never
// call fetch() directly and never fabricate a result themselves.
const API_BASE = "/api";

export class CompilerApiError extends Error {}

export async function lexSource(source: string): Promise<LexResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/lex`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source }),
    });
  } catch (err) {
    throw new CompilerApiError(
      "Could not reach the EVO-COMP backend. Is the FastAPI server running on port 8000?"
    );
  }

  if (!res.ok) {
    throw new CompilerApiError(`Lexer request failed with status ${res.status}`);
  }

  return (await res.json()) as LexResponse;
}
