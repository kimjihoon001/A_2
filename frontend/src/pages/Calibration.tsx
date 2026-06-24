import { useState, useEffect } from 'react';
import type { RobotState, CalibrationData } from '../types';
import type { CalibrateZResult } from '../hooks/useRobotServer';

interface Props {
  robotState: RobotState;
  addLog: (msg: string) => void;
  onGoHome: () => void;
  onSaveCalibration: (data: CalibrationData) => void;
  savedCalib: CalibrationData | null;
  onCalibrateZ?: () => void;
  calibratedZ?: CalibrateZResult | null;
}

const DEFAULT_CALIB: CalibrationData = {
  origin_x:         461.0,   // S자 좌상단
  origin_y:          33.0,
  origin_z:         436.33,
  pen_down_z:       435.33,
  pixel_spacing_mm:   2.0,
  center_x:         356.0,   // 동심원 중심
  center_y:         -41.0,
};

function Row({ label, value, unit }: { label: string; value: string | number; unit?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
      <span style={{ fontSize: 13, color: 'var(--text2)' }}>{label}</span>
      <span style={{ fontWeight: 700, color: 'var(--accent)' }}>{value}{unit && <span style={{ color: 'var(--text2)', fontWeight: 400, marginLeft: 4 }}>{unit}</span>}</span>
    </div>
  );
}

export default function CalibrationPage({ robotState, addLog, onGoHome, onSaveCalibration, savedCalib, onCalibrateZ, calibratedZ }: Props) {
  const [calib, setCalib]           = useState<CalibrationData>(savedCalib ?? DEFAULT_CALIB);
  const [saved, setSaved]           = useState(false);
  const [originSaved, setOriginSaved] = useState(false);
  const [zMeasuring, setZMeasuring] = useState(false);
  const [zMeasured,  setZMeasured]  = useState(false);

  // 자동 Z 측정 결과가 오면 캘리브레이션 값에 반영
  useEffect(() => {
    if (!calibratedZ) return;
    setCalib(c => ({ ...c, origin_z: calibratedZ.pen_up_z, pen_down_z: calibratedZ.pen_down_z }));
    setZMeasuring(false);
    setZMeasured(true);
    setTimeout(() => setZMeasured(false), 3000);
  }, [calibratedZ]);

  function setOriginFromTCP() {
    setCalib(c => ({
      ...c,
      origin_x: robotState.tcpX,
      origin_y: robotState.tcpY,
      origin_z: robotState.tcpZ,
    }));
    setOriginSaved(true);
    addLog(`종이 원점 저장: X=${robotState.tcpX.toFixed(1)}, Y=${robotState.tcpY.toFixed(1)}, Z=${robotState.tcpZ.toFixed(1)}`);
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
              {originSaved ? '✓ 원점 저장됨' : '현재 위치를 종이 원점으로 저장'}
            </button>
            <button className="btn-ghost" onClick={onGoHome}>
              원점 이동
            </button>
          </div>

          <div style={{ marginTop: 16, padding: '10px 12px', background: 'var(--panel2)', borderRadius: 6, fontSize: 12, color: 'var(--text2)' }}>
            <div style={{ fontWeight: 600, marginBottom: 6 }}>저장된 종이 원점</div>
            <div>X: <span style={{ color: 'var(--accent)', fontWeight: 700 }}>{calib.origin_x.toFixed(2)}</span> mm &nbsp;
              Y: <span style={{ color: 'var(--accent)', fontWeight: 700 }}>{calib.origin_y.toFixed(2)}</span> mm &nbsp;
              Z: <span style={{ color: 'var(--accent)', fontWeight: 700 }}>{calib.origin_z.toFixed(2)}</span> mm
            </div>
          </div>
        </div>

        {/* Z 높이 + 픽셀 간격 */}
        <div className="card">
          <div className="card-title">Z 높이 설정</div>
          <button
            className={zMeasured ? 'btn-success' : 'btn-primary'}
            style={{ width: '100%', marginBottom: 12 }}
            disabled={zMeasuring}
            onClick={() => {
              setZMeasuring(true);
              addLog('자동 Z 측정 시작 — 종이에 천천히 내림...');
              onCalibrateZ?.();
            }}>
            {zMeasuring ? '측정 중...' : zMeasured ? '✓ Z 측정 완료' : '자동 Z 측정 (펜 접촉점 자동 감지)'}
          </button>
          {calibratedZ && (
            <div style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--panel2)', borderRadius: 6, fontSize: 12, color: 'var(--text2)' }}>
              접촉 Z: <span style={{ color: 'var(--accent)', fontWeight: 700 }}>{calibratedZ.contact_z} mm</span>
              &nbsp;→&nbsp; pen_up: <span style={{ color: 'var(--accent)', fontWeight: 700 }}>{calibratedZ.pen_up_z}</span>
              &nbsp;/ pen_down: <span style={{ color: 'var(--accent)', fontWeight: 700 }}>{calibratedZ.pen_down_z}</span>
            </div>
          )}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
            {numField('origin_z',   'Pen-up Z (이동 높이)',   'mm')}
            {numField('pen_down_z', 'Pen-down Z (접촉 높이)', 'mm')}
          </div>

          <div className="card-title">픽셀 간격</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 12 }}>
            {numField('pixel_spacing_mm', '픽셀 간격', 'mm', 0.1)}
          </div>
        </div>
      </div>

      {/* 좌표 설정 */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
        {/* S자 — 좌상단 */}
        <div className="card">
          <div className="card-title">▶ S자 기준점 (종이 좌상단)</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            {numField('origin_x', 'X', 'mm')}
            {numField('origin_y', 'Y', 'mm')}
          </div>
          <div style={{ marginTop: 10, padding: '8px 10px', background: 'var(--panel2)', borderRadius: 6, fontSize: 11, color: 'var(--text2)' }}>
            로봇을 종이 좌상단 모서리에 위치시킨 후 저장
          </div>
        </div>
      </div>

      {/* 저장 */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <button className="btn-primary" style={{ padding: '10px 32px' }} onClick={saveCalib}>
          {saved ? '✓ 저장됨' : '캘리브레이션 저장'}
        </button>
        <button className="btn-ghost" onClick={() => setCalib(savedCalib ?? DEFAULT_CALIB)}>
          초기화
        </button>
        <span style={{ fontSize: 12, color: 'var(--text2)' }}>* 저장 즉시 그리기에 반영됩니다</span>
      </div>
    </div>
  );
}
