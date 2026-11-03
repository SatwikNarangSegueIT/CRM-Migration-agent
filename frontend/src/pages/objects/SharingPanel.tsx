import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { errorMessage } from "../../api/client";
import { metaApi, recordsApi } from "../../api/records";
import type { RecordData } from "../../api/types";
import { Combobox, controlClass } from "../../components/record/FieldInput";
import { TrashIcon } from "../../components/icons";
import { Alert, Button, Spinner } from "../../components/ui";
import { Modal } from "../../components/ui/Modal";

/** Manual sharing of one record with a user (owner or administrators only; the server enforces it). */
export function SharingPanel({ object, record, onClose }: { object: string; record: RecordData; onClose: () => void }) {
  const queryClient = useQueryClient();
  const shares = useQuery({ queryKey: ["shares", object, record.id], queryFn: ({ signal }) => recordsApi.shares(object, record.id, signal) });
  const users = useQuery({ queryKey: ["user-picker", "all"], queryFn: ({ signal }) => metaApi.users("", signal) });
  const [userId, setUserId] = useState<string | null>(null);
  const [userName, setUserName] = useState("");
  const [access, setAccess] = useState("read");
  const add = useMutation({
    mutationFn: () => recordsApi.addShare(object, record.id, { principal_type: "user", principal_id: userId!, access }),
    onSuccess: () => {
      setUserId(null);
      setUserName("");
      void queryClient.invalidateQueries({ queryKey: ["shares", object, record.id] });
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => recordsApi.removeShare(object, record.id, id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["shares", object, record.id] }),
  });
  const nameOf = (id: string) => users.data?.find((u) => u.id === id)?.name ?? "User or group";
  return (
    <Modal open onClose={onClose} title={`Sharing: ${record.name}`} size="md" footer={<Button variant="secondary" onClick={onClose}>Done</Button>}>
      <div className="space-y-4">
        <p className="text-sm text-slate-600">
          Owned by <strong>{record.owner?.name ?? "—"}</strong>. Organisation-wide defaults, the role hierarchy and sharing rules also give access; manual shares are listed here.
        </p>
        {(add.isError || remove.isError) && <Alert tone="error">{errorMessage(add.error ?? remove.error)}</Alert>}
        {shares.isPending ? (
          <Spinner label="Loading" />
        ) : shares.isError ? (
          <Alert tone="error">{errorMessage(shares.error)}</Alert>
        ) : shares.data.length === 0 ? (
          <p className="text-sm text-slate-500">No manual shares.</p>
        ) : (
          <ul className="divide-y divide-slate-100 rounded border border-slate-200">
            {shares.data.map((s) => (
              <li key={s.id} className="flex items-center justify-between px-3 py-2 text-sm">
                <span>
                  {s.principal_type === "user" ? nameOf(s.principal_id) : `${s.principal_type.replace(/_/g, " ")}`}{" "}
                  <span className="text-slate-500">— {s.access === "read" ? "Read only" : "Read/Write"}</span>
                </span>
                <button type="button" aria-label="Remove share" className="rounded p-1 text-slate-500 hover:bg-slate-100" onClick={() => remove.mutate(s.id)}>
                  <TrashIcon size={16} />
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="grid gap-2 sm:grid-cols-[1fr_auto_auto]">
          <Combobox
            id="share-user"
            value={userId}
            displayName={userName}
            onChange={(v, n) => {
              setUserId(v);
              setUserName(n ?? "");
            }}
            search={(q, signal) => metaApi.users(q, signal).then((r) => r.map((u) => ({ id: u.id, name: u.name, detail: u.email })))}
            queryKey={["user-picker"]}
            placeholder="Share with a user..."
          />
          <select aria-label="Access" className={controlClass(false)} value={access} onChange={(e) => setAccess(e.target.value)}>
            <option value="read">Read only</option>
            <option value="read_write">Read/Write</option>
          </select>
          <Button onClick={() => add.mutate()} disabled={!userId} loading={add.isPending}>
            Share
          </Button>
        </div>
      </div>
    </Modal>
  );
}
