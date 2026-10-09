import type { Monaco } from "@monaco-editor/react";
import type { languages } from "monaco-editor";

// This registers ONLY cosmetic syntax highlighting inside the Monaco
// editor. It has no bearing on lexical analysis results — the real
// token stream always comes from the backend /api/lex lexer.
export function registerEvoLang(monaco: Monaco) {
  const id = "evolang";
  if (monaco.languages.getLanguages().some((l: languages.ILanguageExtensionPoint) => l.id === id)) return;

  monaco.languages.register({ id });

  monaco.languages.setMonarchTokensProvider(id, {
    keywords: [
      "int", "float", "string", "bool", "if", "else", "for", "while",
      "return", "function", "print",
    ],
    booleans: ["true", "false"],
    operators: [
      "+", "-", "*", "/", "%", "=", "+=", "-=", "*=", "/=",
      "==", "!=", "<", ">", "<=", ">=", "&&", "||", "!", "++", "--",
    ],
    symbols: /[=><!~?:&|+\-*/^%]+/,
    tokenizer: {
      root: [
        [/\/\/.*$/, "comment"],
        [/\/\*/, "comment", "@comment"],
        [/"([^"\\]|\\.)*"/, "string"],
        [/\d+\.\d+/, "number.float"],
        [/\d+/, "number"],
        [/[a-zA-Z_]\w*/, {
          cases: {
            "@keywords": "keyword",
            "@booleans": "number.boolean",
            "@default": "identifier",
          },
        }],
        [/[{}()\[\]]/, "@brackets"],
        [/[;,.]/, "delimiter"],
        [/@symbols/, {
          cases: {
            "@operators": "operator",
            "@default": "",
          },
        }],
      ],
      comment: [
        [/[^/*]+/, "comment"],
        [/\*\//, "comment", "@pop"],
        [/[/*]/, "comment"],
      ],
    },
  });

  monaco.editor.defineTheme("evocomp-dark", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "keyword", foreground: "e2a53d", fontStyle: "bold" },
      { token: "identifier", foreground: "cdd6e4" },
      { token: "number", foreground: "4fc3bd" },
      { token: "number.float", foreground: "4fc3bd" },
      { token: "number.boolean", foreground: "8b83e0" },
      { token: "string", foreground: "9fca8f" },
      { token: "comment", foreground: "5b6779", fontStyle: "italic" },
      { token: "operator", foreground: "e5626a" },
      { token: "delimiter", foreground: "94a1b3" },
    ],
    colors: {
      "editor.background": "#0d1219",
      "editor.lineHighlightBackground": "#161d2688",
      "editorLineNumber.foreground": "#3a4553",
      "editorLineNumber.activeForeground": "#94a1b3",
      "editorCursor.foreground": "#e2a53d",
      "editor.selectionBackground": "#244745aa",
    },
  });
}
