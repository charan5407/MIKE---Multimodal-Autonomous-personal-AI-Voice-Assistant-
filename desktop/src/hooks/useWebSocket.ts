import { useEffect, useRef, useState, useCallback } from 'react';
import { VoiceState } from '../types';
import { ToolActivityItem } from '../components/ToolActivityPanel';

interface UseWebSocketReturn {
  isConnected: boolean;
  voiceState: VoiceState;
  rms: number;
  transcript: string;
  response: string;
  toolActivities: ToolActivityItem[];
  sendAction: (action: string, payload?: Record<string, unknown>) => void;
}

export function useWebSocket(url = 'ws://127.0.0.1:8765/ws'): UseWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [voiceState, setVoiceState] = useState<VoiceState>('IDLE');
  const [rms, setRms] = useState(0);
  const [transcript, setTranscript] = useState('');
  const [response, setResponse] = useState('');
  const [toolActivities, setToolActivities] = useState<ToolActivityItem[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number>();

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          const { event: evtType, data } = parsed;

          switch (evtType) {
            case 'init_state':
              if (data.state) setVoiceState(data.state);
              break;
            case 'state_change':
              if (data.state) setVoiceState(data.state);
              break;
            case 'rms':
              if (typeof data.rms === 'number') setRms(data.rms);
              if (data.state) setVoiceState(data.state);
              break;
            case 'transcript':
              if (data.text) {
                setTranscript(data.text);
                setResponse('');
              }
              break;
            case 'response_chunk':
              if (data.chunk) setResponse((prev) => prev + data.chunk);
              break;
            case 'tool_activity':
              if (data.tool) {
                setToolActivities((prev) => [...prev.slice(-9), data]);
              }
              break;
            default:
              break;
          }
        } catch {
          // Ignore malformed frames
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        wsRef.current = null;
        // Exponential backoff reconnect
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, 2000);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      setIsConnected(false);
    }
  }, [url]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  const sendAction = useCallback((action: string, payload: Record<string, unknown> = {}) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action, ...payload }));
    }
  }, []);

  return { isConnected, voiceState, rms, transcript, response, toolActivities, sendAction };
}

