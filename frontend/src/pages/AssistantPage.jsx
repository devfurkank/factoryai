import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import clsx from "clsx";
import { Send, Sparkles, Bot, User, ChevronRight } from "lucide-react";
import { api } from "../api/client";
import { Badge, Card, Input, Spinner } from "../components/ui";
import { eventTypeLabel, formatDateTime, SEVERITY_META } from "../lib/format";

const SUGGESTIONS = [
  "Bugün kaç olay oldu?",
  "Yangın çıktı mı?",
  "Son 7 gün özeti",
  "En riskli olay hangisi?",
  "Dün KKD ihlali oldu mu?",
  "Kritik olaylar neler?",
];

function AnswerEvents({ events }) {
  const navigate = useNavigate();
  if (!events?.length) return null;
  return (
    <div className="mt-3 space-y-1.5">
      {events.map((ev) => {
        const sev = SEVERITY_META[ev.severity] || SEVERITY_META.LOW;
        return (
          <button
            key={ev.id}
            onClick={() => navigate("/events")}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg bg-white/70 border border-line hover:bg-white transition-colors text-left"
          >
            <span className={clsx("w-1.5 h-1.5 rounded-full shrink-0", sev.dot)} />
            <span className="text-xs font-medium text-ink truncate">
              {eventTypeLabel(ev.event_type)}
            </span>
            <span className="text-[11px] text-ink-faint ml-auto whitespace-nowrap">
              {ev.camera_id} · {formatDateTime(ev.started_at)}
            </span>
            <ChevronRight className="w-3.5 h-3.5 text-ink-faint shrink-0" />
          </button>
        );
      })}
    </div>
  );
}

export default function AssistantPage() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const scrollRef = useRef(null);

  const { data: status } = useQuery({
    queryKey: ["assistant-status"],
    queryFn: api.assistant.status,
  });

  const queryMutation = useMutation({
    mutationFn: api.assistant.query,
    onSuccess: (res) => {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: res.answer, events: res.events, total: res.total },
      ]);
    },
    onError: (err) => {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: `Üzgünüm, bir hata oluştu: ${err.message}`, error: true },
      ]);
    },
  });

  const send = (question) => {
    const q = (question ?? input).trim();
    if (!q || queryMutation.isPending) return;
    setMessages((prev) => [...prev, { role: "user", text: q }]);
    setInput("");
    queryMutation.mutate(q);
  };

  // Yeni mesajda en alta kaydır
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, queryMutation.isPending]);

  return (
    <div className="max-w-3xl mx-auto animate-fade-up">
      <Card className="flex flex-col" style={{ height: "calc(100vh - 8.5rem)" }}>
        {/* Başlık */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-line">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
              <Sparkles className="w-4.5 h-4.5 text-white w-5 h-5" />
            </div>
            <div>
              <p className="text-sm font-semibold text-ink">Güvenlik Asistanı</p>
              <p className="text-[11px] text-ink-faint">
                Olay veritabanına doğal dille soru sorun
              </p>
            </div>
          </div>
          <Badge
            className={
              status?.llm_loaded
                ? "bg-violet-50 text-violet-700 ring-violet-200"
                : "bg-slate-100 text-slate-600 ring-slate-200"
            }
          >
            {status?.llm_loaded ? "Gemma AI" : "Hızlı Mod"}
          </Badge>
        </div>

        {/* Mesajlar */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {messages.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-center">
              <div className="w-14 h-14 rounded-2xl bg-accent-soft flex items-center justify-center mb-4">
                <Bot className="w-7 h-7 text-accent" />
              </div>
              <p className="text-sm font-semibold text-ink">Size nasıl yardımcı olabilirim?</p>
              <p className="text-xs text-ink-faint mt-1 mb-5 max-w-sm">
                Olaylar, riskler ve günlük durum hakkında Türkçe soru sorabilirsiniz.
              </p>
              <div className="flex flex-wrap justify-center gap-2 max-w-md">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="px-3 py-1.5 rounded-full text-xs font-medium bg-slate-100 text-ink-soft hover:bg-accent-soft hover:text-accent-strong transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={clsx("flex gap-3", m.role === "user" && "flex-row-reverse")}>
              <div
                className={clsx(
                  "w-8 h-8 rounded-xl flex items-center justify-center shrink-0",
                  m.role === "user"
                    ? "bg-slate-200 text-slate-600"
                    : "bg-gradient-to-br from-indigo-500 to-violet-600 text-white"
                )}
              >
                {m.role === "user" ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>
              <div
                className={clsx(
                  "max-w-[80%] rounded-2xl px-4 py-3",
                  m.role === "user"
                    ? "bg-accent text-white rounded-tr-md"
                    : m.error
                      ? "bg-rose-50 border border-rose-100 rounded-tl-md"
                      : "bg-slate-50 border border-line rounded-tl-md"
                )}
              >
                <p
                  className={clsx(
                    "text-sm leading-relaxed whitespace-pre-line",
                    m.role === "user" ? "text-white" : m.error ? "text-rose-700" : "text-ink"
                  )}
                >
                  {m.text}
                </p>
                {m.role === "assistant" && <AnswerEvents events={m.events} />}
              </div>
            </div>
          ))}

          {queryMutation.isPending && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4 text-white" />
              </div>
              <div className="bg-slate-50 border border-line rounded-2xl rounded-tl-md px-4 py-3">
                <Spinner className="w-4 h-4" />
              </div>
            </div>
          )}
        </div>

        {/* Giriş alanı */}
        <div className="px-4 py-3 border-t border-line">
          <form
            onSubmit={(e) => { e.preventDefault(); send(); }}
            className="flex items-center gap-2"
          >
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Örn: Bugün kaç KKD ihlali oldu?"
              className="flex-1"
              maxLength={500}
            />
            <button
              type="submit"
              disabled={!input.trim() || queryMutation.isPending}
              className="w-10 h-10 rounded-xl bg-accent text-white flex items-center justify-center hover:bg-accent-strong transition-colors disabled:opacity-40 shrink-0"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </Card>
    </div>
  );
}
