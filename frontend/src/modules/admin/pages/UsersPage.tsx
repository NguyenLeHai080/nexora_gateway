import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Coins, Edit3, Gauge, LockKeyhole, Search, Trash2, UserPlus, X } from 'lucide-react';
import { FormEvent, useMemo, useState } from 'react';
import { apiClient } from '../../../core/api/client';
import type { Model, User } from '../../../core/types';
import { PageHeader } from '../../../shared/components/PageHeader';
import { Badge } from '../../../shared/components/Badge';
import { formatNumber, formatVnd } from '../../../shared/utils/format';
import { usePagination } from '../../../shared/hooks/usePagination';
import { TablePagination } from '../../../shared/components/TablePagination';
import { TableEmpty } from '../../../shared/components/TableEmpty';

type Modal = { type: 'create' } | { type: 'edit' | 'balance' | 'tokens'; user: User } | null;

export function UsersPage() {
  const client = useQueryClient();
  const [query, setQuery] = useState('');
  const [modal, setModal] = useState<Modal>(null);
  const [userForm, setUserForm] = useState({ name: '', email: '', password: '', token_quota: 0 });
  const [balanceForm, setBalanceForm] = useState({ amount: 100000, token_amount: 0, type: 'credit', description: 'Admin credit' });
  const [tokenForm, setTokenForm] = useState({ operation: 'credit', amount: 1000000, description: 'Admin token adjustment' });
  const { data: users = [] } = useQuery({ queryKey: ['admin-users'], queryFn: async () => (await apiClient.get<User[]>('/admin/users')).data });
  const { data: models = [] } = useQuery({ queryKey: ['admin-models'], queryFn: async () => (await apiClient.get<Model[]>('/admin/router/models')).data });
  const filtered = useMemo(() => users.filter((u) => `${u.id} ${u.name} ${u.email}`.toLowerCase().includes(query.toLowerCase())), [users, query]);
  const pagination = usePagination(filtered, 10);
  const refresh = () => client.invalidateQueries({ queryKey: ['admin-users'] });
  const close = () => setModal(null);
  const create = useMutation({ mutationFn: () => apiClient.post('/admin/users', userForm), onSuccess: () => { refresh(); close(); } });
  const update = useMutation({ mutationFn: (user: User) => apiClient.put(`/admin/users/${user.id}`, userForm), onSuccess: () => { refresh(); close(); } });
  const adjust = useMutation({ mutationFn: (user: User) => apiClient.post(`/admin/users/${user.id}/balance`, balanceForm), onSuccess: () => { refresh(); close(); client.invalidateQueries({queryKey:['finance']}); } });
  const adjustTokens = useMutation({ mutationFn: (user: User) => apiClient.post(`/admin/users/${user.id}/tokens`, tokenForm), onSuccess: () => { refresh(); close(); } });
  const toggleStatus = useMutation({ mutationFn: (id: number) => apiClient.patch(`/admin/users/${id}/status`), onSuccess: refresh });
  const archive = useMutation({ mutationFn: (id: number) => apiClient.delete(`/admin/users/${id}`), onSuccess: refresh });
  const grant = useMutation({ mutationFn: ({ userId, modelId }: { userId: number; modelId: string }) => apiClient.post(`/admin/users/${userId}/models`, { model_id: modelId }), onSuccess: refresh });
  const revoke = useMutation({ mutationFn: ({ userId, modelId }: { userId: number; modelId: string }) => apiClient.delete(`/admin/users/${userId}/models/${encodeURIComponent(modelId)}`), onSuccess: refresh });

  function openCreate() { setUserForm({ name: '', email: '', password: '', token_quota: 0 }); setModal({type:'create'}); }
  function openEdit(user: User) { setUserForm({ name:user.name, email:user.email, password:'', token_quota:user.tokenQuota }); setModal({type:'edit',user}); }
  function submitUser(e: FormEvent) { e.preventDefault(); if (modal?.type === 'create') create.mutate(); else if (modal?.type === 'edit') update.mutate(modal.user); }

  return <div className="page">
    <PageHeader eyebrow="SUPER ADMIN / ACCOUNTS" title="Quan ly tai khoan" description="CRUD tai khoan, so du, quota va quyen model." action={<button className="button primary" onClick={openCreate}><UserPlus/> Tao tai khoan</button>} />
    <div className="toolbar"><div className="search"><Search/><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Tim ten, email, ID..."/></div><Badge tone="success">{users.filter((u) => u.status === 'active').length} DANG HOAT DONG</Badge></div>
    <article className="card table-card"><div className="table-section-heading"><div><p className="eyebrow">CLIENT DIRECTORY</p><h3>Danh sach tai khoan</h3></div><span>{filtered.length} ket qua</span></div>{filtered.length ? <div className="table-wrap"><table><thead><tr><th>Khach hang</th><th>So du</th><th>Token quota</th><th>Model da cap</th><th>Trang thai</th><th>Thao tac</th></tr></thead><tbody>{pagination.paginatedItems.map((user) => <tr key={user.id}>
      <td><div className="user-cell"><span className="avatar">{user.name.slice(0,2).toUpperCase()}</span><span><b>{user.name}</b><small>{user.email} · #{user.id}</small></span></div></td>
      <td><b>{formatVnd(user.balance)}</b></td><td><b>{formatNumber(Math.max(0,user.tokenQuota-user.tokenUsed))} con lai</b><small className="block">Da dung {formatNumber(user.tokenUsed)} / {formatNumber(user.tokenQuota)}</small></td>
      <td><div className="entitlements">{user.models.map((id) => <span key={id}>{id}<button title="Thu hoi" onClick={() => confirm(`Thu hoi ${id}?`) && revoke.mutate({userId:user.id,modelId:id})}><X/></button></span>)}<select value="" onChange={(e) => e.target.value && grant.mutate({userId:user.id,modelId:e.target.value})}><option value="">+ Cap model</option>{models.filter((m) => !user.models.includes(m.id)).map((m) => <option key={m.id} value={m.id}>{m.displayName}</option>)}</select></div></td>
      <td><Badge tone={user.status === 'active' ? 'success' : user.status === 'archived' ? 'neutral' : 'danger'}>{user.status.toUpperCase()}</Badge></td>
      <td><div className="row-actions"><button className="icon-button" title="Sua" onClick={() => openEdit(user)}><Edit3/></button><button className="icon-button" title="Dieu chinh so du" onClick={() => { setBalanceForm({amount:100000,token_amount:0,type:'credit',description:'Admin credit'}); setModal({type:'balance',user}); }}><Coins/></button><button className="icon-button" title="Dieu chinh token rieng" onClick={() => { setTokenForm({operation:'credit',amount:1000000,description:'Admin token adjustment'}); setModal({type:'tokens',user}); }}><Gauge/></button><button className="icon-button" title="Khoa/mo" onClick={() => toggleStatus.mutate(user.id)}><LockKeyhole/></button><button className="icon-button danger-text" title="Luu tru" onClick={() => confirm(`Luu tru tai khoan ${user.email}?`) && archive.mutate(user.id)}><Trash2/></button></div></td>
    </tr>)}</tbody></table></div> : <TableEmpty message="Thu thay doi tu khoa tim kiem hoac tao tai khoan moi."/>}<TablePagination page={pagination.page} pageSize={pagination.pageSize} totalItems={pagination.totalItems} totalPages={pagination.totalPages} onPageChange={pagination.setPage} onPageSizeChange={pagination.changePageSize}/></article>

    {(modal?.type === 'create' || modal?.type === 'edit') && <div className="modal-layer" onClick={close}><form className="modal" onSubmit={submitUser} onClick={(e) => e.stopPropagation()}><p className="eyebrow">{modal.type === 'create' ? 'NEW CLIENT' : 'UPDATE CLIENT'}</p><h2>{modal.type === 'create' ? 'Tao tai khoan' : `Sua ${modal.user.name}`}</h2><label>Ho ten<input value={userForm.name} onChange={(e) => setUserForm({...userForm,name:e.target.value})} required/></label><label>Email<input type="email" value={userForm.email} onChange={(e) => setUserForm({...userForm,email:e.target.value})} required/></label><label>{modal.type === 'create' ? 'Mat khau' : 'Mat khau moi (de trong neu khong doi)'}<input type="password" minLength={8} value={userForm.password} onChange={(e) => setUserForm({...userForm,password:e.target.value})} required={modal.type === 'create'}/></label>{modal.type === 'edit' && <label>Token quota<input type="number" min="0" value={userForm.token_quota} onChange={(e) => setUserForm({...userForm,token_quota:Number(e.target.value)})}/></label>}<ModalActions close={close} pending={create.isPending || update.isPending}/></form></div>}
    {modal?.type === 'balance' && <div className="modal-layer" onClick={close}><form className="modal" onSubmit={(e) => {e.preventDefault();adjust.mutate(modal.user);}} onClick={(e) => e.stopPropagation()}><p className="eyebrow">WALLET ADJUSTMENT</p><h2>Dieu chinh so du</h2><p>{modal.user.name} · hien co {formatVnd(modal.user.balance)}</p><label>Loai<select value={balanceForm.type} onChange={(e) => setBalanceForm({...balanceForm,type:e.target.value})}><option value="credit">Cong tien</option><option value="debit">Tru tien</option></select></label><label>So tien<input type="number" min="1" value={balanceForm.amount} onChange={(e) => setBalanceForm({...balanceForm,amount:Number(e.target.value)})}/></label><label>Ly do<input value={balanceForm.description} onChange={(e) => setBalanceForm({...balanceForm,description:e.target.value})}/></label><ModalActions close={close} pending={adjust.isPending}/></form></div>}
    {modal?.type === 'tokens' && <div className="modal-layer" onClick={close}><form className="modal" onSubmit={(e) => {e.preventDefault();adjustTokens.mutate(modal.user);}} onClick={(e) => e.stopPropagation()}><p className="eyebrow">TOKEN QUOTA / INDIVIDUAL</p><h2>Token cua {modal.user.name}</h2><div className="deposit-estimate"><span>CON LAI</span><strong>{formatNumber(Math.max(0,modal.user.tokenQuota-modal.user.tokenUsed))}</strong><small>Da dung {formatNumber(modal.user.tokenUsed)} · Tong quota {formatNumber(modal.user.tokenQuota)}</small></div><label>Thao tac<select value={tokenForm.operation} onChange={(e) => setTokenForm({...tokenForm,operation:e.target.value})}><option value="credit">Cong them token</option><option value="debit">Tru bot token</option><option value="set">Dat tong quota</option></select></label><label>{tokenForm.operation==='set'?'Tong quota moi':'So token thay doi'}<input type="number" min="0" step="1000" value={tokenForm.amount} onChange={(e) => setTokenForm({...tokenForm,amount:Number(e.target.value)})}/></label><label>Ly do<input value={tokenForm.description} onChange={(e) => setTokenForm({...tokenForm,description:e.target.value})} required minLength={3}/></label><ModalActions close={close} pending={adjustTokens.isPending}/></form></div>}
  </div>;
}

function ModalActions({close,pending}:{close:()=>void;pending:boolean}) { return <div className="modal-actions"><button type="button" className="button ghost" onClick={close}>Huy</button><button className="button primary" disabled={pending}>{pending ? 'Dang xu ly...' : 'Luu thay doi'}</button></div>; }
