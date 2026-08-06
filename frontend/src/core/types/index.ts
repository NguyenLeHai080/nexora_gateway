export type Role = 'super_admin' | 'user';

export interface User {
  id: number;
  name: string;
  email: string;
  role: Role;
  status: 'active' | 'locked' | 'archived';
  balance: number;
  tokenQuota: number;
  tokenUsed: number;
  models: string[];
  createdAt?: string;
}

export interface DashboardStats {
  source?: '9router' | 'fallback';
  balance: number;
  requests: number;
  successRequests: number;
  failedRequests: number;
  inputTokens: number;
  outputTokens: number;
  deposited: number;
  spent: number;
  chart: Array<{ time: string; success: number; failed: number; tokens: number; cost: number }>;
}

export interface ApiKey {
  id: number;
  name: string;
  prefix: string;
  status: 'active' | 'disabled';
  quota: number | null;
  createdAt: string;
  lastUsed: string | null;
}

export interface Model {
  id: string;
  provider: string;
  displayName: string;
  inputPrice: number;
  outputPrice: number;
  enabled: boolean;
}
