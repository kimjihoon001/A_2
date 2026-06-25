import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import type { RobotState, Alarm, HistoryPoint, DrawingState } from '../types';
import { STATUS_LABEL, STATUS_COLOR, DRAWING_STATUS_LABEL, DRAWING_STATUS_COLOR } from '../constants';

interface Props {
  robotState: RobotState;
  history: HistoryPoint[];
  alarms: Alarm[];
  drawingState: DrawingState;
  ros2Connected: boolean;
}

function StatCard({ label, value, color, sub, highlight }: {
  label: string; value: string; color: string; sub?: string; highlight?: boolean;
}) {
  return (
    <div className="card" style={{
      display: 'flex', flexDirection: 'column', gap: 6,
      ...(highlight ? { border: '1px solid ' + color, boxShadow: `0 0 12px ${color}33` } : {}),
    }}>
      <div style={{ fontSize: 11, color: 'var(--text2)', textTransform: 'uppercase', letterSpacing: 1 }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 800, color, lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: 'var(--text2)' }}>{sub}</div>}
    </div>
  );
}

function etaStr(drawingState: DrawingState): string {
  const { status, currentPixel, totalPixels, startTime } = drawingState;
  if (status !== 'running' || currentPixel === 0 || startTime === 0) return '—';
  const elapsed = (Date.now() - startTime) / 1000;
  const rate = currentPixel / elapsed;
  if (rate <= 0) return '—';
  const remaining = (totalPixels - currentPixel) / rate;
  const m = Math.floor(remaining / 60);
  const s = Math.floor(remaining % 60);
  return m > 0 ? `${m}분 ${s}초` : `${s}초`;
}

