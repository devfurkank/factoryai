import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { api } from "../api/client";
import { Badge, Button, Card, CardHeader, EmptyState, Input, Select, Spinner } from "../components/ui";
import Icon from "../components/Icon";
import PolygonEditor from "../components/zones/PolygonEditor";

/**
 * Alan İhlali — kamera görüntüsü üzerinde yasaklı alan (poligon) tanımlama.
 *
 * Akış: soldan kamera seç → canlı yayın üzerinde tıklayarak poligon çiz →
 * ad + risk seviyesi ver → "Koordinatları Kaydet". Koordinatlar normalize
 * (0-1) kaydedilir; arka planda AI insan tespiti yapar ve ayak noktası
 * poligona girdiği anda FORBIDDEN_ZONE_ENTRY olayı + alarm üretilir.
 */

const RISK_META = {
  low: { label: "Düşük", badge: "bg-green-500/15 text-green-400 border-green-500/30" },
  medium: { label: "Orta", badge: "bg-amber-500/15 text-amber-400 border-amber-500/30" },
  high: { label: "Yüksek", badge: "bg-error/15 text-error border-error/30" },
};

const round4 = (v) => Math.round(v * 10000) / 10000;

/** Poligon yeni (normalize, 0-1) formatta mı? Eski kayıtlar piksel olabilir. */
function isNormalizedPolygon(polygon) {
  return (
    Array.isArray(polygon) &&
    polygon.length >= 3 &&
    polygon.every((p) => p[0] >= 0 && p[0] <= 1 && p[1] >= 0 && p[1] <= 1)
  );
}

function CameraListItem({ camera, isOnline, isSelected, zoneCount, onSelect }) {
  return (
    <button
      onClick={onSelect}
      className={clsx(
        "w-full text-left px-3 py-2.5 rounded-lg border transition-colors flex items-center gap-3",
        isSelected
          ? "border-primary/40 bg-primary/10"
          : "border-transparent hover:bg-primary/5"
      )}
    >
      <span
        className={clsx(
          "w-2 h-2 rounded-full shrink-0",
          isOnline ? "bg-green-400 shadow-[0_0_6px_rgba(74,222,128,0.8)]" : "bg-error/70"
        )}
      />
      <div className="min-w-0 flex-1">
        <p className={clsx("text-sm truncate", isSelected ? "font-semibold text-primary" : "font-medium text-on-surface")}>
          {camera.name}
        </p>
        <p className="text-[10px] text-on-surface-variant uppercase tracking-wider truncate">
          {camera.location || camera.id}
        </p>
      </div>
      {zoneCount > 0 && (
        <span className="shrink-0 px-1.5 py-0.5 rounded text-[10px] font-bold bg-error/15 text-error border border-error/25">
          {zoneCount}
        </span>
      )}
    </button>
  );
}

function ZoneRow({ zone, onEdit, onToggle, onDelete, confirmingDelete, busy }) {
  const risk = RISK_META[zone.risk_level] || RISK_META.medium;
  return (
    <div
      className={clsx(
        "flex items-center gap-3 px-4 py-3 rounded-lg border bg-surface/40 transition-opacity",
        zone.is_active ? "border-outline-variant/40" : "border-outline-variant/20 opacity-60"
      )}
    >
      <Icon name="polyline" className={clsx("text-[18px]", zone.is_active ? "text-error" : "text-on-surface-variant")} />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-on-surface truncate">{zone.name}</p>
        <p className="text-[11px] text-on-surface-variant">
          {zone.polygon?.length || 0} köşe
          {!isNormalizedPolygon(zone.polygon) && " · eski format (piksel)"}
        </p>
      </div>
      <Badge className={risk.badge}>{risk.label}</Badge>
      {!zone.is_active && (
        <Badge className="bg-surface-container-highest text-on-surface-variant border-outline-variant">
          Pasif
        </Badge>
      )}
      <div className="flex items-center gap-1 shrink-0">
        <button
          onClick={onEdit}
          disabled={busy}
          title="Düzenle"
          className="p-1.5 rounded-lg text-on-surface-variant hover:bg-primary/10 hover:text-primary transition-colors disabled:opacity-40"
        >
          <Icon name="edit" className="text-[18px]" />
        </button>
        <button
          onClick={onToggle}
          disabled={busy}
          title={zone.is_active ? "Pasifleştir (izlemeyi durdur)" : "Aktifleştir"}
          className="p-1.5 rounded-lg text-on-surface-variant hover:bg-primary/10 hover:text-primary transition-colors disabled:opacity-40"
        >
          <Icon name={zone.is_active ? "pause_circle" : "play_circle"} className="text-[18px]" />
        </button>
        <button
          onClick={onDelete}
          disabled={busy}
          title="Sil"
          className={clsx(
            "p-1.5 rounded-lg transition-colors disabled:opacity-40 flex items-center gap-1",
            confirmingDelete
              ? "bg-error/20 text-error border border-error/40"
              : "text-on-surface-variant hover:bg-error/10 hover:text-error"
          )}
        >
          <Icon name="delete" className="text-[18px]" />
          {confirmingDelete && <span className="text-[10px] font-bold pr-1">Emin misiniz?</span>}
        </button>
      </div>
    </div>
  );
}

