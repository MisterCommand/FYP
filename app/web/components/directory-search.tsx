"use client";

import { useEffect, useState } from "react";

export function useDirectorySearch(initialQuery: string) {
  const [query, setQuery] = useState(initialQuery);
  useEffect(() => { setQuery(initialQuery); }, [initialQuery]);
  useEffect(() => {
    const restore = () => setQuery(new URLSearchParams(window.location.search).get("q") || "");
    window.addEventListener("popstate", restore);
    return () => window.removeEventListener("popstate", restore);
  }, []);
  function changeQuery(value: string) {
    setQuery(value);
    const url = new URL(window.location.href);
    if (value) url.searchParams.set("q", value);
    else url.searchParams.delete("q");
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  }
  return { query, changeQuery };
}

export function DirectorySearch({ label, query, onChange }: { label: string; query: string; onChange: (value: string) => void }) {
  return <div className="panel"><label>{label}<input type="search" value={query} onChange={e => onChange(e.target.value)} /></label>{query && <button className="text-button" onClick={() => onChange("")}>Clear search</button>}</div>;
}

export function NoMatches({ clear }: { clear: () => void }) {
  return <div className="empty-archive"><h2>No matches</h2><p>Try another meeting, year, title or outcome.</p><button className="button" onClick={clear}>Clear search</button></div>;
}
