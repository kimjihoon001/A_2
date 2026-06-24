// ================================================================
// useRobotServer.ts — Python 서버 WebSocket 연결 훅
//
// 사용법:
//   const server = useRobotServer('ws://192.168.1.10:8765/ws');
//   server.startDrawing(pixels, settings, imageName);
//   server.stop();
// ================================================================

import { useEffect, useRef, useCallback, useState } from 'react';
import type { PixelPoint, ArtSettings, RobotState } from '../types';

export interface RobotConnInfo {
  ip: string;
  port: number;
  protocol: string;
}

export interface CalibrateZResult {
  contact_z : number;
  pen_up_z  : number;
  pen_down_z: number;
}

interface ServerCallbacks {
  onRobotState?       : (state: Partial<RobotState>) => void;
  onDrawProgress?     : (data: DrawingProgressMsg) => void;
  onLog?              : (msg: string, level: string) => void;
  onConnected?        : (connInfo?: RobotConnInfo) => void;
  onDisconnected?     : () => void;
  onCalibrateZResult? : (data: CalibrateZResult) => void;
  onCalibrationLoad?  : (data: object) => void;
  onSettingsLoad?     : (data: object) => void;
}

interface DrawingProgressMsg {
  drawStatus    : string;
  currentPixel  : number;
  totalPixels   : number;
  currentPenForce: number;
  message       : string;
  jobId         : number | null;
}

export function useRobotServer(url: string, callbacks: ServerCallbacks = {}) {
  const wsRef       = useRef<WebSocket | null>(null);
  const cbRef       = useRef(callbacks);
  cbRef.current     = callbacks;
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [connected, setConnected] = useState(false);

  const send = useCallback((data: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(url);

    ws.onopen = () => {
      setConnected(true);
      ws.send(JSON.stringify({ cmd: 'get_status' }));
      ws.send(JSON.stringify({ cmd: 'get_calibration' }));
      ws.send(JSON.stringify({ cmd: 'get_settings' }));
    };

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        switch (msg.type) {
          case 'connected':
            if (msg.robot) cbRef.current.onRobotState?.(msg.robot);
            cbRef.current.onConnected?.(msg.robotConn);
            break;
          case 'status':
            if (msg.robot) cbRef.current.onRobotState?.(msg.robot);
            if (msg.drawStatus !== undefined) {
              cbRef.current.onDrawProgress?.({
                drawStatus    : msg.drawStatus,
                currentPixel  : msg.currentPixel  ?? 0,
                totalPixels   : msg.totalPixels   ?? 0,
                currentPenForce: msg.currentPenForce ?? 0,
                message       : msg.message ?? '',
                jobId         : msg.jobId ?? null,
              });
            }
            break;
          case 'draw_progress':
            cbRef.current.onDrawProgress?.(msg as DrawingProgressMsg);
            break;
          case 'log':
            cbRef.current.onLog?.(msg.message, msg.level ?? 'INFO');
            break;
          case 'calibration':
            cbRef.current.onCalibrationLoad?.(msg.data);
            break;
          case 'settings':
            cbRef.current.onSettingsLoad?.(msg.data);
            break;
          case 'calibrate_z_result':
            cbRef.current.onCalibrateZResult?.(msg as CalibrateZResult);
            break;
          case 'error':
            cbRef.current.onLog?.(msg.message ?? '서버 명령 처리 실패', 'ERROR');
            break;
        }
      } catch { /* ignore parse errors */ }
    };

    ws.onclose = () => {
      setConnected(false);
      cbRef.current.onDisconnected?.();
      // 3초 후 재연결 시도
      reconnectRef.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => ws.close();
    wsRef.current = ws;
  }, [url]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  // ── 명령 메서드 ──────────────────────────────────────────────
  return {
    connected,
    startDrawing: (pixels: PixelPoint[], settings: ArtSettings, imageName: string) =>
      send({ cmd: 'start_drawing', pixels, settings, imageName }),
    stop         : ()          => send({ cmd: 'stop' }),
    estop        : ()          => send({ cmd: 'estop' }),
    resetEstop   : ()          => send({ cmd: 'reset_estop' }),
    home         : ()          => send({ cmd: 'home' }),
    gripperOpen  : (force = 20) => send({ cmd: 'gripper_open', force }),
    gripperClose : (force = 20) => send({ cmd: 'gripper_close', force }),
    getJobs      : (page = 1, limit = 20) => send({ cmd: 'get_jobs', page, limit }),
    getLogs      : (limit = 100) => send({ cmd: 'get_logs', limit }),
    getCalibration: ()         => send({ cmd: 'get_calibration' }),
    saveCalibration: (data: object) => send({ cmd: 'save_calibration', data }),
    getSettings   : ()          => send({ cmd: 'get_settings' }),
    saveSettings  : (data: object) => send({ cmd: 'save_settings', data }),
    calibrateZ    : ()          => send({ cmd: 'calibrate_z' }),
    frameTask     : ()          => send({ cmd: 'frame_task' }),
  };
}
