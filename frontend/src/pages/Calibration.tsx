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

const BASE_X = 462.0;
const BASE_Y = -16.0;

const STEP_OPTIONS = [0.5, 1, 2, 5] as const;
type Step = typeof STEP_OPTIONS[number];

const JOG_SPEED_OPTIONS = [10, 20, 30, 50] as const;

function Row({ label, value, unit }: { label: string; value: string | number; unit?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
      <span style={{ fontSize: 13, color: 'var(--text2)' }}>{label}</span>
      <span style={{ fontWeight: 700, color: 'var(--accent)' }}>{value}{unit && <span style={{ color: 'var(--text2)', fontWeight: 400, marginLeft: 4 }}>{unit}</span>}</span>
    </div>
  );
}

export default function CalibrationPage({
  robotState, addLog, onGoHome, onSaveCalibration, savedCalib,
  onJogStart, onJogStop, onJogMultiStart, onJogMultiStop, onSetRobotMode,
  onGripperOpen, onGripperClose,
}: Props) {
  const [offsetX, setOffsetX] = useState(0);
  const [offsetY, setOffsetY] = useState(0);
  const [step, setStep]       = useState<Step>(1);
  const [saved, setSaved]     = useState(false);
  const [jogSpeed, setJogSpeed]   = useState<number>(20);
  const [teaching, setTeaching]   = useState(false);
  const [jogMode,  setJogMode]    = useState<'axis' | 'plane'>('axis');
  const [jogPlane, setJogPlane]   = useState<'XY' | 'XZ' | 'YZ'>('XY');

  useEffect(() => {
    if (savedCalib) {
      setOffsetX(parseFloat(((savedCalib.origin_x ?? BASE_X) - BASE_X).toFixed(2)));
      setOffsetY(parseFloat(((savedCalib.origin_y ?? BASE_Y) - BASE_Y).toFixed(2)));
    }
  }, [savedCalib]);

  function adjust(axis: 'x' | 'y', sign: 1 | -1) {
    if (axis === 'x') setOffsetX(v => parseFloat((v + sign * step).toFixed(2)));
    else              setOffsetY(v => parseFloat((v + sign * step).toFixed(2)));
  }

  function saveCalib() {
    const data: CalibrationData = {
      ...(savedCalib ?? { origin_z: 0, pen_down_z: 0, pixel_spacing_mm: 2.0, center_x: 0, center_y: 0 }),
      origin_x: parseFloat((BASE_X + offsetX).toFixed(2)),
      origin_y: parseFloat((BASE_Y + offsetY).toFixed(2)),
    };
    onSaveCalibration(data);
    setSaved(true);
    addLog(`보정값 저장: X${offsetX >= 0 ? '+' : ''}${offsetX}mm, Y${offsetY >= 0 ? '+' : ''}${offsetY}mm → (${data.origin_x}, ${data.origin_y})`);
    setTimeout(() => setSaved(false), 2000);
  }

  function toggleTeaching() {
    const next = !teaching;
    setTeaching(next);
    onSetRobotMode?.(next ? 0 : 1);
    addLog(next ? '직접교시 모드 ON' : '직접교시 모드 OFF');
  }

  function jogHandlers(axis: number, sign: 1 | -1) {
    const speed = sign * jogSpeed;
    return {
      onMouseDown:  () => onJogStart?.(axis, speed),
      onMouseUp:    () => onJogStop?.(axis),
      onMouseLeave: () => onJogStop?.(axis),
      onTouchStart: (e: React.TouchEvent) => { e.preventDefault(); onJogStart?.(axis, speed); },
      onTouchEnd:   () => onJogStop?.(axis),
    };
  }

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
      onMouseDown:  () => isStop ? onJogMultiStop?.() : onJogMultiStart?.(vec, jogSpeed),
      onMouseUp:    () => onJogMultiStop?.(),
      onMouseLeave: () => onJogMultiStop?.(),
      onTouchStart: (e: React.TouchEvent) => { e.preventDefault(); isStop ? onJogMultiStop?.() : onJogMultiStart?.(vec, jogSpeed); },
      onTouchEnd:   () => onJogMultiStop?.(),
    };
  }

  const effectiveX = parseFloat((BASE_X + offsetX).toFixed(2));
  const effectiveY = parseFloat((BASE_Y + offsetY).toFixed(2));

  const btnAdj: React.CSSProperties = {
    width: 44, height: 44, fontSize: 20, fontWeight: 700,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  };

  return (
    <div>
      <h2 style={{ marginBottom: 20, fontSize: 20, fontWeight: 700 }}>캘리브레이션</h2>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>

        {/* 위치 보정 */}
        <div className="card">
          <div className="card-title">위치 보정 (기준점으로부터 이동량)</div>

          <div style={{ marginBottom: 14, padding: '8px 12px', background: 'var(--panel2)', borderRadius: 6, fontSize: 12, color: 'var(--text2)' }}>
            기준점 &nbsp; X = <b style={{ color: 'var(--accent)' }}>{BASE_X}</b> &nbsp; Y = <b style={{ color: 'var(--accent)' }}>{BASE_Y}</b>
          </div>

          {/* 이동 단위 선택 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 16 }}>
            <span style={{ fontSize: 12, color: 'var(--text2)' }}>단위</span>
            {STEP_OPTIONS.map(s => (
              <button key={s}
                className={step === s ? 'btn-primary' : 'btn-ghost'}
                style={{ padding: '3px 10px', fontSize: 12 }}
                onClick={() => setStep(s)}>
                {s}mm
              </button>
            ))}
          </div>

          {/* X 보정 */}
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 6 }}>X 보정</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <button className="btn-ghost" style={btnAdj} onClick={() => adjust('x', -1)}>−</button>
              <div style={{ flex: 1, textAlign: 'center' }}>
                <span style={{ fontSize: 22, fontWeight: 700, color: 'var(--accent)' }}>
                  {offsetX >= 0 ? '+' : ''}{offsetX}
                </span>
                <span style={{ fontSize: 13, color: 'var(--text2)', marginLeft: 4 }}>mm</span>
              </div>
              <button className="btn-ghost" style={btnAdj} onClick={() => adjust('x', 1)}>+</button>
            </div>
          </div>

          {/* Y 보정 */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 6 }}>Y 보정</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <button className="btn-ghost" style={btnAdj} onClick={() => adjust('y', -1)}>−</button>
              <div style={{ flex: 1, textAlign: 'center' }}>
                <span style={{ fontSize: 22, fontWeight: 700, color: 'var(--accent)' }}>
                  {offsetY >= 0 ? '+' : ''}{offsetY}
                </span>
                <span style={{ fontSize: 13, color: 'var(--text2)', marginLeft: 4 }}>mm</span>
              </div>
              <button className="btn-ghost" style={btnAdj} onClick={() => adjust('y', 1)}>+</button>
            </div>
          </div>

          {/* 적용될 좌표 */}
          <div style={{ padding: '10px 12px', background: 'var(--panel2)', borderRadius: 6, fontSize: 12, color: 'var(--text2)', marginBottom: 14 }}>
            적용 위치 &nbsp;
            X: <b style={{ color: 'var(--accent)' }}>{effectiveX}</b> &nbsp;
            Y: <b style={{ color: 'var(--accent)' }}>{effectiveY}</b>
          </div>

          <div style={{ display: 'flex', gap: 10 }}>
            <button className={saved ? 'btn-success' : 'btn-primary'} style={{ flex: 1 }} onClick={saveCalib}>
              {saved ? '✓ 저장됨' : '보정값 저장'}
            </button>
            <button className="btn-ghost" onClick={() => { setOffsetX(0); setOffsetY(0); }}>
              초기화
            </button>
          </div>
        </div>

        {/* 현재 TCP + 픽셀 간격 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card">
            <div className="card-title">현재 TCP 위치 (실시간)</div>
            <Row label="X" value={robotState.tcpX.toFixed(2)} unit="mm" />
            <Row label="Y" value={robotState.tcpY.toFixed(2)} unit="mm" />
            <Row label="Z" value={robotState.tcpZ.toFixed(2)} unit="mm" />
            <button className="btn-ghost" style={{ marginTop: 12, width: '100%' }} onClick={onGoHome}>
              원점 이동
            </button>
          </div>
          <div className="card">
            <div className="card-title">Z</div>
            <div style={{ padding: '8px 10px', background: 'var(--panel2)', borderRadius: 6, fontSize: 12, color: 'var(--text2)' }}>
              Z 높이는 그리기 시작 시 첫 픽셀 위치에서 자동 측정됩니다
            </div>
          </div>
        </div>
      </div>

      {/* 조그 */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div className="card-title" style={{ margin: 0 }}>조그</div>
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
    </div>
  );
}
