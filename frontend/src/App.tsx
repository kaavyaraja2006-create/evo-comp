import { useEffect, useRef, useState } from "react";
import type { editor } from "monaco-editor";
import clsx from "clsx";
import { Header } from "./components/compiler/Header";
import { PipelineSidebar } from "./components/compiler/PipelineSidebar";
import { SourceEditor } from "./components/compiler/SourceEditor";
import { LexerWorkspace } from "./components/compiler/LexerWorkspace";
import { PipelineWorkspace } from "./components/pipeline/PipelineWorkspace";
import { useCompilation } from "./hooks/useCompilation";
import { usePipeline } from "./hooks/usePipeline";
import { EXAMPLE_PROGRAMS } from "./data/examples";
import type { Token } from "./types/compiler";

type Mode = "lexer-lab" | "pipeline";

function App() {
  const [mode, setMode] = useState<Mode>("lexer-lab");
  const { compilation, setSource, analyze, events, apiError } = useCompilation();
  const pipeline = usePipeline();
  const [selectedToken, setSelectedToken] = useState<Token | null>(null);
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const decorationsRef = useRef<editor.IEditorDecorationsCollection | null>(null);

  // Seed the editor with the first example so the lab isn't blank on load.
  useEffect(() => {
    setSource(EXAMPLE_PROGRAMS[0].source);
    pipeline.setSource(EXAMPLE_PROGRAMS[0].source);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const currentSource = mode === "pipeline" ? pipeline.state.source : compilation.source;
  const handleSourceChange = (src: string) => {
    if (mode === "pipeline") {
      pipeline.setSource(src);
      pipeline.reset();
    } else {
      setSource(src);
    }
  };

  const handleAnalyze = () => {
    setSelectedToken(null);
    analyze(compilation.source);
  };

 
  const highlightToken = (token: Token) => {
    const editorInstance = editorRef.current;
    if (!editorInstance) return;
    const model = editorInstance.getModel();
    if (!model) return;

    const startPos = model.getPositionAt(token.start);
    const endPos = model.getPositionAt(token.end);

    if (!decorationsRef.current) {
      decorationsRef.current = editorInstance.createDecorationsCollection();
    }
    decorationsRef.current.set([
      {
        range: {
          startLineNumber: startPos.lineNumber,
          startColumn: startPos.column,
          endLineNumber: endPos.lineNumber,
          endColumn: endPos.column,
        },
        options: {
          className: "evocomp-token-highlight",
          inlineClassName: "evocomp-token-highlight-inline",
        },
      },
    ]);
    editorInstance.revealLineInCenter(startPos.lineNumber);
  };

  const handleSelectToken = (token: Token) => {
    setSelectedToken(token);
    highlightToken(token);
  };

  const handleJumpToLocation = (line: number, column: number) => {
    const editorInstance = editorRef.current;
    if (!editorInstance) return;
    editorInstance.revealLineInCenter(line);
    editorInstance.setPosition({ lineNumber: line, column });
    editorInstance.focus();
  };

  return (
    <div className="flex h-screen flex-col bg-void">
      <Header />
      <div className="flex items-center gap-1 border-b border-border-soft bg-panel px-4 py-1.5">
        {(["lexer-lab", "pipeline"] as Mode[]).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={clsx(
              "rounded px-2.5 py-1 text-[11px] font-medium",
              mode === m ? "bg-cyan-dim/40 text-cyan" : "text-text-dim hover:text-text-secondary"
            )}
          >
            {m === "lexer-lab" ? "Lexer Lab (Phase 1)" : "Compiler Pipeline (Parser → Validation)"}
          </button>
        ))}
      </div>
      <div className="flex min-h-0 flex-1">
        {mode === "lexer-lab" ? (
          <PipelineSidebar mode="lexer-lab" lexerStatus={compilation.status} />
        ) : (
          <PipelineSidebar
            mode="pipeline"
            stages={pipeline.state.stages}
            selected={pipeline.state.selectedStage}
            runningStage={pipeline.state.runningStage}
            onSelect={pipeline.selectStage}
          />
        )}

        <main className="flex min-h-0 flex-1 flex-col lg:flex-row">
          <section className="flex min-h-[320px] flex-1 flex-col border-b border-border lg:border-b-0 lg:border-r">
            <SourceEditor
              source={currentSource}
              onSourceChange={handleSourceChange}
              onAnalyze={mode === "lexer-lab" ? handleAnalyze : () => pipeline.runAll()}
              isRunning={mode === "lexer-lab" ? compilation.status === "running" : pipeline.state.mode !== "idle"}
              editorRef={editorRef}
            />
          </section>

          <section className="flex min-h-0 flex-1 flex-col lg:max-w-[720px]">
            {mode === "lexer-lab" ? (
              <LexerWorkspace
                compilation={compilation}
                events={events}
                apiError={apiError}
                selectedToken={selectedToken}
                onSelectToken={handleSelectToken}
                onJumpToLocation={handleJumpToLocation}
              />
            ) : (
              <PipelineWorkspace pipeline={pipeline} />
            )}
          </section>
        </main>
      </div>
      <style>{`
        .evocomp-token-highlight-inline {
          background-color: rgba(226, 165, 61, 0.28);
          border-radius: 2px;
        }
      `}</style>
    </div>
  );
}

export default App;
