"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Message {
  role: "user" | "assistant";
  content: string;
  route?: string;
}

interface DocItem {
  id: number;
  filename: string;
  file_type?: string;
  uploaded_at?: string | null;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState("");
  const [uploading, setUploading] = useState(false);
  const [documents, setDocuments] = useState<DocItem[]>([]);
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

  const handleSendMessage = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage: Message = { role: "user", content: input.trim() };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${apiUrl}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: userMessage.content }),
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || `Erreur serveur (${res.status})`);
      }

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer || "_Aucune réponse générée._",
          route: data.route_pris,
        },
      ]);
    } catch (error) {
      const detail =
        error instanceof Error
          ? error.message
          : "Erreur de communication avec le serveur.";
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `**Erreur** — ${detail}` },
      ]);
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

  return (
    <main className="min-h-screen px-3 py-3 md:px-6 md:py-5">
      <div className="mx-auto grid h-[calc(100vh-1.5rem)] max-w-7xl overflow-hidden rounded-[28px] border border-[var(--line)] bg-[color-mix(in_srgb,var(--bg-elevated)_88%,transparent)] shadow-[var(--shadow)] backdrop-blur-sm md:h-[calc(100vh-2.5rem)] md:grid-cols-[300px_1fr]">
        <aside className="flex flex-col border-b border-[var(--line)] bg-white/70 p-5 md:border-b-0 md:border-r">
          <div className="animate-rise">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--accent)]">
              Knowledge workspace
            </p>
            <h1
              className="mt-2 text-3xl leading-none text-[var(--ink)]"
              style={{ fontFamily: "var(--font-display), Georgia, serif" }}
            >
              Enterprise Copilot
            </h1>
            <p className="mt-3 text-sm leading-relaxed text-[var(--muted)]">
              Interrogez vos PDF, politiques RH et rapports financiers via RAG +
              agents MCP.
            </p>
          </div>

          <form onSubmit={handleUpload} className="mt-8 space-y-3">
            <label className="block text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--muted)]">
              Ajouter un document
            </label>
            <label className="flex cursor-pointer flex-col gap-2 rounded-2xl border border-dashed border-[var(--line)] bg-[var(--bg)] px-4 py-4 transition hover:border-[var(--accent)] hover:bg-[var(--accent-soft)]">
              <span className="text-sm font-semibold text-[var(--ink)]">
                {file ? file.name : "Choisir PDF / TXT / MD / CSV / XLSX"}
              </span>
              <span className="text-xs text-[var(--muted)]">
                Glissez un fichier ou cliquez pour parcourir
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
              className="w-full rounded-xl bg-[var(--accent)] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[var(--accent-strong)] disabled:cursor-not-allowed disabled:bg-[#9bb5ac]"
            >
              {uploading ? "Indexation…" : "Uploader & indexer"}
            </button>
            {uploadStatus && (
              <p className="rounded-xl border border-[var(--line)] bg-white px-3 py-2 text-xs leading-relaxed text-[var(--muted)]">
                {uploadStatus}
              </p>
            )}
          </form>

          <div className="mt-6 min-h-0 flex-1 overflow-y-auto">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--muted)]">
              Corpus indexé
            </p>
            <ul className="space-y-2">
              {documents.length === 0 && (
                <li className="text-xs text-[var(--muted)]">Aucun document listé.</li>
              )}
              {documents.map((doc) => (
                <li
                  key={doc.id}
                  className="rounded-xl border border-[var(--line)] bg-white px-3 py-2 text-xs text-[var(--ink)]"
                >
                  <div className="font-semibold">{doc.filename}</div>
                  <div className="mt-1 text-[var(--muted)]">
                    {(doc.file_type || "file").toUpperCase()}
                    {doc.uploaded_at
                      ? ` · ${new Date(doc.uploaded_at).toLocaleString("fr-FR")}`
                      : ""}
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <p className="mt-4 border-t border-[var(--line)] pt-3 text-[11px] text-[var(--muted)]">
            FastAPI · LangGraph · RAG · MCP
          </p>
        </aside>

        <section className="flex min-h-0 flex-col bg-[color-mix(in_srgb,white_55%,transparent)]">
          <header className="flex items-center justify-between border-b border-[var(--line)] px-5 py-4">
            <div>
              <p
                className="text-lg text-[var(--ink)]"
                style={{ fontFamily: "var(--font-display), Georgia, serif" }}
              >
                Session documentaire
              </p>
              <p className="text-xs text-[var(--muted)]">
                Réponses grounded avec citations issues de vos fichiers
              </p>
            </div>
            <span className="inline-flex items-center gap-2 rounded-full border border-[var(--line)] bg-white px-3 py-1 text-xs font-semibold text-[var(--accent-strong)]">
              <span className="h-2 w-2 rounded-full bg-[var(--accent)]" />
              En ligne
            </span>
          </header>

          <div className="flex-1 space-y-4 overflow-y-auto px-4 py-5 md:px-6">
            {messages.length === 0 && (
              <div className="animate-rise mx-auto flex h-full max-w-xl flex-col justify-center">
                <h2
                  className="text-3xl text-[var(--ink)]"
                  style={{ fontFamily: "var(--font-display), Georgia, serif" }}
                >
                  Posez une question sur vos documents.
                </h2>
                <p className="mt-3 text-sm text-[var(--muted)]">
                  Exemples : chiffres IFRS, compétences d’un CV, politiques
                  internes.
                </p>
                <div className="mt-5 flex flex-wrap gap-2">
                  {suggestions.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => setInput(s)}
                      className="rounded-full border border-[var(--line)] bg-white px-3 py-1.5 text-xs font-medium text-[var(--ink)] transition hover:border-[var(--accent)] hover:bg-[var(--accent-soft)]"
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
                  className={`max-w-[min(42rem,92%)] rounded-2xl px-4 py-3 shadow-sm ${
                    msg.role === "user"
                      ? "rounded-br-md bg-[var(--user)] text-white"
                      : "rounded-bl-md border border-[var(--line)] bg-white"
                  }`}
                >
                  {msg.role === "user" ? (
                    <p className="whitespace-pre-wrap text-sm leading-relaxed">
                      {msg.content}
                    </p>
                  ) : (
                    <div className="md-body">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                  )}
                  {msg.route && (
                    <div className="mt-3 flex items-center justify-between border-t border-[var(--line)] pt-2 text-[10px] uppercase tracking-[0.12em] text-[var(--muted)]">
                      <span>Route</span>
                      <span className="rounded-md bg-[var(--accent-soft)] px-2 py-0.5 font-bold text-[var(--accent-strong)]">
                        {msg.route}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="inline-flex items-center gap-2 rounded-2xl border border-[var(--line)] bg-white px-4 py-3 text-sm text-[var(--muted)]">
                  <span className="thinking-dot" />
                  <span className="thinking-dot" />
                  <span className="thinking-dot" />
                  <span className="ml-1">Analyse du corpus…</span>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <form
            onSubmit={handleSendMessage}
            className="border-t border-[var(--line)] bg-white/80 p-4 backdrop-blur"
          >
            <div className="flex gap-3">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ex. Capitaux propres consolidés OCP 2023…"
                className="flex-1 rounded-2xl border border-[var(--line)] bg-[var(--bg)] px-4 py-3 text-sm text-[var(--ink)] outline-none transition focus:border-[var(--accent)] focus:bg-white"
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className="rounded-2xl bg-[var(--accent)] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[var(--accent-strong)] disabled:cursor-not-allowed disabled:bg-[#9bb5ac]"
              >
                Envoyer
              </button>
            </div>
          </form>
        </section>
      </div>
    </main>
  );
}
