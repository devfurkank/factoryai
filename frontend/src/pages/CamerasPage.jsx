import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { Cctv, Plus, Pencil, Webcam, Globe, MapPin } from "lucide-react";
import { api } from "../api/client";
import { Badge, Button, Card, EmptyState, Input, Modal, Select, Spinner } from "../components/ui";

const EMPTY_FORM = {
  id: "", name: "", source_type: "webcam", source_url: "",
  device_index: 0, location: "", fps_limit: 8,
};

function CameraFormModal({ open, onClose, initial }) {
  const isEdit = Boolean(initial);
  const [form, setForm] = useState(initial || EMPTY_FORM);
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (body) =>
      isEdit ? api.cameras.update(body.id, body) : api.cameras.add(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cameras"] });
      queryClient.invalidateQueries({ queryKey: ["cameras-status"] });
      onClose();
    },
  });

  const set = (key) => (e) =>
    setForm((f) => ({
      ...f,
      [key]: e.target.type === "number" ? Number(e.target.value) : e.target.value,
    }));

  const submit = (e) => {
    e.preventDefault();
    const body = {
      ...form,
      source_url: form.source_type === "rtsp" ? form.source_url : null,
      is_active: true,
    };
    mutation.mutate(body);
  };

  return (
    <Modal open={open} onClose={onClose} title={isEdit ? "Kamerayı Düzenle" : "Yeni Kamera Ekle"}>
      <form onSubmit={submit} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-medium text-ink-faint">Kamera ID</label>
            <Input
              value={form.id} onChange={set("id")} placeholder="cam_depo_01"
              required disabled={isEdit} pattern="[a-zA-Z0-9_-]+"
              title="Yalnızca harf, rakam, tire ve alt çizgi"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-medium text-ink-faint">Ad</label>
            <Input value={form.name} onChange={set("name")} placeholder="Depo Kamerası" required />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-medium text-ink-faint">Kaynak Türü</label>
            <Select value={form.source_type} onChange={set("source_type")}>
              <option value="webcam">Webcam (yerel)</option>
              <option value="rtsp">RTSP (IP kamera)</option>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-medium text-ink-faint">Konum</label>
            <Input value={form.location} onChange={set("location")} placeholder="Üretim Alanı A" />
          </div>
        </div>

        {form.source_type === "rtsp" ? (
          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-medium text-ink-faint">RTSP URL</label>
            <Input
              value={form.source_url || ""} onChange={set("source_url")}
              placeholder="rtsp://kullanici:sifre@192.168.1.10:554/stream" required
            />
          </div>
        ) : (
          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-medium text-ink-faint">Cihaz İndeksi</label>
            <Input type="number" min={0} max={9} value={form.device_index} onChange={set("device_index")} />
          </div>
        )}

        <div className="flex flex-col gap-1 w-1/2">
          <label className="text-[11px] font-medium text-ink-faint">FPS Limiti</label>
          <Input type="number" min={1} max={30} value={form.fps_limit} onChange={set("fps_limit")} />
        </div>

        {mutation.isError && (
          <p className="text-xs text-rose-600">Kaydetme başarısız: {mutation.error.message}</p>
        )}

        <div className="flex justify-end gap-2 pt-2 border-t border-line">
          <Button type="button" variant="secondary" onClick={onClose}>Vazgeç</Button>
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending && <Spinner className="w-4 h-4 text-white" />}
            {isEdit ? "Kaydet" : "Ekle"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export default function CamerasPage() {
  const [modal, setModal] = useState(null); // null | {} (yeni) | camera (düzenle)

  const { data: cameras = [], isLoading } = useQuery({
    queryKey: ["cameras"],
    queryFn: api.cameras.list,
  });
  const { data: statuses = [] } = useQuery({
    queryKey: ["cameras-status"],
    queryFn: api.cameras.allStatus,
    refetchInterval: 5000,
  });
  const statusMap = Object.fromEntries((statuses || []).map((s) => [s.camera_id, s]));

  return (
    <div className="space-y-4 animate-fade-up">
      <div className="flex items-center justify-between">
        <p className="text-sm text-ink-soft">
          <span className="font-semibold text-ink">{cameras.length}</span> kayıtlı kamera
        </p>
        <Button onClick={() => setModal({ isNew: true })}>
          <Plus className="w-4 h-4" /> Kamera Ekle
        </Button>
      </div>

      <Card className="overflow-hidden">
        {isLoading ? (
          <div className="flex justify-center py-16"><Spinner /></div>
        ) : cameras.length === 0 ? (
          <EmptyState icon={Cctv} title="Kayıtlı kamera yok" hint="Kamera Ekle ile başlayın." />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line bg-slate-50/60">
                <th className="text-left font-medium text-ink-faint text-xs px-5 py-3">Kamera</th>
                <th className="text-left font-medium text-ink-faint text-xs px-4 py-3 hidden md:table-cell">Kaynak</th>
                <th className="text-left font-medium text-ink-faint text-xs px-4 py-3 hidden lg:table-cell">Konum</th>
                <th className="text-left font-medium text-ink-faint text-xs px-4 py-3">Durum</th>
                <th className="text-left font-medium text-ink-faint text-xs px-4 py-3 hidden sm:table-cell">FPS</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {cameras.map((cam) => {
                const status = statusMap[cam.id];
                const online = status?.is_connected;
                return (
                  <tr key={cam.id} className="border-b border-line last:border-0 hover:bg-slate-50/80 transition-colors">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        <div className={clsx(
                          "w-9 h-9 rounded-xl flex items-center justify-center shrink-0",
                          online ? "bg-emerald-50 text-emerald-600" : "bg-slate-100 text-slate-400"
                        )}>
                          <Cctv className="w-4.5 h-4.5 w-5 h-5" />
                        </div>
                        <div className="min-w-0">
                          <p className="font-medium text-ink truncate">{cam.name}</p>
                          <p className="text-[11px] text-ink-faint">{cam.id}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 hidden md:table-cell">
                      <Badge className="bg-slate-100 text-slate-600 ring-slate-200">
                        {cam.source_type === "rtsp"
                          ? <><Globe className="w-3 h-3" /> RTSP</>
                          : <><Webcam className="w-3 h-3" /> Webcam</>}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-ink-soft hidden lg:table-cell">
                      <span className="flex items-center gap-1">
                        <MapPin className="w-3.5 h-3.5 text-ink-faint" />
                        {cam.location || "—"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <Badge className={online
                        ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
                        : "bg-rose-50 text-rose-700 ring-rose-200"}>
                        <span className={clsx("w-1.5 h-1.5 rounded-full", online ? "bg-emerald-500" : "bg-rose-500")} />
                        {online ? "Bağlı" : "Bağlantı yok"}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-ink-soft tabular-nums hidden sm:table-cell">
                      {online ? status.fps.toFixed(1) : "—"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button variant="ghost" size="sm" onClick={() => setModal(cam)}>
                        <Pencil className="w-3.5 h-3.5" /> Düzenle
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>

      {modal && (
        <CameraFormModal
          open
          onClose={() => setModal(null)}
          initial={modal.isNew ? null : modal}
        />
      )}
    </div>
  );
}
