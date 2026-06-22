import { useState } from 'react';
import type { Settings } from '../types';
import { RESOLUTIONS } from '../constants';

interface Props {
  settings: Settings;
  setSettings: (s: Settings) => void;
  addLog: (msg: string) => void;
}

const PAPER_SIZES = ['A4', 'A3', 'custom'] as const;

export default function SettingsPage({ settings, setSettings, addLog }: Props) {
  const [form, setForm] = useState<Settings>({ ...settings });
  const [saved, setSaved] = useState(false);

  function n(key: keyof Settings, min?: number, max?: number) {
    return (
      <input
        type="number"
        value={form[key] as number}
        min={min}
        max={max}
        onChange={e => setForm(p => ({ ...p, [key]: Number(e.target.value) }))}
      />
    );
  }

  function save(e: React.FormEvent) {
    e.preventDefault();
    setSettings({ ...form });
    setSaved(true);
    addLog('시스템 설정 저장됨');
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div>
      <h2 style={{ marginBottom: 20, fontSize: 20, fontWeight: 700 }}>시스템 설정</h2>
      <form onSubmit={save}>

        {/* 이미지 설정 */}
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--accent)', marginBottom: 16 }}>이미지 설정</div>
          <div>
            <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 8 }}>해상도</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 8 }}>
              {RESOLUTIONS.filter(r => r.key !== 'custom').map(r => (
                <button type="button" key={r.key}
                  onClick={() => setForm(p => ({ ...p, resolutionKey: r.key }))}
                  style={{
                    padding: '10px 0', borderRadius: 6, border: '1px solid',
                    borderColor: form.resolutionKey === r.key ? 'var(--accent)' : 'var(--border)',
                    background: form.resolutionKey === r.key ? 'rgba(0,102,255,0.15)' : 'var(--panel2)',
                    color: form.resolutionKey === r.key ? 'var(--accent)' : 'var(--text2)',
                    cursor: 'pointer', fontSize: 13, fontWeight: form.resolutionKey === r.key ? 700 : 400,
                  }}>
                  {r.key === '50'  && <><div style={{ fontSize: 15, fontWeight: 700 }}>50×50</div><div style={{ fontSize: 10 }}>2,500px · 빠름</div></>}
                  {r.key === '80'  && <><div style={{ fontSize: 15, fontWeight: 700 }}>80×80</div><div style={{ fontSize: 10 }}>6,400px</div></>}
                  {r.key === '100' && <><div style={{ fontSize: 15, fontWeight: 700 }}>100×100</div><div style={{ fontSize: 10 }}>10,000px · 기본</div></>}
                  {r.key === '150' && <><div style={{ fontSize: 15, fontWeight: 700 }}>150×150</div><div style={{ fontSize: 10 }}>22,500px</div></>}
                  {r.key === '200' && <><div style={{ fontSize: 15, fontWeight: 700 }}>200×200</div><div style={{ fontSize: 10 }}>40,000px</div></>}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* 힘 제어 설정 */}
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--accent2)', marginBottom: 16 }}>힘 제어 설정</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 16 }}>
            <div>
              <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 6 }}>최소 힘 (N) <span style={{ color: 'var(--border)' }}>1~30</span></div>
              {n('minForce', 1, 30)}
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 6 }}>최대 힘 (N) <span style={{ color: 'var(--border)' }}>1~80</span></div>
              {n('maxForce', 1, 80)}
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 6 }}>최대 허용 힘 (N) <span style={{ color: 'var(--border)' }}>최대 힘+10</span></div>
              {n('maxAllowedForce', 1, 100)}
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 6 }}>점 유지 시간 (ms) <span style={{ color: 'var(--border)' }}>50~2000</span></div>
              {n('dotHoldMs', 50, 2000)}
            </div>
          </div>
          <div style={{ marginTop: 12, padding: '10px 14px', background: 'var(--panel2)', borderRadius: 6, fontSize: 12, color: 'var(--text2)' }}>
            힘 매핑: 회색값 255(흰색) → {form.minForce} N, 회색값 0(검정) → {form.maxForce} N
          </div>
        </div>

        {/* 출력 설정 */}
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--yellow)', marginBottom: 16 }}>출력 설정</div>
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 8 }}>용지 크기</div>
            <div style={{ display: 'flex', gap: 8 }}>
              {PAPER_SIZES.map(s => (
                <button type="button" key={s}
                  onClick={() => setForm(p => ({ ...p, paperSize: s }))}
                  style={{
                    padding: '8px 20px', borderRadius: 6, border: '1px solid',
                    borderColor: form.paperSize === s ? 'var(--yellow)' : 'var(--border)',
                    background: form.paperSize === s ? 'rgba(255,234,0,0.12)' : 'var(--panel2)',
                    color: form.paperSize === s ? 'var(--yellow)' : 'var(--text2)',
                    cursor: 'pointer', fontWeight: form.paperSize === s ? 700 : 400, fontSize: 13,
                  }}>
                  {s === 'A4' ? 'A4 (210×297mm)' : s === 'A3' ? 'A3 (297×420mm)' : '사용자 정의'}
                </button>
              ))}
            </div>
          </div>
          {form.paperSize === 'custom' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div>
                <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 6 }}>너비 (mm)</div>
                {n('customPaperW', 50, 600)}
              </div>
              <div>
                <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 6 }}>높이 (mm)</div>
                {n('customPaperH', 50, 600)}
              </div>
            </div>
          )}
        </div>

        {/* 로봇 설정 */}
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--green)', marginBottom: 16 }}>로봇 설정</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 16 }}>
            <div>
              <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 6 }}>최대 TCP 속도 (mm/s) <span style={{ color: 'var(--border)' }}>1~2000</span></div>
              {n('maxSpeed', 1, 2000)}
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 6 }}>최대 가속도 (mm/s²) <span style={{ color: 'var(--border)' }}>1~5000</span></div>
              {n('maxAccel', 1, 5000)}
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 6 }}>로그 보관 (일) <span style={{ color: 'var(--border)' }}>1~365</span></div>
              {n('logRetention', 1, 365)}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <button type="submit" className="btn-primary" style={{ padding: '10px 32px' }}>
            {saved ? '✓ 저장됨' : '저장'}
          </button>
          <button type="button" className="btn-ghost" onClick={() => setForm({ ...settings })}>
            변경사항 취소
          </button>
          <span style={{ fontSize: 12, color: 'var(--text2)' }}>* 저장 즉시 반영됩니다</span>
        </div>
      </form>
    </div>
  );
}
