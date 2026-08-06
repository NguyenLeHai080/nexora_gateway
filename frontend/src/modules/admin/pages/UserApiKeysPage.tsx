import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Clipboard, Edit3, KeyRound, Plus, Power, Search, Trash2, UserRound } from 'lucide-react';
import { FormEvent, useMemo, useState } from 'react';
import { apiClient } from '../../../core/api/client';
import type { ApiKey, User } from '../../../core/types';
import { Badge } from '../../../shared/components/Badge';
import { PageHeader } from '../../../shared/components/PageHeader';
import { formatNumber } from '../../../shared/utils/format';

type ManagedKey = ApiKey & { key?: string };

export function UserApiKeysPage() {
  const client = useQueryClient();
  const [query, setQuery] = useState('');
  const [userId, setUserId] = useState<number | null>(null);
  const [editing, setEditing] = useState<ManagedKey | 'new' | null>(null);
  const [form, setForm] = useState({ name: '', quota: '' });
  const [createdSecret, setCreatedSecret] = useState('');
  const { data: users = [] } = useQuery({ queryKey: ['admin-users'], queryFn: async () => (await apiClient.get<User[]>('/admin/users')).data });
  const selectedUser = users.find((user) => user.id === userId);
  const filteredUsers = useMemo(() => users.filter((user) => `${user.name} ${user.email} ${user.id}`.toLowerCase().includes(query.toLowerCase())), [query, users]);
  const { data: keys = [], isLoading } = useQuery({ queryKey: ['admin-user-api-keys', userId], queryFn: async () => (await apiClient.get<ManagedKey[]>(`/admin/users/${userId}/api-keys`)).data, enabled: userId !== null });
  const refresh = () => client.invalidateQueries({ queryKey: ['admin-user-api-keys', userId] });
  const save = useMutation({ mutationFn: async () => { const payload = { name: form.name, quota: form.quota ? Number(form.quota) : null }; return editing === 'new' ? apiClient.post<ManagedKey>(`/admin/users/${userId}/api-keys`, payload) : apiClient.put(`/admin/users/${userId}/api-keys/${editing?.id}`, payload); }, onSuccess: (response) => { refresh(); setEditing(null); if (response.data.key) setCreatedSecret(response.data.key); } });
  const toggle = useMutation({ mutationFn: (keyId: number) => apiClient.patch(`/admin/users/${userId}/api-keys/${keyId}/toggle`), onSuccess: refresh });
  const remove = useMutation({ mutationFn: (keyId: number) => apiClient.delete(`/admin/users/${userId}/api-keys/${keyId}`), onSuccess: refresh });

  function selectUser(id: number) { setUserId(id); setCreatedSecret(''); setEditing(null); }
  function open(item: ManagedKey | 'new') { setEditing(item); setForm(item === 'new' ? { name: '', quota: '' } : { name: item.name, quota: item.quota?.toString() ?? '' }); }
  function submit(event: FormEvent) { event.preventDefault(); save.mutate(); }

  return <div className="page admin-key-page">
    <PageHeader eyebrow="SUPER ADMIN / CLIENT ACCESS" title="API key theo tài khoản" description="Chọn từng khách hàng để tạo khóa, giới hạn quota và thu hồi quyền truy cập riêng." action={selectedUser && <button className="button primary" onClick={() => open('new')}><Plus/> Tạo key cho {selectedUser.name}</button>} />
    <div className="admin-key-layout">
      <section className="card account-picker"><div className="account-picker-head"><p className="eyebrow">CLIENTS</p><h3>Tài khoản khách hàng</h3><div className="search"><Search/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm tên hoặc email..."/></div></div><div className="account-picker-list">{filteredUsers.map((user) => <button key={user.id} className={user.id === userId ? 'active' : ''} onClick={() => selectUser(user.id)}><span className="avatar">{user.name.slice(0, 2).toUpperCase()}</span><span><b>{user.name}</b><small>{user.email}</small></span><Badge tone={user.status === 'active' ? 'success' : 'danger'}>{user.status}</Badge></button>)}</div></section>
      <section className="card managed-key-panel">
        {!selectedUser ? <div className="managed-key-empty"><UserRound/><h3>Chọn một tài khoản</h3><p>Danh sách API key và hạn mức riêng sẽ xuất hiện tại đây.</p></div> : <><div className="managed-user-summary"><div><span className="avatar">{selectedUser.name.slice(0,2).toUpperCase()}</span><div><p className="eyebrow">SELECTED CLIENT</p><h3>{selectedUser.name}</h3><small>{selectedUser.email} · #{selectedUser.id}</small></div></div><dl><div><dt>Hạn mức token</dt><dd>{selectedUser.tokenQuota>0?formatNumber(Math.max(0,selectedUser.tokenQuota-selectedUser.tokenUsed)):'Không giới hạn'}</dd></div><div><dt>Model</dt><dd>{selectedUser.models.length}</dd></div><div><dt>API key</dt><dd>{keys.length}</dd></div></dl></div>
          {createdSecret && <div className="admin-secret"><div><p className="eyebrow">CHỈ HIỂN THỊ MỘT LẦN</p><code>{createdSecret}</code></div><button className="button primary" onClick={() => navigator.clipboard.writeText(createdSecret)}><Clipboard/> Sao chép</button><button className="icon-button" onClick={() => setCreatedSecret('')}>×</button></div>}
          <div className="managed-key-list">{isLoading ? <p className="managed-loading">Đang tải...</p> : keys.length ? keys.map((key) => <article key={key.id}><span className="key-icon"><KeyRound/></span><div><div><h4>{key.name}</h4><Badge tone={key.status === 'active' ? 'success' : 'neutral'}>{key.status === 'active' ? 'HOẠT ĐỘNG' : 'VÔ HIỆU'}</Badge></div><code>{key.prefix}••••••••</code><small>{key.quota === null ? 'Không giới hạn' : `Quota ${formatNumber(key.quota)} token`} · Dùng lần cuối {key.lastUsed ?? 'chưa dùng'}</small></div><nav><button className="icon-button" title="Sửa quota" onClick={() => open(key)}><Edit3/></button><button className="icon-button" title={key.status === 'active' ? 'Vô hiệu hóa' : 'Kích hoạt'} onClick={() => toggle.mutate(key.id)}><Power/></button><button className="icon-button danger-text" title="Xóa" onClick={() => confirm(`Xóa key ${key.name} của ${selectedUser.name}?`) && remove.mutate(key.id)}><Trash2/></button></nav></article>) : <div className="managed-key-empty small"><KeyRound/><h3>Chưa có API key</h3><p>Tạo khóa đầu tiên cho tài khoản này.</p><button className="button primary" onClick={() => open('new')}><Plus/> Tạo API key</button></div>}</div></>}
      </section>
    </div>
    {editing && selectedUser && <div className="modal-layer" onClick={() => setEditing(null)}><form className="modal" onSubmit={submit} onClick={(event) => event.stopPropagation()}><p className="eyebrow">{editing === 'new' ? 'ISSUE CLIENT KEY' : 'UPDATE KEY POLICY'}</p><h2>{editing === 'new' ? `Tạo key cho ${selectedUser.name}` : `Sửa ${editing.name}`}</h2><label>Tên khóa<input value={form.name} onChange={(event) => setForm({...form, name: event.target.value})} required/></label><label>Quota token (để trống = không giới hạn)<input type="number" min="1" value={form.quota} onChange={(event) => setForm({...form, quota: event.target.value})}/></label>{save.isError && <p className="form-error">Không thể lưu API key.</p>}<div className="modal-actions"><button type="button" className="button ghost" onClick={() => setEditing(null)}>Hủy</button><button className="button primary" disabled={save.isPending}>{save.isPending ? 'Đang lưu...' : 'Lưu API key'}</button></div></form></div>}
  </div>;
}
