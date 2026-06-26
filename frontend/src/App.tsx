import { useState, useEffect, useRef } from 'react';
import './App.css';
import type {
  User, RobotState, RobotStatus, Alarm, LogEntry, HistoryPoint,
  Connection, ArtSettings, PixelPoint, DrawingJob, DrawingState,
  Settings, CalibrationData,
} from './types';
import {
  DEFAULT_SETTINGS, DEFAULT_CONNECTION,
  INITIAL_DRAWING_STATE, RESOLUTIONS,
} from './constants';
import { useRobotServer } from './hooks/useRobotServer';
import type { CalibrateZResult } from './hooks/useRobotServer';

import CustomerScreen  from './pages/CustomerScreen';
import LoginScreen     from './pages/Login';
import Layout          from './components/Layout';
import Dashboard       from './pages/Dashboard';
import DrawingControl  from './pages/DrawingControl';
import CalibrationPage from './pages/Calibration';
import SafetyPage      from './pages/Safety';
import ConnectionPage  from './pages/Connection';
import SettingsPage    from './pages/Settings';
import LogsPage        from './pages/Logs';

type AppMode = 'customer' | 'login' | 'admin';

let idSeq = 0;
const uid   = () => ++idSeq;
function nowStr() { return new Date().toLocaleTimeString('ko-KR'); }

const INITIAL_ROBOT: RobotState = {
  status: 'idle', joints: [0, 0, 0, 0, 0, 0],
  speed: 0, penForce: 0,
  tcpX: 0, tcpY: 0, tcpZ: 0,
  ros2: false,
};

const DEFAULT_SERVER_URL = `ws://${window.location.hostname}:8765/ws`;

