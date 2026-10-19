"use client";

import { useState } from "react";

interface Message {
  role: "user" | "assistant";
  content: string;
  route?: string;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState("");

  const apiUrl = "http://127.0.0.1:8000";

  // Gérer l'envoi du message au backend FastAPI
  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${apiUrl}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: userMessage.content }),
      });

      const data = await res.json();
      const botMessage: Message = {
        role: "assistant",
        content: data.answer,
        route: data.route_pris,
      };
      setMessages((prev) => [...prev, botMessage]);
    } catch (error) {
      console.error(error);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "❌ Erreur de communication avec le serveur." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  // Gérer l'upload de documents
  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);
    setUploadStatus("Upload et indexation en cours...");

    try {
      const res = await fetch(`${apiUrl}/upload`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (res.ok) {
        setUploadStatus(`✅ Fichier ${data.filename} indexé avec succès !`);
        setFile(null);
      } else {
        setUploadStatus(`❌ Erreur : ${data.detail || "Échec de l'upload"}`);
      }
    } catch (error) {
      console.error(error);
      setUploadStatus("❌ Erreur réseau lors de l'upload.");
    }
  };

  return (
    <main className="flex h-screen bg-gray-900 text-white">
      {/* Sidebar - Upload de documents */}
      <aside className="w-80 bg-gray-800 p-6 flex flex-col justify-between border-r border-gray-700">
        <div>
          <h1 className="text-xl font-bold mb-4 text-blue-400">Enterprise Copilot</h1>
          <p className="text-sm text-gray-400 mb-6">
            Gérez vos documents internes et interagissez avec vos agents IA connectés en RAG et MCP.
          </p>

          <form onSubmit={handleUpload} className="space-y-4">
            <div>
              <label className="block text-xs uppercase text-gray-400 mb-2 font-semibold">
                Ajouter un document (PDF / TXT)
              </label>
              <input
                type="file"
                accept=".pdf,.txt,.md"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-700 cursor-pointer"
              />
            </div>
            <button
              type="submit"
              disabled={!file}
              className="w-full py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 rounded-md font-medium text-sm transition"
            >
              Uploader & Indexer
            </button>
          </form>

          {uploadStatus && (
            <p className="mt-4 text-xs bg-gray-900 p-3 rounded text-gray-300 border border-gray-700">
              {uploadStatus}
            </p>
          )}
        </div>

        <div className="text-xs text-gray-500 border-t border-gray-700 pt-4">
          Architecture Modulaire | FastAPI + LangGraph + MCP
        </div>
      </aside>

      {/* Zone de Chat principale */}
      <section className="flex-1 flex flex-col justify-between">
        {/* En-tête du chat */}
        <header className="p-4 bg-gray-800 border-b border-gray-700 flex justify-between items-center shadow-md">
          <span className="font-medium text-sm text-gray-300">Session active - Assistant d'Entreprise</span>
          <span className="text-xs bg-blue-900 text-blue-300 px-3 py-1 rounded-full border border-blue-700">
            En ligne
          </span>
        </header>

        {/* Liste des messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-gray-500">
              <p className="text-lg">Comment puis-je vous aider aujourd'hui ?</p>
              <p className="text-sm mt-1">Posez une question sur le système, demandez une analyse ou interrogez vos documents.</p>
            </div>
          )}

          {messages.map((msg, index) => (
            <div
              key={index}
              className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}
            >
              <div
                className={`max-w-xl p-4 rounded-xl text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white rounded-br-none"
                    : "bg-gray-800 text-gray-200 border border-gray-700 rounded-bl-none shadow-sm"
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
                {msg.route && (
                  <div className="mt-2 pt-2 border-t border-gray-700 flex justify-between items-center text-[10px] text-gray-400">
                    <span>Route empruntée :</span>
                    <span className="bg-gray-900 px-2 py-0.5 rounded text-blue-400 font-mono font-bold">
                      {msg.route}
                    </span>
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex items-start">
              <div className="bg-gray-800 text-gray-400 p-4 rounded-xl text-sm border border-gray-700 animate-pulse">
                L'agent réfléchit et exécute les outils nécessaires...
              </div>
            </div>
          )}
        </div>

        {/* Barre de saisie */}
        <form onSubmit={handleSendMessage} className="p-4 bg-gray-800 border-t border-gray-700 flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Posez votre question (ex: Quel est le statut du système ?)..."
            className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-blue-500 text-white"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 rounded-lg font-medium text-sm transition shadow"
          >
            Envoyer
          </button>
        </form>
      </section>
    </main>
  );
}