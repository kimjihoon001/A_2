import type { ReactNode } from 'react';
import type { User } from '../types';
import { NAV_ITEMS, ROLE_LABELS, ROLE_COLORS } from '../constants';

interface Props {
  user: User;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  onLogout: () => void;
  alarmCount: number;
  serverConnected: boolean;
  children: ReactNode;
}

export default function Layout({ user, activeTab, setActiveTab, onLogout, alarmCount, serverConnected, children }: Props) {
  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* 사이드바 */}
      <aside style={{ width: 210, minWidth: 210, background: 'var(--panel)', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--accent)' }}>🤖 ROBOT PEN ART</div>
          <div style={{ fontSize: 10, color: 'var(--text2)', marginTop: 2, marginBottom: 10 }}>M0609 · 힘 제어 점묘화 시스템</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 10px', background: 'var(--panel2)', borderRadius: 6 }}>
            <div style={{
              width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
              background: serverConnected ? 'var(--green)' : 'var(--red)',
              boxShadow: serverConnected ? '0 0 6px var(--green)' : 'none',
            }} />
            <span style={{ fontSize: 11, color: serverConnected ? 'var(--green)' : 'var(--text2)' }}>
              {serverConnected ? '서버 연결됨' : '서버 연결 끊김'}
            </span>
          </div>
        </div>

        <nav style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
          {NAV_ITEMS.map(item => {
            const active = activeTab === item.id;
            return (
              <button key={item.id} onClick={() => setActiveTab(item.id)}
                style={{
                  width: '100%', textAlign: 'left',
                  background: active ? 'rgba(0,102,255,0.18)' : 'transparent',
                  color: active ? 'var(--accent)' : 'var(--text2)',
                  borderLeft: active ? '3px solid var(--accent)' : '3px solid transparent',
                  border: 'none', borderRadius: 0,
                  padding: '10px 18px',
                  fontSize: 13, display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer',
                }}>
                <span style={{ fontSize: 15 }}>{item.icon}</span>
                <span style={{ flex: 1 }}>{item.label}</span>
                {item.id === 'safety' && alarmCount > 0 && (
                  <span style={{ background: 'var(--red)', color: '#fff', borderRadius: 10, fontSize: 10, padding: '1px 6px', fontWeight: 700 }}>
                    {alarmCount}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        <div style={{ padding: 14, borderTop: '1px solid var(--border)', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
            <div style={{
              width: 32, height: 32, borderRadius: '50%',
              background: ROLE_COLORS[user.role],
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 14, fontWeight: 700, color: '#fff', flexShrink: 0,
            }}>
              {user.name[0]}
            </div>
            <div style={{ overflow: 'hidden' }}>
              <div style={{ fontSize: 13, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user.name}</div>
              <span className="tag" style={{ background: ROLE_COLORS[user.role] + '22', color: ROLE_COLORS[user.role], marginTop: 2 }}>
                {ROLE_LABELS[user.role]}
              </span>
            </div>
          </div>
          <button className="btn-ghost" style={{ width: '100%', fontSize: 12, marginBottom: 6 }} onClick={onLogout}>
            로그아웃
          </button>
          <button className="btn-outline" style={{ width: '100%', fontSize: 11 }} onClick={onLogout}>
            🎨 손님 화면으로
          </button>
        </div>
      </aside>

      {/* 메인 콘텐츠 */}
      <main style={{ flex: 1, overflowY: 'auto', padding: 24, background: 'var(--bg)' }}>
        {children}
      </main>
    </div>
  );
}
