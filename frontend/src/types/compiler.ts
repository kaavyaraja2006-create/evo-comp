// These types are a direct mirror of the backend's Pydantic response
// models (see backend/models/compilation.py). The frontend never
// invents fields that aren't actually returned by /api/lex.

export type TokenType =
  | "KEYWORD"
  | "IDENTIFIER"
  | "INTEGER_LITERAL"
  | "FLOAT_LITERAL"
  | "STRING_LITERAL"
  | "BOOLEAN_LITERAL"
  | "OPERATOR"
  | "DELIMITER"
  | "COMMENT"
  | "EOF";

export interface Token {
  index: number;
  type: TokenType;
  value: unknown;
  lexeme: string;
  line: number;
  column: number;
  start: number;
  end: number;
}

export interface LexicalError {
  message: string;
  line: number;
  column: number;
  character: string;
}

export interface TokenStatistics {
  totalTokens: number;
  keywords: number;
  identifiers: number;
  integerLiterals: number;
  floatLiterals: number;
  stringLiterals: number;
  booleanLiterals: number;
  literals: number;
  operators: number;
  delimiters: number;
  comments: number;
  eof: number;
}

export interface LexerPerformance {
  inputSizeCharacters: number;
  inputSizeLines: number;
  tokensGenerated: number;
  lexingTimeMs: number;
}

export interface LexResponse {
  success: boolean;
  tokens: Token[];
  statistics: TokenStatistics;
  errors: LexicalError[];
  performance: LexerPerformance;
}

// One real compilation result feeds every UI component. No component
// invents its own copy of the data.
export interface LexicalCompilation {
  source: string;
  result: LexResponse | null;
  status: "idle" | "running" | "success" | "failed";
  requestedAt: number | null;
  completedAt: number | null;
}

export interface CompilerEvent {
  id: number;
  timestamp: string;
  message: string;
}

export const TOKEN_CATEGORY_FILTERS = [
  "All",
  "Keywords",
  "Identifiers",
  "Literals",
  "Operators",
  "Delimiters",
  "Comments",
  "Errors",
] as const;

export type TokenCategoryFilter = (typeof TOKEN_CATEGORY_FILTERS)[number];