export default function App() {
  const [mode, setMode]           = useState<AppMode>('customer');
  const [user, setUser]           = useState<User | null>(null);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [settings, setSettings]   = useState<Settings>(DEFAULT_SETTINGS);
  const [conn, setConn]           = useState<Connection>(DEFAULT_CONNECTION);
  const [serverUrl, setServerUrl] = useState(DEFAULT_SERVER_URL);
  const [robotState, setRobotState]     = useState<RobotState>(INITIAL_ROBOT);
  const [drawingState, setDrawingState] = useState<DrawingState>(INITIAL_DRAWING_STATE);
  const [calibration, setCalibration]     = useState<CalibrationData | null>(null);
  const [confirmRequest, setConfirmRequest] = useState<string | null>(null);
  const [calibratedZ,  setCalibratedZ]   = useState<CalibrateZResult | null>(null);
  const [alarms, setAlarms] = useState<Alarm[]>([
    { id: uid(), level: 'info', msg: '시스템 시작됨', time: '00:00:00' },
  ]);
  const [logs, setLogs] = useState<LogEntry[]>([
    { id: uid(), time: '00:00:00', msg: '시스템 초기화 완료' },
  ]);
  const [history, setHistory] = useState<HistoryPoint[]>([]
  );

  const settingsRef    = useRef(settings);
  settingsRef.current  = settings;
  const historyTickRef = useRef(0);
  const penForceRef    = useRef({ min: 10, max: 50 });
  const logsRef        = useRef<(msg: string) => void>(() => {});
  const alarmsRef      = useRef<(level: Alarm['level'], msg: string) => void>(() => {});

  function addLog(msg: string)   { setLogs(l => [...l, { id: uid(), time: nowStr(), msg }]); }
  function addAlarm(level: Alarm['level'], msg: string) { setAlarms(a => [...a, { id: uid(), level, msg, time: nowStr() }]); }
  useEffect(() => { logsRef.current   = addLog; });
  useEffect(() => { alarmsRef.current = addAlarm; });

  // ── Python 서버 WebSocket 연결 ──────────────────────────────
  const server = useRobotServer(serverUrl, {
    onRobotState: (state) => {
      setRobotState(prev => ({
        ...prev,
        ...(state.status && (prev.status !== 'estop' || state.status === 'estop')
            && { status: state.status as RobotStatus }),
        ...(state.joints           && { joints:    state.joints }),
        ...(state.tcpX  != null    && { tcpX:      state.tcpX }),
        ...(state.tcpY  != null    && { tcpY:      state.tcpY }),
        ...(state.tcpZ  != null    && { tcpZ:      state.tcpZ }),
        ...(state.speed != null    && { speed:     state.speed }),
        ...(state.penForce != null && { penForce:  state.penForce }),
        ...(state.ros2 != null     && { ros2:      state.ros2 }),
      }));
      const now = Date.now();
      if (now - historyTickRef.current > 1000) {
        historyTickRef.current = now;
        setHistory(h => [...h.slice(-29), {
          t: nowStr().slice(0, 8),
          speed: state.speed ?? 0,
          force: state.penForce ?? 0,
        }]);
      }
    },
    onDrawProgress: (data) => {
      setDrawingState(prev => {
        const finishing =
          (data.drawStatus === 'success' || data.drawStatus === 'failed' || data.drawStatus === 'cancelled')
          && prev.status === 'running';
        const elapsed = ((Date.now() - prev.startTime) / 1000).toFixed(1);
        const next: DrawingState = {
          ...prev,
          status:          data.drawStatus as DrawingState['status'],
          currentStep:     data.currentStep ?? '',
          currentPixel:    data.currentPixel,
          totalPixels:     data.totalPixels > 0 ? data.totalPixels : prev.totalPixels,
          currentPenForce: data.currentPenForce,
          message:         data.message,
        };
        if (finishing) {
          const job: DrawingJob = {
            id: uid(),
            startTime:   new Date(prev.startTime).toLocaleTimeString('ko-KR'),
            endTime:     nowStr(),
            imageName:   prev.imageName,
            frameSize:   prev.frameSize,
            paperType:   prev.paperType,
            resLabel:    prev.resLabel,
            totalPixels: prev.totalPixels,
            failPixels:  prev.failPixels,
            status:      data.drawStatus as DrawingJob['status'],
            dryRun:      prev.dryRun,
            duration:    `${elapsed}s`,
          };
          if (data.drawStatus === 'success') next.successCount = prev.successCount + 1;
          if (data.drawStatus === 'failed')  next.failCount    = prev.failCount + 1;
          next.history = [job, ...prev.history];
          // E-STOP 중이면 로봇 status를 idle로 되돌리지 않음
          setRobotState(s => s.status === 'estop' ? s : { ...s, status: 'idle', speed: 0, penForce: 0 });
        }
        return next;
      });
    },
    onLog: (msg, level) => {
      logsRef.current(`[서버] ${msg}`);
      if (level === 'ERROR')   alarmsRef.current('error',   msg);
      if (level === 'WARNING') alarmsRef.current('warning', msg);
    },
    onConnected: (connInfo) => {
      logsRef.current('[서버] Python 서버 연결됨');
      alarmsRef.current('info', 'Python 서버 연결됨');
      setConn(c => ({
        ...c,
        lastConnect: new Date().toLocaleTimeString('ko-KR'),
        ...(connInfo && { ip: connInfo.ip, port: connInfo.port, protocol: connInfo.protocol }),
      }));
    },
    onDisconnected: () => {
      logsRef.current('[서버] Python 서버 연결 끊김');
      setConn(c => ({ ...c, status: 'disconnected' }));
    },
    onCalibrateZResult: (data) => {
      setCalibratedZ(data);
      addLog(`[Z 자동측정] 접촉=${data.contact_z}mm → pen_up=${data.pen_up_z}, pen_down=${data.pen_down_z} (자동 저장됨)`);
    },
    onConfirmRequest: (message) => {
      setConfirmRequest(message);
    },
    onCalibrationLoad: (data) => {
      setCalibration(data as CalibrationData);
    },
    onSettingsLoad: (data) => {
      const d = data as Record<string, { value: string }>;
      const parse = (key: string, fallback: number) => {
        const v = parseFloat(d[key]?.value ?? '');
        return isNaN(v) ? fallback : v;
      };
      const hmi = d['hmi_settings']?.value;
      if (hmi) {
        try { setSettings(s => ({ ...s, ...JSON.parse(hmi) })); } catch { /* ignore */ }
      } else {
        setSettings(s => ({
          ...s,
          maxSpeed:     parse('move_speed',          s.maxSpeed),
          minForce:     parse('pen_force_min',        s.minForce),
          maxForce:     parse('pen_force_max',        s.maxForce),
          dotHoldMs:    parse('dot_hold_ms',          s.dotHoldMs),
          logRetention: parse('log_retention_days',   s.logRetention),
        }));
      }
    },
  });

  const serverConnected = server.connected;
  const ros2Connected   = serverConnected && robotState.ros2 === true;
  const robotConnected  = ros2Connected;

  useEffect(() => {
    setConn(c => ({ ...c, status: robotConnected ? 'connected' : 'disconnected' }));
  }, [robotConnected]);

  // ── E-STOP ──────────────────────────────────────────────────
  function handleEstop() {
    if (serverConnected) server.estop();
    setRobotState(s => ({ ...s, status: 'estop', speed: 0 }));
    addAlarm('error', '비상정지 활성화됨');
    addLog('E-STOP 활성화');
  }
  function handleResetEstop() {
    if (serverConnected) server.resetEstop();
    // 서버 연결 여부와 무관하게 로컬 상태를 즉시 해제
    // (onRobotState 가드가 서버 브로드캐스트의 'idle'을 막으므로 여기서 직접 처리)
    setRobotState(s => ({ ...s, status: 'idle' }));
    addAlarm('info', '비상정지 해제됨');
    addLog('E-STOP 해제');
  }

  // ── 원점 복귀 ────────────────────────────────────────────────
  function handleGoHome() {
    if (serverConnected) server.home();
  }

  // ── 일시정지 / 재개 ─────────────────────────────────────────
  function handlePause() {
    if (serverConnected) server.pause();
    addLog('그리기 일시정지');
  }
  function handleResume() {
    if (serverConnected) server.resume();
    addLog('그리기 재개');
  }

  // ── 그리기 시작 ─────────────────────────────────────────────
  function handleStartDrawing(pixels: PixelPoint[], artSettings: ArtSettings, imageName: string) {
    if (robotState.status === 'estop') {
      addAlarm('error', '비상정지 상태에서는 그리기를 시작할 수 없습니다.');
      return;
    }
    const resEntry  = RESOLUTIONS.find(r => r.key === artSettings.resolutionKey);
    const resLabel  = resEntry ? resEntry.label.split('·')[0].trim() : `${artSettings.resWidth}×${artSettings.resHeight}`;
    const frameSize = artSettings.frameSizeKey === 'custom'
      ? `${artSettings.frameWidth}×${artSettings.frameHeight}mm`
      : artSettings.frameSizeKey;

    penForceRef.current = { min: artSettings.penForceMin, max: artSettings.penForceMax };

    setDrawingState(s => ({
      ...s,
      status: 'running', currentPixel: 0, totalPixels: pixels.length,
      resWidth: artSettings.resWidth, resHeight: artSettings.resHeight,
      currentX: 0, currentY: 0, currentGray: 0, targetForce: 0,
      currentPenForce: 0, failPixels: 0,
      message: serverConnected ? `서버로 전송 중... (${pixels.length.toLocaleString()}픽셀)` : '그리기 시작',
      imageName, frameSize, paperType: artSettings.paperType, resLabel,
      dryRun: artSettings.dryRun, startTime: Date.now(),
    }));
    setRobotState(s => ({ ...s, status: 'running' }));
    addLog(`그리기 시작: ${imageName} (${pixels.length.toLocaleString()}픽셀)${artSettings.dryRun ? ' [건식]' : ''}`);
    addAlarm('info', `그리기 시작: ${imageName}`);

    if (serverConnected) {
      server.startDrawing(pixels, artSettings, imageName);
    }
  }



  function handleCancelDrawing() {
    if (serverConnected) server.stop();
    addLog('그리기 취소됨');
  }


  // ── 렌더 분기 ─────────────────────────────────────────────────
  const activeAlarms = alarms.filter(a => a.level === 'error').length;

  const pages: Record<string, React.ReactNode> = {
    dashboard: (
      <Dashboard
        robotState={robotState}
        history={history}
        alarms={alarms}
        drawingState={drawingState}
        ros2Connected={ros2Connected}
      />
    ),
    drawing: (
      <DrawingControl
        drawingState={drawingState}
        robotState={robotState}
        onStop={() => {
          if (serverConnected) server.stop();
          addLog('[관리자] 그리기 강제 정지');
        }}
        onPause={handlePause}
        onResume={handleResume}
        onGoHome={handleGoHome}
        onPaperCheck={() => { if (serverConnected) server.paperCheck(); addLog('[관리자] 종이 확인 시작'); }}
        onPencilGrip={() => { if (serverConnected) server.pencilGrip(); addLog('[관리자] 연필 파지 시작'); }}
        onPencilRelease={() => { if (serverConnected) server.pencilRelease(); addLog('[관리자] 연필 반납 시작'); }}
        onFrameLower={() => { if (serverConnected) server.frameLower(); addLog('[관리자] 액자 하판 시작'); }}
        onFramePaperPickup={() => { if (serverConnected) server.framePaperPickup(); addLog('[관리자] 종이 픽업 시작'); }}
        onFrameAlign={() => { if (serverConnected) server.frameAlign(); addLog('[관리자] 정렬 시작'); }}
        onFrameUpper={() => { if (serverConnected) server.frameUpper(); addLog('[관리자] 액자 상판 시작'); }}
        onFrameEject={() => { if (serverConnected) server.frameEject(); addLog('[관리자] 액자 배출 시작'); }}
        addLog={addLog}
      />
    ),
    calibration: (
      <CalibrationPage
        robotState={robotState}
        addLog={addLog}
        onGoHome={handleGoHome}
        onSaveCalibration={data => {
          setCalibration(data);
          if (serverConnected) server.saveCalibration(data);
        }}
        savedCalib={calibration}
        onJogStart={(axis, speed) => { if (serverConnected) server.jogStart(axis, speed); }}
        onJogStop={(axis) => { if (serverConnected) server.jogStop(axis); }}
        onJogMultiStart={(vec, speed) => { if (serverConnected) server.jogMultiStart(vec, speed); }}
        onJogMultiStop={() => { if (serverConnected) server.jogMultiStop(); }}
        onSetRobotMode={(mode) => { if (serverConnected) server.setRobotMode(mode); }}
        onGripperOpen={() => { if (serverConnected) server.gripperOpen(); addLog('[관리자] 그리퍼 열기'); }}
        onGripperClose={() => { if (serverConnected) server.gripperClose(); addLog('[관리자] 그리퍼 닫기'); }}
        onPencilGrip={() => { if (serverConnected) server.pencilGrip(); addLog('[관리자] 연필 파지 시작'); }}
        onPencilRelease={() => { if (serverConnected) server.pencilRelease(); addLog('[관리자] 연필 반납 시작'); }}
      />
    ),
    safety: (
      <SafetyPage
        robotState={robotState}
        alarms={alarms}
        onEstop={handleEstop}
        onResetEstop={handleResetEstop}
        settings={settings}
        forceExceedCount={drawingState.forceExceedCount}
      />
    ),
    connection: (
      <ConnectionPage
        conn={conn}
        setConn={setConn}
        addLog={addLog}
        serverUrl={serverUrl}
        setServerUrl={setServerUrl}
        serverConnected={serverConnected}
        ros2Connected={ros2Connected}
        robotConnected={robotConnected}
      />
    ),
    settings: (
      <SettingsPage settings={settings} setSettings={(s) => {
        setSettings(s);
        if (serverConnected) server.saveSettings({
          move_speed:         String(s.maxSpeed),
          dot_hold_ms:        String(s.dotHoldMs),
          log_retention_days: String(s.logRetention),
          pen_force_min:      String(s.minForce),
          pen_force_max:      String(s.maxForce),
          hmi_settings:       JSON.stringify(s),
        });
      }} addLog={addLog} />
    ),
    logs: (
      <LogsPage logs={logs} jobHistory={drawingState.history} />
    ),
  };

  return (
    <>
      {/* CustomerScreen은 항상 같은 트리 위치에 마운트 유지, 비활성 시만 숨김 */}
      <div style={{ display: mode === 'customer' ? 'block' : 'none' }}>
        <CustomerScreen
          drawingState={drawingState}
          onStartDrawing={handleStartDrawing}
          onCancelDrawing={handleCancelDrawing}
          onAdminClick={() => setMode('login')}
          confirmRequest={confirmRequest}
          onConfirmRetry={() => {
            setConfirmRequest(null);
            if (serverConnected) server.confirmRetry();
          }}
        />
      </div>

      {mode === 'login' && (
        <LoginScreen
          onLogin={u => { setUser(u); setMode('admin'); addLog(`로그인: ${u.name} (${u.role})`); }}
          onBack={() => setMode('customer')}
        />
      )}

      {mode === 'admin' && (
        <Layout
          user={user!}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          onLogout={() => { addLog(`로그아웃: ${user?.name}`); setUser(null); setMode('customer'); setActiveTab('dashboard'); }}
          alarmCount={activeAlarms}
          serverConnected={serverConnected}
        >
          {pages[activeTab] ?? pages.dashboard}
        </Layout>
      )}

      {/* 준비 확인 팝업 — 모드 무관하게 표시 */}
      {confirmRequest && mode !== 'customer' && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 2000,
          background: 'rgba(0,0,0,0.6)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            background: 'var(--panel)', borderRadius: 16,
            padding: '36px 40px', maxWidth: 420, width: '90%',
            boxShadow: '0 8px 48px rgba(0,0,0,0.4)',
            border: '2px solid var(--yellow)', textAlign: 'center',
          }}>
            <div style={{ fontSize: 40, marginBottom: 16 }}>⚠️</div>
            <div style={{ fontSize: 17, fontWeight: 700, color: 'var(--text)', marginBottom: 12 }}>준비 확인 필요</div>
            <div style={{ fontSize: 15, color: 'var(--text2)', marginBottom: 28, lineHeight: 1.7 }}>{confirmRequest}</div>
            <button className="btn-primary"
              style={{ fontSize: 16, padding: '13px 48px', fontWeight: 800 }}
              onClick={() => { setConfirmRequest(null); if (serverConnected) server.confirmRetry(); }}>
              확인 (재시도)
            </button>
          </div>
        </div>
      )}
    </>
  );
}
