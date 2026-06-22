import type { RobotState, Alarm, Settings } from '../types';

interface Props {
  robotState: RobotState;
  alarms: Alarm[];
  onEstop: () => void;
  onResetEstop: () => void;
  settings: Settings;
  forceExceedCount: number;
}

export default function SafetyPage({ robotState, alarms, onEstop, onResetEstop, settings, forceExceedCount }: Props) {
  const isEstop = robotState.status === 'estop';

  const checks = [
    { label: '비상정지 회로',   ok: !isEstop },
    { label: '관절 각도 한계',  ok: robotState.joints.every(j => Math.abs(j) < 170) },
    { label: 'TCP 속도 제한',   ok: robotState.speed <= settings.maxSpeed },
    { label: '힘 제한',         ok: robotState.penForce <= settings.maxAllowedForce },
  ];

  const errorAlarms  = alarms.filter(a => a.level === 'error');
  const warnAlarms   = alarms.filter(a => a.level === 'warning');
  const safetyEvents = alarms.filter(a => a.msg.includes('E-STOP') || a.msg.includes('비상') || a.msg.includes('힘') || a.msg.includes('초과'));

  const forceOk     = robotState.penForce <= settings.maxAllowedForce;
  const forcePct    = settings.maxAllowedForce > 0 ? (robotState.penForce / settings.maxAllowedForce * 100) : 0;

  return (
    <div>
      <h2 style={{ marginBottom: 20, fontSize: 20, fontWeight: 700 }}>안전관리</h2>

      {/* E-STOP 패널 */}
      <div style={{
        background: 'var(--panel)',
        border: `2px solid ${isEstop ? 'var(--red)' : 'var(--border)'}`,
        borderRadius: 8, padding: 28, marginBottom: 20, textAlign: 'center',
        boxShadow: isEstop ? '0 0 24px rgba(255,23,68,0.35)' : 'none',
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>비상정지 (E-STOP)</div>
        {isEstop ? (
          <>
            <div style={{ fontSize: 24, color: 'var(--red)', fontWeight: 800, marginBottom: 16 }}>
              ⚠ 비상정지 활성화됨
            </div>
            <div style={{ fontSize: 13, color: 'var(--text2)', marginBottom: 20 }}>
              모든 동작이 즉시 정지되었습니다. 안전 확인 후 해제하십시오.
            </div>
            <button className="btn-success" style={{ padding: '12px 40px', fontSize: 15 }} onClick={onResetEstop}>
              비상정지 해제
            </button>
          </>
        ) : (
          <>
            <div style={{ fontSize: 13, color: 'var(--text2)', marginBottom: 20 }}>
              긴급 상황 발생 시 즉시 눌러 모든 동작을 정지합니다.
            </div>
            <button className="btn-danger" style={{ padding: '16px 60px', fontSize: 22, fontWeight: 800, letterSpacing: 2 }} onClick={onEstop}>
              E-STOP
            </button>
          </>
        )}
      </div>

      {/* 힘 모니터링 + 안전 체크 */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>

        {/* 힘 모니터링 */}
        <div className="card">
          <div className="card-title">힘 모니터링</div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 10, marginBottom: 16 }}>
            <div style={{ background: 'var(--panel2)', borderRadius: 6, padding: '12px 14px' }}>
              <div style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 4 }}>현재 힘</div>
              <div style={{ fontSize: 22, fontWeight: 800, color: forceOk ? 'var(--yellow)' : 'var(--red)' }}>
                {robotState.penForce > 0 ? `${robotState.penForce.toFixed(1)} N` : '—'}
              </div>
            </div>
            <div style={{ background: 'var(--panel2)', borderRadius: 6, padding: '12px 14px' }}>
              <div style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 4 }}>최대 허용 힘</div>
              <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--text)' }}>
                {settings.maxAllowedForce} N
              </div>
            </div>
            <div style={{ background: 'var(--panel2)', borderRadius: 6, padding: '12px 14px',
              ...(forceExceedCount > 0 ? { border: '1px solid var(--red)' } : {}) }}>
              <div style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 4 }}>힘 초과 횟수</div>
              <div style={{ fontSize: 22, fontWeight: 800, color: forceExceedCount > 0 ? 'var(--red)' : 'var(--green)' }}>
                {forceExceedCount}회
              </div>
            </div>
          </div>

          {/* 힘 게이지 */}
          <div style={{ marginBottom: 6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 5 }}>
              <span style={{ color: 'var(--text2)' }}>힘 게이지</span>
              <span style={{ color: forceOk ? 'var(--text2)' : 'var(--red)', fontWeight: 700 }}>
                {forcePct.toFixed(0)}%
              </span>
            </div>
            <div style={{ height: 16, background: 'var(--panel2)', borderRadius: 8, overflow: 'hidden', position: 'relative' }}>
              <div style={{
                height: '100%', width: `${Math.min(forcePct, 100)}%`,
                background: forcePct > 90 ? 'var(--red)' : forcePct > 70 ? 'var(--yellow)' : 'var(--green)',
                borderRadius: 8, transition: 'width 0.3s',
              }} />
              {/* 최대 허용 마커 */}
              <div style={{
                position: 'absolute', top: 0, right: 0, bottom: 0, width: 2,
                background: 'var(--red)', opacity: 0.7,
              }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text2)', marginTop: 3 }}>
              <span>0 N</span>
              <span style={{ color: 'var(--red)', fontSize: 10 }}>한계 {settings.maxAllowedForce} N</span>
            </div>
          </div>

          <div style={{ marginTop: 12, padding: '10px 12px', background: 'var(--panel2)', borderRadius: 6 }}>
            <div style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 4 }}>설정 범위</div>
            <div style={{ fontSize: 13 }}>
              최소 <span style={{ color: 'var(--accent2)', fontWeight: 700 }}>{settings.minForce} N</span>
              &nbsp;→&nbsp;
              최대 <span style={{ color: 'var(--accent)', fontWeight: 700 }}>{settings.maxForce} N</span>
              &nbsp;(점 유지 <span style={{ fontWeight: 700 }}>{settings.dotHoldMs} ms</span>)
            </div>
          </div>
        </div>

        {/* 안전 상태 체크 */}
        <div className="card">
          <div className="card-title">안전 상태 체크</div>
          {checks.map((c, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '11px 0', borderBottom: '1px solid var(--border)' }}>
              <span style={{ fontSize: 13 }}>{c.label}</span>
              <span className={`tag ${c.ok ? 'tag-green' : 'tag-red'}`}>{c.ok ? '정상' : '이상'}</span>
            </div>
          ))}

          <div style={{ marginTop: 16, display: 'flex', gap: 10 }}>
            <div style={{ flex: 1, textAlign: 'center', padding: '10px 0', background: 'rgba(255,23,68,0.1)', borderRadius: 6 }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--red)' }}>{errorAlarms.length}</div>
              <div style={{ fontSize: 11, color: 'var(--text2)' }}>오류</div>
            </div>
            <div style={{ flex: 1, textAlign: 'center', padding: '10px 0', background: 'rgba(255,234,0,0.1)', borderRadius: 6 }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--yellow)' }}>{warnAlarms.length}</div>
              <div style={{ fontSize: 11, color: 'var(--text2)' }}>경고</div>
            </div>
            <div style={{ flex: 1, textAlign: 'center', padding: '10px 0', background: 'rgba(0,230,118,0.1)', borderRadius: 6 }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--green)' }}>{checks.filter(c => c.ok).length}/{checks.length}</div>
              <div style={{ fontSize: 11, color: 'var(--text2)' }}>정상</div>
            </div>
          </div>

          <div style={{ marginTop: 16 }}>
            <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 8 }}>로봇 제한값</div>
            {[
              { l: '최대 TCP 속도', v: `${settings.maxSpeed} mm/s`,  c: 'var(--accent)' },
              { l: '최대 가속도',   v: `${settings.maxAccel} mm/s²`, c: 'var(--accent2)' },
            ].map((z, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
                <span style={{ color: 'var(--text2)', fontSize: 12 }}>{z.l}</span>
                <span style={{ fontWeight: 700, color: z.c, fontSize: 13 }}>{z.v}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 최근 안전 이벤트 */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <div className="card-title" style={{ marginBottom: 0 }}>최근 안전 이벤트</div>
          <span style={{ fontSize: 12, color: 'var(--text2)' }}>총 {alarms.length}건</span>
        </div>
        <div style={{ maxHeight: 260, overflowY: 'auto' }}>
          {safetyEvents.length === 0
            ? <div style={{ color: 'var(--text2)', fontSize: 13 }}>안전 이벤트 없음</div>
            : [...safetyEvents].reverse().map(a => (
              <div key={a.id} style={{ display: 'flex', gap: 12, padding: '8px 0', borderBottom: '1px solid var(--border)', alignItems: 'center' }}>
                <span className={`tag ${a.level === 'error' ? 'tag-red' : a.level === 'warning' ? 'tag-yellow' : 'tag-blue'}`}>
                  {a.level === 'error' ? '오류' : a.level === 'warning' ? '경고' : '정보'}
                </span>
                <span style={{ flex: 1, fontSize: 13 }}>{a.msg}</span>
                <span style={{ fontSize: 11, color: 'var(--text2)', flexShrink: 0 }}>{a.time}</span>
              </div>
            ))
          }
        </div>
      </div>
    </div>
  );
}
