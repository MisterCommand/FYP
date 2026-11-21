"use client";

import { useId, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Answer, api } from "./api";
import { Citation } from "./ui";

type Context = {
  eventId?: string;
  eventTitle?: string;
  runId?: string;
  outcome?: string;
  asset?: "SPY";
  horizon?: number;
};

export function Assistant({ eventId, eventTitle, runId, outcome, asset = "SPY", horizon }: Context) {
  const inputId = useId();
  const [question, setQuestion] = useState("");
  const mutation = useMutation({
    mutationFn: (q: string) => api<Answer>("/assistant/query", {
      question: q,
      event_id: eventId,
      run_id: runId,
      outcome: outcome || undefined,
      asset,
      horizon,
    }),
  });
  const suggestions = runId
    ? ["What is the VaR and ES for this run?", "What volatility did this run estimate?", "What probability did this run use?"]
    : ["Why do estimates differ?", "What does the forecast say?", "What is the probability of the selected outcome?"];

  function ask(q: string) {
    if (!q.trim() || mutation.isPending) return;
    mutation.mutate(q.trim());
    setQuestion("");
  }

  return (
    <aside className="assistant">
      <div className="section-title"><h2>Research assistant</h2><span aria-hidden="true">✳</span></div>
      <span className="badge">Rule-based · no LLM</span>
      <p className="muted small">
        {runId ? "Context: this saved run" : eventTitle
          ? [eventTitle.replace("FOMC rate decision — ", ""), outcome, horizon && `${asset} ${horizon}D`].filter(Boolean).join(" · ")
          : "Select a meeting for market odds, or ask about the SPY forecast."}
      </p>
      <div className="assistant-conversation">
        {mutation.variables ? (
          <div className="question"><div className="eyebrow">Your question</div><p>{mutation.variables}</p></div>
        ) : (
          <div className="assistant-intro">
            <span className="assistant-symbol" aria-hidden="true">↗</span>
            <h3>Start with the evidence.</h3>
            <p>Ask a standalone question about {runId ? "this run’s inputs and results" : "Fed market odds, meeting decisions or SPY forecasts"}.</p>
          </div>
        )}
        <div aria-live="polite" aria-atomic="true">
          {mutation.isPending && <p>Reading research context…</p>}
          {mutation.data && !mutation.isPending && (
            <div className="answer">
              <div className="eyebrow">Assistant</div>
              {mutation.data.answer.split("\n\n").map((paragraph, i) => <p key={i}>{paragraph}</p>)}
              {mutation.data.citations.length > 0 && (
                <>
                  <div className="eyebrow">Sources</div>
                  <ul className="citations">
                    {mutation.data.citations.map(c => <li key={c}><Citation value={c} /></li>)}
                  </ul>
                </>
              )}
            </div>
          )}
        </div>
        {mutation.error && <p className="error" role="alert">{mutation.error.message}</p>}
      </div>
      <div className="suggestions">
        <span className="eyebrow">Suggested questions</span>
        {suggestions.map(q => <button type="button" key={q} disabled={mutation.isPending} onClick={() => ask(q)}>{q}<span aria-hidden="true">↗</span></button>)}
      </div>
      <form className="ask-form" onSubmit={e => { e.preventDefault(); ask(question); }}>
        <label className="sr-only" htmlFor={inputId}>Research question</label>
        <textarea id={inputId} value={question} onChange={e => setQuestion(e.target.value)} placeholder={runId ? "Ask about this run…" : "Ask about Fed odds or SPY forecasts…"} rows={3} maxLength={500} />
        <button aria-label="Send question" disabled={!question.trim() || mutation.isPending}>↑</button>
      </form>
      <p className="tiny muted">Each question is answered on its own. No web browsing.</p>
    </aside>
  );
}
