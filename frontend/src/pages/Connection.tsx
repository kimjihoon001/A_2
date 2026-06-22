import { useState } from 'react';
import type { Connection } from '../types';

interface Props {
  conn: Connection;
  setConn: React.Dispatch<React.SetStateAction<Connection>>;
  addLog: (msg: string) => void;
  serverUrl: string;
  setServerUrl: (url: string) => void;
  serverConnected: boolean;
  ros2Connected: boolean;
  robotConnected: boolean;
}

const DOT = ({ ok, pulse }: { ok: boolean; pulse?: boolean }) => (
  <div style={{
    width: 12, height: 12, borderRadius: '50%', flexShrink: 0,
    background: ok ? 'var(--green)' : 'var(--red)',
    boxShadow: ok && pulse ? '0 0 10px var(--green)' : 'none',
  }} />
);

function ConnCard({ icon, title, status, sub, color, children }: {
  icon: string; title: string; status: string; sub?: string; color: string; children?: React.ReactNode;
}) {
  const ok = status === '연결됨';
  return (
    <div className="card" style={{ borderLeft: `3px solid ${ok ? 'var(--green)' : color}` }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
        <span style={{ fontSize: 20 }}>{icon}</span>
        <div>
          <div style={{ fontWeight: 700, fontSize: 14 }}>{title}</div>
          {sub && <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 2 }}>{sub}</div>}
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 14px', background: 'var(--panel2)', borderRadius: 8, marginBottom: children ? 12 : 0 }}>
        <DOT ok={ok} pulse />
        <span style={{ fontWeight: 700, color: ok ? 'var(--green)' : 'var(--red)', fontSize: 14 }}>{status}</span>
        {ok  && <span className="tag tag-green" style={{ marginLeft: 'auto', fontSize: 10 }}>정상</span>}
        {!ok && <span className="tag tag-red"   style={{ marginLeft: 'auto', fontSize: 10 }}>오프라인</span>}
      </div>
      {children}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border)', fontSize: 12 }}>
      <span style={{ color: 'var(--text2)' }}>{label}</span>
      <span style={{ fontWeight: 600, fontFamily: 'monospace' }}>{value}</span>
    </div>
  );
}

