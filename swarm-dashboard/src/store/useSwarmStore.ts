import { create } from 'zustand'

export interface Agent {
  id: string;
  type: string;
  status: 'idle' | 'running' | 'failed' | 'completed';
}

interface SwarmState {
  agents: Agent[];
  activeTasks: number;
  addAgent: (agent: Agent) => void;
  updateAgentStatus: (id: string, status: Agent['status']) => void;
}

// Zustand store for high-performance React state management without context re-rendering penalties
export const useSwarmStore = create<SwarmState>((set) => ({
  agents: [],
  activeTasks: 0,
  
  addAgent: (agent) => set((state) => ({ 
    agents: [...state.agents, agent] 
  })),
  
  updateAgentStatus: (id, status) => set((state) => ({
    agents: state.agents.map(a => a.id === id ? { ...a, status } : a)
  })),
}))
