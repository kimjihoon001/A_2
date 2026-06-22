import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
from matplotlib.font_manager import FontProperties

FP      = FontProperties(fname='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', size=10)
FP_B    = FontProperties(fname='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',    size=10)
FP_SM   = FontProperties(fname='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', size=8)
FP_SM_B = FontProperties(fname='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',    size=8)
FP_LG_B = FontProperties(fname='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',    size=13)
FP_TTL  = FontProperties(fname='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',    size=15)

fig, ax = plt.subplots(figsize=(26, 18))
ax.set_xlim(0, 24)
ax.set_ylim(14.2, 28.5)
ax.axis('off')
fig.patch.set_facecolor('#F8F9FA')

C1f, C1b = '#E8F5E9', '#2E7D32'
C2f, C2b = '#E3F2FD', '#1565C0'
C3f, C3b = '#FFF3E0', '#E65100'
C4f, C4b = '#F3E5F5', '#6A1B9A'
C5f, C5b = '#FCE4EC', '#880E4F'
C_Df, C_Db = '#FFFDE7', '#F9A825'
C_Ef, C_Eb = '#FFEBEE', '#C62828'
C_DBf, C_DBb = '#ECEFF1', '#546E7A'
C_ENDf = '#37474F'


def txt(ax, x, y, s, fp=FP, color='#111', ha='center', va='center', wrap=False, zorder=4):
    ax.text(x, y, s, ha=ha, va=va, color=color,
            fontproperties=fp, zorder=zorder)


def box(ax, x, y, w, h, title, sub='', fc='#E8F5E9', ec='#2E7D32', lw=2):
    p = FancyBboxPatch((x-w/2, y-h/2), w, h,
                       boxstyle='round,pad=0.04,rounding_size=0.18',
                       fc=fc, ec=ec, lw=lw, zorder=3)
    ax.add_patch(p)
    if sub:
        txt(ax, x, y+h/4, title, fp=FP_B, color='#111')
        txt(ax, x, y-h/4, sub,   fp=FP_SM, color='#555')
    else:
        txt(ax, x, y, title, fp=FP_B, color='#111')


def diamond(ax, x, y, w, h, lines, fc=C_Df, ec=C_Db):
    pts = [(x, y+h/2), (x+w/2, y), (x, y-h/2), (x-w/2, y)]
    ax.add_patch(plt.Polygon(pts, closed=True, fc=fc, ec=ec, lw=2, zorder=3))
    n = len(lines)
    for i, line in enumerate(lines):
        dy = (i - (n-1)/2) * 0.22
        fp = FP_B if i == 0 else FP_SM
        txt(ax, x, y-dy, line, fp=fp, color='#111')


def oval(ax, x, y, w, h, label, fc=C_ENDf, tc='white'):
    ax.add_patch(mpatches.Ellipse((x, y), w, h, fc=fc, ec=fc, lw=2, zorder=3))
    txt(ax, x, y, label, fp=FP_B, color=tc)


def arr(ax, x1, y1, x2, y2, c='#333', lw=1.8, ls='-'):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=c, lw=lw,
                                linestyle=ls, mutation_scale=13), zorder=2)


def line(ax, pts, c='#333', lw=1.8, ls='-'):
    xs, ys = zip(*pts)
    ax.plot(xs, ys, c=c, lw=lw, ls=ls, zorder=2)


def polyarr(ax, pts, c='#333', lw=1.8, ls='-'):
    line(ax, pts[:-1], c, lw, ls)
    arr(ax, pts[-2][0], pts[-2][1], pts[-1][0], pts[-1][1], c, lw, ls)


def lbl(ax, x, y, s, c='#444'):
    ax.text(x, y, s, ha='center', va='center', fontproperties=FP_SM, color=c, zorder=5,
            bbox=dict(fc='white', ec='none', pad=1))


def sec(ax, x, y, s, c):
    ax.text(x, y, s, ha='left', va='center', fontproperties=FP_LG_B, color=c, zorder=5)


