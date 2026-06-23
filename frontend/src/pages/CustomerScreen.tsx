import { useState, useEffect, useRef } from 'react';
import type { ArtSettings, PixelPoint, DrawingState } from '../types';
import { FRAME_SIZES, PAPER_TYPES, RESOLUTIONS, DEFAULT_ART_SETTINGS, DRAWING_STATUS_COLOR, DRAWING_STATUS_LABEL } from '../constants';

interface Props {
  drawingState: DrawingState;
  onStartDrawing: (pixels: PixelPoint[], settings: ArtSettings, imageName: string) => void;
  onCancelDrawing: () => void;
  onAdminClick: () => void;
}

type BottomPanel = 'adjust' | 'pixel' | null;

function clamp(v: number, lo: number, hi: number) { return Math.max(lo, Math.min(hi, v)); }

export default function CustomerScreen({ drawingState, onStartDrawing, onCancelDrawing, onAdminClick }: Props) {
  const [imageFile, setImageFile]         = useState<File | null>(null);
  const [originalUrl, setOriginalUrl]     = useState('');
  const [pixelData, setPixelData]         = useState<PixelPoint[]>([]);
  const [artSettings, setArtSettings]     = useState<ArtSettings>(DEFAULT_ART_SETTINGS);
  const [isDragging, setIsDragging]       = useState(false);
  const [bottomPanel, setBottomPanel]     = useState<BottomPanel>(null);
  const [editTool, setEditTool]           = useState<'pen' | 'eraser'>('pen');
  const [brushSize, setBrushSize]         = useState(1);
  const [penGray, setPenGray]             = useState(0);
  const [redrawKey, setRedrawKey]         = useState(0);

  const dragCounter        = useRef(0);
  const isMouseDown        = useRef(false);
  const pixelDataRef       = useRef<PixelPoint[]>([]);
  const scaleRef           = useRef(1);
  const gapRef             = useRef(0);
  const processedCanvasRef = useRef<HTMLCanvasElement>(null);
  const fileInputRef       = useRef<HTMLInputElement>(null);

  // Refs used in event handlers to always read latest values (avoids stale closure)
  const bottomPanelRef = useRef<BottomPanel>(null);
  const editToolRef    = useRef<'pen' | 'eraser'>('pen');
  const penGrayRef     = useRef(0);
  const brushSizeRef   = useRef(1);
  const artSettingsRef = useRef(artSettings);

  bottomPanelRef.current = bottomPanel;
  editToolRef.current    = editTool;
  penGrayRef.current     = penGray;
  brushSizeRef.current   = brushSize;
  artSettingsRef.current = artSettings;

  useEffect(() => { pixelDataRef.current = [...pixelData]; }, [pixelData]);

  // Object URL
  useEffect(() => {
    if (!imageFile) { setOriginalUrl(''); return; }
    const url = URL.createObjectURL(imageFile);
    setOriginalUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [imageFile]);

  // Image processing — runs whenever originalUrl or artSettings changes
  useEffect(() => {
    if (!originalUrl) return;
    let cancelled = false;
    const img = new Image();
    img.onload = () => {
      if (cancelled) return;
      const { resWidth, resHeight, brightness, contrast, rotation, flipH, flipV } = artSettingsRef.current;

      const proc = document.createElement('canvas');
      proc.width  = resWidth;
      proc.height = resHeight;
      const pCtx  = proc.getContext('2d')!;

      pCtx.save();
      pCtx.translate(resWidth / 2, resHeight / 2);
      if (rotation) pCtx.rotate((rotation * Math.PI) / 180);
      if (flipH) pCtx.scale(-1, 1);
      if (flipV) pCtx.scale(1, -1);
      const srcA = img.width / img.height;
      const dstA = resWidth / resHeight;
      let dw, dh;
      if (srcA > dstA) { dh = resHeight; dw = dh * srcA; }
      else              { dw = resWidth;  dh = dw / srcA; }
      pCtx.drawImage(img, -dw / 2, -dh / 2, dw, dh);
      pCtx.restore();

      const imgData = pCtx.getImageData(0, 0, resWidth, resHeight);
      const pixels: PixelPoint[] = [];

      for (let i = 0; i < imgData.data.length; i += 4) {
        const r = imgData.data[i], g = imgData.data[i + 1], b = imgData.data[i + 2];
        let gray = Math.round(0.299 * r + 0.587 * g + 0.114 * b);
        gray = clamp(Math.round(gray * brightness), 0, 255);
        gray = clamp(Math.round((gray - 128) * contrast + 128), 0, 255);
        imgData.data[i] = imgData.data[i + 1] = imgData.data[i + 2] = gray;
        pixels.push({ x: (i / 4) % resWidth, y: Math.floor((i / 4) / resWidth), gray });
      }
      pCtx.putImageData(imgData, 0, 0);
      setPixelData(pixels);
      pixelDataRef.current = pixels;

      const disp = processedCanvasRef.current;
      if (!disp) return;
      const maxW = disp.parentElement?.clientWidth  || 480;
      const maxH = disp.parentElement?.clientHeight || 400;
      const scale = clamp(Math.floor(Math.min(maxW / resWidth, maxH / resHeight)), 1, 12);
      const gap   = scale >= 5 ? 1 : 0;
      scaleRef.current = scale;
      gapRef.current   = gap;

      disp.width  = resWidth  * (scale + gap);
      disp.height = resHeight * (scale + gap);
      const dCtx = disp.getContext('2d')!;
      dCtx.fillStyle = '#111';
      dCtx.fillRect(0, 0, disp.width, disp.height);
      for (let y = 0; y < resHeight; y++) {
        for (let x = 0; x < resWidth; x++) {
          const gv = pixels[y * resWidth + x].gray;
          dCtx.fillStyle = `rgb(${gv},${gv},${gv})`;
          dCtx.fillRect(x * (scale + gap), y * (scale + gap), scale, scale);
        }
      }
    };
    img.src = originalUrl;
    return () => { cancelled = true; };
  }, [originalUrl, artSettings, redrawKey]); // redrawKey: 편집 모드 진입/종료 시 컨테이너 크기 반영

  // ── 픽셀 페인팅 ──────────────────────────────────────────────
  function getPixelCoord(e: React.MouseEvent<HTMLCanvasElement>) {
    const canvas = processedCanvasRef.current!;
    const rect = canvas.getBoundingClientRect();
    const sx = canvas.width  / rect.width;
    const sy = canvas.height / rect.height;
    const cell = scaleRef.current + gapRef.current;
    return {
      px: Math.floor((e.clientX - rect.left) * sx / cell),
      py: Math.floor((e.clientY - rect.top)  * sy / cell),
    };
  }

  function paintAt(px: number, py: number) {
    const { resWidth, resHeight } = artSettingsRef.current;
    const gray = editToolRef.current === 'eraser' ? 255 : penGrayRef.current;
    const half = Math.floor(brushSizeRef.current / 2);
    const cell = scaleRef.current + gapRef.current;
    const canvas = processedCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d')!;
    for (let dy = -half; dy <= half; dy++) {
      for (let dx = -half; dx <= half; dx++) {
        const nx = px + dx, ny = py + dy;
        if (nx < 0 || nx >= resWidth || ny < 0 || ny >= resHeight) continue;
        pixelDataRef.current[ny * resWidth + nx] = { x: nx, y: ny, gray };
        ctx.fillStyle = `rgb(${gray},${gray},${gray})`;
        ctx.fillRect(nx * cell, ny * cell, scaleRef.current, scaleRef.current);
      }
    }
  }

  function handleCanvasMouseDown(e: React.MouseEvent<HTMLCanvasElement>) {
    if (bottomPanelRef.current !== 'pixel') return;
    isMouseDown.current = true;
    const { px, py } = getPixelCoord(e);
    paintAt(px, py);
  }

  function handleCanvasMouseMove(e: React.MouseEvent<HTMLCanvasElement>) {
    if (bottomPanelRef.current !== 'pixel' || !isMouseDown.current) return;
    const { px, py } = getPixelCoord(e);
    paintAt(px, py);
  }

  function handleCanvasMouseUp() {
    if (!isMouseDown.current) return;
    isMouseDown.current = false;
    setPixelData([...pixelDataRef.current]);
  }

  function handleFile(file: File) {
    if (!file.type.startsWith('image/')) return;
    setImageFile(file);
    setBottomPanel(null);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    dragCounter.current = 0;
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  function setRes(key: string) {
    const found = RESOLUTIONS.find(r => r.key === key);
    if (!found || found.key === 'custom') setArtSettings(s => ({ ...s, resolutionKey: key }));
    else setArtSettings(s => ({ ...s, resolutionKey: key, resWidth: found.w, resHeight: found.h }));
  }

  function setFrame(key: string) {
    const found = FRAME_SIZES.find(f => f.key === key);
    if (!found || found.key === 'custom') setArtSettings(s => ({ ...s, frameSizeKey: key }));
    else setArtSettings(s => ({ ...s, frameSizeKey: key, frameWidth: found.w, frameHeight: found.h }));
  }

  function upd<K extends keyof ArtSettings>(k: K, v: ArtSettings[K]) {
    setArtSettings(s => ({ ...s, [k]: v }));
  }

  const editMode   = bottomPanel === 'pixel';
  const isRunning  = drawingState.status === 'running';
  const isFinished = ['success', 'failed', 'cancelled'].includes(drawingState.status);
  const progress   = drawingState.totalPixels > 0
    ? Math.round((drawingState.currentPixel / drawingState.totalPixels) * 100) : 0;
  const estMin     = Math.round(pixelData.length * 0.5 / 60);
  const frameLabel = FRAME_SIZES.find(f => f.key === artSettings.frameSizeKey)?.label ?? '';

  return (
    // Fragment: 메인 div와 fixed 패널을 형제로 — overflow:hidden 바깥에 패널 배치
    <>
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--bg)' }}>

      {/* ── 헤더 ── */}
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 24px', flexShrink: 0,
        background: 'linear-gradient(90deg, #2d6e23 0%, #3a8f35 100%)',
        borderBottom: '1px solid var(--border)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <span style={{ fontSize: 26 }}>🎨</span>
          <div>
            <div style={{ fontSize: 18, fontWeight: 800, color: '#fff', letterSpacing: 1 }}>Robot Art Studio</div>
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.75)' }}>M0609 · RG2 그리퍼 · 픽셀 아트 프린터</div>
          </div>
        </div>
        <button className="btn-ghost" onClick={onAdminClick} style={{ fontSize: 12 }}>관리자 로그인</button>
      </header>

      {/* ── 업로드 존 ── */}
      <div
        onDragEnter={e => { e.preventDefault(); dragCounter.current++; setIsDragging(true); }}
        onDragLeave={() => { dragCounter.current--; if (dragCounter.current <= 0) { dragCounter.current = 0; setIsDragging(false); } }}
        onDragOver={e => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => !isRunning && fileInputRef.current?.click()}
        style={{
          margin: '12px 24px 0', padding: '12px 20px', flexShrink: 0,
          border: `2px dashed ${isDragging ? 'var(--accent)' : 'var(--border)'}`,
          borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 14,
          cursor: isRunning ? 'default' : 'pointer',
          background: isDragging ? 'rgba(58,143,53,0.08)' : 'var(--panel)',
          transition: 'border-color 0.15s, background 0.15s',
        }}>
        <input ref={fileInputRef} type="file" accept="image/*" style={{ display: 'none' }}
          onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); e.target.value = ''; }} />
        {imageFile ? (
          <>
            <span style={{ fontSize: 20 }}>✅</span>
            <span style={{ fontWeight: 700, color: 'var(--accent)', fontSize: 14 }}>{imageFile.name}</span>
            <span style={{ fontSize: 11, color: 'var(--text2)' }}>
              {(imageFile.size / 1024).toFixed(0)} KB · 클릭하여 변경
            </span>
          </>
        ) : (
          <>
            <span style={{ fontSize: 22 }}>📁</span>
            <span style={{ fontWeight: 600, color: 'var(--text)' }}>이미지를 끌어다 놓거나 클릭하여 선택</span>
            <span style={{ fontSize: 12, color: 'var(--text2)' }}>JPG, PNG, BMP, WEBP</span>
          </>
        )}
      </div>

      {/* ── 이미지 2분할 (픽셀 편집 시 미리보기 확대) ── */}
      <div style={{ display: 'flex', gap: 16, padding: '12px 24px', flex: 1, minHeight: 0, overflow: 'hidden' }}>

        {/* 원본 — 픽셀 편집 모드에선 숨김 */}
        {!editMode && (
          <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#888', display: 'inline-block' }} />
              원본 이미지
            </div>
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 0, overflow: 'hidden' }}>
              {originalUrl
                ? <img src={originalUrl} alt="original" style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain', borderRadius: 6 }} />
                : <span style={{ color: 'var(--text2)', fontSize: 13 }}>이미지를 업로드하면 여기에 표시됩니다</span>
              }
            </div>
          </div>
        )}

        {/* 변환 미리보기 — 픽셀 편집 시 전체 너비로 확대 */}
        <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, flexShrink: 0 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent)', display: 'inline-block' }} />
            <span style={{ fontWeight: 600, fontSize: 13 }}>변환 미리보기</span>
            {pixelData.length > 0 && (
              <span className="tag tag-blue">{artSettings.resWidth}×{artSettings.resHeight}</span>
            )}
            {editMode && (
              <span style={{ fontSize: 11, color: 'var(--accent)', marginLeft: 4 }}>편집 모드 — 클릭·드래그하여 그리세요</span>
            )}
          </div>
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 0, overflow: 'hidden' }}>
            {originalUrl ? (
              <canvas
                ref={processedCanvasRef}
                style={{
                  maxWidth: '100%', maxHeight: '100%',
                  imageRendering: 'pixelated', borderRadius: 4,
                  cursor: editMode ? (editTool === 'eraser' ? 'cell' : 'crosshair') : 'default',
                  outline: editMode ? '2px solid var(--accent)' : 'none',
                }}
                onMouseDown={handleCanvasMouseDown}
                onMouseMove={handleCanvasMouseMove}
                onMouseUp={handleCanvasMouseUp}
                onMouseLeave={handleCanvasMouseUp}
              />
            ) : (
              <div style={{ color: 'var(--text2)', fontSize: 13, textAlign: 'center' }}>
                <div style={{ fontSize: 28, marginBottom: 8 }}>🖼️</div>
                이미지를 업로드하면 그레이스케일로 변환된 모습이 표시됩니다
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── 설정 행 ── */}
      <div style={{ padding: '0 24px 6px', flexShrink: 0 }}>
        {/* 0행: 중심 좌표 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          <span style={{ fontSize: 11, color: 'var(--text2)', flexShrink: 0 }}>종이 좌상단 좌표 (mm)</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 11, color: 'var(--text2)' }}>X</span>
            <input type="number" step="1"
              value={artSettings.originX}
              onChange={e => upd('originX', parseFloat(e.target.value) || 0)}
              disabled={isRunning}
              style={{ width: 80 }} />
            <span style={{ fontSize: 11, color: 'var(--text2)' }}>Y</span>
            <input type="number" step="1"
              value={artSettings.originY}
              onChange={e => upd('originY', parseFloat(e.target.value) || 0)}
              disabled={isRunning}
              style={{ width: 80 }} />
          </div>
          <span style={{ fontSize: 11, color: 'var(--text2)' }}>
            → 좌상단 기준으로 {artSettings.frameWidth}×{artSettings.frameHeight}mm 범위에 그림
          </span>
        </div>
        {/* 1행: 드롭다운 설정 */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 10, marginBottom: 8 }}>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 4 }}>액자 크기</div>
            <select value={artSettings.frameSizeKey} onChange={e => setFrame(e.target.value)} disabled={isRunning}>
              {FRAME_SIZES.map(f => <option key={f.key} value={f.key}>{f.label}</option>)}
            </select>
            {artSettings.frameSizeKey === 'custom' && (
              <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                <input type="number" placeholder="너비(mm)" min="50" max="500"
                  value={artSettings.frameWidth || ''} onChange={e => upd('frameWidth', parseInt(e.target.value) || 0)} style={{ width: '50%' }} />
                <input type="number" placeholder="높이(mm)" min="50" max="500"
                  value={artSettings.frameHeight || ''} onChange={e => upd('frameHeight', parseInt(e.target.value) || 0)} style={{ width: '50%' }} />
              </div>
            )}
          </div>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 4 }}>용지 종류</div>
            <select value={artSettings.paperType} onChange={e => upd('paperType', e.target.value)} disabled={isRunning}>
              {PAPER_TYPES.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 4 }}>픽셀 해상도</div>
            <select value={artSettings.resolutionKey} onChange={e => setRes(e.target.value)} disabled={isRunning}>
              {RESOLUTIONS.map(r => <option key={r.key} value={r.key}>{r.label}</option>)}
            </select>
            {artSettings.resolutionKey === 'custom' && (
              <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                <input type="number" placeholder="가로" min="10" max="500"
                  value={artSettings.resWidth || ''} onChange={e => upd('resWidth', parseInt(e.target.value) || 0)} style={{ width: '50%' }} />
                <input type="number" placeholder="세로" min="10" max="500"
                  value={artSettings.resHeight || ''} onChange={e => upd('resHeight', parseInt(e.target.value) || 0)} style={{ width: '50%' }} />
              </div>
            )}
          </div>
        </div>
        {/* 2행: 이미지 편집 버튼 */}
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            className={bottomPanel === 'adjust' ? 'btn-primary' : 'btn-outline'}
            style={{ fontSize: 12, padding: '6px 16px' }}
            disabled={!originalUrl || isRunning}
            onClick={() => setBottomPanel(p => p === 'adjust' ? null : 'adjust')}>
            🎚️ 조정
          </button>
          <button
            className={bottomPanel === 'pixel' ? 'btn-primary' : 'btn-outline'}
            style={{ fontSize: 12, padding: '6px 16px' }}
            disabled={!originalUrl || isRunning}
            onClick={() => { setBottomPanel(p => p === 'pixel' ? null : 'pixel'); setRedrawKey(k => k + 1); }}>
            🖌️ 픽셀 편집
          </button>
        </div>
      </div>

      {/* ── 하단 바 ── */}
      <div style={{ padding: '12px 24px 20px', background: 'var(--panel)', borderTop: '1px solid var(--border)', flexShrink: 0 }}>
        <div style={{ display: 'flex', gap: 28, marginBottom: 12, flexWrap: 'wrap' }}>
          <Stat label="총 픽셀" value={pixelData.length > 0 ? pixelData.length.toLocaleString() : '—'} unit="픽셀" />
          <Stat label="예상 소요" value={pixelData.length > 0 ? `~${estMin}` : '—'} unit="분" />
          <Stat label="액자 크기" value={frameLabel || '—'} unit="" />
          <Stat label="용지" value={artSettings.paperType} unit="" />
        </div>

        {(isRunning || isFinished) && (
          <div style={{ marginBottom: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 5 }}>
              <span style={{ color: DRAWING_STATUS_COLOR[drawingState.status], fontWeight: 700 }}>
                {DRAWING_STATUS_LABEL[drawingState.status]}
                {isRunning && ` — ${drawingState.currentPixel.toLocaleString()} / ${drawingState.totalPixels.toLocaleString()} 픽셀`}
              </span>
              <span style={{ color: 'var(--text2)' }}>{progress}%</span>
            </div>
            <div style={{ height: 8, background: 'var(--panel2)', borderRadius: 4, overflow: 'hidden' }}>
              <div style={{
                height: '100%', width: `${progress}%`, borderRadius: 4, transition: 'width 0.5s',
                background: drawingState.status === 'success' ? 'var(--green)'
                  : drawingState.status === 'failed' ? 'var(--red)'
                  : 'linear-gradient(90deg, var(--accent2), var(--accent))',
              }} />
            </div>
            {isRunning && (
              <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 4 }}>
                X: {drawingState.currentX.toFixed(1)}mm  Y: {drawingState.currentY.toFixed(1)}mm · 팬 힘: {drawingState.currentPenForce.toFixed(1)} N
              </div>
            )}
            {isFinished && (
              <div style={{ fontSize: 13, marginTop: 5, fontWeight: 600, color: drawingState.status === 'success' ? 'var(--green)' : 'var(--red)' }}>
                {drawingState.message}
              </div>
            )}
          </div>
        )}

        <div style={{ display: 'flex', gap: 12 }}>
          <button className="btn-primary"
            style={{ flex: 2, padding: '13px', fontSize: 16, fontWeight: 800, letterSpacing: 1 }}
            disabled={!imageFile || pixelData.length === 0 || isRunning}
            onClick={() => onStartDrawing(pixelData, artSettings, imageFile?.name ?? 'image')}>
            {isRunning && drawingState.message.includes('S자') ? '그리는 중...' : '▶ S자 시작'}
          </button>
          <button className="btn-outline"
            style={{ flex: 2, padding: '13px', fontSize: 16, fontWeight: 800 }}
            disabled={!imageFile || pixelData.length === 0 || isRunning}
            onClick={() => onStartDrawing(pixelData, { ...artSettings, drawMode: 'concentric' }, imageFile?.name ?? 'image')}>
            {isRunning && drawingState.message.includes('동심원') ? '그리는 중...' : '◎ 동심원 시작'}
          </button>
          <button className="btn-secondary"
            style={{ flex: 2, padding: '13px', fontSize: 16, fontWeight: 800 }}
            disabled={!imageFile || pixelData.length === 0 || isRunning}
            onClick={() => onStartDrawing(pixelData, { ...artSettings, drawMode: 'contour' }, imageFile?.name ?? 'image')}>
            {isRunning && drawingState.message.includes('등고선') ? '그리는 중...' : '〰 등고선 시작'}
          </button>
          <button className="btn-danger"
            style={{ flex: 1, padding: '13px', fontSize: 14 }}
            disabled={!isRunning}
            onClick={onCancelDrawing}>
            정지
          </button>
        </div>
      </div>
    </div>

    {/* ── 하단 패널 — overflow:hidden 바깥 형제로 렌더링 ── */}
    {bottomPanel && (
      <div style={{
        position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 200,
        background: 'var(--panel)',
        borderTop: `2px solid ${bottomPanel === 'pixel' ? 'var(--accent)' : 'var(--accent2)'}`,
        boxShadow: '0 -8px 32px rgba(0,0,0,0.12)',
        padding: '14px 24px 20px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 14 }}>
          <span style={{ fontWeight: 700, fontSize: 14 }}>
            {bottomPanel === 'adjust' ? '🎚️ 이미지 조정' : '🖌️ 픽셀 편집'}
          </span>
          {bottomPanel === 'pixel' && (
            <span style={{ fontSize: 11, color: 'var(--accent)', marginLeft: 10 }}>
              캔버스에 클릭·드래그하여 그리세요
            </span>
          )}
          <button className="btn-ghost" style={{ marginLeft: 'auto', padding: '3px 10px', fontSize: 15 }}
            onClick={() => setBottomPanel(null)}>✕</button>
        </div>

        {/* 조정 컨트롤 */}
        {bottomPanel === 'adjust' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 24, flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 200 }}>
              <span style={{ fontSize: 12, color: 'var(--text2)', flexShrink: 0, minWidth: 24 }}>밝기</span>
              <input type="range" min="0.2" max="2" step="0.05"
                value={artSettings.brightness}
                onChange={e => upd('brightness', parseFloat(e.target.value))}
                style={{ flex: 1, accentColor: 'var(--accent)' }} />
              <span style={{ fontSize: 12, fontWeight: 700, minWidth: 40, textAlign: 'right' }}>
                {artSettings.brightness.toFixed(2)}×
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 200 }}>
              <span style={{ fontSize: 12, color: 'var(--text2)', flexShrink: 0, minWidth: 24 }}>대비</span>
              <input type="range" min="0.2" max="3" step="0.05"
                value={artSettings.contrast}
                onChange={e => upd('contrast', parseFloat(e.target.value))}
                style={{ flex: 1, accentColor: 'var(--accent)' }} />
              <span style={{ fontSize: 12, fontWeight: 700, minWidth: 40, textAlign: 'right' }}>
                {artSettings.contrast.toFixed(2)}×
              </span>
            </div>
            <div style={{ width: 1, height: 32, background: 'var(--border)', flexShrink: 0 }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 12, color: 'var(--text2)', flexShrink: 0 }}>회전</span>
              {[0, 90, 180, 270].map(deg => (
                <button key={deg}
                  className={artSettings.rotation === deg ? 'btn-primary' : 'btn-ghost'}
                  style={{ padding: '5px 10px', fontSize: 12 }}
                  onClick={() => upd('rotation', deg)}>{deg}°</button>
              ))}
            </div>
            <div style={{ width: 1, height: 32, background: 'var(--border)', flexShrink: 0 }} />
            <div style={{ display: 'flex', gap: 6 }}>
              <button className={artSettings.flipH ? 'btn-primary' : 'btn-ghost'}
                style={{ padding: '5px 12px', fontSize: 12 }}
                onClick={() => upd('flipH', !artSettings.flipH)}>↔ 좌우</button>
              <button className={artSettings.flipV ? 'btn-primary' : 'btn-ghost'}
                style={{ padding: '5px 12px', fontSize: 12 }}
                onClick={() => upd('flipV', !artSettings.flipV)}>↕ 상하</button>
            </div>
            <div style={{ width: 1, height: 32, background: 'var(--border)', flexShrink: 0 }} />
            <button className="btn-ghost" style={{ padding: '5px 14px', fontSize: 12 }}
              onClick={() => setArtSettings(s => ({ ...s, brightness: 1, contrast: 1, rotation: 0, flipH: false, flipV: false }))}>
              ↺ 초기화
            </button>
          </div>
        )}

        {/* 픽셀 편집 컨트롤 */}
        {bottomPanel === 'pixel' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', gap: 6 }}>
              <button className={editTool === 'pen' ? 'btn-primary' : 'btn-ghost'}
                style={{ padding: '6px 14px', fontSize: 13 }}
                onClick={() => setEditTool('pen')}>🖊 펜</button>
              <button className={editTool === 'eraser' ? 'btn-primary' : 'btn-ghost'}
                style={{ padding: '6px 14px', fontSize: 13 }}
                onClick={() => setEditTool('eraser')}>🧹 지우개</button>
            </div>
            <div style={{ width: 1, height: 32, background: 'var(--border)', flexShrink: 0 }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 12, color: 'var(--text2)', flexShrink: 0 }}>크기</span>
              {[1, 3, 5].map(s => (
                <button key={s}
                  className={brushSize === s ? 'btn-primary' : 'btn-ghost'}
                  style={{ padding: '5px 10px', fontSize: 12 }}
                  onClick={() => setBrushSize(s)}>{s}px</button>
              ))}
            </div>
            {editTool === 'pen' && <>
              <div style={{ width: 1, height: 32, background: 'var(--border)', flexShrink: 0 }} />
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 220 }}>
                <span style={{ fontSize: 12, color: 'var(--text2)', flexShrink: 0 }}>농도</span>
                <input type="range" min="0" max="255" step="1"
                  value={penGray}
                  onChange={e => setPenGray(parseInt(e.target.value))}
                  style={{ flex: 1, accentColor: 'var(--accent)' }} />
                <div style={{
                  width: 24, height: 24, borderRadius: 4, flexShrink: 0,
                  background: `rgb(${penGray},${penGray},${penGray})`,
                  border: '1px solid var(--border)',
                }} />
                <span style={{ fontSize: 12, color: 'var(--text2)', minWidth: 28 }}>{penGray}</span>
              </div>
            </>}
            <div style={{ width: 1, height: 32, background: 'var(--border)', flexShrink: 0 }} />
            <button className="btn-ghost" style={{ padding: '6px 14px', fontSize: 12 }}
              onClick={() => {
                // artSettings가 바뀌지 않으므로 강제로 useEffect 재실행 트릭: 임시 복사
                setArtSettings(s => ({ ...s }));
              }}>
              ↺ 초기화
            </button>
          </div>
        )}
      </div>
    )}
    </>
  );
}

function Stat({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: 'var(--text2)' }}>{label}</div>
      <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)' }}>
        {value} <span style={{ fontSize: 11, color: 'var(--text2)', fontWeight: 400 }}>{unit}</span>
      </div>
    </div>
  );
}
