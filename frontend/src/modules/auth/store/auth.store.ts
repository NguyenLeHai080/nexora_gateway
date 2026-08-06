import { create } from 'zustand';
import type { User } from '../../../core/types';
import { apiClient } from '../../../core/api/client';

interface AuthState {
  user: User | null;
  loading: boolean;
  hydrated: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (name: string, email: string, password: string) => Promise<User>;
  restore: () => Promise<void>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  loading: false,
  hydrated: false,
  login: async (email, password) => {
    set({ loading: true });
    try {
      const { data } = await apiClient.post('/auth/login', { email, password });
      localStorage.setItem('nexora_access_token', data.access_token);
      set({ user: data.user });
      return data.user;
    } finally {
      set({ loading: false, hydrated: true });
    }
  },
  register: async (name, email, password) => {
    set({ loading: true });
    try {
      const { data } = await apiClient.post('/auth/register', { name, email, password });
      localStorage.setItem('nexora_access_token', data.access_token);
      set({ user: data.user });
      return data.user;
    } finally {
      set({ loading: false, hydrated: true });
    }
  },
  restore: async () => {
    if (!localStorage.getItem('nexora_access_token')) {
      set({ hydrated: true });
      return;
    }
    try {
      const { data } = await apiClient.get('/auth/me');
      set({ user: data });
    } catch {
      localStorage.removeItem('nexora_access_token');
    } finally {
      set({ hydrated: true });
    }
  },
  logout: () => {
    localStorage.removeItem('nexora_access_token');
    set({ user: null });
  },
}));
