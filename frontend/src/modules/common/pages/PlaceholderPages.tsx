import { FormEvent, useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bell, CheckCircle2, Save, UserRound, XCircle } from 'lucide-react';
import { apiClient } from '../../../core/api/client';
import { PageHeader } from '../../../shared/components/PageHeader';
import { Badge } from '../../../shared/components/Badge';
import { formatNumber, formatVnd } from '../../../shared/utils/format';
import { useAuth } from '../../auth/hooks/useAuth';
import { usePagination } from '../../../shared/hooks/usePagination';
import { TablePagination } from '../../../shared/components/TablePagination';
import { TableEmpty } from '../../../shared/components/TableEmpty';

interface Log { id: number; requestId: string; model: string; status: string; inputTokens: number; outputTokens: number; cost: number; latencyMs: number; createdAt: string; userId:number; userName:string; userEmail:string }
interface Settings { telegramEnabled: boolean; telegramChatId: string; lowBalanceThreshold: number }

export function LogsPage() {
  const { user } = useAuth();
  const { data = [] } = useQuery({ queryKey: ['usage-logs'], queryFn: async () => (await apiClient.get<Log[]>('/logs')).data });
  const pagination = usePagination(data, 10);
  const admin=user?.role==='super_admin';
  return <div className="page"><PageHeader eyebrow="OBSERVABILITY / EVENTS" title="Nhật ký sử dụng" description={admin?'Theo dõi request và lỗi theo từng tài khoản khách hàng.':'Theo dõi request, model, token, độ trễ và chi phí.'}/><article className="card table-card"><div className="table-section-heading"><div><p className="eyebrow">REQUEST LOG</p><h3>Hoạt động gateway</h3></div><span>{data.filter(item=>item.status!=='success').length} lỗi / {data.length} request</span></div>{data.length?<div className="table-wrap"><table><thead><tr><th>Thời gian</th>{admin&&<th>Tài khoản</th>}<th>Request ID</th><th>Model</th><th>Trạng thái</th><th>Token I/O</th><th>Latency</th><th>Chi phí</th></tr></thead><tbody>{pagination.paginatedItems.map((item) => <tr key={item.id}><td>{item.createdAt}</td>{admin&&<td><b>{item.userName}</b><small className="block">{item.userEmail} · #{item.userId}</small></td>}<td><code>{item.requestId}</code></td><td><b>{item.model}</b></td><td><Badge tone={item.status === 'success' ? 'success' : 'danger'}>{item.status === 'success' ? <CheckCircle2/> : <XCircle/>}{item.status.toUpperCase()}</Badge></td><td>{formatNumber(item.inputTokens)} / {formatNumber(item.outputTokens)}</td><td>{item.latencyMs} ms</td><td>{formatVnd(item.cost)}</td></tr>)}</tbody></table></div>:<TableEmpty message="Chưa có request nào được ghi nhận."/>}<TablePagination page={pagination.page} pageSize={pagination.pageSize} totalItems={pagination.totalItems} totalPages={pagination.totalPages} onPageChange={pagination.setPage} onPageSizeChange={pagination.changePageSize}/></article></div>;
}

export function SettingsPage() {
  const client = useQueryClient();
  const { data } = useQuery({ queryKey: ['settings'], queryFn: async () => (await apiClient.get<Settings>('/settings')).data });
  const [form, setForm] = useState<Settings>({ telegramEnabled: false, telegramChatId: '', lowBalanceThreshold: 100000 });
  useEffect(() => { if (data) setForm(data); }, [data]);
  const save = useMutation({ mutationFn: () => apiClient.put('/settings', { telegram_enabled: form.telegramEnabled, telegram_chat_id: form.telegramChatId, low_balance_threshold: form.lowBalanceThreshold }), onSuccess: () => client.invalidateQueries({ queryKey: ['settings'] }) });
  return <div className="page"><PageHeader eyebrow="ACCOUNT / ALERTS" title="Cai dat" description="Cau hinh canh bao so du va kenh nhan thong bao."/><article className="card form-card"><span className="icon-chip"><Bell/></span><h3>Canh bao so du thap</h3><label className="switch-row"><span><b>Gui canh bao Telegram</b><small>Thong bao mot lan khi so du vuot qua nguong.</small></span><input type="checkbox" checked={form.telegramEnabled} onChange={(e) => setForm({...form, telegramEnabled:e.target.checked})}/></label><label>Telegram Chat ID<input value={form.telegramChatId} onChange={(e) => setForm({...form, telegramChatId:e.target.value})} placeholder="-100xxxxxxxxxx" /></label><label>Nguong canh bao (VND)<input type="number" value={form.lowBalanceThreshold} onChange={(e) => setForm({...form, lowBalanceThreshold:Number(e.target.value)})}/></label><button className="button primary" onClick={() => save.mutate()}><Save/> {save.isPending ? 'Dang luu...' : 'Luu cau hinh'}</button>{save.isSuccess && <p className="success-text">Da luu cau hinh.</p>}</article></div>;
}

export function ProfilePage() {
  const { user } = useAuth(); const [current, setCurrent] = useState(''); const [next, setNext] = useState(''); const [confirm, setConfirm] = useState(''); const [message, setMessage] = useState('');
  const change = useMutation({ mutationFn: () => apiClient.post('/profile/change-password', { current_password: current, new_password: next }), onSuccess: () => { setCurrent(''); setNext(''); setConfirm(''); setMessage('Doi mat khau thanh cong.'); }, onError: () => setMessage('Mat khau hien tai khong dung.') });
  function submit(e: FormEvent) { e.preventDefault(); if (next !== confirm) { setMessage('Mat khau xac nhan khong khop.'); return; } change.mutate(); }
  return <div className="page"><PageHeader eyebrow="ACCOUNT / PROFILE" title="Ho so"/><article className="card profile-card"><span className="avatar large"><UserRound/></span><div><h2>{user?.name}</h2><p>{user?.email}</p></div><dl><dt>USER ID</dt><dd>#{user?.id}</dd><dt>ROLE</dt><dd>{user?.role}</dd><dt>STATUS</dt><dd>{user?.status}</dd></dl></article><form className="card form-card password-card" onSubmit={submit}><h3>Doi mat khau</h3><label>Mat khau hien tai<input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} required/></label><label>Mat khau moi<input type="password" minLength={8} value={next} onChange={(e) => setNext(e.target.value)} required/></label><label>Xac nhan mat khau<input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required/></label><button className="button primary"><Save/> Cap nhat mat khau</button>{message && <p className="form-message">{message}</p>}</form></div>;
}
