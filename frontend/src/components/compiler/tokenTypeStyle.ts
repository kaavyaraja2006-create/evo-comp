import type { TokenType } from "../../types/compiler";

export const TOKEN_TYPE_COLOR: Record<TokenType, string> = {
  KEYWORD: "text-amber border-amber-dim bg-amber-dim/10",
  IDENTIFIER: "text-cyan border-cyan-dim bg-cyan-dim/10",
  INTEGER_LITERAL: "text-violet border-violet/30 bg-violet/10",
  FLOAT_LITERAL: "text-violet border-violet/30 bg-violet/10",
  STRING_LITERAL: "text-green border-green-dim bg-green-dim/10",
  BOOLEAN_LITERAL: "text-violet border-violet/30 bg-violet/10",
  OPERATOR: "text-red border-red-dim bg-red-dim/10",
  DELIMITER: "text-text-secondary border-border bg-panel-raised",
  COMMENT: "text-text-dim border-border-soft bg-panel-raised",
  EOF: "text-text-dim border-border-soft bg-panel-raised",
};
