import { useCallback, useEffect, useRef, useState } from "react";
import Icon from "../Icon";

/**
 * Poligon Çizim Editörü — Alan İhlali sayfası.
 *
 * Seçilen kameranın canlı MJPEG tespit akışı üzerine, video içeriğiyle
 * birebir hizalanan (letterbox-duyarlı) bir SVG katmanı bindirir. Canvas
 * yerine SVG tercih edildi: köşe tutamaçlarında hazır hit-testing (sürükleme),
 * her DPI'da keskin çizim ve React state'inden deklaratif render — manuel
 * redraw döngüsü gerekmez.
 *
 * Etkileşim:
 *  - Tıkla → köşe ekle
 *  - İlk noktaya tıkla (≥3 köşe) veya çift tıkla → poligonu kapat
 *  - Esc / sağ tık → son köşeyi geri al
 *  - Köşeleri sürükleyerek ince ayar (kapalıyken tümü, açıkken ilk nokta hariç)
 *
 * Koordinatlar video çözünürlüğünden bağımsız olması için NORMALİZE edilir
 * (0-1 aralığı, örn. x: 0.45, y: 0.60) — kontrollü bileşen: `points`
 * ([[x,y], ...]) ve `closed` dışarıdan gelir, her değişiklik
 * `onChange(nextPoints, nextClosed)` ile yukarı bildirilir.
 */

// İlk noktaya bu piksel mesafesi içinde tıklanırsa poligon kapanır
const CLOSE_SNAP_PX = 14;

