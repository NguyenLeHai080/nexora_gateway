import { useEffect } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from '../core/layout/AppShell';
import { ProtectedRoute } from '../modules/auth/components/ProtectedRoute';
import { LoginPage } from '../modules/auth/pages/LoginPage';
import { useAuth } from '../modules/auth/hooks/useAuth';
import { DashboardPage } from '../modules/dashboard/pages/DashboardPage';
import { WalletPage } from '../modules/wallet/pages/WalletPage';
import { ApiKeysPage } from '../modules/api-keys/pages/ApiKeysPage';
import { ToolSetupPage } from '../modules/tool-setup/pages/ToolSetupPage';
import { ModelsPage } from '../modules/models/pages/ModelsPage';
import { LogsPage, ProfilePage, SettingsPage } from '../modules/common/pages/PlaceholderPages';
import { UsersPage } from '../modules/admin/pages/UsersPage';
import { FinancePage } from '../modules/admin/pages/FinancePage';
import { RouterPage } from '../modules/admin/pages/RouterPage';
import { ProvidersPage } from '../modules/admin/pages/ProvidersPage';
import { AuditPage } from '../modules/admin/pages/AuditPage';
import { RoutingPoolsPage } from '../modules/admin/pages/RoutingPoolsPage';
import { BankAccountsPage } from '../modules/admin/pages/BankAccountsPage';
import { UserApiKeysPage } from '../modules/admin/pages/UserApiKeysPage';
import { TokenXPage } from '../modules/admin/pages/TokenXPage';

function OAuthCallbackRelay() {
  const params = new URLSearchParams(window.location.search);
  const code = params.get('code');
  const state = params.get('state');
  const error = params.get('error');
  const errorDescription = params.get('error_description');
  const isCallback = Boolean(state && (code || error));

  useEffect(() => {
    if (!isCallback) return;
    const callbackData = {
      code,
      state,
      error,
      errorDescription,
      fullUrl: window.location.href,
    };
    window.opener?.postMessage(
      { type: 'oauth_callback', data: callbackData },
      window.location.origin,
    );
    localStorage.setItem(
      'oauth_callback',
      JSON.stringify({ ...callbackData, timestamp: Date.now() }),
    );
    window.history.replaceState(null, '', '/');
    window.setTimeout(() => window.close(), 300);
  }, [code, error, errorDescription, isCallback, state]);

  if (!isCallback) return null;
  return (
    <main className="oauth-callback-relay" aria-live="polite">
      <p>Đang hoàn tất kết nối Antigravity…</p>
    </main>
  );
}

export function App() {
  const { restore } = useAuth();
  useEffect(() => { void restore(); }, [restore]);
  const relay = <OAuthCallbackRelay />;
  const params = new URLSearchParams(window.location.search);
  if (params.get('state') && (params.get('code') || params.get('error'))) return relay;
  return <Routes>
    <Route path="/login" element={<LoginPage/>}/>
    <Route element={<ProtectedRoute/>}><Route element={<AppShell/>}>
      <Route path="/dashboard" element={<DashboardPage/>}/><Route path="/wallet" element={<WalletPage/>}/><Route path="/api-keys" element={<ApiKeysPage/>}/><Route path="/tool-setup" element={<ToolSetupPage/>}/><Route path="/models" element={<ModelsPage/>}/><Route path="/logs" element={<LogsPage/>}/><Route path="/profile" element={<ProfilePage/>}/><Route path="/settings" element={<SettingsPage/>}/>
      <Route element={<ProtectedRoute roles={['super_admin']}/> }><Route path="/admin/users" element={<UsersPage/>}/><Route path="/admin/user-api-keys" element={<UserApiKeysPage/>}/><Route path="/admin/finance" element={<FinancePage/>}/><Route path="/admin/banks" element={<BankAccountsPage/>}/><Route path="/admin/providers" element={<ProvidersPage/>}/><Route path="/admin/routing-pools" element={<RoutingPoolsPage/>}/><Route path="/admin/tokenx" element={<TokenXPage/>}/><Route path="/admin/router" element={<RouterPage/>}/><Route path="/admin/audit" element={<AuditPage/>}/></Route>
    </Route></Route>
    <Route path="*" element={<Navigate to="/dashboard" replace/>}/>
  </Routes>;
}