export default function Dashboard({ robotState, history, alarms, drawingState, ros2Connected }: Props) {
  const { status, joints, tcpX, tcpY, tcpZ, penForce } = robotState;
  const drawProgress = drawingState.totalPixels > 0
    ? Math.round((drawingState.currentPixel / drawingState.totalPixels) * 100) : 0;
  const isRunning = drawingState.status === 'running';
  const currentRow = drawingState.resWidth > 0
    ? Math.floor(drawingState.currentPixel / drawingState.resWidth) : 0;
  const currentCol = drawingState.resWidth > 0
    ? drawingState.currentPixel % drawingState.resWidth : 0;

  return (
    <div>
      <h2 style={{ marginBottom: 20, fontSize: 20, fontWeight: 700 }}>대시보드</h2>

      {/* 상단 5개 stat 카드 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 14, marginBottom: 20 }}>
        <StatCard
          label="로봇 상태"
          value={!ros2Connected ? '미연결' : (STATUS_LABEL[status] ?? status)}
          color={!ros2Connected ? 'var(--text2)' : (STATUS_COLOR[status] ?? 'var(--text)')}
          highlight={status === 'estop' || status === 'error'}
        />
        <StatCard
          label="현재 진행률"
          value={`${drawProgress}%`}
          color="var(--accent)"
          sub={isRunning ? `${drawingState.currentPixel.toLocaleString()} / ${drawingState.totalPixels.toLocaleString()} px` : '대기 중'}
        />
        <StatCard
          label="현재 힘"
          value={penForce > 0 ? `${penForce.toFixed(1)} N` : '—'}
          color={penForce > 0 ? 'var(--accent2)' : 'var(--text2)'}
          sub="펜 접촉력"
          highlight={penForce > 55}
        />
        <StatCard
          label="남은 예상 시간"
          value={etaStr(drawingState)}
          color="var(--green)"
          sub={isRunning ? '현재 속도 기준' : ''}
        />
      </div>

      {/* 작업 현황 카드 */}
      <div className="card" style={{
        marginBottom: 20,
        borderLeft: `3px solid ${DRAWING_STATUS_COLOR[drawingState.status]}`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
          <div style={{ fontSize: 14, fontWeight: 700 }}>🎨 작업 현황</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {drawingState.imageName && (
              <span style={{ fontSize: 12, color: 'var(--text2)' }}>
                {drawingState.imageName} · {drawingState.resLabel}
              </span>
            )}
            <span className={`tag ${
              drawingState.status === 'running'  ? 'tag-blue'
              : drawingState.status === 'success'? 'tag-green'
              : drawingState.status === 'failed' ? 'tag-red'
              : drawingState.status === 'paused' ? 'tag-yellow'
              : 'tag-gray'
            }`}>
              {DRAWING_STATUS_LABEL[drawingState.status]}
            </span>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5,1fr)', gap: 10, marginBottom: 14 }}>
          {[
            { l: '완료 픽셀',  v: drawingState.currentPixel.toLocaleString(), c: 'var(--accent)' },
            { l: '전체 픽셀',  v: drawingState.totalPixels.toLocaleString(),  c: 'var(--text)' },
            { l: '성공 횟수',  v: `${drawingState.successCount}회`,           c: 'var(--green)' },
            { l: '실패 횟수',  v: `${drawingState.failCount}회`,              c: 'var(--red)' },
            { l: '현재 위치',  v: isRunning ? `R${currentRow} C${currentCol}` : '—', c: 'var(--yellow)' },
          ].map(({ l, v, c }) => (
            <div key={l} style={{ background: 'var(--panel2)', borderRadius: 6, padding: '10px 12px' }}>
              <div style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 4 }}>{l}</div>
              <div style={{ fontSize: 15, fontWeight: 700, color: c }}>{v}</div>
            </div>
          ))}
        </div>

        {/* 진행 바 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 5 }}>
          <span style={{ color: 'var(--text2)' }}>진행률</span>
          <span style={{ color: 'var(--accent)', fontWeight: 700 }}>{drawProgress}%</span>
        </div>
        <div style={{ height: 8, background: 'var(--panel2)', borderRadius: 4, overflow: 'hidden' }}>
          <div style={{
            height: '100%', width: `${drawProgress}%`,
            background: drawingState.status === 'success' ? 'var(--green)'
              : drawingState.status === 'failed' ? 'var(--red)'
              : 'linear-gradient(90deg, var(--accent2), var(--accent))',
            borderRadius: 4, transition: 'width 0.5s',
          }} />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
        {/* TCP 좌표 + 관절 */}
        <div className="card">
          <div className="card-title">TCP 위치 / 관절</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 8, marginBottom: 16 }}>
            {[
              { l: 'X', v: `${tcpX.toFixed(1)} mm`, c: 'var(--text)' },
              { l: 'Y', v: `${tcpY.toFixed(1)} mm`, c: 'var(--text)' },
              { l: 'Z', v: `${tcpZ.toFixed(1)} mm`, c: 'var(--text)' },
            ].map(({ l, v, c }) => (
              <div key={l} style={{ background: 'var(--panel2)', borderRadius: 6, padding: '10px 10px' }}>
                <div style={{ fontSize: 10, color: 'var(--text2)', marginBottom: 3 }}>{l}</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: c }}>{v}</div>
              </div>
            ))}
          </div>
          {joints.map((j, i) => (
            <div key={i} style={{ marginBottom: 7 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 2 }}>
                <span style={{ color: 'var(--text2)' }}>J{i + 1}</span>
                <span style={{ fontWeight: 600 }}>{j.toFixed(1)}°</span>
              </div>
              <div style={{ height: 4, background: 'var(--panel2)', borderRadius: 2, overflow: 'hidden' }}>
                <div style={{
                  height: '100%', width: `${Math.abs(j) / 180 * 100}%`,
                  background: Math.abs(j) > 160 ? 'var(--red)' : 'var(--accent2)',
                  borderRadius: 2, transition: 'width 0.4s',
                }} />
              </div>
            </div>
          ))}
        </div>

        {/* 힘 추이 차트 */}
        <div className="card">
          <div className="card-title">힘 추이 (N)</div>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={history}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="t" tick={{ fontSize: 10, fill: 'var(--text2)' }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 10, fill: 'var(--text2)' }} />
              <Tooltip contentStyle={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 11 }} />
              <Line type="monotone" dataKey="force" stroke="var(--accent2)" strokeWidth={2} dot={false} name="힘(N)" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 최근 알람 */}
      <div className="card">
        <div className="card-title">최근 알람</div>
        {alarms.length === 0
          ? <div style={{ color: 'var(--text2)', fontSize: 13 }}>알람 없음</div>
          : [...alarms].reverse().slice(0, 6).map(a => (
            <div key={a.id} style={{ display: 'flex', gap: 12, padding: '7px 0', borderBottom: '1px solid var(--border)', alignItems: 'center' }}>
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
  );
}
