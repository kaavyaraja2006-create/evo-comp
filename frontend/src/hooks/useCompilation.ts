import { useCallback, useRef, useState } from "react";
import { lexSource, CompilerApiError } from "../services/compilerApi";
import type { CompilerEvent, LexicalCompilation } from "../types/compiler";

const initialState: LexicalCompilation = {
  source: "",
  result: null,
  status: "idle",
  requestedAt: null,
  completedAt: null,
};

function timestamp(): string {
  return new Date().toLocaleTimeString("en-US", { hour12: false });
}

export function useCompilation() {
  const [compilation, setCompilation] = useState<LexicalCompilation>(initialState);
  const [events, setEvents] = useState<CompilerEvent[]>([]);
  const [apiError, setApiError] = useState<string | null>(null);
  const eventIdRef = useRef(0);

  const logEvent = useCallback((message: string) => {
    eventIdRef.current += 1;
    setEvents((prev) => [
      ...prev,
      { id: eventIdRef.current, timestamp: timestamp(), message },
    ]);
  }, []);

  const setSource = useCallback((source: string) => {
    setCompilation((prev) => ({ ...prev, source }));
  }, []);

  const resetEvents = useCallback(() => setEvents([]), []);

  const analyze = useCallback(
    async (source: string) => {
      setApiError(null);
      resetEvents();
      const requestedAt = performance.now();
      setCompilation((prev) => ({
        ...prev,
        source,
        status: "running",
        requestedAt,
        completedAt: null,
      }));

      logEvent("Source received");
      logEvent(`Lexer initialized (${source.length} characters)`);
      logEvent("Scanning source");

      try {
        const result = await lexSource(source);
        const completedAt = performance.now();

        if (result.success) {
          logEvent(`${result.tokens.length} tokens generated`);
          logEvent("Calculating statistics");
          logEvent("Lexical analysis completed");
        } else {
          logEvent(`${result.errors.length} lexical error(s) detected`);
          logEvent("Lexical analysis failed");
        }

        setCompilation((prev) => ({
          ...prev,
          source,
          result,
          status: result.success ? "success" : "failed",
          completedAt,
        }));
      } catch (err) {
        const message =
          err instanceof CompilerApiError
            ? err.message
            : "Unexpected error while contacting the lexer backend.";
        setApiError(message);
        logEvent(`Backend error: ${message}`);
        setCompilation((prev) => ({
          ...prev,
          source,
          status: "failed",
          completedAt: performance.now(),
        }));
      }
    },
    [logEvent, resetEvents]
  );

  return { compilation, setSource, analyze, events, apiError };
}
