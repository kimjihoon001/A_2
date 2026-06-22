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
function randInt(a: number, b: number) { return Math.floor(Math.random() * (b - a + 1)) + a; }

const INITIAL_ROBOT: RobotState = {
  status: 'idle', joints: [0, -30, 60, 0, 45, 0],
  speed: 0, penForce: 0,
  tcpX: 423, tcpY: 12, tcpZ: 315,
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
  const [calibratedZ,  setCalibratedZ]   = useState<CalibrateZResult | null>(null);
  const [alarms, setAlarms] = useState<Alarm[]>([
    { id: uid(), level: 'info', msg: '시스템 시작됨', time: '00:00:00' },
  ]);
  const [logs, setLogs] = useState<LogEntry[]>([
    { id: uid(), time: '00:00:00', msg: '시스템 초기화 완료' },
  ]);
  const [history, setHistory] = useState<HistoryPoint[]>(
    Array.from({ length: 20 }, (_, i) => ({ t: `${i}s`, speed: 0, force: 0 }))
  );

  const settingsRef    = useRef(settings);
  settingsRef.current  = settings;
  const historyTickRef = useRef(0);
  const drawTimerRef   = useRef<ReturnType<typeof setInterval> | null>(null);
  const drawPixelsRef  = useRef<PixelPoint[]>([]);
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
        status: connInfo?.protocol === 'ROS2' ? 'connected' : 'disconnected',
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
      addLog(`[Z 자동측정] 접촉=${data.contact_z}mm → pen_up=${data.pen_up_z}, pen_down=${data.pen_down_z}`);
    },
  });

  const serverConnected = server.connected;
  const ros2Connected   = serverConnected && robotState.ros2 === true;
  const robotConnected  = ros2Connected;

  // ── E-STOP ──────────────────────────────────────────────────
  function handleEstop() {
    if (serverConnected) server.estop();
    else                 stopDrawingNow('failed', '비상정지로 작업 중단');
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
    if (serverConnected) {
      server.home();
    } else {
      setRobotState(s => ({ ...s, status: 'homing', speed: 0 }));
      addLog('원점 복귀 중...');
      setTimeout(() => {
        setRobotState(s => ({ ...s, status: 'idle', joints: [0, -30, 60, 0, 45, 0], tcpX: 423, tcpY: 12, tcpZ: 315 }));
        addLog('원점 복귀 완료');
      }, 2000);
    }
  }

  // ── 일시정지 / 재개 ─────────────────────────────────────────
  function handlePause() {
    setDrawingState(s => s.status === 'running' ? { ...s, status: 'paused' } : s);
    addLog('그리기 일시정지');
  }
  function handleResume() {
    setDrawingState(s => s.status === 'paused' ? { ...s, status: 'running' } : s);
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

    penForceRef.current   = { min: artSettings.penForceMin, max: artSettings.penForceMax };
    drawPixelsRef.current = pixels;

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
    addLog(`그리기 시작: ${imageName} (${pixels.length.toLocaleString()}픽셀)${artSettings.dryRun ? ' [건식]' : ''}${serverConnected ? ' → 서버' : ' → 시뮬'}`);
    addAlarm('info', `그리기 시작: ${imageName}`);

    if (serverConnected) {
      server.startDrawing(pixels, artSettings, imageName);
    } else {
      _runSimulation(pixels, artSettings);
    }
  }

  function _runSimulation(pixels: PixelPoint[], _artSettings: ArtSettings) {
    if (drawTimerRef.current) clearInterval(drawTimerRef.current);
    const stepPx = 50;
    drawTimerRef.current = setInterval(() => {
      setDrawingState(prev => {
        if (prev.status !== 'running') {
          clearInterval(drawTimerRef.current!); drawTimerRef.current = null;
          return prev;
        }
        const next = prev.currentPixel + stepPx;
        const px   = pixels[Math.min(next, pixels.length - 1)];
        const { min, max } = penForceRef.current;
        const targetF = max - (px.gray / 255) * (max - min);

        if (next >= prev.totalPixels) {
          clearInterval(drawTimerRef.current!); drawTimerRef.current = null;
          const elapsed = ((Date.now() - prev.startTime) / 1000).toFixed(1);
          const job: DrawingJob = {
            id: uid(), startTime: new Date(prev.startTime).toLocaleTimeString('ko-KR'),
            endTime: nowStr(), imageName: prev.imageName, frameSize: prev.frameSize,
            paperType: prev.paperType, resLabel: prev.resLabel,
            totalPixels: prev.totalPixels, failPixels: prev.failPixels,
            status: 'success', dryRun: prev.dryRun, duration: `${elapsed}s`,
          };
          logsRef.current(`그리기 완료: ${prev.imageName} (${elapsed}s)`);
          alarmsRef.current('info', `그리기 완료: ${prev.imageName}`);
          setRobotState(s => ({ ...s, status: 'idle', speed: 0, penForce: 0 }));
          return { ...prev, status: 'success', currentPixel: prev.totalPixels,
            message: `완료! ${prev.totalPixels.toLocaleString()}픽셀 (${elapsed}s)`,
            successCount: prev.successCount + 1, history: [job, ...prev.history] };
        }

        const mmPerPixelX = _artSettings.frameWidth  / _artSettings.resWidth;
        const mmPerPixelY = _artSettings.frameHeight / _artSettings.resHeight;
        const tcpX = _artSettings.originX + px.x * mmPerPixelX;
        const tcpY = _artSettings.originY + px.y * mmPerPixelY;

        setRobotState(s => s.status === 'running' ? {
          ...s, speed: randInt(80, 250),
          tcpX, tcpY,
          penForce: targetF + (Math.random() - 0.5) * 3,
          joints: s.joints.map((j, i) => parseFloat((j + (Math.random() - 0.5) * (i < 2 ? 2 : 0.3)).toFixed(1))),
        } : s);

        return {
          ...prev, currentPixel: next,
          currentX: tcpX, currentY: tcpY,
          currentGray: px.gray, targetForce: parseFloat(targetF.toFixed(1)),
          currentPenForce: targetF,
          message: `그리는 중... ${next.toLocaleString()} / ${prev.totalPixels.toLocaleString()} 픽셀`,
        };
      });
    }, 100);
  }

  function stopDrawingNow(finalStatus: DrawingState['status'], msg: string) {
    if (drawTimerRef.current) { clearInterval(drawTimerRef.current); drawTimerRef.current = null; }
    setDrawingState(prev => {
      if (prev.status !== 'running' && prev.status !== 'paused') return prev;
      const elapsed = ((Date.now() - prev.startTime) / 1000).toFixed(1);
      const job: DrawingJob = {
        id: uid(), startTime: new Date(prev.startTime).toLocaleTimeString('ko-KR'),
        endTime: nowStr(), imageName: prev.imageName, frameSize: prev.frameSize,
        paperType: prev.paperType, resLabel: prev.resLabel,
        totalPixels: prev.totalPixels, failPixels: prev.failPixels,
        status: finalStatus, dryRun: prev.dryRun, duration: `${elapsed}s`,
      };
      return { ...prev, status: finalStatus, message: msg,
        failCount: finalStatus === 'failed' ? prev.failCount + 1 : prev.failCount,
        history: [job, ...prev.history] };
    });
    setRobotState(s => ({ ...s, status: 'idle', speed: 0, penForce: 0 }));
  }

  function handleCancelDrawing() {
    if (serverConnected) server.stop();
    else                 stopDrawingNow('cancelled', '사용자가 작업을 취소했습니다.');
    addLog('그리기 취소됨');
  }

  // ── 아이들 시뮬레이션 (서버 없을 때만) ─────────────────────
  useEffect(() => {
    if (mode !== 'admin' || serverConnected) return;
    const timer = setInterval(() => {
      setRobotState(prev => {
        if (prev.status === 'estop' || prev.status === 'running' || prev.status === 'homing') return prev;
        return {
          ...prev,
          joints: prev.joints.map(j => parseFloat((j + (Math.random() - 0.5) * 0.5).toFixed(1))),
          tcpX:   parseFloat((prev.tcpX + (Math.random() - 0.5) * 1.5).toFixed(1)),
          tcpY:   parseFloat((prev.tcpY + (Math.random() - 0.5) * 1.5).toFixed(1)),
          tcpZ:   parseFloat((prev.tcpZ + (Math.random() - 0.5) * 0.5).toFixed(1)),
        };
      });
    }, 1500);
    return () => clearInterval(timer);
  }, [mode, serverConnected]);

  // ── 렌더 분기 ─────────────────────────────────────────────────
  if (mode === 'customer') {
    return (
      <CustomerScreen
        drawingState={drawingState}
        onStartDrawing={handleStartDrawing}
        onCancelDrawing={handleCancelDrawing}
        onAdminClick={() => setMode('login')}
      />
    );
  }

  if (mode === 'login') {
    return (
      <LoginScreen
        onLogin={u => { setUser(u); setMode('admin'); addLog(`로그인: ${u.name} (${u.role})`); }}
        onBack={() => setMode('customer')}
      />
    );
  }

  const activeAlarms = alarms.filter(a => a.level === 'error').length;

  const pages: Record<string, React.ReactNode> = {
    dashboard: (
      <Dashboard
        robotState={robotState}
        history={history}
        alarms={alarms}
        drawingState={drawingState}
      />
    ),
    drawing: (
      <DrawingControl
        drawingState={drawingState}
        robotState={robotState}
        onStop={() => {
          if (serverConnected) server.stop();
          else stopDrawingNow('cancelled', '관리자가 작업을 중단했습니다.');
          addLog('[관리자] 그리기 강제 정지');
        }}
        onPause={handlePause}
        onResume={handleResume}
        onGoHome={handleGoHome}
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
        onCalibrateZ={() => { if (serverConnected) server.calibrateZ(); }}
        calibratedZ={calibratedZ}
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
      <SettingsPage settings={settings} setSettings={setSettings} addLog={addLog} />
    ),
    logs: (
      <LogsPage logs={logs} jobHistory={drawingState.history} />
    ),
  };

  return (
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
  );
}