export default function ZonesPage() {
  const queryClient = useQueryClient();

  // ── Sunucu durumu ──────────────────────────────────────────────────────────
  const { data: cameras = [], isLoading: camerasLoading } = useQuery({
    queryKey: ["cameras"],
    queryFn: api.cameras.list,
    refetchInterval: 10000,
  });
  const { data: statuses = [] } = useQuery({
    queryKey: ["cameras-status"],
    queryFn: api.cameras.allStatus,
    refetchInterval: 5000,
  });
  const { data: zones = [], isLoading: zonesLoading } = useQuery({
    queryKey: ["zones"],
    queryFn: () => api.zones.list(null, true), // pasifler de listelensin
  });

  const statusMap = useMemo(
    () => Object.fromEntries((statuses || []).map((s) => [s.camera_id, s])),
    [statuses]
  );
  const zonesByCamera = useMemo(() => {
    const grouped = {};
    for (const z of zones) (grouped[z.camera_id] ||= []).push(z);
    return grouped;
  }, [zones]);

  // ── Editör durumu ──────────────────────────────────────────────────────────
  const [selectedId, setSelectedId] = useState(null);
  const [points, setPoints] = useState([]); // normalize [[x,y], ...]
  const [closed, setClosed] = useState(false);
  const [name, setName] = useState("");
  const [risk, setRisk] = useState("medium");
  const [editing, setEditing] = useState(null); // düzenlenen mevcut zone
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);
  const [notice, setNotice] = useState(null); // {text, tone}

  const selectedCamera = cameras.find((c) => c.id === selectedId) || null;
  const cameraZones = selectedId ? zonesByCamera[selectedId] || [] : [];
  const isOnline = !!statusMap[selectedId]?.is_connected;

  const flash = (text, tone = "success") => {
    setNotice({ text, tone });
    setTimeout(() => setNotice(null), 3000);
  };

  const resetEditor = () => {
    setPoints([]);
    setClosed(false);
    setName("");
    setRisk("medium");
    setEditing(null);
  };

  const selectCamera = (id) => {
    if (id === selectedId) return;
    setSelectedId(id);
    resetEditor();
    setConfirmDeleteId(null);
  };

  const handleDrawChange = (nextPoints, nextClosed) => {
    setPoints(nextPoints);
    setClosed(nextClosed);
  };

  const startEdit = (zone) => {
    setEditing(zone);
    setName(zone.name);
    setRisk(RISK_META[zone.risk_level] ? zone.risk_level : "medium");
    if (isNormalizedPolygon(zone.polygon)) {
      setPoints(zone.polygon.map((p) => [p[0], p[1]]));
      setClosed(true);
    } else {
      // Eski piksel-formatlı kayıt görüntüye oturtulamaz — yeniden çizilir
      setPoints([]);
      setClosed(false);
      flash("Bu alan eski (piksel) formatta — poligonu yeniden çizin.", "warn");
    }
  };

  // ── Mutasyonlar ────────────────────────────────────────────────────────────
  const invalidateZones = () => queryClient.invalidateQueries({ queryKey: ["zones"] });

  const saveMutation = useMutation({
    mutationFn: (body) =>
      body.id ? api.zones.update(body.id, body) : api.zones.create(body),
    onSuccess: () => {
      invalidateZones();
      const wasEditing = !!editing;
      resetEditor();
      flash(wasEditing ? "Alan güncellendi." : "Yasaklı alan kaydedildi — izleme aktif.");
    },
  });

  const toggleMutation = useMutation({
    mutationFn: (zone) => api.zones.update(zone.id, { ...zone, is_active: !zone.is_active }),
    onSuccess: invalidateZones,
  });

  const deleteMutation = useMutation({
    mutationFn: (id) => api.zones.remove(id),
    onSuccess: () => {
      invalidateZones();
      flash("Alan silindi.");
    },
  });

  const handleDelete = (zone) => {
    if (confirmDeleteId !== zone.id) {
      setConfirmDeleteId(zone.id);
      setTimeout(() => setConfirmDeleteId((cur) => (cur === zone.id ? null : cur)), 3000);
      return;
    }
    setConfirmDeleteId(null);
    if (editing?.id === zone.id) resetEditor();
    deleteMutation.mutate(zone.id);
  };

  const canSave = closed && points.length >= 3 && name.trim().length > 0 && !!selectedId;

  const handleSave = () => {
    if (!canSave) return;
    saveMutation.mutate({
      ...(editing ? { id: editing.id } : {}),
      camera_id: selectedId,
      name: name.trim(),
      zone_type: "forbidden",
      polygon: points.map(([x, y]) => [round4(x), round4(y)]),
      risk_level: risk,
      allowed_classes: [],
      rules: editing?.rules || {},
      is_active: editing ? editing.is_active : true,
    });
  };

  // ── Çizim durumu ipucu ─────────────────────────────────────────────────────
  const drawHint = closed
    ? "Alan kapatıldı — köşeleri sürükleyerek ince ayar yapabilirsiniz."
    : points.length > 0
      ? `${points.length} köşe eklendi — ilk noktaya tıklayarak veya çift tıklayarak alanı kapatın (en az 3 köşe). Esc / sağ tık: son köşeyi geri al.`
      : "Görüntü üzerine tıklayarak yasaklı alanın köşelerini ekleyin.";

  return (
    <div className="space-y-8 animate-fade-up">
      {/* Başlık */}
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-3xl font-headline font-bold text-on-surface mb-2 tracking-tight">
            Alan İhlali
          </h2>
          <p className="text-on-surface-variant text-sm">
            Kamera görüntüsü üzerinde yasaklı alanlar tanımlayın — AI, alana giren kişileri{" "}
            <span className="font-semibold text-on-surface">gerçek zamanlı</span> tespit edip alarm üretir.
          </p>
        </div>
        <p className="text-xs text-on-surface-variant hidden md:block">
          Koordinatlar çözünürlükten bağımsız (0-1 normalize) saklanır
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[300px_1fr] gap-6 items-start">
        {/* Kamera listesi */}
        <Card className="p-3">
          <div className="px-2 pt-1 pb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-on-surface flex items-center gap-2">
              <Icon name="videocam" className="text-primary text-[18px]" />
              Kameralar
            </h3>
            <span className="text-[11px] text-on-surface-variant">
              {(statuses || []).filter((s) => s.is_connected).length}/{cameras.length} yayında
            </span>
          </div>
          {camerasLoading ? (
            <div className="flex justify-center py-8">
              <Spinner />
            </div>
          ) : cameras.length === 0 ? (
            <EmptyState
              icon="videocam_off"
              title="Kayıtlı kamera yok"
              hint="Kameralar sayfasından yeni kamera ekleyebilirsiniz."
            />
          ) : (
            <div className="space-y-1">
              {cameras.map((cam) => (
                <CameraListItem
                  key={cam.id}
                  camera={cam}
                  isOnline={!!statusMap[cam.id]?.is_connected}
                  isSelected={cam.id === selectedId}
                  zoneCount={(zonesByCamera[cam.id] || []).filter((z) => z.is_active).length}
                  onSelect={() => selectCamera(cam.id)}
                />
              ))}
            </div>
          )}
        </Card>

        {/* Editör + kayıtlı alanlar */}
        <div className="space-y-6 min-w-0">
          <Card className="overflow-hidden">
            <div className="p-4 border-b border-primary/10 flex flex-wrap items-center justify-between gap-3 bg-surface/40">
              <div className="flex items-center gap-2">
                <Icon name="polyline" className="text-primary text-[20px]" />
                <div>
                  <h3 className="font-semibold text-sm text-on-surface">
                    {selectedCamera ? selectedCamera.name : "Poligon Çizim Aracı"}
                  </h3>
                  <p className="text-[11px] text-on-surface-variant">
                    {selectedCamera
                      ? editing
                        ? `Düzenleniyor: ${editing.name}`
                        : "Yeni yasaklı alan çizimi"
                      : "Başlamak için soldan bir kamera seçin"}
                  </p>
                </div>
              </div>
              {selectedCamera &&
                (isOnline ? (
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-green-500/20 text-green-400 border border-green-500/30">
                    CANLI
                  </span>
                ) : (
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-surface-container-highest text-on-surface-variant border border-outline-variant">
                    ÇEVRİMDIŞI
                  </span>
                ))}
            </div>

            {/* Video + çizim yüzeyi */}
            <div className="relative aspect-video bg-black/80 w-full overflow-hidden">
              {selectedCamera ? (
                <PolygonEditor
                  camera={selectedCamera}
                  points={points}
                  closed={closed}
                  onChange={handleDrawChange}
                />
              ) : (
                <div className="absolute inset-0 flex items-center justify-center">
                  <EmptyState
                    icon="highlight_alt"
                    title="Kamera seçilmedi"
                    hint="Canlı görüntü üzerinde alan çizebilmek için soldaki listeden bir kamera seçin."
                  />
                </div>
              )}
            </div>

            {selectedCamera && (
              <div className="p-4 space-y-3 border-t border-primary/10">
                {!isOnline && (
                  <p className="text-xs text-amber-400 flex items-center gap-1.5">
                    <Icon name="warning" className="text-[14px]" />
                    Kamera çevrimdışı — canlı görüntü yerine bekleme karesi gösteriliyor; çizim yine de kaydedilebilir.
                  </p>
                )}
                <p className="text-xs text-on-surface-variant flex items-center gap-1.5">
                  <Icon name="info" className="text-[14px] text-primary" />
                  {drawHint}
                </p>

                <div className="flex flex-wrap items-end gap-3">
                  <div className="flex-1 min-w-[180px]">
                    <label className="block text-[11px] font-medium text-on-surface-variant mb-1">
                      Alan adı
                    </label>
                    <Input
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="örn. Pres Makinesi Sahası"
                      className="w-full"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-medium text-on-surface-variant mb-1">
                      Risk seviyesi
                    </label>
                    <Select value={risk} onChange={(e) => setRisk(e.target.value)}>
                      <option value="low">Düşük</option>
                      <option value="medium">Orta</option>
                      <option value="high">Yüksek</option>
                    </Select>
                  </div>
                  <div className="flex items-center gap-2 ml-auto">
                    {editing && (
                      <Button variant="ghost" onClick={resetEditor}>
                        <Icon name="close" className="text-[16px]" />
                        Vazgeç
                      </Button>
                    )}
                    <Button
                      variant="secondary"
                      onClick={() => {
                        setPoints([]);
                        setClosed(false);
                      }}
                      disabled={points.length === 0}
                    >
                      <Icon name="ink_eraser" className="text-[16px]" />
                      Alanı Temizle
                    </Button>
                    <Button onClick={handleSave} disabled={!canSave || saveMutation.isPending}>
                      {saveMutation.isPending ? (
                        <Spinner className="text-[16px]" />
                      ) : (
                        <Icon name="save" className="text-[16px]" />
                      )}
                      Koordinatları Kaydet
                    </Button>
                  </div>
                </div>

                {/* Durum satırı: kayıt sonucu / doğrulama / hata */}
                <div className="min-h-[18px] text-xs">
                  {notice && (
                    <span
                      className={clsx(
                        "flex items-center gap-1.5",
                        notice.tone === "success" ? "text-green-400" : "text-amber-400"
                      )}
                    >
                      <Icon
                        name={notice.tone === "success" ? "check_circle" : "warning"}
                        className="text-[14px]"
                      />
                      {notice.text}
                    </span>
                  )}
                  {!notice && saveMutation.isError && (
                    <span className="text-error flex items-center gap-1.5">
                      <Icon name="error" className="text-[14px]" />
                      Kaydedilemedi: {saveMutation.error.message}
                    </span>
                  )}
                  {!notice && !saveMutation.isError && closed && !name.trim() && (
                    <span className="text-on-surface-variant">
                      Kaydetmek için alana bir ad verin.
                    </span>
                  )}
                </div>
              </div>
            )}
          </Card>

          {/* Kayıtlı alanlar */}
          {selectedCamera && (
            <Card>
              <CardHeader
                icon="fence"
                title="Kayıtlı Yasaklı Alanlar"
                subtitle={`${selectedCamera.name} · ${cameraZones.length} alan`}
              />
              <div className="px-5 pb-4 pt-2 space-y-2">
                {zonesLoading ? (
                  <div className="flex justify-center py-6">
                    <Spinner />
                  </div>
                ) : cameraZones.length === 0 ? (
                  <EmptyState
                    icon="polyline"
                    title="Bu kamera için tanımlı alan yok"
                    hint="Yukarıdaki canlı görüntü üzerine tıklayarak ilk yasaklı alanınızı çizin."
                  />
                ) : (
                  cameraZones.map((zone) => (
                    <ZoneRow
                      key={zone.id}
                      zone={zone}
                      busy={toggleMutation.isPending || deleteMutation.isPending}
                      confirmingDelete={confirmDeleteId === zone.id}
                      onEdit={() => startEdit(zone)}
                      onToggle={() => toggleMutation.mutate(zone)}
                      onDelete={() => handleDelete(zone)}
                    />
                  ))
                )}
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
