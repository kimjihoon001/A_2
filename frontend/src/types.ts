export type Role = 'admin' | 'operator' | 'safety';
export type RobotStatus = 'idle' | 'running' | 'homing' | 'error' | 'estop';
export type ConnStatus = 'connected' | 'disconnected' | 'connecting';
export type AlarmLevel = 'info' | 'warning' | 'error';
export type DrawingStatus = 'idle' | 'running' | 'paused' | 'success' | 'failed' | 'cancelled';

export interface User {
  id: number;
  name: string;
  role: Role;
  username: string;
  password: string;
}

export interface RobotState {
  status: RobotStatus;
  joints: number[];
  speed: number;
  tcpX: number;
  tcpY: number;
  tcpZ: number;
  ros2?: boolean;
  penForce: number;
}

export interface Settings {
  minForce: number;
  maxForce: number;
  maxAllowedForce: number;
  dotHoldMs: number;
  resolutionKey: string;
  maxSpeed: number;
  logRetention: number;
}

export interface Connection {
  protocol: string;
  ip: string;
  port: number;
  status: ConnStatus;
  lastConnect: string | null;
}

export interface Alarm {
  level: AlarmLevel;
  msg: string;
  time: string;
  id: number;
}

export interface LogEntry {
  time: string;
  msg: string;
  id: number;
}

export interface HistoryPoint {
  t: string;
  speed: number;
  force: number;
}

export interface PixelPoint {
  x: number;
  y: number;
  gray: number;
}

export interface DrawingJob {
  id: number;
  startTime: string;
  endTime: string;
  imageName: string;
  frameSize: string;
  paperType: string;
  resLabel: string;
  totalPixels: number;
  failPixels: number;
  status: DrawingStatus;
  dryRun: boolean;
  duration: string;
}

export interface DrawingState {
  status: DrawingStatus;
  currentStep: string;
  currentPixel: number;
  totalPixels: number;
  resWidth: number;
  resHeight: number;
  currentX: number;
  currentY: number;
  currentGray: number;
  targetForce: number;
  currentPenForce: number;
  message: string;
  successCount: number;
  failCount: number;
  failPixels: number;
  forceExceedCount: number;
  history: DrawingJob[];
  imageName: string;
  frameSize: string;
  paperType: string;
  resLabel: string;
  dryRun: boolean;
  startTime: number;
}

export interface ArtSettings {
  frameSizeKey: string;
  frameWidth: number;
  frameHeight: number;
  paperType: string;
  resolutionKey: string;
  resWidth: number;
  resHeight: number;
  brightness: number;
  contrast: number;
  rotation: number;
  flipH: boolean;
  flipV: boolean;
  penForceMin: number;
  penForceMax: number;
  dryRun: boolean;
}

export interface CalibrationData {
  origin_x: number;   // S자 좌상단 X
  origin_y: number;   // S자 좌상단 Y
  origin_z: number;
  pen_down_z: number;
  travel_z?: number;
  pixel_spacing_mm: number;
  center_x: number;
  center_y: number;
  canvas_width_mm?: number;
  canvas_height_mm?: number;
  name?: string;
}
