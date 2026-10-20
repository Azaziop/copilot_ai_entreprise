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
  reasoning?: string[];
  sources?: SourceItem[];
  streaming?: boolean;
}

interface DocItem {
  id: number;
  filename: string;
  file_type?: string;
  uploaded_at?: string | null;
}

type StreamEvent = {
  type: string;
  text?: string;
  route?: string;
  sources?: SourceItem[];
  answer?: string;
  history_id?: number;
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState("");
  const [uploading, setUploading] = useState(false);
  const [documents, setDocuments] = useState<DocItem[]>([]);
  const [reasoningOpen, setReasoningOpen] = useState(true);
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
      /* backend optional at first paint */
    }
  };

  useEffect(() => {
    loadDocuments();
  }, [apiUrl]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const patchAssistant = (patch: Partial<Message>) => {
    setMessages((prev) => {
      const next = [...prev];
      const last = next[next.length - 1];
      if (!last || last.role !== "assistant") return prev;
      next[next.length - 1] = { ...last, ...patch };
      return next;
    });
  };

  const appendReasoning = (text: string) => {
    setMessages((prev) => {
      const next = [...prev];
      const last = next[next.length - 1];
      if (!last || last.role !== "assistant") return prev;
      next[next.length - 1] = {
        ...last,
        reasoning: [...(last.reasoning || []), text],
      };
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

  const handleSendMessage = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const question = input.trim();
    setInput("");
    setLoading(true);
    setReasoningOpen(true);
    setMessages((prev) => [
      ...prev,
      { role: "user", content: question },
      {
        role: "assistant",
        content: "",
        reasoning: [],
        sources: [],
        streaming: true,
      },
    ]);

    try {
      const res = await fetch(`${apiUrl}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      if (!res.ok || !res.body) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Erreur serveur (${res.status})`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

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

          if (event.type === "reasoning" && event.text) {
            appendReasoning(event.text);
          } else if (event.type === "route" && event.route) {
            patchAssistant({ route: event.route });
          } else if (event.type === "sources" && event.sources) {
            patchAssistant({ sources: event.sources });
          } else if (event.type === "token" && event.text) {
            appendToken(event.text);
          } else if (event.type === "done") {
            patchAssistant({
              ...(event.answer != null ? { content: event.answer } : {}),
              ...(event.route ? { route: event.route } : {}),
              streaming: false,
            });
          } else if (event.type === "error") {
            throw new Error(event.text || "Erreur de stream");
          }
        }
      }

      patchAssistant({ streaming: false });
    } catch (error) {
      const detail =
        error instanceof Error
          ? error.message
          : "Erreur de communication avec le serveur.";
      patchAssistant({
        content: `**Erreur** — ${detail}`,
        streaming: false,
      });
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
    setUploadStatus("Indexation en cours… les gros PDF peuvent prendre 1–2 min.");

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
      <div className="mx-auto grid h-screen max-w-[1400px] overflow-hidden border-0 bg-[var(--panel)] shadow-[var(--shadow)] md:h-[calc(100vh-2rem)] md:grid-cols-[280px_1fr] md:rounded-xl md:border md:border-[var(--line)]">
        <aside className="flex flex-col border-b border-[var(--line)] bg-[var(--bg-elevated)] md:border-b-0 md:border-r">
          <div className="animate-rise border-b border-[var(--line)] px-5 py-5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[var(--accent)]">
              Enterprise AI
            </p>
            <h1
              className="mt-1.5 text-[1.65rem] leading-tight text-[var(--ink)]"
              style={{ fontFamily: "var(--font-display), Georgia, serif" }}
            >
              Copilot
            </h1>
            <p className="mt-2 text-[13px] leading-relaxed text-[var(--muted)]">
              Assistant documentaire professionnel — réponses sourcées, raisonnement
              visible en direct.
            </p>
          </div>

          <form onSubmit={handleUpload} className="space-y-3 px-5 py-4">
            <label className="block text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--muted)]">
              Base documentaire
            </label>
            <label className="flex cursor-pointer flex-col gap-1 rounded-lg border border-[var(--line)] bg-white px-3 py-3 transition hover:border-[var(--accent)]">
              <span className="truncate text-sm font-medium text-[var(--ink)]">
                {file ? file.name : "Importer PDF, TXT, MD, CSV, XLSX"}
              </span>
              <span className="text-[11px] text-[var(--muted)]">
                Indexation locale Chroma · citations fichier / lignes
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
              className="w-full rounded-lg bg-[var(--accent)] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[var(--accent-strong)] disabled:cursor-not-allowed disabled:opacity-45"
            >
              {uploading ? "Indexation…" : "Indexer"}
            </button>
            {uploadStatus && (
              <p className="rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-xs leading-relaxed text-[var(--muted)]">
                {uploadStatus}
              </p>
            )}
          </form>

          <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-4">
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
                  className="rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-xs"
                >
                  <div className="font-medium text-[var(--ink)]">{doc.filename}</div>
                  <div className="mt-0.5 text-[var(--muted)]">
                    {(doc.file_type || "file").toUpperCase()}
                    {doc.uploaded_at
                      ? ` · ${new Date(doc.uploaded_at).toLocaleString("fr-FR")}`
                      : ""}
                  </div>
                </li>
              ))}
            </ul>
          </div>
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
                Stream · raisonnement agent · sources citées
              </p>
            </div>
            <div className="flex items-center gap-2">
              {lastAssistant?.route && (
                <span className="rounded-md border border-[var(--line)] bg-[var(--accent-soft)] px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-[var(--accent-strong)]">
                  {lastAssistant.route}
                </span>
              )}
              <span className="inline-flex items-center gap-1.5 rounded-md border border-[var(--line)] bg-white px-2.5 py-1 text-[11px] font-medium text-[var(--muted)]">
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
                  Posez une question sur vos documents. L’agent affiche son
                  raisonnement en direct, puis la réponse avec les fichiers et
                  lignes utilisés.
                </p>
                <div className="mt-6 flex flex-wrap gap-2">
                  {suggestions.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => setInput(s)}
                      className="rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-left text-xs font-medium text-[var(--ink)] transition hover:border-[var(--accent)] hover:bg-[var(--accent-soft)]"
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
                    <div className="max-w-[min(36rem,92%)] rounded-xl rounded-br-sm bg-[var(--user)] px-4 py-3 text-sm leading-relaxed text-white">
                      {msg.content}
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {(msg.reasoning?.length || 0) > 0 && (
                        <div className="overflow-hidden rounded-lg border border-[var(--line)] bg-[var(--reason-bg)]">
                          <button
                            type="button"
                            onClick={() => setReasoningOpen((v) => !v)}
                            className="flex w-full items-center justify-between px-3.5 py-2.5 text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--muted)]"
                          >
                            <span>Raisonnement de l’agent</span>
                            <span>{reasoningOpen ? "Masquer" : "Afficher"}</span>
                          </button>
                          {reasoningOpen && (
                            <ol className="reason-scroll max-h-48 space-y-2 overflow-y-auto border-t border-[var(--line)] px-3.5 py-3">
                              {msg.reasoning!.map((step, i) => (
                                <li
                                  key={`${index}-r-${i}`}
                                  className="flex gap-2.5 text-[13px] leading-snug text-[var(--ink)]"
                                >
                                  <span className="mt-0.5 shrink-0 font-mono text-[10px] font-bold text-[var(--accent)]">
                                    {String(i + 1).padStart(2, "0")}
                                  </span>
                                  <span className="md-body !text-[13px]">
                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                      {step}
                                    </ReactMarkdown>
                                  </span>
                                </li>
                              ))}
                              {msg.streaming && !msg.content && (
                                <li className="flex items-center gap-1.5 text-xs text-[var(--muted)]">
                                  <span className="thinking-dot" />
                                  <span className="thinking-dot" />
                                  <span className="thinking-dot" />
                                  <span className="ml-1">Réflexion en cours…</span>
                                </li>
                              )}
                            </ol>
                          )}
                        </div>
                      )}

                      {(msg.content || msg.streaming) && (
                        <div
                          className={`rounded-xl border border-[var(--line)] bg-white px-4 py-3.5 shadow-sm ${
                            msg.streaming ? "stream-cursor" : ""
                          }`}
                        >
                          <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--accent)]">
                            Réponse
                          </div>
                          <div className="md-body">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {msg.content || "_…_"}
                            </ReactMarkdown>
                          </div>
                        </div>
                      )}

                      {(msg.sources?.length || 0) > 0 && (
                        <div className="rounded-xl border border-[var(--line)] bg-white px-4 py-3">
                          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--muted)]">
                            Sources
                          </p>
                          <ul className="mt-2 space-y-2">
                            {msg.sources!.map((s, i) => (
                              <li
                                key={`${index}-s-${i}`}
                                className="rounded-lg border border-[var(--line)] bg-[var(--bg-elevated)] px-3 py-2"
                              >
                                <div className="flex flex-wrap items-baseline justify-between gap-2">
                                  <span className="text-sm font-semibold text-[var(--ink)]">
                                    {s.filename}
                                  </span>
                                  <span className="text-[11px] font-medium text-[var(--accent-strong)]">
                                    {s.type === "direct"
                                      ? "DIRECT"
                                      : s.type === "tool"
                                        ? "TOOL / MCP"
                                        : "RAG"}
                                  </span>
                                </div>
                                <p className="mt-0.5 text-xs text-[var(--muted)]">
                                  {s.location || s.label || "Source"}
                                </p>
                                {s.snippet && (
                                  <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-[var(--muted)]">
                                    {s.snippet}
                                  </p>
                                )}
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
                className="flex-1 rounded-lg border border-[var(--line)] bg-white px-4 py-3 text-sm text-[var(--ink)] outline-none transition focus:border-[var(--accent)]"
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className="rounded-lg bg-[var(--accent)] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[var(--accent-strong)] disabled:cursor-not-allowed disabled:opacity-45"
              >
                {loading ? "…" : "Envoyer"}
              </button>
            </div>
          </form>
        </section>
      </div>
    </main>
  );
}
