import { useState, useEffect } from 'react';
import type { RobotState, CalibrationData } from '../types';

interface Props {
  robotState: RobotState;
  addLog: (msg: string) => void;
  onGoHome: () => void;
  onSaveCalibration: (data: CalibrationData) => void;
  savedCalib: CalibrationData | null;
  onJogStart?:      (axis: number, speed: number) => void;
  onJogStop?:       (axis: number) => void;
  onJogMultiStart?: (vector: number[], speed: number) => void;
  onJogMultiStop?:  () => void;
  onSetRobotMode?:  (mode: number) => void;
  onGripperOpen?:   () => void;
  onGripperClose?:  () => void;
}

const EMPTY_CALIB: CalibrationData = {
  origin_x: 0, origin_y: 0, origin_z: 0,
  pen_down_z: 0, pixel_spacing_mm: 2.0,
  center_x: 0, center_y: 0,
};

function Row({ label, value, unit }: { label: string; value: string | number; unit?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
      <span style={{ fontSize: 13, color: 'var(--text2)' }}>{label}</span>
      <span style={{ fontWeight: 700, color: 'var(--accent)' }}>{value}{unit && <span style={{ color: 'var(--text2)', fontWeight: 400, marginLeft: 4 }}>{unit}</span>}</span>
    </div>
  );
}

// 0=BASE, 1=TOOL  /  axis: 6=X 7=Y 8=Z (task space)
const JOG_SPEED_OPTIONS = [10, 20, 30, 50] as const;

