import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { apiRequest, errorMessage } from "../../api/client";
import type { RecordData } from "../../api/types";
import { Alert, Button, FormField, Input } from "../ui";
import { Modal } from "../ui/Modal";
import { controlClass } from "./FieldInput";

/** Privacy requests for a person (contact or lead): subject-access export (JSON) or erasure (anonymise). */
export function PrivacyDialog({
  object,
  record,
  mode,
  onClose,
  onErased,
}: {
  object: string;
  record: RecordData;
  mode: "export" | "erase";
  onClose: () => void;
  onErased: () => void;
}) {
  const [reason, setReason] = useState("");
  const [confirm, setConfirm] = useState("");
  const exportData = useMutation({
    mutationFn: () => apiRequest<unknown>(`/privacy/${object}/${record.id}/export`),
    onSuccess: (data) => {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `privacy-export-${object}-${record.id}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      onClose();
    },
  });
  const erase = useMutation({
    mutationFn: () =>
      apiRequest<RecordData>(`/privacy/${object}/${record.id}/erase`, {
        method: "POST",
        body: { reason, confirm },
      }),
    onSuccess: onErased,
  });
  const error = exportData.error ?? erase.error;

  if (mode === "export") {
    return (
      <Modal
        open
        onClose={onClose}
        title="Export personal data"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button onClick={() => exportData.mutate()} loading={exportData.isPending}>
              Download export
            </Button>
          </>
        }
      >
        {error && <Alert tone="error">{errorMessage(error)}</Alert>}
        <p className="text-sm text-slate-700">
          Downloads everything held about <strong>{record.name}</strong> — the record, its change history,
          linked records, consent and e-mail history — as a JSON file for a subject access request. The export
          is recorded in the audit log.
        </p>
      </Modal>
    );
  }
  return (
    <Modal
      open
      onClose={onClose}
      title="Erase personal data"
      size="sm"
      busy={erase.isPending}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={erase.isPending}>
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={() => erase.mutate()}
            loading={erase.isPending}
            disabled={!reason.trim() || confirm !== "ERASE"}
          >
            Erase permanently
          </Button>
        </>
      }
    >
      <div className="space-y-3 text-sm">
        {error && <Alert tone="error">{errorMessage(error)}</Alert>}
        <Alert tone="warning" title="This can't be undone">
          Personal fields, notes, files and change history of <strong>{record.name}</strong> are removed and
          any portal account is deactivated. Business records (cases, invoices, consent decisions) are kept
          without the personal details.
        </Alert>
        <FormField label="Reason / request reference" required>
          {({ id }) => (
            <textarea
              id={id}
              rows={2}
              className={controlClass(false)}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          )}
        </FormField>
        <FormField label='Type "ERASE" to confirm' required>
          {({ id }) => <Input id={id} value={confirm} onChange={(e) => setConfirm(e.target.value)} />}
        </FormField>
      </div>
    </Modal>
  );
}
