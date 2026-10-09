import clsx from "clsx";
import type { StageName, StageStateDTO } from "../../types/pipeline";
import { STAGE_ORDER } from "../../types/pipeline";
import { STAGE_LABELS } from "../pipeline/stageMeta";

type StageStatus = "done" | "running" | "waiting" | "not-implemented" | "failed";

interface Stage {
  label: string;
  status: StageStatus;
}

const STAGES_BASE: Stage[] = [
  { label: "Source", status: "done" },
];

const STATUS_GLYPH: Record<StageStatus, string> = {
  done: "✓",
  running: "◌",
  waiting: "○",
  "not-implemented": "—",
  failed: "✕",
};

const STATUS_COLOR: Record<StageStatus, string> = {
  done: "text-green",
  running: "text-amber",
  waiting: "text-text-dim",
  "not-implemented": "text-text-dim",
  failed: "text-red",
};

interface LexerLabProps {
  mode?: "lexer-lab";
  lexerStatus: "idle" | "running" | "success" | "failed";
}

interface PipelineProps {
  mode: "pipeline";
  stages: Record<StageName, StageStateDTO>;
  selected: StageName;
  runningStage: StageName | null;
  onSelect: (stage: StageName) => void;
}

type Props = LexerLabProps | PipelineProps;

function toStatus(dto: StageStateDTO, running: boolean): StageStatus {
  if (running) return "running";
  if (dto.status === "completed") return "done";
  if (dto.status === "failed") return "failed";
  return "waiting";
}

export function PipelineSidebar(props: Props) {
  const isPipeline = props.mode === "pipeline";

  const stages: (Stage & { key?: StageName })[] = isPipeline
    ? [
        ...STAGES_BASE,
        ...STAGE_ORDER.map((s) => ({
          key: s,
          label: STAGE_LABELS[s],
          status: toStatus(props.stages[s], props.runningStage === s),
        })),
      ]
    : [
        ...STAGES_BASE,
        {
          label: "Lexer",
          status:
            props.lexerStatus === "running"
              ? "running"
              : props.lexerStatus === "success"
              ? "done"
              : props.lexerStatus === "failed"
              ? "failed"
              : "waiting",
        },
        ...STAGE_ORDER.filter((s) => s !== "lexer").map((s) => ({
          label: STAGE_LABELS[s],
          status: "not-implemented" as StageStatus,
        })),
      ];

  return (
    <aside className="flex h-full w-56 shrink-0 flex-col border-r border-border bg-panel">
      <div className="border-b border-border-soft px-4 py-3">
        <p className="text-[11px] font-medium tracking-wide text-text-dim">
          Compiler pipeline
        </p>
      </div>
      <ol className="flex-1 overflow-y-auto px-2 py-2 font-mono text-[13px]">
        {stages.map((stage) => {
          const clickable = isPipeline && stage.key;
          return (
            <li
              key={stage.label}
              onClick={clickable ? () => (props as PipelineProps).onSelect(stage.key as StageName) : undefined}
              className={clsx(
                "flex items-center gap-2 rounded px-2 py-1.5",
                clickable && "cursor-pointer hover:bg-panel-hover",
                isPipeline && stage.key === (props as PipelineProps).selected && "ring-1 ring-cyan/50",
                stage.status === "done" && "bg-green-dim/20",
                stage.status === "running" && "bg-amber-dim/20",
                stage.status === "failed" && "bg-red-dim/20"
              )}
            >
              <span className={clsx("w-3 text-center", STATUS_COLOR[stage.status])}>
                {STATUS_GLYPH[stage.status]}
              </span>
              <span
                className={clsx(
                  stage.status === "not-implemented" ? "text-text-dim" : "text-text-primary"
                )}
              >
                {stage.label}
              </span>
            </li>
          );
        })}
      </ol>
      <div className="border-t border-border-soft px-4 py-3">
        <p className="text-[11px] leading-relaxed text-text-dim">
          {isPipeline
            ? "Click a stage to inspect it. \"Run through\" executes every stage up to that point."
            : "Phase 1 lexer lab. Switch to \"Compiler Pipeline\" above to run the full parser → validation pipeline."}
        </p>
      </div>
    </aside>
  );
}
