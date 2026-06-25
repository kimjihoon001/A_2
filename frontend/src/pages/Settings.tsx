import { useState } from 'react';
import type { Settings } from '../types';

interface Props {
  settings: Settings;
  setSettings: (s: Settings) => void;
  addLog: (msg: string) => void;
}

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

        {/* 로봇 설정 */}
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--green)', marginBottom: 16 }}>로봇 설정</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 16 }}>
            <div>
              <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 6 }}>이동 속도 (mm/s) <span style={{ color: 'var(--border)' }}>10~500</span></div>
              {n('maxSpeed', 10, 500)}
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 6 }}>로그 보관 (일) <span style={{ color: 'var(--border)' }}>1~365</span></div>
              {n('logRetention', 1, 365)}
            </div>
          </div>
          <div style={{ marginTop: 12, padding: '10px 14px', background: 'var(--panel2)', borderRadius: 6, fontSize: 12, color: 'var(--text2)' }}>
            픽셀 간 이동 속도 · 가속도는 속도의 ×2 자동 적용
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