# ═══════════════════════════════════════════════════
# 제목
# ═══════════════════════════════════════════════════
ax.add_patch(FancyBboxPatch((3, 26.8), 18, 0.95,
                             boxstyle='round,pad=0.1', fc='white', ec='#BDBDBD', lw=1.5, zorder=3))
txt(ax, 12, 27.45, '협동로봇 기반 픽셀 점묘화 시스템 — 전체 워크플로우', fp=FP_TTL, color='#111')
txt(ax, 12, 27.05, 'Doosan M0609 · OnRobot RG2 · ROS2 Humble', fp=FP_SM, color='#555')

# ═══════════════════════════════════════════════════
# ① SYSTEM START
# ═══════════════════════════════════════════════════
sec(ax, 0.3, 26.2, '① SYSTEM START', C1b)
ax.axhline(26.0, 0, 1, color='#DDD', lw=0.8)

oval(ax, 1.6, 25.2, 2.2, 0.75, '관리자 시작', fc='#2E7D32')
box(ax, 4.5, 25.2, 2.8, 0.8, 'React HMI 접속', 'useRobotServer()', fc=C1f, ec=C1b)
arr(ax, 2.7, 25.2, 3.1, 25.2, C1b)

diamond(ax, 7.8, 25.2, 2.8, 1.1, ['서버 연결 확인', 'serverConnected'])
arr(ax, 5.9, 25.2, 6.4, 25.2, C1b)

diamond(ax, 12.0, 25.2, 2.8, 1.1, ['ROS2·로봇 연결', 'ros2Connected'])
arr(ax, 9.2, 25.2, 10.6, 25.2, C1b)
lbl(ax, 9.9, 25.45, '성공', C1b)

box(ax, 16.0, 25.2, 3.0, 0.8, '연결 상태 HMI 표시', 'conn.status', fc=C1f, ec=C1b)
arr(ax, 13.4, 25.2, 14.5, 25.2, C1b)
lbl(ax, 14.0, 25.45, '성공', C1b)

# 실패 분기
box(ax, 7.8, 23.9, 2.8, 0.7, '오류표시·3초 재시도', fc=C_Ef, ec=C_Eb)
polyarr(ax, [(7.8, 24.65), (7.8, 24.25)], C_Eb)
lbl(ax, 8.2, 24.45, '실패', C_Eb)
polyarr(ax, [(6.4, 23.9), (4.5, 23.9), (4.5, 24.8)], C_Eb)

box(ax, 13.5, 23.9, 2.8, 0.7, '실제 연결 실패\n오류 및 로그 저장', fc=C_Ef, ec=C_Eb)
polyarr(ax, [(12.0, 24.65), (12.0, 24.25)], C_Eb)
lbl(ax, 12.4, 24.45, '실패', C_Eb)

# ═══════════════════════════════════════════════════
# ② IMAGE & PATH
# ═══════════════════════════════════════════════════
sec(ax, 0.3, 23.3, '② IMAGE & PATH', C2b)
ax.axhline(23.1, 0, 1, color='#DDD', lw=0.8)

polyarr(ax, [(16.0, 24.8), (16.0, 22.7), (1.6, 22.7), (1.6, 22.35)], C2b)

box(ax, 1.6,  22.0, 2.4, 0.65, '이미지 업로드\n및 편집', fc=C2f, ec=C2b)
box(ax, 4.5,  22.0, 2.4, 0.65, '해상도·용지·힘\n설정', fc=C2f, ec=C2b)
arr(ax, 2.8, 22.0, 3.3, 22.0, C2b)
box(ax, 7.5,  22.0, 2.6, 0.65, '픽셀·회색조\n데이터 생성', fc=C2f, ec=C2b)
arr(ax, 5.7, 22.0, 6.2, 22.0, C2b)
box(ax, 10.7, 22.0, 2.6, 0.65, '흰색 제외\n접촉력 매핑', fc=C2f, ec=C2b)
arr(ax, 8.8, 22.0, 9.4, 22.0, C2b)
box(ax, 14.0, 22.0, 2.8, 0.65, 'S자 경로 및\nTCP 좌표 변환', fc=C2f, ec=C2b)
arr(ax, 12.0, 22.0, 12.6, 22.0, C2b)

