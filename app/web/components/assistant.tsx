"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Answer, api } from "./api";
import { Citation } from "./ui";

export function Assistant({ eventId, runId, asset, horizon }: { eventId?: string; runId?: string; asset?: string; horizon?: number }) {
  const [question, setQuestion] = useState("");
  const [asked, setAsked] = useState("");
  const mutation = useMutation({ mutationFn: (q: string) => api<Answer>("/assistant/query", { question: q, event_id: eventId, run_id: runId, asset, horizon }) });
  function ask(q: string) { if (!q.trim()) return; setAsked(q); mutation.mutate(q); setQuestion(""); }
  return <aside className="assistant"><div className="section-title"><h2>Research assistant</h2><span aria-hidden="true">✳</span></div><span className="badge">Rule-based · no LLM</span><p className="muted small">A transparent guide to the data, methods and limitations behind this event.</p><div className="assistant-conversation">{asked ? <div className="question"><div className="eyebrow">Your question</div><p>{asked}</p></div> : <div className="assistant-intro"><span className="assistant-symbol" aria-hidden="true">↗</span><h3>Start with the evidence.</h3><p>Ask about probabilities, forecasts or what we can’t estimate yet.</p></div>}{mutation.isPending && <p role="status">Reading research context…</p>}{mutation.error && <p className="error" role="alert">{mutation.error.message}</p>}{mutation.data && !mutation.isPending && <div className="answer"><div className="eyebrow">Assistant</div><p>{mutation.data.answer}</p><div className="eyebrow">Sources</div><ul className="citations">{mutation.data.citations.map(c => <li key={c}><Citation value={c} /></li>)}</ul></div>}</div><div className="suggestions"><span className="eyebrow">Suggested questions</span>{["Why do estimates differ?", "What does the forecast say?", "What is the probability now?"].map(q => <button type="button" key={q} disabled={mutation.isPending} onClick={() => ask(q)}>{q}<span aria-hidden="true">↗</span></button>)}</div><form className="ask-form" onSubmit={e => { e.preventDefault(); ask(question); }}><label className="sr-only" htmlFor="assistant-question">Ask about this event</label><textarea id="assistant-question" value={question} onChange={e => setQuestion(e.target.value)} placeholder="Ask about this event…" rows={3} /><button aria-label="Send question" disabled={!question.trim() || mutation.isPending}>↑</button></form><p className="tiny muted">Answers use dataset and model outputs only.</p></aside>;
}
