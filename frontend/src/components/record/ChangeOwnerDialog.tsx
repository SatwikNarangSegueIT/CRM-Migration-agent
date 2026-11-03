import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { errorMessage } from "../../api/client";
import { metaApi, recordsApi } from "../../api/records";
import { Alert, Button, FormField } from "../ui";
import { Modal } from "../ui/Modal";
import { Combobox, controlClass } from "./FieldInput";

/** Change the owner of one record or of several (bulk) to a user or, where allowed, a queue. */
export function ChangeOwnerDialog({
  object,
  ids,
  allowQueues,
  onClose,
  onDone,
}: {
  object: string;
  ids: string[];
  allowQueues: boolean;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const [kind, setKind] = useState<"user" | "queue">("user");
  const [ownerId, setOwnerId] = useState<string | null>(null);
  const [ownerName, setOwnerName] = useState("");
  const queues = useQuery({
    queryKey: ["meta", "queues", object],
    queryFn: ({ signal }) => metaApi.queues(object, signal),
    enabled: allowQueues,
  });
  const run = useMutation({
    mutationFn: async () => {
      const body = kind === "user" ? { owner_id: ownerId! } : { queue_id: ownerId! };
      if (ids.length === 1) {
        await recordsApi.changeOwner(object, ids[0]!, body);
        return "Owner changed.";
      }
      const result = await recordsApi.bulk(object, { ids, operation: "change_owner", ...body } as never);
      return `${result.succeeded} record(s) updated${result.failed ? `, ${result.failed} failed` : ""}.`;
    },
    onSuccess: onDone,
  });
  return (
    <Modal
      open
      onClose={onClose}
      title={ids.length > 1 ? `Change owner of ${ids.length} records` : "Change owner"}
      size="sm"
      busy={run.isPending}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => run.mutate()} disabled={!ownerId} loading={run.isPending}>
            Change owner
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {run.isError && <Alert tone="error">{errorMessage(run.error)}</Alert>}
        {allowQueues && (
          <div className="flex gap-4 text-sm">
            <label className="flex items-center gap-1.5">
              <input
                type="radio"
                checked={kind === "user"}
                onChange={() => {
                  setKind("user");
                  setOwnerId(null);
                }}
              />{" "}
              User
            </label>
            <label className="flex items-center gap-1.5">
              <input
                type="radio"
                checked={kind === "queue"}
                onChange={() => {
                  setKind("queue");
                  setOwnerId(null);
                }}
              />{" "}
              Queue
            </label>
          </div>
        )}
        <FormField label={kind === "user" ? "New owner" : "Queue"} required>
          {({ id }) =>
            kind === "user" ? (
              <Combobox
                id={id}
                value={ownerId}
                displayName={ownerName}
                onChange={(v, name) => {
                  setOwnerId(v);
                  setOwnerName(name ?? "");
                }}
                search={(q, signal) =>
                  metaApi
                    .users(q, signal)
                    .then((r) => r.map((u) => ({ id: u.id, name: u.name, detail: u.title ?? u.email })))
                }
                queryKey={["user-picker"]}
                placeholder="Search users..."
              />
            ) : (
              <select
                id={id}
                className={controlClass(false)}
                value={ownerId ?? ""}
                onChange={(e) => setOwnerId(e.target.value || null)}
              >
                <option value="">Select a queue…</option>
                {queues.data?.map((q) => (
                  <option key={q.id} value={q.id}>
                    {q.name}
                  </option>
                ))}
              </select>
            )
          }
        </FormField>
      </div>
    </Modal>
  );
}
