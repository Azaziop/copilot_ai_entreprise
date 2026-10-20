"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface SourceItem {
  type?: string;
  filename: string;
  location?: string;
  lines?: number | null;
  label?: string;
  snippet?: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  route?: string;
  sources?: SourceItem[];
  streaming?: boolean;
}

interface DocItem {
  id: number;
  filename: string;
  file_type?: string;
  uploaded_at?: string | null;
}

interface SessionItem {
  id: number;
  title: string;
  created_at?: string | null;
  message_count?: number;
}

type StreamEvent = {
  type: string;
  text?: string;
  route?: string;
  sources?: SourceItem[];
  answer?: string;
  history_id?: number;
  session_id?: number;
};

/** Collapse duplicate filenames into one card (frontend safety net). */
function dedupeSources(sources: SourceItem[]): SourceItem[] {
  const map = new Map<string, SourceItem & { pages: string[] }>();
  for (const s of sources) {
    const key = s.filename || s.label || "document";
    const pageMatch = (s.location || "").match(/page[s]?\s+([\d,\s]+)/i);
    const pagesFromLoc = pageMatch
      ? pageMatch[1].split(/[,\s]+/).filter(Boolean)
      : [];

    if (!map.has(key)) {
      map.set(key, { ...s, pages: [...pagesFromLoc] });
      continue;
    }
    const cur = map.get(key)!;
    for (const p of pagesFromLoc) {
      if (!cur.pages.includes(p)) cur.pages.push(p);
    }
  }
  return Array.from(map.values()).map((s) => {
    const { pages, ...rest } = s;
    const location =
      pages.length === 0
        ? rest.location || "document indexé"
        : pages.length === 1
          ? `page ${pages[0]}`
          : `pages ${pages.join(", ")}`;
    return { ...rest, location, snippet: undefined };
  });
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState("");
  const [uploading, setUploading] = useState(false);
  const [documents, setDocuments] = useState<DocItem[]>([]);
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [sideTab, setSideTab] = useState<"chats" | "docs">("chats");
  const [liveReasoning, setLiveReasoning] = useState<string[]>([]);
  const [showReasoningPanel, setShowReasoningPanel] = useState(false);
  const hideReasoningTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const apiUrl = useMemo(
    () =>
      process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
      "http://127.0.0.1:18000",
    []
  );

  const loadDocuments = async () => {
    try {
      const res = await fetch(`${apiUrl}/documents`);
      if (!res.ok) return;
      const data = (await res.json()) as DocItem[];
      setDocuments(Array.isArray(data) ? data : []);
    } catch {
      /* optional */
    }
  };

  const loadSessions = async () => {
    try {
      const res = await fetch(`${apiUrl}/sessions`);
      if (!res.ok) return;
      const data = (await res.json()) as SessionItem[];
      setSessions(Array.isArray(data) ? data : []);
    } catch {
      /* optional */
    }
  };

  useEffect(() => {
    loadDocuments();
    loadSessions();
  }, [apiUrl]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    return () => {
      if (hideReasoningTimer.current) clearTimeout(hideReasoningTimer.current);
    };
  }, []);

  const patchAssistant = (patch: Partial<Message>) => {
    setMessages((prev) => {
      const next = [...prev];
      const last = next[next.length - 1];
      if (!last || last.role !== "assistant") return prev;
      next[next.length - 1] = { ...last, ...patch };
      return next;
    });
  };

  const appendToken = (text: string) => {
    setMessages((prev) => {
      const next = [...prev];
      const last = next[next.length - 1];
      if (!last || last.role !== "assistant") return prev;
      next[next.length - 1] = {
        ...last,
        content: (last.content || "") + text,
      };
      return next;
    });
  };

  const openReasoningPanel = (text: string) => {
    if (hideReasoningTimer.current) {
      clearTimeout(hideReasoningTimer.current);
      hideReasoningTimer.current = null;
    }
    setShowReasoningPanel(true);
    setLiveReasoning((prev) => [...prev, text]);
  };

  const closeReasoningPanel = () => {
    if (hideReasoningTimer.current) clearTimeout(hideReasoningTimer.current);
    hideReasoningTimer.current = setTimeout(() => {
      setShowReasoningPanel(false);
      setLiveReasoning([]);
    }, 450);
  };

  const startNewChat = async () => {
    try {
      const res = await fetch(`${apiUrl}/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: "Nouvelle discussion" }),
      });
      if (res.ok) {
        const s = (await res.json()) as SessionItem;
        setSessionId(s.id);
        await loadSessions();
      } else {
        setSessionId(null);
      }
    } catch {
      setSessionId(null);
    }
    setMessages([]);
    setInput("");
    setShowReasoningPanel(false);
    setLiveReasoning([]);
    setSideTab("chats");
  };

  const openSession = async (id: number) => {
    try {
      const res = await fetch(`${apiUrl}/sessions/${id}`);
      if (!res.ok) return;
      const data = await res.json();
      setSessionId(id);
      const restored: Message[] = [];
      for (const m of data.messages || []) {
        restored.push({ role: "user", content: m.question });
        restored.push({
          role: "assistant",
          content: m.answer,
          route: m.route_pris,
        });
      }
      setMessages(restored);
      setShowReasoningPanel(false);
      setLiveReasoning([]);
    } catch {
      /* ignore */
    }
  };

  const handleSendMessage = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const question = input.trim();
    setInput("");
    setLoading(true);
    setLiveReasoning([]);
    setShowReasoningPanel(false);
    setMessages((prev) => [
      ...prev,
      { role: "user", content: question },
      {
        role: "assistant",
        content: "",
        sources: [],
        streaming: true,
      },
    ]);

    try {
      const res = await fetch(`${apiUrl}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          session_id: sessionId,
        }),
      });
      if (!res.ok || !res.body) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Erreur serveur (${res.status})`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let answerStarted = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";

        for (const part of parts) {
          const line = part
            .split("\n")
            .map((l) => l.trim())
            .find((l) => l.startsWith("data:"));
          if (!line) continue;
          const raw = line.replace(/^data:\s*/, "");
          let event: StreamEvent;
          try {
            event = JSON.parse(raw) as StreamEvent;
          } catch {
            continue;
          }

          if (event.type === "session" && event.session_id) {
            setSessionId(event.session_id);
          } else if (event.type === "reasoning" && event.text) {
            if (!answerStarted) openReasoningPanel(event.text);
          } else if (event.type === "route" && event.route) {
            patchAssistant({ route: event.route });
          } else if (event.type === "sources" && event.sources) {
            patchAssistant({ sources: dedupeSources(event.sources) });
          } else if (event.type === "token" && event.text) {
            if (!answerStarted) {
              answerStarted = true;
              closeReasoningPanel();
            }
            appendToken(event.text);
          } else if (event.type === "done") {
            patchAssistant({
              ...(event.answer != null ? { content: event.answer } : {}),
              ...(event.route ? { route: event.route } : {}),
              ...(event.sources
                ? { sources: dedupeSources(event.sources) }
                : {}),
              streaming: false,
            });
            if (event.session_id) setSessionId(event.session_id);
            closeReasoningPanel();
            loadSessions();
          } else if (event.type === "error") {
            throw new Error(event.text || "Erreur de stream");
          }
        }
      }

      patchAssistant({ streaming: false });
      closeReasoningPanel();
    } catch (error) {
      const detail =
        error instanceof Error
          ? error.message
          : "Erreur de communication avec le serveur.";
      patchAssistant({
        content: `**Erreur** — ${detail}`,
        streaming: false,
      });
      closeReasoningPanel();
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (e: FormEvent) => {
    e.preventDefault();
    if (!file || uploading) return;

    const formData = new FormData();
    formData.append("file", file);
    setUploading(true);
    setUploadStatus("Indexation en cours…");

    try {
      const res = await fetch(`${apiUrl}/upload`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || "Échec de l'upload");
      }
      setUploadStatus(`Document indexé : ${data.filename}`);
      setFile(null);
      await loadDocuments();
    } catch (error) {
      const detail =
        error instanceof Error ? error.message : "Erreur réseau lors de l'upload.";
      setUploadStatus(detail);
    } finally {
      setUploading(false);
    }
  };

  const suggestions = [
    "Capitaux propres OCP en 2023 ?",
    "Compétences du CV Zaoui Anass",
    "Politique de congés AlphaCorp",
  ];

  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");

  return (
    <main className="min-h-screen px-0 py-0 md:px-4 md:py-4">
      <div
        className={`mx-auto grid h-screen max-w-[1440px] overflow-hidden border-0 bg-[var(--panel)] shadow-[var(--shadow)] transition-[grid-template-columns] duration-300 md:h-[calc(100vh-2rem)] md:rounded-2xl md:border md:border-[var(--line)] ${
          showReasoningPanel
            ? "md:grid-cols-[280px_1fr_300px]"
            : "md:grid-cols-[280px_1fr]"
        }`}
      >
        <aside className="flex flex-col border-b border-[var(--line)] bg-[var(--bg-elevated)] md:border-b-0 md:border-r">
          <div className="animate-rise border-b border-[var(--line)] px-5 py-5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[var(--accent-strong)]">
              Enterprise AI
            </p>
            <h1
              className="mt-1.5 text-[1.7rem] leading-tight text-[var(--ink)]"
              style={{ fontFamily: "var(--font-display), Georgia, serif" }}
            >
              Copilot
            </h1>
            <button
              type="button"
              onClick={startNewChat}
              className="mt-4 w-full rounded-xl bg-[var(--accent)] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[var(--accent-strong)]"
            >
              Nouvelle conversation
            </button>
          </div>

          <div className="flex gap-1 border-b border-[var(--line)] px-3 py-2">
            <button
              type="button"
              onClick={() => setSideTab("chats")}
              className={`flex-1 rounded-lg px-2 py-2 text-xs font-semibold transition ${
                sideTab === "chats"
                  ? "bg-white text-[var(--accent-strong)] shadow-sm"
                  : "text-[var(--muted)] hover:bg-white/70"
              }`}
            >
              Historique
            </button>
            <button
              type="button"
              onClick={() => setSideTab("docs")}
              className={`flex-1 rounded-lg px-2 py-2 text-xs font-semibold transition ${
                sideTab === "docs"
                  ? "bg-white text-[var(--accent-strong)] shadow-sm"
                  : "text-[var(--muted)] hover:bg-white/70"
              }`}
            >
              Documents
            </button>
          </div>

          {sideTab === "chats" ? (
            <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3">
              <p className="mb-2 px-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--muted)]">
                Conversations ({sessions.length})
              </p>
              <ul className="space-y-1">
                {sessions.length === 0 && (
                  <li className="px-2 text-xs text-[var(--muted)]">
                    Aucune conversation.
                  </li>
                )}
                {sessions.map((s) => (
                  <li key={s.id}>
                    <button
                      type="button"
                      onClick={() => openSession(s.id)}
                      className={`w-full rounded-xl border px-3 py-2.5 text-left transition ${
                        sessionId === s.id
                          ? "border-[var(--accent)] bg-white shadow-sm"
                          : "border-transparent hover:border-[var(--line)] hover:bg-white/80"
                      }`}
                    >
                      <div className="truncate text-sm font-medium text-[var(--ink)]">
                        {s.title || "Sans titre"}
                      </div>
                      <div className="mt-0.5 text-[11px] text-[var(--muted)]">
                        {s.message_count ?? 0} msg
                        {s.created_at
                          ? ` · ${new Date(s.created_at).toLocaleDateString("fr-FR")}`
                          : ""}
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <div className="flex min-h-0 flex-1 flex-col">
              <form
                onSubmit={handleUpload}
                className="space-y-3 border-b border-[var(--line)] px-4 py-3"
              >
                <label className="flex cursor-pointer flex-col gap-1 rounded-xl border border-dashed border-[var(--line)] bg-white px-3 py-3 transition hover:border-[var(--accent)]">
                  <span className="truncate text-sm font-medium text-[var(--ink)]">
                    {file ? file.name : "Importer PDF, TXT, MD, CSV, XLSX"}
                  </span>
                  <input
                    type="file"
                    accept=".pdf,.txt,.md,.csv,.xlsx,.xls,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
                    className="hidden"
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                  />
                </label>
                <button
                  type="submit"
                  disabled={!file || uploading}
                  className="w-full rounded-xl bg-[var(--accent)] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[var(--accent-strong)] disabled:cursor-not-allowed disabled:opacity-45"
                >
                  {uploading ? "Indexation…" : "Indexer"}
                </button>
                {uploadStatus && (
                  <p className="rounded-xl border border-[var(--line)] bg-white px-3 py-2 text-xs text-[var(--muted)]">
                    {uploadStatus}
                  </p>
                )}
              </form>
              <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--muted)]">
                  Corpus ({documents.length})
                </p>
                <ul className="space-y-1.5">
                  {documents.length === 0 && (
                    <li className="text-xs text-[var(--muted)]">Aucun document.</li>
                  )}
                  {documents.map((doc) => (
                    <li
                      key={doc.id}
                      className="rounded-xl border border-[var(--line)] bg-white px-3 py-2 text-xs"
                    >
                      <div className="font-medium text-[var(--ink)]">{doc.filename}</div>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </aside>

        <section className="flex min-h-0 flex-col bg-[var(--panel)]">
          <header className="flex items-center justify-between border-b border-[var(--line)] px-5 py-3.5">
            <div>
              <p
                className="text-base font-semibold text-[var(--ink)]"
                style={{ fontFamily: "var(--font-display), Georgia, serif" }}
              >
                Assistant
              </p>
              <p className="text-[11px] text-[var(--muted)]">
                {sessionId ? `Conversation #${sessionId}` : "Nouvelle session"}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {lastAssistant?.route && (
                <span className="rounded-lg border border-[var(--line)] bg-[var(--accent-soft)] px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-[var(--accent-strong)]">
                  {lastAssistant.route}
                </span>
              )}
              <span className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--line)] bg-white px-2.5 py-1 text-[11px] font-medium text-[var(--muted)]">
                <span className="h-1.5 w-1.5 rounded-full bg-[var(--accent)]" />
                En ligne
              </span>
            </div>
          </header>

          <div className="flex-1 space-y-5 overflow-y-auto px-4 py-5 md:px-8">
            {messages.length === 0 && (
              <div className="animate-rise mx-auto flex h-full max-w-2xl flex-col justify-center">
                <h2
                  className="text-[2rem] leading-tight text-[var(--ink)]"
                  style={{ fontFamily: "var(--font-display), Georgia, serif" }}
                >
                  Comment puis-je vous aider ?
                </h2>
                <p className="mt-3 max-w-lg text-sm leading-relaxed text-[var(--muted)]">
                  Posez une question sur vos documents. Le raisonnement s’affiche
                  à droite pendant l’analyse, puis la réponse avec les sources
                  utilisées.
                </p>
                <div className="mt-6 flex flex-wrap gap-2">
                  {suggestions.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => setInput(s)}
                      className="rounded-xl border border-[var(--line)] bg-white px-3 py-2 text-left text-xs font-medium text-[var(--ink)] transition hover:border-[var(--accent)] hover:bg-[var(--accent-soft)]"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, index) => (
              <div
                key={`${msg.role}-${index}`}
                className={`animate-rise flex ${
                  msg.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`w-full max-w-[min(48rem,100%)] ${
                    msg.role === "user" ? "flex justify-end" : ""
                  }`}
                >
                  {msg.role === "user" ? (
                    <div className="max-w-[min(36rem,92%)] rounded-2xl rounded-br-md bg-[var(--user)] px-4 py-3 text-sm leading-relaxed text-white">
                      {msg.content}
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {(msg.content || msg.streaming) && (
                        <div
                          className={`rounded-2xl border border-[var(--line)] bg-white px-4 py-3.5 ${
                            msg.streaming ? "stream-cursor" : ""
                          }`}
                        >
                          <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--accent-strong)]">
                            Réponse
                          </div>
                          <div className="md-body">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {msg.content || "_Génération…_"}
                            </ReactMarkdown>
                          </div>
                        </div>
                      )}

                      {!msg.streaming && (msg.sources?.length || 0) > 0 && (
                        <div className="rounded-2xl border border-[var(--line)] bg-white px-4 py-3">
                          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--muted)]">
                            Source{msg.sources!.length > 1 ? "s" : ""} utilisée
                            {msg.sources!.length > 1 ? "s" : ""}
                          </p>
                          <ul className="mt-2 space-y-2">
                            {msg.sources!.map((s, i) => (
                              <li
                                key={`${index}-s-${i}`}
                                className="rounded-xl border border-[var(--line)] bg-[var(--bg-elevated)] px-3 py-2"
                              >
                                <div className="flex flex-wrap items-baseline justify-between gap-2">
                                  <span className="text-sm font-semibold text-[var(--ink)]">
                                    {s.filename}
                                  </span>
                                  <span className="text-[11px] font-medium text-[var(--accent-strong)]">
                                    {s.type === "direct"
                                      ? "DIRECT"
                                      : s.type === "tool"
                                        ? "TOOL"
                                        : "RAG"}
                                  </span>
                                </div>
                                <p className="mt-0.5 text-xs text-[var(--muted)]">
                                  {s.location || "document indexé"}
                                </p>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          <form
            onSubmit={handleSendMessage}
            className="border-t border-[var(--line)] bg-[var(--bg-elevated)] p-4"
          >
            <div className="mx-auto flex max-w-3xl gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Posez votre question à l’assistant…"
                className="flex-1 rounded-xl border border-[var(--line)] bg-white px-4 py-3 text-sm text-[var(--ink)] outline-none transition focus:border-[var(--accent)]"
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className="rounded-xl bg-[var(--accent)] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[var(--accent-strong)] disabled:cursor-not-allowed disabled:opacity-45"
              >
                {loading ? "…" : "Envoyer"}
              </button>
            </div>
          </form>
        </section>

        {showReasoningPanel && (
          <aside className="animate-rise flex min-h-0 flex-col border-t border-[var(--line)] bg-[var(--reason-bg)] md:border-t-0 md:border-l">
            <div className="flex items-center justify-between border-b border-[var(--line)] px-4 py-3">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--accent-strong)]">
                  Raisonnement
                </p>
                <p className="text-[11px] text-[var(--muted)]">En cours…</p>
              </div>
              <span className="flex items-center gap-1">
                <span className="thinking-dot" />
                <span className="thinking-dot" />
                <span className="thinking-dot" />
              </span>
            </div>
            <ol className="reason-scroll min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-4">
              {liveReasoning.map((step, i) => (
                <li key={`lr-${i}`} className="flex gap-2.5 text-[13px] leading-snug">
                  <span className="mt-0.5 shrink-0 font-mono text-[10px] font-bold text-[var(--accent-strong)]">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span className="md-body !text-[13px] text-[var(--ink)]">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{step}</ReactMarkdown>
                  </span>
                </li>
              ))}
            </ol>
          </aside>
        )}
      </div>
    </main>
  );
}
