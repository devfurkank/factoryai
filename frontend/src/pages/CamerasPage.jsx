import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { api } from "../api/client";
import { Badge, Button, Card, EmptyState, Input, Modal, Select, Spinner } from "../components/ui";
import Icon from "../components/Icon";

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
            <label className="text-xs font-medium text-on-surface-variant">Kamera ID</label>
            <Input
              value={form.id} onChange={set("id")} placeholder="cam_depo_01"
              required disabled={isEdit} pattern="[a-zA-Z0-9_-]+"
              title="Yalnızca harf, rakam, tire ve alt çizgi"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-on-surface-variant">Ad</label>
            <Input value={form.name} onChange={set("name")} placeholder="Depo Kamerası" required />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-on-surface-variant">Kaynak Türü</label>
            <Select value={form.source_type} onChange={set("source_type")}>
              <option value="webcam">Webcam (yerel)</option>
              <option value="rtsp">RTSP (IP kamera)</option>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-on-surface-variant">Konum</label>
            <Input value={form.location} onChange={set("location")} placeholder="Üretim Alanı A" />
          </div>
        </div>

        {form.source_type === "rtsp" ? (
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-on-surface-variant">RTSP URL</label>
            <Input
              value={form.source_url || ""} onChange={set("source_url")}
              placeholder="rtsp://kullanici:sifre@192.168.1.10:554/stream" required
            />
          </div>
        ) : (
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-on-surface-variant">Cihaz İndeksi</label>
            <Input type="number" min={0} max={9} value={form.device_index} onChange={set("device_index")} />
          </div>
        )}

        <div className="flex flex-col gap-1 w-1/2">
          <label className="text-xs font-medium text-on-surface-variant">FPS Limiti</label>
          <Input type="number" min={1} max={30} value={form.fps_limit} onChange={set("fps_limit")} />
        </div>

        {mutation.isError && (
          <p className="text-xs text-error">Kaydetme başarısız: {mutation.error.message}</p>
        )}

        <div className="flex justify-end gap-2 pt-2 border-t border-primary/10">
          <Button type="button" variant="secondary" onClick={onClose}>Vazgeç</Button>
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending && <Spinner className="text-sm" />}
            {isEdit ? "Kaydet" : "Ekle"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export default function CamerasPage() {
  const [modal, setModal] = useState(null); // null | {isNew:true} | camera (düzenle)

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
    <div className="space-y-8 animate-fade-up">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h2 className="text-3xl font-headline font-semibold tracking-tight text-on-surface mb-2">Kamera Envanteri</h2>
          <p className="text-on-surface-variant">
            <span className="font-semibold text-on-surface">{cameras.length}</span> kayıtlı kamera
          </p>
        </div>
        <Button onClick={() => setModal({ isNew: true })} className="!px-6 !py-3">
          <Icon name="add" className="text-sm" /> Yeni Kamera Ekle
        </Button>
      </div>

      <Card className="overflow-hidden">
        {isLoading ? (
          <div className="flex justify-center py-16"><Spinner /></div>
        ) : cameras.length === 0 ? (
          <EmptyState icon="videocam" title="Kayıtlı kamera yok" hint="Kamera Ekle ile başlayın." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-primary/10 text-on-surface-variant font-medium text-sm">
                  <th className="py-4 px-6">Durum</th>
                  <th className="py-4 px-6">ID</th>
                  <th className="py-4 px-6">Kamera Adı</th>
                  <th className="py-4 px-6">Tür</th>
                  <th className="py-4 px-6">Konum</th>
                  <th className="py-4 px-6">FPS</th>
                  <th className="py-4 px-6 text-right">İşlem</th>
                </tr>
              </thead>
              <tbody className="text-sm divide-y divide-primary/5">
                {cameras.map((cam) => {
                  const status = statusMap[cam.id];
                  const online = status?.is_connected;
                  return (
                    <tr key={cam.id}>
                      <td className="py-4 px-6">
                        <div className="flex items-center gap-2">
                          <span className={clsx("w-2 h-2 rounded-full", online ? "bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.5)]" : "bg-error shadow-[0_0_10px_rgba(255,107,107,0.5)]")} />
                          <span className={clsx("text-xs", online ? "text-emerald-400/90" : "text-error/90")}>
                            {online ? "Çevrimiçi" : "Çevrimdışı"}
                          </span>
                        </div>
                      </td>
                      <td className="py-4 px-6 text-on-surface-variant font-mono text-xs">{cam.id}</td>
                      <td className="py-4 px-6 font-medium text-on-surface">{cam.name}</td>
                      <td className="py-4 px-6 text-on-surface-variant">
                        <Badge className="bg-surface-container text-on-surface-variant border-outline-variant/30">
                          <Icon name={cam.source_type === "rtsp" ? "public" : "videocam"} className="text-[13px]" />
                          {cam.source_type === "rtsp" ? "RTSP" : "Webcam"}
                        </Badge>
                      </td>
                      <td className="py-4 px-6 text-on-surface-variant">{cam.location || "—"}</td>
                      <td className="py-4 px-6 text-on-surface-variant tabular-nums">{online ? status.fps.toFixed(1) : "—"}</td>
                      <td className="py-4 px-6 text-right">
                        <button
                          onClick={() => setModal(cam)}
                          className="text-on-surface-variant hover:text-primary transition-colors p-2 rounded-lg hover:bg-primary/10"
                          title="Düzenle"
                        >
                          <Icon name="edit" className="text-[20px]" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
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
