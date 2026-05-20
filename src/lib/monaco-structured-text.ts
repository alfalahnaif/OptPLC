import type * as Monaco from "monaco-editor";

const structuredTextKeywords = [
  "PROGRAM",
  "END_PROGRAM",
  "FUNCTION_BLOCK",
  "END_FUNCTION_BLOCK",
  "VAR",
  "VAR_INPUT",
  "VAR_OUTPUT",
  "END_VAR",
  "IF",
  "THEN",
  "ELSE",
  "ELSIF",
  "END_IF",
  "CASE",
  "OF",
  "END_CASE",
  "FOR",
  "WHILE",
  "DO",
  "END_FOR",
  "END_WHILE"
];

const structuredTextTypes = ["BOOL", "INT", "REAL", "TIME", "STRING"];
const structuredTextConstants = ["TRUE", "FALSE"];
const structuredTextTimers = ["TON", "TOF", "TP"];

export function registerStructuredTextLanguage(monaco: typeof Monaco) {
  if (monaco.languages.getLanguages().some((language) => language.id === "structured-text")) {
    return;
  }

  monaco.languages.register({ id: "structured-text" });
  monaco.languages.setLanguageConfiguration("structured-text", {
    comments: {
      lineComment: "//",
      blockComment: ["(*", "*)"]
    },
    brackets: [
      ["(", ")"],
      ["[", "]"]
    ],
    autoClosingPairs: [
      { open: "(", close: ")" },
      { open: "[", close: "]" },
      { open: "'", close: "'" },
      { open: '"', close: '"' }
    ]
  });

  monaco.languages.setMonarchTokensProvider("structured-text", {
    ignoreCase: true,
    keywords: structuredTextKeywords,
    typeKeywords: structuredTextTypes,
    constants: structuredTextConstants,
    timers: structuredTextTimers,
    tokenizer: {
      root: [
        [/\/\/.*$/, "comment"],
        [/\(\*/, "comment", "@comment"],
        [/[a-zA-Z_]\w*/, {
          cases: {
            "@keywords": "keyword",
            "@typeKeywords": "type",
            "@constants": "constant",
            "@timers": "predefined",
            "@default": "identifier"
          }
        }],
        [/\d+(\.\d+)?/, "number"],
        [/'[^']*'/, "string"],
        [/"[^"]*"/, "string"],
        [/[:=<>+\-*/]+/, "operator"]
      ],
      comment: [
        [/[^*)]+/, "comment"],
        [/\*\)/, "comment", "@pop"],
        [/./, "comment"]
      ]
    }
  });

  monaco.editor.defineTheme("optplc-structured-text", {
    base: "vs",
    inherit: true,
    rules: [
      { token: "keyword", foreground: "4F46E5", fontStyle: "bold" },
      { token: "type", foreground: "0E7490" },
      { token: "constant", foreground: "7C3AED", fontStyle: "bold" },
      { token: "predefined", foreground: "0369A1", fontStyle: "bold" },
      { token: "comment", foreground: "8B94A7", fontStyle: "italic" },
      { token: "string", foreground: "B45309" },
      { token: "number", foreground: "0D9488" },
      { token: "operator", foreground: "64748B" }
    ],
    colors: {
      "editor.background": "#FFFFFF",
      "editorLineNumber.foreground": "#94A3B8",
      "editorGutter.background": "#FFFFFF"
    }
  });
}
