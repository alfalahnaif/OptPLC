"use client";

import dynamic from "next/dynamic";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { registerStructuredTextLanguage } from "@/lib/monaco-structured-text";

const Editor = dynamic(() => import("@monaco-editor/react"), { ssr: false });

export function CodePanel({
  title,
  code,
  height = "680px"
}: {
  title: string;
  code: string;
  height?: string;
}) {
  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex flex-row items-center justify-between py-3">
        <CardTitle className="font-mono text-xs">{title}</CardTitle>
        <span className="font-mono text-[11px] text-muted-foreground">IEC 61131-3</span>
      </CardHeader>
      <CardContent className="p-0">
        <div className="code-editor" style={{ height }}>
          <Editor
            height="100%"
            beforeMount={registerStructuredTextLanguage}
            defaultLanguage="structured-text"
            value={code}
            theme="optplc-structured-text"
            options={{
              readOnly: true,
              minimap: { enabled: false },
              fontSize: 13,
              fontFamily: "var(--font-mono)",
              lineNumbersMinChars: 3,
              scrollBeyondLastLine: false,
              renderLineHighlight: "none",
              wordWrap: "on"
            }}
          />
        </div>
      </CardContent>
    </Card>
  );
}
