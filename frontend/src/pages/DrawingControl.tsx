import type { DrawingState, RobotState } from '../types';
import { DRAWING_STATUS_LABEL, DRAWING_STATUS_COLOR } from '../constants';

interface Props {
  drawingState: DrawingState;
  robotState: RobotState;
  onStop: () => void;
  onPause: () => void;
  onResume: () => void;
  onGoHome: () => void;
  addLog: (msg: string) => void;
}

export default function DrawingControl({ drawingState, robotState, onStop, onPause, onResume, onGoHome, addLog }: Props) {
  const {
    status, currentPixel, totalPixels, resWidth,
    currentGray, targetForce, currentPenForce,
    message, successCount, failPixels, history,
  } = drawingState;

  const progress   = totalPixels > 0 ? Math.round((currentPixel / totalPixels) * 100) : 0;
  const isRunning  = status === 'running';
  const isPaused   = status === 'paused';
  const isActive   = isRunning || isPaused;
  const currentRow = resWidth > 0 ? Math.floor(currentPixel / resWidth) : 0;
  const currentCol = resWidth > 0 ? currentPixel % resWidth : 0;

  // 힘-회색값 관계 표시용 (0~255 → minForce~maxForce)
  const grayPct  = currentGray / 255 * 100;
  const forcePct = targetForce  > 0 ? Math.min(currentPenForce / targetForce * 100, 130) : 0;

  const statusColor = DRAWING_STATUS_COLOR[status];
  const statusLabel = DRAWING_STATUS_LABEL[status];

  return (
    <div>
      <h2 style={{ marginBottom: 20, fontSize: 20, fontWeight: 700 }}>그림 제어</h2>

      {/* 상단 상태 + 제어 버튼 */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 16, marginBottom: 20, alignItems: 'start' }}>
        <div className="card" style={{ borderLeft: `3px solid ${statusColor}` }}>
          <div style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 1 }}>현재 상태</div>
          <div style={{ fontSize: 26, fontWeight: 800, color: statusColor, marginBottom: 4 }}>{statusLabel}</div>
          <div style={{ fontSize: 12, color: 'var(--text2)' }}>{message}</div>
          {drawingState.imageName && (
            <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text2)' }}>
              {drawingState.imageName} · {drawingState.frameSize} · {drawingState.resLabel}
              {drawingState.dryRun && <span className="tag tag-yellow" style={{ marginLeft: 8 }}>건식</span>}
            </div>
          )}
        </div>
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 10, minWidth: 160 }}>
          <button className="btn-outline" disabled={!isRunning}
            style={{ width: '100%' }}
            onClick={() => { onPause(); addLog('[관리자] 일시정지'); }}>
            일시정지
          </button>
          <button className="btn-success" disabled={!isPaused}
            style={{ width: '100%' }}
            onClick={() => { onResume(); addLog('[관리자] 재개'); }}>
            재개
          </button>
          <button className="btn-danger" disabled={!isActive}
            style={{ width: '100%' }}
            onClick={() => { onStop(); addLog('[관리자] 강제 정지'); }}>
            강제정지
          </button>
          <button className="btn-ghost" disabled={isActive}
            style={{ width: '100%' }}
            onClick={() => { onGoHome(); addLog('[관리자] 원점 복귀'); }}>
            원점복귀
          </button>
        </div>
      </div>

      {/* 핵심 지표: 회색값 → 목표 힘 → 실제 힘 */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-title">힘 제어 상태 — 회색값 → 목표 힘 → 실제 힘</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 16 }}>
          {/* 회색값 */}
          <div>
            <div style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 6 }}>현재 회색값 (0~255)</div>
            <div style={{ fontSize: 28, fontWeight: 800, color: `rgb(${currentGray},${currentGray},${currentGray})`,
              textShadow: currentGray < 50 ? 'none' : '0 0 8px rgba(255,255,255,0.3)' }}>
              {isActive ? currentGray : '—'}
            </div>
            <div style={{ marginTop: 8, height: 8, background: 'var(--panel2)', borderRadius: 4, overflow: 'hidden' }}>
              <div style={{
                height: '100%', width: `${grayPct}%`,
                background: `rgb(${currentGray},${currentGray},${currentGray})`,
                borderRadius: 4, transition: 'width 0.3s',
              }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text2)', marginTop: 3 }}>
              <span>0 (검정)</span><span>255 (흰색)</span>
            </div>
          </div>

          {/* 목표 힘 */}
          <div>
            <div style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 6 }}>목표 힘 (N)</div>
            <div style={{ fontSize: 28, fontWeight: 800, color: 'var(--accent2)' }}>
              {isActive && targetForce > 0 ? `${targetForce.toFixed(1)} N` : '—'}
            </div>
            <div style={{ marginTop: 8, height: 8, background: 'var(--panel2)', borderRadius: 4, overflow: 'hidden' }}>
              <div style={{
                height: '100%', width: `${targetForce > 0 ? (targetForce / 60 * 100) : 0}%`,
                background: 'var(--accent2)', borderRadius: 4, transition: 'width 0.3s',
              }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text2)', marginTop: 3 }}>
              <span>0 N</span><span>60 N</span>
            </div>
          </div>

          {/* 실제 힘 */}
          <div>
            <div style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 6 }}>실제 힘 (N)</div>
            <div style={{ fontSize: 28, fontWeight: 800,
              color: forcePct > 110 ? 'var(--red)' : isActive ? 'var(--yellow)' : 'var(--text2)' }}>
              {robotState.penForce > 0 ? `${robotState.penForce.toFixed(1)} N` : '—'}
            </div>
            <div style={{ marginTop: 8, height: 8, background: 'var(--panel2)', borderRadius: 4, overflow: 'hidden' }}>
              <div style={{
                height: '100%',
                width: `${Math.min(robotState.penForce / 60 * 100, 100)}%`,
                background: forcePct > 110 ? 'var(--red)' : 'var(--yellow)',
                borderRadius: 4, transition: 'width 0.3s',
              }} />
            </div>
            {targetForce > 0 && (
              <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 3 }}>
                오차: {Math.abs(robotState.penForce - targetForce).toFixed(1)} N
                {forcePct > 110 && <span style={{ color: 'var(--red)', marginLeft: 6 }}>⚠ 초과</span>}
              </div>
            )}
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
        {/* 진행 상황 */}
        <div className="card">
          <div className="card-title">진행 상황</div>

          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 5 }}>
            <span style={{ color: statusColor, fontWeight: 700 }}>{statusLabel}</span>
            <span style={{ color: 'var(--text2)' }}>{progress}%</span>
          </div>
          <div style={{ height: 12, background: 'var(--panel2)', borderRadius: 6, overflow: 'hidden', marginBottom: 16 }}>
            <div style={{
              height: '100%', width: `${progress}%`, borderRadius: 6, transition: 'width 0.5s',
              background: status === 'success' ? 'var(--green)' : status === 'failed' ? 'var(--red)'
                : 'linear-gradient(90deg, var(--accent2), var(--accent))',
            }} />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 8 }}>
            {[
              { l: '현재 픽셀',  v: currentPixel.toLocaleString() },
              { l: '전체 픽셀',  v: totalPixels.toLocaleString() },
              { l: '행(Row)',    v: isActive ? `${currentRow}` : '—' },
              { l: '열(Col)',    v: isActive ? `${currentCol}` : '—' },
              { l: '성공',       v: `${successCount}회` },
              { l: '실패픽셀',   v: `${failPixels}` },
            ].map(({ l, v }) => (
              <div key={l} style={{ background: 'var(--panel2)', borderRadius: 6, padding: '8px 10px' }}>
                <div style={{ fontSize: 10, color: 'var(--text2)', marginBottom: 3 }}>{l}</div>
                <div style={{ fontSize: 14, fontWeight: 700 }}>{v}</div>
              </div>
            ))}
          </div>
        </div>

        {/* 로봇 TCP + 관절 */}
        <div className="card">
          <div className="card-title">로봇 현재 좌표</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: 8, marginBottom: 14 }}>
            {[
              { l: 'TCP X', v: `${robotState.tcpX.toFixed(1)} mm`, c: 'var(--accent)' },
              { l: 'TCP Y', v: `${robotState.tcpY.toFixed(1)} mm`, c: 'var(--accent)' },
              { l: 'TCP Z', v: `${robotState.tcpZ.toFixed(1)} mm`, c: 'var(--accent)' },
              { l: '속도',  v: `${robotState.speed} mm/s`,         c: 'var(--yellow)' },
            ].map(({ l, v, c }) => (
              <div key={l} style={{ background: 'var(--panel2)', borderRadius: 6, padding: '10px 12px' }}>
                <div style={{ fontSize: 10, color: 'var(--text2)', marginBottom: 3 }}>{l}</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: c }}>{v}</div>
              </div>
            ))}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 8 }}>관절 각도 (°)</div>
          {robotState.joints.map((j, i) => (
            <div key={i} style={{ marginBottom: 6 }}>
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
      </div>

      {/* 작업 이력 */}
      <div className="card">
        <div className="card-title">작업 이력 ({history.length}건)</div>
        {history.length === 0 ? (
          <div style={{ color: 'var(--text2)', fontSize: 13 }}>작업 이력 없음</div>
        ) : (
          <div style={{ maxHeight: 280, overflowY: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>시작</th>
                  <th>종료</th>
                  <th>이미지</th>
                  <th>해상도</th>
                  <th>용지</th>
                  <th>픽셀</th>
                  <th>실패픽셀</th>
                  <th>소요</th>
                  <th>모드</th>
                  <th>결과</th>
                </tr>
              </thead>
              <tbody>
                {history.map(job => (
                  <tr key={job.id}>
                    <td style={{ color: 'var(--text2)', whiteSpace: 'nowrap', fontSize: 11 }}>{job.startTime}</td>
                    <td style={{ color: 'var(--text2)', whiteSpace: 'nowrap', fontSize: 11 }}>{job.endTime}</td>
                    <td style={{ maxWidth: 100, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{job.imageName}</td>
                    <td>{job.resLabel}</td>
                    <td>{job.paperType}</td>
                    <td>{job.totalPixels.toLocaleString()}</td>
                    <td style={{ color: job.failPixels > 0 ? 'var(--red)' : 'var(--text2)' }}>{job.failPixels}</td>
                    <td>{job.duration}</td>
                    <td>{job.dryRun ? <span className="tag tag-yellow">건식</span> : <span className="tag tag-blue">실제</span>}</td>
                    <td>
                      <span className={`tag ${job.status === 'success' ? 'tag-green' : job.status === 'failed' ? 'tag-red' : 'tag-gray'}`}>
                        {DRAWING_STATUS_LABEL[job.status]}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
