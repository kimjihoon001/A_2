import type { User, Settings, Connection, ArtSettings, DrawingState } from './types';

export const ROLE_LABELS = { admin: '관리자', operator: '작업자', safety: '안전관리자' } as const;
export const ROLE_COLORS = { admin: '#0066ff', operator: '#00e676', safety: '#ff9100' } as const;

export const INITIAL_USERS: User[] = [
  { id: 1, name: '김관리', role: 'admin',    username: 'admin',    password: '1234' },
  { id: 2, name: '이작업', role: 'operator', username: 'operator', password: '1234' },
  { id: 3, name: '박안전', role: 'safety',   username: 'safety',   password: '1234' },
];

export const DEFAULT_SETTINGS: Settings = {
  minForce:        2,
  maxForce:        8,
  maxAllowedForce: 10,
  dotHoldMs:      150,
  resolutionKey: 'A5_M',
  maxSpeed:      200,
  logRetention:   30,
  graySteps:     '50,100,150,200',
};

export const DEFAULT_CONNECTION: Connection = {
  protocol:    'ROS2',
  ip:          '192.168.1.100',
  port:        12345,
  status:      'disconnected',
  lastConnect: null,
};

export const STATUS_LABEL: Record<string, string> = {
  idle: '대기중', running: '운전중', homing: '원점복귀', error: '오류', estop: '비상정지',
};
export const STATUS_COLOR: Record<string, string> = {
  idle:   'var(--green)',
  running:'var(--accent)',
  homing: 'var(--yellow)',
  error:  'var(--red)',
  estop:  'var(--red)',
};

export const NAV_ITEMS = [
  { id: 'dashboard',   label: '대시보드',    icon: '📊' },
  { id: 'drawing',     label: '로봇 제어',   icon: '🤖' },
  { id: 'calibration', label: '캘리브레이션', icon: '📐' },
  { id: 'safety',      label: '안전관리',    icon: '🛡️' },
  { id: 'connection',  label: '연결관리',    icon: '🔌' },
  { id: 'settings',    label: '설정',        icon: '⚙️' },
  { id: 'logs',        label: '작업로그',    icon: '📋' },
] as const;

export const FRAME_SIZES = [
  { key: 'SQ107',  label: '107×107mm (64px·1.67mm)', w: 107, h: 107 },
  { key: 'SQ128',  label: '128×128mm (64px·2mm)', w: 128, h: 128 },
  { key: 'SQ256',  label: '256×256mm (64px·4mm)', w: 256, h: 256 },
  { key: 'A5',     label: 'A5  (148×210mm)',       w: 148, h: 210 },
  { key: 'A5_IN',  label: 'A5 액자 내부 (130×185mm)', w: 130, h: 185 },
  { key: 'A4',     label: 'A4  (210×297mm)',       w: 210, h: 297 },
  { key: 'A3',     label: 'A3  (297×420mm)',       w: 297, h: 420 },
  { key: 'B5',     label: 'B5  (182×257mm)',       w: 182, h: 257 },
  { key: 'SQ200',  label: '정사각 (200×200mm)',    w: 200, h: 200 },
  { key: 'custom', label: '커스텀',                w:   0, h:   0 },
];

export const PAPER_TYPES = ['일반 용지', '수채화지', '캔버스', '아크릴보드'];

export const RESOLUTIONS = [
  { key:  'SQ64',  label:  '64×64   (4,096픽셀)  · 정사각',  w:  64, h:  64 },
  { key:  'A5_S',  label:  '50×71   (3,550픽셀)  · 빠름',    w:  50, h:  71 },
  { key:  'A5_M',  label:  '74×105  (7,770픽셀)  · 중간',    w:  74, h: 105 },
  { key:  'A5_L',  label: '100×142 (14,200픽셀) · 기본',     w: 100, h: 142 },
  { key:  'A5_XL', label: '148×210 (31,080픽셀) · 고해상도 (1px=1mm)', w: 148, h: 210 },
];

export const DEFAULT_ART_SETTINGS: ArtSettings = {
  frameSizeKey: 'A5_IN',
  frameWidth:   130,
  frameHeight:  185,
  paperType:    '일반 용지',
  resolutionKey:'SQ64',
  resWidth:      64,
  resHeight:     64,
  brightness:   1.0,
  contrast:     1.0,
  rotation:     0,
  flipH:        false,
  flipV:        false,
  penForceMin:   3,
  penForceMax:  10,
  dryRun:       false,
};

export const INITIAL_DRAWING_STATE: DrawingState = {
  status:          'idle',
  currentStep:     '',
  currentPixel:    0,
  totalPixels:     0,
  resWidth:        100,
  resHeight:       100,
  currentX:        0,
  currentY:        0,
  currentGray:     0,
  targetForce:     0,
  currentPenForce: 0,
  message:         '대기 중',
  successCount:    0,
  failCount:       0,
  failPixels:      0,
  forceExceedCount:0,
  history:         [],
  imageName:       '',
  frameSize:       '',
  paperType:       '',
  resLabel:        '',
  dryRun:          false,
  startTime:       0,
};

export const DRAWING_STATUS_LABEL: Record<string, string> = {
  idle:      '대기 중',
  running:   '그리는 중',
  paused:    '일시정지',
  success:   '완료',
  failed:    '실패',
  cancelled: '취소됨',
};
export const DRAWING_STATUS_COLOR: Record<string, string> = {
  idle:      'var(--text2)',
  running:   'var(--accent)',
  paused:    'var(--yellow)',
  success:   'var(--green)',
  failed:    'var(--red)',
  cancelled: 'var(--yellow)',
};
