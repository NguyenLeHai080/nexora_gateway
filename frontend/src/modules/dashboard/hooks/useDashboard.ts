import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../../core/api/client';
import type { DashboardStats } from '../../../core/types';

export function useDashboard() {
  return useQuery({ queryKey: ['dashboard'], queryFn: async () => (await apiClient.get<DashboardStats>('/dashboard')).data });
}

