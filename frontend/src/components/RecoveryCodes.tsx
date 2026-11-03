import { useState } from "react";
import { Alert, Button, Checkbox } from "./ui";

/** Shows freshly generated recovery codes once, with copy/download and an acknowledgement. */
export function RecoveryCodes({
  codes,
  onDone,
  doneLabel = "Continue",
}: {
  codes: string[];
  onDone: () => void;
  doneLabel?: string;
}) {
  const [saved, setSaved] = useState(false);
  const [copied, setCopied] = useState(false);
  const text = `Meridian CRM recovery codes\nEach code can be used once if you lose access to your authenticator app.\n\n${codes.join("\n")}\n`;

  async function copy() {
    try {
      await navigator.clipboard.writeText(codes.join("\n"));
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  function download() {
    const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "migratecrm-recovery-codes.txt";
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-4">
      <Alert tone="warning" title="Save your recovery codes now">
        They will not be shown again. Store them somewhere safe, such as a password manager.
      </Alert>
      <ul
        aria-label="Recovery codes"
        className="grid grid-cols-2 gap-2 rounded-md border border-slate-200 bg-slate-50 p-4 font-mono text-sm"
      >
        {codes.map((code) => (
          <li key={code}>{code}</li>
        ))}
      </ul>
      <div className="flex gap-2">
        <Button variant="secondary" size="sm" onClick={() => void copy()}>
          {copied ? "Copied" : "Copy"}
        </Button>
        <Button variant="secondary" size="sm" onClick={download}>
          Download .txt
        </Button>
      </div>
      <Checkbox
        label="I have saved my recovery codes"
        checked={saved}
        onChange={(e) => setSaved(e.target.checked)}
      />
      <Button className="w-full" disabled={!saved} onClick={onDone}>
        {doneLabel}
      </Button>
    </div>
  );
}