diamond(ax, 18.0, 22.0, 2.8, 1.1, ['건식 실행 모드?', 'dry_run'])
arr(ax, 15.4, 22.0, 16.6, 22.0, C2b)

box(ax, 21.0, 22.0, 2.4, 0.65, '경로만 순회\n(이동 없음)', fc=C_Df, ec=C_Db)
arr(ax, 19.4, 22.0, 19.8, 22.0, C_Db)
lbl(ax, 19.65, 22.25, '예', C_Db)

# ═══════════════════════════════════════════════════
# ③ ROBOT DRAWING
# ═══════════════════════════════════════════════════
sec(ax, 0.3, 21.2, '③ ROBOT DRAWING', C3b)
ax.axhline(21.0, 0, 1, color='#DDD', lw=0.8)

# dry_run=No → 드로잉 시작
polyarr(ax, [(18.0, 21.45), (18.0, 20.6), (16.5, 20.6)], C3b)
lbl(ax, 18.5, 21.0, '아니오', C3b)

# dry_run=Yes → 작업 종료로
polyarr(ax, [(21.0, 21.67), (21.0, 19.3), (12.5, 19.3), (12.5, 19.65)], C_Db)

box(ax, 14.8, 20.6, 3.0, 0.8, '저속·저힘으로\n점묘화 시작', fc=C3f, ec=C3b)
box(ax, 11.0, 20.6, 3.0, 0.8, '픽셀 위치 이동\nmovel', fc=C3f, ec=C3b)
arr(ax, 13.3, 20.6, 12.5, 20.6, C3b)
box(ax, 7.3,  20.6, 3.0, 0.8, '회색조별 힘 제어\n8N·6N·4N·2N', fc=C3f, ec=C3b)
arr(ax, 9.5, 20.6, 8.8, 20.6, C3b)
box(ax, 3.6,  20.6, 3.0, 0.8, '펜 접촉 후 상승\n다음 픽셀 진행', fc=C3f, ec=C3b)
arr(ax, 5.8, 20.6, 5.1, 20.6, C3b)

diamond(ax, 1.8, 19.5, 2.8, 1.0, ['모든 픽셀', '완료?'])
arr(ax, 3.6, 20.2, 3.6, 19.7)
polyarr(ax, [(3.6, 19.7), (1.8, 19.7), (1.8, 20.0)], '#555')

# 아니오 (반복)
polyarr(ax, [(0.4, 19.5), (0.4, 20.6), (2.1, 20.6)], '#666')
lbl(ax, 0.15, 20.0, '아니오', '#666')

# 예
box(ax, 5.5, 19.5, 3.0, 0.8, '작업 결과·시간\nSQLite 저장', fc=C3f, ec=C3b)
arr(ax, 3.2, 19.5, 4.0, 19.5, C3b)
lbl(ax, 3.65, 19.75, '예', C3b)

oval(ax, 9.2, 19.5, 2.8, 0.75, '작업 종료', fc=C_ENDf)
arr(ax, 7.0, 19.5, 7.8, 19.5, C3b)

# ④ REAL-TIME MONITORING (오른쪽)
sec(ax, 13.0, 21.2, '④ REAL-TIME MONITORING', C4b)

box(ax, 14.8, 19.5, 3.0, 0.8, 'Robot State 구독\nJ1-J6·TCP·힘', fc=C4f, ec=C4b)
polyarr(ax, [(11.0, 20.2), (11.0, 19.5), (13.3, 19.5)], C4b)
lbl(ax, 11.7, 19.85, 'ROS2 Topic', C4b)

box(ax, 18.5, 19.5, 3.0, 0.8, 'WebSocket 실시간\n상태 전송', fc=C4f, ec=C4b)
arr(ax, 16.3, 19.5, 17.0, 19.5, C4b)

box(ax, 22.0, 19.5, 3.0, 0.8, '진행률·상태\nHMI 갱신', fc=C4f, ec=C4b)
arr(ax, 20.0, 19.5, 20.5, 19.5, C4b)

