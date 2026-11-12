export type VoiceState = 'IDLE' | 'LISTENING' | 'THINKING' | 'SPEAKING' | 'STOPPED' | 'ERROR';

export interface ChatMessageItem {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
  media_url?: string;
  media_type?: 'image' | 'video' | 'audio' | 'code';
}

export interface AudioDevice {
  index: number;
  name: string;
  channels: number;
  default_samplerate: number;
}

export interface AppSettings {
  wake_word_enabled: boolean;
  microphone_index: number;
  voice_speed: string;
  voice_pitch: string;
  primary_provider: 'ollama' | 'gemini' | 'groq';
  always_on_top: boolean;
  start_on_boot: boolean;
  permission_tier: 'A' | 'B' | 'C';
}

declare global {
  interface Window {
    mikeAPI?: {
      minimizeToTray: () => Promise<void>;
      closeWindow: () => Promise<void>;
      toggleMaximize?: () => Promise<boolean>;
      toggleFullScreen?: () => Promise<boolean>;
      toggleAlwaysOnTop: (flag: boolean) => Promise<boolean>;
      setStartOnBoot: (flag: boolean) => Promise<boolean>;
    };
  }
}