export default function CalibrationPage({ robotState, addLog, onGoHome, onSaveCalibration, savedCalib, onJogStart, onJogStop, onJogMultiStart, onJogMultiStop, onSetRobotMode, onGripperOpen, onGripperClose }: Props) {
  const [calib, setCalib]           = useState<CalibrationData>(savedCalib ?? EMPTY_CALIB);
  const [saved, setSaved]           = useState(false);
  const [originSaved, setOriginSaved] = useState(false);
  const [jogSpeed,  setJogSpeed]    = useState<number>(20);
  const [teaching,  setTeaching]    = useState(false);
  const [jogMode,   setJogMode]     = useState<'axis' | 'plane'>('axis');
  const [jogPlane,  setJogPlane]    = useState<'XY' | 'XZ' | 'YZ'>('XY');

  function toggleTeaching() {
    const next = !teaching;
    setTeaching(next);
    onSetRobotMode?.(next ? 0 : 1); // 0=MANUAL, 1=AUTONOMOUS
    addLog(next ? '직접교시 모드 ON — 로봇을 손으로 움직일 수 있습니다' : '직접교시 모드 OFF');
  }

  function jogHandlers(axis: number, sign: 1 | -1) {
    const speed = sign * jogSpeed;
    return {
      onMouseDown:   () => onJogStart?.(axis, speed),
      onMouseUp:     () => onJogStop?.(axis),
      onMouseLeave:  () => onJogStop?.(axis),
      onTouchStart:  (e: React.TouchEvent) => { e.preventDefault(); onJogStart?.(axis, speed); },
      onTouchEnd:    () => onJogStop?.(axis),
    };
  }

  // 면정렬: 평면별 단위벡터 [Tx, Ty, Tz, Rx, Ry, Rz] 생성
  const D = 1 / Math.SQRT2;
  const PLANE_DIRS: Record<'XY'|'XZ'|'YZ', { label: string; vec: number[] }[]> = {
    XY: [
      { label: '↖', vec: [-D,  D, 0, 0, 0, 0] }, { label: '↑', vec: [ 0,  1, 0, 0, 0, 0] }, { label: '↗', vec: [ D,  D, 0, 0, 0, 0] },
      { label: '←', vec: [-1,  0, 0, 0, 0, 0] }, { label: '·', vec: [0, 0, 0, 0, 0, 0]    }, { label: '→', vec: [ 1,  0, 0, 0, 0, 0] },
      { label: '↙', vec: [-D, -D, 0, 0, 0, 0] }, { label: '↓', vec: [ 0, -1, 0, 0, 0, 0] }, { label: '↘', vec: [ D, -D, 0, 0, 0, 0] },
    ],
    XZ: [
      { label: '↖', vec: [-D, 0,  D, 0, 0, 0] }, { label: '↑', vec: [ 0, 0,  1, 0, 0, 0] }, { label: '↗', vec: [ D, 0,  D, 0, 0, 0] },
      { label: '←', vec: [-1, 0,  0, 0, 0, 0] }, { label: '·', vec: [0, 0, 0, 0, 0, 0]    }, { label: '→', vec: [ 1, 0,  0, 0, 0, 0] },
      { label: '↙', vec: [-D, 0, -D, 0, 0, 0] }, { label: '↓', vec: [ 0, 0, -1, 0, 0, 0] }, { label: '↘', vec: [ D, 0, -D, 0, 0, 0] },
    ],
    YZ: [
      { label: '↖', vec: [0, -D,  D, 0, 0, 0] }, { label: '↑', vec: [0,  0,  1, 0, 0, 0] }, { label: '↗', vec: [0,  D,  D, 0, 0, 0] },
      { label: '←', vec: [0, -1,  0, 0, 0, 0] }, { label: '·', vec: [0, 0, 0, 0, 0, 0]    }, { label: '→', vec: [0,  1,  0, 0, 0, 0] },
      { label: '↙', vec: [0, -D, -D, 0, 0, 0] }, { label: '↓', vec: [0,  0, -1, 0, 0, 0] }, { label: '↘', vec: [0,  D, -D, 0, 0, 0] },
    ],
  };

  function multiHandlers(vec: number[]) {
    const isStop = vec.every(v => v === 0);
    return {
      onMouseDown:   () => isStop ? onJogMultiStop?.() : onJogMultiStart?.(vec, jogSpeed),
      onMouseUp:     () => onJogMultiStop?.(),
      onMouseLeave:  () => onJogMultiStop?.(),
      onTouchStart:  (e: React.TouchEvent) => { e.preventDefault(); isStop ? onJogMultiStop?.() : onJogMultiStart?.(vec, jogSpeed); },
      onTouchEnd:    () => onJogMultiStop?.(),
    };
  }

  // 서버에서 캘리브레이션이 로드되면 UI에 반영
  useEffect(() => {
    if (savedCalib) setCalib(savedCalib);
  }, [savedCalib]);

  function setOriginFromTCP() {
    const updated = { ...calib, origin_x: robotState.tcpX, origin_y: robotState.tcpY, origin_z: robotState.tcpZ };
    setCalib(updated);
    onSaveCalibration(updated);
    setOriginSaved(true);
    addLog(`종이 우하단 저장: X=${robotState.tcpX.toFixed(1)}, Y=${robotState.tcpY.toFixed(1)}, Z=${robotState.tcpZ.toFixed(1)}`);
    setTimeout(() => setOriginSaved(false), 2000);
  }

  function saveCalib() {
    onSaveCalibration(calib);
    setSaved(true);
    addLog('캘리브레이션 저장됨');
    setTimeout(() => setSaved(false), 2000);
  }

  function numField(key: keyof CalibrationData, label: string, unit: string, step = 0.1) {
    return (
      <div key={key}>
        <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 5 }}>{label} ({unit})</div>
        <input
          type="number"
          step={step}
          value={calib[key] ?? 0}
          onChange={e => setCalib(p => ({ ...p, [key]: Number(e.target.value) }))}
        />
      </div>
    );
  }

  return (
    <div>
      <h2 style={{ marginBottom: 20, fontSize: 20, fontWeight: 700 }}>캘리브레이션</h2>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
        {/* 현재 TCP 위치 */}
        <div className="card">
          <div className="card-title">현재 TCP 위치 (실시간)</div>
          <Row label="X" value={robotState.tcpX.toFixed(2)} unit="mm" />
          <Row label="Y" value={robotState.tcpY.toFixed(2)} unit="mm" />
          <Row label="Z" value={robotState.tcpZ.toFixed(2)} unit="mm" />
          <Row label="속도" value={`${robotState.speed} mm/s`} />

          <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
            <button className={originSaved ? 'btn-success' : 'btn-primary'} style={{ flex: 1 }}
              onClick={setOriginFromTCP}>
              {originSaved ? '✓ 우하단 저장됨' : '현재 위치를 종이 우하단으로 저장'}
            </button>
            <button className="btn-ghost" onClick={onGoHome}>
              원점 이동
            </button>
          </div>

          <div style={{ marginTop: 16, padding: '10px 12px', background: 'var(--panel2)', borderRadius: 6, fontSize: 12, color: 'var(--text2)' }}>
            <div style={{ fontWeight: 600, marginBottom: 6 }}>저장된 종이 우하단</div>
            <div>X: <span style={{ color: 'var(--accent)', fontWeight: 700 }}>{calib.origin_x.toFixed(2)}</span> mm &nbsp;
              Y: <span style={{ color: 'var(--accent)', fontWeight: 700 }}>{calib.origin_y.toFixed(2)}</span> mm &nbsp;
              Z: <span style={{ color: 'var(--accent)', fontWeight: 700 }}>{calib.origin_z.toFixed(2)}</span> mm
            </div>
          </div>
        </div>

        {/* 픽셀 간격 */}
        <div className="card">
          <div className="card-title">픽셀 간격</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 12 }}>
            {numField('pixel_spacing_mm', '픽셀 간격', 'mm', 0.1)}
          </div>
          <div style={{ marginTop: 12, padding: '8px 10px', background: 'var(--panel2)', borderRadius: 6, fontSize: 11, color: 'var(--text2)' }}>
            Z 높이는 그리기 시작 시 첫 픽셀 위치에서 자동 측정됩니다
          </div>
        </div>
      </div>

      {/* 좌표 설정 */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
        {/* S자 — 우하단 */}
        <div className="card">
          <div className="card-title">▶ S자 기준점 (종이 우하단)</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            {numField('origin_x', 'X', 'mm')}
            {numField('origin_y', 'Y', 'mm')}
          </div>
          <div style={{ marginTop: 10, padding: '8px 10px', background: 'var(--panel2)', borderRadius: 6, fontSize: 11, color: 'var(--text2)' }}>
            로봇을 종이 우하단 모서리에 위치시킨 후 저장
          </div>
        </div>
      </div>

      {/* 조그 */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div className="card-title" style={{ margin: 0 }}>조그 (축정렬)</div>
          <button
            className={teaching ? 'btn-primary' : 'btn-ghost'}
            style={{ padding: '6px 14px', fontSize: 13 }}
            onClick={toggleTeaching}>
            {teaching ? '✋ 직접교시 ON' : '손으로 움직이기'}
          </button>
        </div>

        {teaching && (
          <div style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--panel2)', borderRadius: 6, fontSize: 12, color: 'var(--accent)' }}>
            직접교시 모드: 로봇을 손으로 잡고 원하는 위치로 이동하세요. 종료하려면 버튼을 다시 누르세요.
          </div>
        )}

        {/* 축정렬 / 면정렬 탭 */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 12, opacity: teaching ? 0.35 : 1, pointerEvents: teaching ? 'none' : 'auto' }}>
          {(['axis', 'plane'] as const).map(m => (
            <button key={m}
              className={jogMode === m ? 'btn-primary' : 'btn-ghost'}
              style={{ padding: '4px 14px', fontSize: 13 }}
              onClick={() => setJogMode(m)}>
              {m === 'axis' ? '축정렬' : '면정렬'}
            </button>
          ))}
          <div style={{ flex: 1 }} />
          <span style={{ fontSize: 12, color: 'var(--text2)', alignSelf: 'center' }}>속도</span>
          {JOG_SPEED_OPTIONS.map(v => (
            <button key={v}
              className={jogSpeed === v ? 'btn-primary' : 'btn-ghost'}
              style={{ padding: '3px 10px', fontSize: 12 }}
              onClick={() => setJogSpeed(v)}>
              {v}%
            </button>
          ))}
        </div>

        <div style={{ opacity: teaching ? 0.35 : 1, pointerEvents: teaching ? 'none' : 'auto' }}>
          {jogMode === 'axis' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
              {([['X', 6], ['Y', 7], ['Z', 8]] as [string, number][]).map(([label, axis]) => (
                <div key={axis} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <div style={{ fontSize: 12, color: 'var(--text2)', textAlign: 'center' }}>{label}</div>
                  <button className="btn-ghost" style={{ userSelect: 'none' }} {...jogHandlers(axis, 1)}>{label}+</button>
                  <button className="btn-ghost" style={{ userSelect: 'none' }} {...jogHandlers(axis, -1)}>{label}−</button>
                </div>
              ))}
            </div>
          )}

          {jogMode === 'plane' && (
            <div>
              <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
                {(['XY', 'XZ', 'YZ'] as const).map(p => (
                  <button key={p}
                    className={jogPlane === p ? 'btn-primary' : 'btn-ghost'}
                    style={{ padding: '3px 14px', fontSize: 13 }}
                    onClick={() => setJogPlane(p)}>
                    {p}
                  </button>
                ))}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 52px)', gap: 4 }}>
                {PLANE_DIRS[jogPlane].map((d, i) => (
                  <button key={i}
                    style={{
                      height: 52, fontSize: 20, userSelect: 'none',
                      opacity: d.label === '·' ? 0.2 : 1,
                      cursor:  d.label === '·' ? 'default' : 'pointer',
                    }}
                    disabled={d.label === '·'}
                    {...(d.label !== '·' ? multiHandlers(d.vec) : {})}>
                    {d.label}
                  </button>
                ))}
              </div>
              <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text2)' }}>
                {jogPlane === 'XY' && '← → = X축  ↑ ↓ = Y축'}
                {jogPlane === 'XZ' && '← → = X축  ↑ ↓ = Z축'}
                {jogPlane === 'YZ' && '← → = Y축  ↑ ↓ = Z축'}
              </div>
            </div>
          )}

          {/* 그리퍼 */}
          <div style={{ marginTop: 16, display: 'flex', gap: 10 }}>
            <button className="btn-outline" style={{ flex: 1 }}
              onMouseDown={() => onGripperOpen?.()} onTouchStart={() => onGripperOpen?.()}>
              그리퍼 열기
            </button>
            <button className="btn-outline" style={{ flex: 1 }}
              onMouseDown={() => onGripperClose?.()} onTouchStart={() => onGripperClose?.()}>
              그리퍼 닫기
            </button>
          </div>
        </div>
      </div>

      {/* 저장 */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <button className="btn-primary" style={{ padding: '10px 32px' }} onClick={saveCalib}>
          {saved ? '✓ 저장됨' : '캘리브레이션 저장'}
        </button>
        <button className="btn-ghost" onClick={() => setCalib(savedCalib ?? EMPTY_CALIB)}>
          초기화
        </button>
        <span style={{ fontSize: 12, color: 'var(--text2)' }}>* 저장 즉시 그리기에 반영됩니다</span>
      </div>
    </div>
  );
}
