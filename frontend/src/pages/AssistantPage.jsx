import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import clsx from "clsx";
import { api } from "../api/client";
import { Badge, Card, Input, Spinner } from "../components/ui";
import Icon from "../components/Icon";
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
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4">
      {events.map((ev) => {
        const sev = SEVERITY_META[ev.severity] || SEVERITY_META.LOW;
        return (
          <button
            key={ev.id}
            onClick={() => navigate("/events")}
            className="bg-surface/50 border border-white/10 rounded-xl overflow-hidden hover:border-primary/30 hover:bg-surface-container transition-all group flex flex-col text-left"
          >
            <div className="h-24 relative overflow-hidden bg-surface-container-high flex items-center justify-center">
              {ev.thumbnail_path ? (
                <img
                  src={api.events.thumbnailUrl(ev.id)}
                  alt=""
                  className="absolute inset-0 w-full h-full object-cover transition-transform duration-500 group-hover:scale-105 opacity-70"
                />
              ) : (
                <Icon name="videocam" className="text-on-surface-variant/40 text-3xl" />
              )}
              <div className="absolute inset-0 bg-gradient-to-t from-background to-transparent" />
              <div className={clsx("absolute top-2 left-2 text-[10px] font-bold px-2 py-0.5 rounded flex items-center gap-1 backdrop-blur-md border", sev.badge)}>
                <Icon name="warning" className="text-[12px]" /> {sev.label} Risk
              </div>
            </div>
            <div className="p-3">
              <h4 className="font-semibold text-on-surface text-sm mb-1 truncate">{eventTypeLabel(ev.event_type)}</h4>
              <div className="flex justify-between items-center text-xs text-on-surface-variant">
                <span className="flex items-center gap-1 truncate">
                  <Icon name="videocam" className="text-[14px]" /> {ev.camera_id}
                </span>
                <span className="shrink-0">{formatDateTime(ev.started_at)}</span>
              </div>
            </div>
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
    <div className="w-full max-w-5xl mx-auto h-[calc(100vh-8rem)] flex flex-col animate-fade-up">
      <Card className="flex-1 flex flex-col overflow-hidden relative">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-3/4 h-32 bg-primary/5 blur-[100px] rounded-full pointer-events-none" />

        {/* Başlık */}
        <div className="px-6 py-4 border-b border-white/5 flex items-center justify-between bg-surface/40 z-10 flex-wrap gap-2">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center border border-primary/20">
              <Icon name="robot_2" filled className="text-primary text-xl" />
            </div>
            <div>
              <h2 className="font-headline font-semibold text-on-surface text-lg tracking-tight">Güvenlik Asistanı</h2>
              <p className="text-xs text-on-surface-variant flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-primary inline-block animate-pulse" />
                Olay veritabanına doğal dille soru sorun
              </p>
            </div>
          </div>
          <Badge className={status?.llm_loaded ? "bg-tertiary/20 text-tertiary border-tertiary/30" : "bg-primary/20 text-primary border-primary/30"}>
            {status?.llm_loaded ? "Gemma AI" : "Hızlı Mod"}
          </Badge>
        </div>

        {/* Mesajlar */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 flex flex-col gap-6 z-10">
          {messages.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-center">
              <div className="w-14 h-14 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center mb-4">
                <Icon name="robot_2" filled className="text-primary text-2xl" />
              </div>
              <p className="text-sm font-semibold text-on-surface">Size nasıl yardımcı olabilirim?</p>
              <p className="text-xs text-on-surface-variant mt-1 mb-5 max-w-sm">
                Olaylar, riskler ve günlük durum hakkında Türkçe soru sorabilirsiniz.
              </p>
              <div className="flex flex-wrap justify-center gap-2 max-w-md">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="bg-surface border border-white/5 text-on-surface-variant text-xs py-2 px-4 rounded-full hover:bg-primary/10 hover:text-primary hover:border-primary/30 transition-all"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={clsx("flex gap-4 max-w-[85%]", m.role === "user" && "self-end flex-row-reverse")}>
              <div
                className={clsx(
                  "w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center border mt-1",
                  m.role === "user"
                    ? "bg-primary-container border-primary/30 text-xs font-bold text-on-primary-container"
                    : "bg-primary/10 border-primary/20"
                )}
              >
                {m.role === "user" ? "FK" : <Icon name="robot_2" filled className="text-primary text-sm" />}
              </div>
              <div className={clsx("flex flex-col gap-1 w-full", m.role === "user" && "items-end")}>
                <span className={clsx("text-xs text-on-surface-variant", m.role === "user" ? "mr-1" : "ml-1")}>
                  {m.role === "user" ? "Siz" : "Güvenlik Asistanı"}
                </span>
                <div
                  className={clsx(
                    "backdrop-blur-md border rounded-2xl p-4 text-sm leading-relaxed w-full",
                    m.role === "user"
                      ? "bg-primary/15 border-primary/20 rounded-tr-sm text-on-surface"
                      : m.error
                        ? "bg-error/10 border-error/20 rounded-tl-sm text-error"
                        : "bg-surface-variant/40 border-white/5 rounded-tl-sm text-on-surface"
                  )}
                >
                  <p className="whitespace-pre-line">{m.text}</p>
                  {m.role === "assistant" && <AnswerEvents events={m.events} />}
                </div>
              </div>
            </div>
          ))}

          {queryMutation.isPending && (
            <div className="flex gap-4">
              <div className="w-8 h-8 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center shrink-0">
                <Icon name="robot_2" filled className="text-primary text-sm" />
              </div>
              <div className="bg-surface-variant/40 border border-white/5 rounded-2xl rounded-tl-sm px-4 py-3">
                <Spinner className="text-base" />
              </div>
            </div>
          )}
        </div>

        {/* Giriş & öneriler */}
        <div className="p-4 bg-surface/80 backdrop-blur-2xl border-t border-white/5 z-20">
          {messages.length > 0 && (
            <div className="flex overflow-x-auto gap-2 pb-4 no-scrollbar">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="flex-shrink-0 bg-surface border border-white/5 text-on-surface-variant text-xs py-2 px-4 rounded-full hover:bg-primary/10 hover:text-primary hover:border-primary/30 transition-all whitespace-nowrap"
                >
                  {s}
                </button>
              ))}
            </div>
          )}
          <form
            onSubmit={(e) => { e.preventDefault(); send(); }}
            className="bg-background border border-white/10 rounded-2xl p-1.5 flex items-end gap-2 focus-within:border-primary/30 transition-all"
          >
            <div className="flex-1 relative min-h-[44px] flex items-center">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Sorunuzu yazın... (ör. Dün kaç KKD ihlali oldu?)"
                maxLength={500}
                className="w-full !bg-transparent !border-none focus:!ring-0 py-3"
              />
            </div>
            <button
              type="submit"
              disabled={!input.trim() || queryMutation.isPending}
              className="p-2.5 bg-primary/10 text-primary hover:bg-primary/20 rounded-xl transition-colors border border-primary/20 disabled:opacity-40 shrink-0 mb-0.5 mr-0.5"
            >
              <Icon name="send" filled />
            </button>
          </form>
          <p className="text-center text-[10px] text-on-surface-variant/50 mt-3">
            AI Asistan bazen hatalı bilgiler verebilir. Önemli kararlar almadan önce olay kayıtlarını doğrulayın.
          </p>
        </div>
      </Card>
    </div>
  );
}
