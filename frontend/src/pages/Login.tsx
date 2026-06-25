import { useState } from 'react';
import type { User } from '../types';
import { INITIAL_USERS, ROLE_LABELS, ROLE_COLORS } from '../constants';

interface Props {
  onLogin: (user: User) => void;
  onBack?: () => void;
}

export default function LoginScreen({ onLogin, onBack }: Props) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [err, setErr] = useState('');

  function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    const u = INITIAL_USERS.find(u => u.username === username && u.password === password);
    if (u) { setErr(''); onLogin(u); }
    else setErr('아이디 또는 비밀번호가 올바르지 않습니다.');
  }

  return (
    <div style={{ minHeight:'100vh', display:'flex', alignItems:'center', justifyContent:'center' }}>
      <div style={{ width:400, background:'var(--panel)', border:'1px solid var(--border)', borderRadius:12, padding:40 }}>
        <div style={{ textAlign:'center', marginBottom:32 }}>
          <div style={{ fontSize:48, marginBottom:8 }}>🦾</div>
          <div style={{ fontSize:22, fontWeight:700, color:'var(--accent)', letterSpacing:2 }}>ROBOT ARM HMI</div>
          <div style={{ fontSize:12, color:'var(--text2)', marginTop:4 }}>Industrial Control System v2.1</div>
        </div>

        <form onSubmit={handleLogin}>
          <div style={{ marginBottom:16 }}>
            <div style={{ fontSize:12, color:'var(--text2)', marginBottom:6 }}>아이디</div>
            <input value={username} onChange={e => setUsername(e.target.value)} placeholder="아이디 입력" autoFocus />
          </div>
          <div style={{ marginBottom:24 }}>
            <div style={{ fontSize:12, color:'var(--text2)', marginBottom:6 }}>비밀번호</div>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="비밀번호 입력" />
          </div>
          {err && <div style={{ color:'var(--red)', fontSize:12, marginBottom:12 }}>{err}</div>}
          <button type="submit" className="btn-primary" style={{ width:'100%', padding:12, fontSize:15 }}>
            로그인
          </button>
        </form>

        {onBack && (
          <button className="btn-ghost" style={{ width:'100%', marginTop:12, fontSize:13 }} onClick={onBack}>
            ← 손님 화면으로 돌아가기
          </button>
        )}

        <div style={{ marginTop:16, padding:16, background:'var(--panel2)', borderRadius:8, fontSize:12 }}>
          <div style={{ fontWeight:700, marginBottom:8, color:'var(--text)' }}>테스트 계정</div>
          {INITIAL_USERS.map(u => (
            <div key={u.id} style={{ display:'flex', justifyContent:'space-between', marginBottom:4, color:'var(--text2)' }}>
              <span style={{ color: ROLE_COLORS[u.role] }}>{ROLE_LABELS[u.role]}</span>
              <span>{u.username} / {u.password}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