export default function ConnectionPage({
  conn, addLog, serverUrl, setServerUrl, serverConnected, ros2Connected, robotConnected,
}: Props) {
  const [serverUrlInput, setServerUrlInput] = useState(serverUrl);

  function applyServerUrl() {
    setServerUrl(serverUrlInput);
    addLog(`서버 URL 변경: ${serverUrlInput}`);
  }

  const allOk   = serverConnected && ros2Connected && robotConnected;
  const okCount = [serverConnected, ros2Connected, robotConnected].filter(Boolean).length;

  // serverUrl에서 호스트 추출 (ws://192.168.1.230:8765/ws → 192.168.1.230)
  const serverHost = serverUrl.replace(/^wss?:\/\//, '').split(':')[0] ?? '—';
  const serverPort = serverUrl.replace(/^wss?:\/\//, '').split(':')[1]?.split('/')[0] ?? '8765';

  return (
    <div>
      <h2 style={{ marginBottom: 20, fontSize: 20, fontWeight: 700 }}>연결관리</h2>

      {/* 전체 상태 요약 */}
      <div className="card" style={{
        marginBottom: 20,
        borderLeft: `3px solid ${allOk ? 'var(--green)' : okCount >= 2 ? 'var(--yellow)' : 'var(--red)'}`,
        background: allOk ? 'rgba(0,230,118,0.04)' : undefined,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>시스템 연결 상태</div>
            <div style={{ fontSize: 12, color: 'var(--text2)' }}>
              {allOk ? '모든 연결 정상' : `${okCount}/3 연결됨`}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 20, marginLeft: 'auto', flexWrap: 'wrap' }}>
            {[
              { l: 'Python 서버', ok: serverConnected },
              { l: 'ROS2',        ok: ros2Connected   },
              { l: 'M0609 로봇',  ok: robotConnected  },
            ].map(({ l, ok }) => (
              <div key={l} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <DOT ok={ok} pulse={ok} />
                <span style={{ fontSize: 12, color: ok ? 'var(--green)' : 'var(--text2)', fontWeight: ok ? 600 : 400 }}>{l}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>

        {/* Python 서버 */}
        <ConnCard icon="🖥️" title="Python 제어 서버" color="var(--accent)"
          status={serverConnected ? '연결됨' : '연결 끊김'} sub={serverUrl}>
          <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 6 }}>WebSocket URL</div>
          <div style={{ display: 'flex', gap: 8 }}>
            <input value={serverUrlInput} onChange={e => setServerUrlInput(e.target.value)}
              placeholder="ws://192.168.1.10:8765/ws" style={{ flex: 1 }} />
            <button className="btn-primary" onClick={applyServerUrl} style={{ flexShrink: 0 }}>적용</button>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 8 }}>
            {serverConnected ? '✓ 연결됨' : '연결 끊김 — 3초마다 자동 재시도'}
          </div>
        </ConnCard>

        {/* ROS2 */}
        <ConnCard icon="🔄" title="ROS2 드라이버" color="var(--accent2)"
          status={ros2Connected ? '연결됨' : '오프라인'} sub="dsr_bringup2 / DSR_ROBOT2">
          <InfoRow label="네임스페이스" value="/dsr01" />
          <InfoRow label="드라이버"     value="dsr_controller2" />
          <InfoRow label="토픽"         value="/dsr01/msg/joint_state" />
        </ConnCard>

        {/* M0609 로봇 — 서버에서 받은 실제 값 표시 */}
        <ConnCard icon="🤖" title="M0609 로봇팔" color="var(--green)"
          status={robotConnected ? '연결됨' : '연결 끊김'}
          sub={`${conn.ip} : ${conn.port} (${conn.protocol})`}>
          <InfoRow label="IP 주소"     value={conn.ip || '—'} />
          <InfoRow label="포트"        value={conn.port ? `${conn.port}` : '—'} />
          <InfoRow label="프로토콜"    value={conn.protocol || '—'} />
          <InfoRow label="마지막 연결" value={conn.lastConnect ?? '—'} />
          <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 10, padding: '8px', background: 'var(--panel2)', borderRadius: 6 }}>
            IP/포트는 <code>dsr01_parameters.yaml</code> 에서 자동 읽힘.
            변경 시 YAML 수정 후 서버를 재시작하세요.
          </div>
        </ConnCard>

        {/* 네트워크 구성 — 실제 값 사용 */}
        <ConnCard icon="📡" title="네트워크 구성" color="var(--yellow)"
          status={serverConnected ? '연결됨' : '연결 끊김'} sub="HMI ↔ Python 서버 ↔ 로봇">
          {[
            { l: 'HMI / Python 서버', ip: serverHost,  port: serverPort,         c: 'var(--accent)',  d: 'WebSocket 서버' },
            { l: 'M0609 로봇',        ip: conn.ip||'—', port: `${conn.port||'—'}`, c: 'var(--green)',   d: 'Doosan DRCF' },
            { l: 'RG2 그리퍼',        ip: '192.168.1.1', port: '502',             c: 'var(--yellow)',  d: 'Modbus TCP' },
          ].map((n, i) => (
            <div key={i} style={{ padding: '8px 10px', marginBottom: 6, background: 'var(--panel2)', borderRadius: 6, borderLeft: `3px solid ${n.c}` }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                <span style={{ fontWeight: 600, fontSize: 12, color: n.c }}>{n.l}</span>
                <span style={{ fontSize: 11, color: 'var(--text2)', fontFamily: 'monospace' }}>{n.ip} : {n.port}</span>
              </div>
              <div style={{ fontSize: 11, color: 'var(--text2)' }}>{n.d}</div>
            </div>
          ))}
        </ConnCard>

      </div>
    </div>
  );
}
