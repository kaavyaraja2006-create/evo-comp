import type { StageName } from "../../types/pipeline";

export const STAGE_LABELS: Record<StageName, string> = {
  lexer: "Lexer", parser: "Parser", ast: "AST", semantic: "Semantic Analysis",
  ir: "IR", cfg: "CFG", dna: "Program DNA", evolution: "Evolution",
  twin: "Digital Twin", codegen: "Target Code", evovm: "EvoVM",
  execution: "Execution", validation: "Validation",
};