export default function PolygonEditor({ camera, points, closed, onChange, disabled = false }) {
  const containerRef = useRef(null);
  const imgRef = useRef(null);
  const svgRef = useRef(null);
  const dragIndexRef = useRef(null);
  const suppressClickRef = useRef(false);

  // Video içeriğinin container içindeki gerçek kapladığı alan (letterbox payı düşülmüş)
  const [rect, setRect] = useState(null);
  const [cursor, setCursor] = useState(null); // normalize [x, y] — cetvel + lastik bant

  const measure = useCallback(() => {
    const container = containerRef.current;
    const img = imgRef.current;
    if (!container || !img || !img.naturalWidth || !img.naturalHeight) return;
    const cw = container.clientWidth;
    const ch = container.clientHeight;
    if (!cw || !ch) return;
    const scale = Math.min(cw / img.naturalWidth, ch / img.naturalHeight);
    const width = img.naturalWidth * scale;
    const height = img.naturalHeight * scale;
    const next = { left: (cw - width) / 2, top: (ch - height) / 2, width, height };
    setRect((prev) =>
      prev &&
      Math.abs(prev.left - next.left) < 0.5 &&
      Math.abs(prev.top - next.top) < 0.5 &&
      Math.abs(prev.width - next.width) < 0.5 &&
      Math.abs(prev.height - next.height) < 0.5
        ? prev
        : next
    );
  }, []);

  // Kamera değişince içerik alanını yeniden ölç (çözünürlük farklı olabilir)
  useEffect(() => {
    setRect(null);
    setCursor(null);
  }, [camera?.id]);

  useEffect(() => {
    const ro = new ResizeObserver(measure);
    if (containerRef.current) ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, [measure]);

  // MJPEG akışlarında load olayı tarayıcıya göre değişebilir — ilk frame
  // gelene kadar kısa aralıklarla ölçmeyi dene (rect oluşunca durur)
  useEffect(() => {
    if (rect) return;
    const timer = setInterval(measure, 500);
    return () => clearInterval(timer);
  }, [rect, measure, camera?.id]);

  const toNorm = (e) => {
    const box = svgRef.current.getBoundingClientRect();
    const x = (e.clientX - box.left) / box.width;
    const y = (e.clientY - box.top) / box.height;
    return [Math.min(1, Math.max(0, x)), Math.min(1, Math.max(0, y))];
  };

  const closePolygon = () => {
    if (points.length >= 3) onChange(points, true);
  };

  const handleClick = (e) => {
    if (disabled || closed) return;
    if (suppressClickRef.current) {
      // Sürükleme veya köşe etkileşimi sonrası üretilen click'i yut
      suppressClickRef.current = false;
      return;
    }
    if (e.detail > 1) return; // çift tıklamanın 2. click'i — onDoubleClick kapatır
    onChange([...points, toNorm(e)], false);
  };

  const handleDoubleClick = () => {
    if (disabled || closed) return;
    closePolygon();
  };

  const handleContextMenu = (e) => {
    e.preventDefault(); // sağ tık = son köşeyi geri al
    if (disabled || closed) return;
    if (points.length > 0) onChange(points.slice(0, -1), false);
  };

  const handleVertexPointerDown = (index) => (e) => {
    if (disabled) return;
    e.stopPropagation();
    suppressClickRef.current = true;
    // Açık poligonda ilk nokta "kapat" düğmesi gibi davranır
    if (!closed && index === 0 && points.length >= 3) {
      closePolygon();
      return;
    }
    dragIndexRef.current = index;
    svgRef.current.setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e) => {
    const norm = toNorm(e);
    setCursor(norm);
    if (dragIndexRef.current !== null) {
      const next = points.slice();
      next[dragIndexRef.current] = norm;
      onChange(next, closed);
    }
  };

  const handlePointerUp = (e) => {
    if (dragIndexRef.current !== null) {
      dragIndexRef.current = null;
      if (svgRef.current.hasPointerCapture(e.pointerId)) {
        svgRef.current.releasePointerCapture(e.pointerId);
      }
    }
  };

  // Esc → son köşeyi geri al
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape" && !disabled && !closed && points.length > 0) {
        onChange(points.slice(0, -1), false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [points, closed, disabled, onChange]);

  // ── Render yardımcıları ──────────────────────────────────────────────────
  const px = ([x, y]) => [x * rect.width, y * rect.height];

  const nearFirst =
    rect &&
    !closed &&
    points.length >= 3 &&
    cursor &&
    Math.hypot(
      (cursor[0] - points[0][0]) * rect.width,
      (cursor[1] - points[0][1]) * rect.height
    ) <= CLOSE_SNAP_PX;

  // Kapalı poligon "yasak alan" hissi için error tonunda, çizim primary tonunda
  const strokeColor = closed ? "rgb(var(--color-error))" : "rgb(var(--color-primary))";
  const fillColor = closed ? "rgb(var(--color-error) / 0.20)" : "rgb(var(--color-primary) / 0.10)";

  return (
    <div ref={containerRef} className="relative w-full h-full">
      <img
        ref={imgRef}
        key={camera.id}
        src={`/api/detection/${camera.id}/stream`}
        alt={`${camera.name} canlı yayın`}
        draggable={false}
        onLoad={measure}
        className="w-full h-full object-contain select-none"
      />

      {rect && !disabled && (
        <svg
          ref={svgRef}
          className="absolute z-10"
          style={{
            left: rect.left,
            top: rect.top,
            width: rect.width,
            height: rect.height,
            touchAction: "none",
            cursor: closed ? "default" : "crosshair",
          }}
          viewBox={`0 0 ${rect.width} ${rect.height}`}
          onClick={handleClick}
          onDoubleClick={handleDoubleClick}
          onContextMenu={handleContextMenu}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerLeave={() => setCursor(null)}
        >
          {/* Kapalı poligon / açık polyline */}
          {points.length > 0 &&
            (closed ? (
              <polygon
                points={points.map((p) => px(p).join(",")).join(" ")}
                fill={fillColor}
                stroke={strokeColor}
                strokeWidth="2.5"
                strokeLinejoin="round"
              />
            ) : (
              <>
                {points.length >= 3 && (
                  <polygon
                    points={points.map((p) => px(p).join(",")).join(" ")}
                    fill={fillColor}
                    stroke="none"
                  />
                )}
                <polyline
                  points={points.map((p) => px(p).join(",")).join(" ")}
                  fill="none"
                  stroke={strokeColor}
                  strokeWidth="2.5"
                  strokeLinejoin="round"
                />
                {/* Lastik bant: son köşeden imlece */}
                {cursor && points.length > 0 && (
                  <line
                    x1={px(points[points.length - 1])[0]}
                    y1={px(points[points.length - 1])[1]}
                    x2={px(nearFirst ? points[0] : cursor)[0]}
                    y2={px(nearFirst ? points[0] : cursor)[1]}
                    stroke={strokeColor}
                    strokeWidth="1.5"
                    strokeDasharray="6 4"
                  />
                )}
              </>
            ))}

          {/* Köşe tutamaçları */}
          {points.map((p, i) => {
            const [cx, cy] = px(p);
            const isFirst = i === 0;
            const highlight = isFirst && (nearFirst || (!closed && points.length >= 3));
            return (
              <circle
                key={i}
                cx={cx}
                cy={cy}
                r={nearFirst && isFirst ? 9 : highlight ? 7 : 5.5}
                fill={highlight ? strokeColor : "rgb(var(--color-surface))"}
                stroke={strokeColor}
                strokeWidth="2"
                style={{
                  cursor:
                    !closed && isFirst && points.length >= 3
                      ? "pointer"
                      : "grab",
                }}
                onPointerDown={handleVertexPointerDown(i)}
              />
            );
          })}
        </svg>
      )}

      {/* Normalize koordinat cetveli */}
      {rect && cursor && !disabled && (
        <div className="absolute bottom-2 right-2 z-20 px-2 py-1 rounded bg-black/60 backdrop-blur-sm border border-white/10 text-[10px] font-mono text-on-surface pointer-events-none">
          x: {cursor[0].toFixed(2)} · y: {cursor[1].toFixed(2)}
        </div>
      )}

      {/* Akış henüz ölçülemedi (ilk frame bekleniyor) */}
      {!rect && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-on-surface-variant pointer-events-none">
          <Icon name="progress_activity" className="animate-spin text-2xl text-primary" />
          <span className="text-xs">Canlı yayın bekleniyor…</span>
        </div>
      )}
    </div>
  );
}
