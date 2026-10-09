import { useState } from "react";
import Editor, { type Monaco, type OnMount } from "@monaco-editor/react";
import type { editor } from "monaco-editor";
import { registerEvoLang } from "../../monaco/evolang";
import { EXAMPLE_PROGRAMS } from "../../data/examples";

interface Props {
  source: string;
  onSourceChange: (value: string) => void;
  onAnalyze: () => void;
  isRunning: boolean;
  editorRef: React.MutableRefObject<editor.IStandaloneCodeEditor | null>;
}

export function SourceEditor({
  source,
  onSourceChange,
  onAnalyze,
  isRunning,
  editorRef,
}: Props) {
  const [exampleId, setExampleId] = useState<string>("");

  const handleMount: OnMount = (editorInstance) => {
    editorRef.current = editorInstance;
  };

  const handleBeforeMount = (monaco: Monaco) => {
    registerEvoLang(monaco);
  };

  const lines = source.length === 0 ? 0 : source.split("\n").length;
  const characters = source.length;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border-soft px-4 py-2.5">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-medium text-text-primary">Source program</h2>
          <span className="rounded border border-border bg-panel-raised px-1.5 py-0.5 font-mono text-[10px] text-text-secondary">
            EvoLang
          </span>
        </div>
        <div className="flex items-center gap-4 font-mono text-[11px] text-text-dim">
          <span>{lines} lines</span>
          <span>{characters} chars</span>
        </div>
      </div>

      <div className="flex items-center gap-2 border-b border-border-soft bg-panel px-4 py-2">
        <select
          className="rounded border border-border bg-panel-raised px-2 py-1 text-xs text-text-secondary outline-none focus-visible:outline-cyan"
          value={exampleId}
          onChange={(e) => {
            const id = e.target.value;
            setExampleId(id);
            const example = EXAMPLE_PROGRAMS.find((p) => p.id === id);
            if (example) onSourceChange(example.source);
          }}
        >
          <option value="" disabled>
            Load an example…
          </option>
          {EXAMPLE_PROGRAMS.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </select>

        <button
          className="rounded border border-border px-2 py-1 text-xs text-text-secondary hover:bg-panel-hover"
          onClick={() => navigator.clipboard.writeText(source)}
        >
          Copy
        </button>
        <button
          className="rounded border border-border px-2 py-1 text-xs text-text-secondary hover:bg-panel-hover"
          onClick={() => {
            setExampleId("");
            onSourceChange("");
          }}
        >
          Reset
        </button>

        <button
          onClick={onAnalyze}
          disabled={isRunning}
          className="ml-auto rounded bg-amber px-4 py-1.5 text-xs font-semibold text-void transition-colors hover:bg-amber/90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isRunning ? "Analyzing…" : "Lexical analyze"}
        </button>
      </div>

      <div className="min-h-0 flex-1">
        <Editor
          language="evolang"
          theme="evocomp-dark"
          value={source}
          onChange={(value) => onSourceChange(value ?? "")}
          beforeMount={handleBeforeMount}
          onMount={handleMount}
          options={{
            fontFamily: "IBM Plex Mono, monospace",
            fontSize: 13,
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            padding: { top: 12 },
            renderLineHighlight: "all",
            automaticLayout: true,
          }}
        />
      </div>
    </div>
  );
}

// Exported so the workspace can push a decoration for the selected token.
export type { Props as SourceEditorProps };
