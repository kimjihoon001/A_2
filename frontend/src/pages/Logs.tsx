import { useState } from 'react';
import type { LogEntry, DrawingJob } from '../types';
import { DRAWING_STATUS_LABEL } from '../constants';

interface Props {
  logs: LogEntry[];
  jobHistory: DrawingJob[];
}

type LogTab = 'system' | 'jobs';

export default function LogsPage({ logs, jobHistory }: Props) {
  const [tab, setTab]       = useState<LogTab>('system');
  const [filter, setFilter] = useState('');

  const filtered = filter
    ? logs.filter(l => l.msg.toLowerCase().includes(filter.toLowerCase()))
    : logs;

  function downloadLogs() {
    const text = [...filtered].reverse().map(l => `[${l.time}] ${l.msg}`).join('\n');
    const a = Object.assign(document.createElement('a'), {
      href: URL.createObjectURL(new Blob([text], { type: 'text/plain' })),
      download: `robot_log_${new Date().toISOString().slice(0, 10)}.txt`,
    });
    a.click();
  }

  function downloadJobs() {
    const header = '시작\t종료\t이미지\t해상도\t용지\t픽셀\t실패픽셀\t소요\t모드\t결과';
    const rows = jobHistory.map(j =>
      `${j.startTime}\t${j.endTime}\t${j.imageName}\t${j.resLabel}\t${j.paperType}\t${j.totalPixels}\t${j.failPixels}\t${j.duration}\t${j.dryRun ? '건식' : '실제'}\t${DRAWING_STATUS_LABEL[j.status]}`
    ).join('\n');
    const a = Object.assign(document.createElement('a'), {
      href: URL.createObjectURL(new Blob([header + '\n' + rows], { type: 'text/plain' })),
      download: `job_history_${new Date().toISOString().slice(0, 10)}.tsv`,
    });
    a.click();
  }

  return (
    <div>
      <h2 style={{ marginBottom: 20, fontSize: 20, fontWeight: 700 }}>작업 로그</h2>

      {/* 탭 */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16 }}>
        {(['system', 'jobs'] as LogTab[]).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={tab === t ? 'btn-primary' : 'btn-ghost'}
            style={{ fontSize: 13 }}>
            {t === 'system' ? `시스템 로그 (${logs.length})` : `작업 이력 (${jobHistory.length})`}
          </button>
        ))}
      </div>

      {tab === 'system' && (
        <div className="card">
          <div style={{ display: 'flex', gap: 12, marginBottom: 14, alignItems: 'center' }}>
            <input value={filter} onChange={e => setFilter(e.target.value)}
              placeholder="로그 검색..." style={{ maxWidth: 280 }} />
            <span style={{ color: 'var(--text2)', fontSize: 12, flexShrink: 0 }}>{filtered.length}건</span>
            <button className="btn-ghost" style={{ marginLeft: 'auto' }} onClick={downloadLogs}>다운로드</button>
          </div>
          <div style={{ maxHeight: 520, overflowY: 'auto', fontFamily: 'ui-monospace, monospace', fontSize: 12 }}>
            {[...filtered].reverse().map(l => {
              const isEstop   = l.msg.includes('E-STOP') || l.msg.includes('비상정지');
              const isStart   = l.msg.includes('그리기 시작');
              const isEnd     = l.msg.includes('그리기 완료') || l.msg.includes('취소') || l.msg.includes('실패');
              const isSafety  = l.msg.includes('초과') || l.msg.includes('안전');
              return (
                <div key={l.id} style={{
                  display: 'flex', gap: 14, padding: '5px 0',
                  borderBottom: '1px solid var(--border)', alignItems: 'flex-start',
                  color: isEstop ? 'var(--red)' : isSafety ? 'var(--yellow)' : isStart || isEnd ? 'var(--accent)' : undefined,
                }}>
                  <span style={{ color: 'var(--text2)', flexShrink: 0, minWidth: 75 }}>{l.time}</span>
                  <span style={{ lineHeight: 1.4 }}>{l.msg}</span>
                </div>
              );
            })}
            {filtered.length === 0 && <div style={{ color: 'var(--text2)', padding: 8 }}>로그 없음</div>}
          </div>
        </div>
      )}

      {tab === 'jobs' && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
            <span style={{ fontSize: 13, color: 'var(--text2)' }}>총 {jobHistory.length}건</span>
            <button className="btn-ghost" onClick={downloadJobs}>TSV 다운로드</button>
          </div>
          {jobHistory.length === 0 ? (
            <div style={{ color: 'var(--text2)', fontSize: 13 }}>작업 이력 없음</div>
          ) : (
            <div style={{ maxHeight: 520, overflowY: 'auto' }}>
              <table>
                <thead>
                  <tr>
                    <th>시작</th>
                    <th>종료</th>
                    <th>이미지</th>
                    <th>해상도</th>
                    <th>용지</th>
                    <th>전체픽셀</th>
                    <th>실패픽셀</th>
                    <th>소요시간</th>
                    <th>모드</th>
                    <th>결과</th>
                  </tr>
                </thead>
                <tbody>
                  {jobHistory.map(job => (
                    <tr key={job.id}>
                      <td style={{ fontSize: 11, color: 'var(--text2)', whiteSpace: 'nowrap' }}>{job.startTime}</td>
                      <td style={{ fontSize: 11, color: 'var(--text2)', whiteSpace: 'nowrap' }}>{job.endTime}</td>
                      <td style={{ maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{job.imageName}</td>
                      <td>{job.resLabel}</td>
                      <td>{job.paperType}</td>
                      <td>{job.totalPixels.toLocaleString()}</td>
                      <td style={{ color: job.failPixels > 0 ? 'var(--red)' : undefined }}>
                        {job.failPixels}
                      </td>
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

          {/* 요약 통계 */}
          {jobHistory.length > 0 && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10, marginTop: 16 }}>
              {[
                { l: '총 작업',    v: `${jobHistory.length}건`,                                                     c: 'var(--text)' },
                { l: '성공',       v: `${jobHistory.filter(j => j.status === 'success').length}건`,                  c: 'var(--green)' },
                { l: '실패/취소',  v: `${jobHistory.filter(j => j.status === 'failed' || j.status === 'cancelled').length}건`, c: 'var(--red)' },
                { l: '총 픽셀',    v: jobHistory.reduce((s, j) => s + j.totalPixels, 0).toLocaleString() + 'px',     c: 'var(--accent)' },
              ].map(({ l, v, c }) => (
                <div key={l} style={{ background: 'var(--panel2)', borderRadius: 6, padding: '10px 12px', textAlign: 'center' }}>
                  <div style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 4 }}>{l}</div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: c }}>{v}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
