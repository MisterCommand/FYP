"use client";

import { FormEvent, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { api, Run } from "./api";
import "./run-actions.css";

export function RunActions({ run, title, detail = false }: { run: Run; title: string; detail?: boolean }) {
  const client = useQueryClient();
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(run.title || "");
  const [confirming, setConfirming] = useState(false);
  const rename = useMutation({
    mutationFn: () => api<Run>(`/analyses/${run.id}`, { title: draft }, "PATCH"),
    onSuccess: updated => {
      client.setQueryData(["run", run.id], updated);
      client.invalidateQueries({ queryKey: ["runs"] });
      setEditing(false);
    },
  });
  const remove = useMutation({
    mutationFn: () => api<void>(`/analyses/${run.id}`, undefined, "DELETE"),
    onSuccess: () => {
      client.setQueryData<Run[]>(["runs"], rows => rows?.filter(row => row.id !== run.id));
      client.removeQueries({ queryKey: ["run", run.id], exact: true });
      client.invalidateQueries({ queryKey: ["runs"] });
      setConfirming(false);
      if (detail) router.push("/runs");
    },
  });
  function submit(event: FormEvent) { event.preventDefault(); rename.mutate(); }
  return <div className="run-actions">
    {editing ? <form onSubmit={submit}><label>Research title<input maxLength={160} value={draft} placeholder={title} onChange={e => setDraft(e.target.value)} /></label><small className="muted">Leave blank to use the default title.</small><div className="action-row"><button className="button" disabled={rename.isPending}>Save title</button><button type="button" className="button" onClick={() => setEditing(false)}>Cancel</button></div>{rename.error && <p role="alert">{rename.error.message}</p>}</form> : <button className="text-button" onClick={() => { setDraft(run.title || ""); rename.reset(); setEditing(true); }}>Rename</button>}
    <button className="text-button" onClick={() => { remove.reset(); setConfirming(true); }}>Delete</button>
    {confirming && <dialog ref={node => { if (node && !node.open) node.showModal(); }} onCancel={() => setConfirming(false)} aria-labelledby={`delete-title-${run.id}`}><h2 id={`delete-title-${run.id}`}>Delete saved research?</h2><p>{title}</p><p>This permanently removes the saved run and cannot be undone.</p>{remove.error && <p role="alert">{remove.error.message}</p>}<div className="action-row"><button className="button" onClick={() => setConfirming(false)} disabled={remove.isPending}>Cancel</button><button className="button primary" onClick={() => remove.mutate()} disabled={remove.isPending}>Delete permanently</button></div></dialog>}
  </div>;
}