# ═══════════════════════════════════════════════════
# ⑤ CONTROL & EXCEPTION
# ═══════════════════════════════════════════════════
sec(ax, 0.3, 18.7, '⑤ CONTROL & EXCEPTION', C5b)
ax.axhline(18.5, 0, 1, color='#DDD', lw=0.8)

# 버스 라인
line(ax, [(7.3, 21.0), (7.3, 18.0)], '#BBB', ls='--')

box(ax, 2.2, 17.8, 2.8, 0.8, '작업 중단 버튼\ncmd: stop', fc=C5f, ec=C5b)
polyarr(ax, [(2.2, 18.3), (2.2, 18.2)], C5b)
box(ax, 5.8, 17.8, 2.8, 0.8, '중단 상태 저장\nengine.stop()', fc=C5f, ec=C5b)
arr(ax, 3.6, 17.8, 4.4, 17.8, C5b)

box(ax, 10.0, 17.8, 2.8, 0.8, '비상정지 버튼\ncmd: estop', fc=C5f, ec=C5b)
polyarr(ax, [(10.0, 18.3), (10.0, 18.2)], C5b)
box(ax, 14.0, 17.8, 3.0, 0.8, '즉시 모션 정지\n추가 명령 차단', fc=C5f, ec=C5b)
arr(ax, 11.4, 17.8, 12.5, 17.8, C5b)

diamond(ax, 17.8, 17.8, 2.8, 1.0, ['로봇 상태', '정상?'])
arr(ax, 15.5, 17.8, 16.4, 17.8)

# 정상
box(ax, 17.8, 16.5, 3.0, 0.8, 'IDLE / RUNNING 표시\nstatus: idle·running', fc=C1f, ec=C1b)
arr(ax, 17.8, 17.3, 17.8, 16.9, C1b)
lbl(ax, 18.2, 17.1, '정상', C1b)

# 오류
box(ax, 21.5, 17.8, 2.8, 0.8, 'ERROR·E-STOP\n알림 표시', fc=C_Ef, ec=C_Eb)
arr(ax, 19.2, 17.8, 20.1, 17.8, C_Eb)
lbl(ax, 19.8, 18.05, '오류', C_Eb)

box(ax, 21.5, 16.5, 2.8, 0.8, '오류·중단\n로그 저장', fc=C_DBf, ec=C_DBb)
arr(ax, 21.5, 17.4, 21.5, 16.9, C_Eb)

oval(ax, 17.8, 15.5, 2.8, 0.75, '안전 종료', fc=C_ENDf)
arr(ax, 17.8, 16.1, 17.8, 15.88, '#555')
polyarr(ax, [(21.5, 16.1), (21.5, 15.5), (19.2, 15.5)], '#555')

# SQLite DB
box(ax, 2.5, 16.5, 2.8, 1.2, 'SQLite DB\ndatabase.db\nusers · orders · log', fc=C_DBf, ec=C_DBb)
polyarr(ax, [(5.8, 17.4), (5.8, 16.0), (3.9, 16.0)], '#888', ls='--')
polyarr(ax, [(5.8, 17.4), (5.8, 16.5)], '#888', ls='--')

# ═══════════════════════════════════════════════════
# 범례
# ═══════════════════════════════════════════════════
lx, ly = 0.5, 14.8
items = [
    (C1b, '-',  '정상 흐름'),
    (C_Eb, '--', '오류·예외 흐름'),
    ('#888', '--', '제어 버스 (비동기)'),
]
for i, (c, ls, label) in enumerate(items):
    ox = lx + i * 5.5
    ax.plot([ox, ox+1.2], [ly, ly], color=c, lw=2, ls=ls)
    ax.annotate('', xy=(ox+1.2, ly), xytext=(ox+0.9, ly),
                arrowprops=dict(arrowstyle='->', color=c, lw=2, mutation_scale=11))
    ax.text(ox+1.4, ly, label, va='center', fontproperties=FP_SM, color='#333')

plt.tight_layout(pad=0.5)
plt.savefig('/home/kimhuyngjun/바탕화면/P/A_2/docs/workflow_clean.png',
            dpi=180, bbox_inches='tight', facecolor='#F8F9FA')
print('저장 완료')
