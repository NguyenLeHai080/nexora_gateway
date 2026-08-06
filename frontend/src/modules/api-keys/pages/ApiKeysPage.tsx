import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Copy, Edit3, KeyRound, Plus, Power, Trash2 } from 'lucide-react';
import { FormEvent, useState } from 'react';
import { apiClient } from '../../../core/api/client';
import type { ApiKey } from '../../../core/types';
import { PageHeader } from '../../../shared/components/PageHeader';
import { Badge } from '../../../shared/components/Badge';

export function ApiKeysPage() {
  const client = useQueryClient(); const [editing,setEditing] = useState<ApiKey | 'new' | null>(null); const [form,setForm] = useState({name:'',quota:''}); const [createdKey,setCreatedKey] = useState('');
  const { data = [] } = useQuery({ queryKey: ['api-keys'], queryFn: async () => (await apiClient.get<ApiKey[]>('/api-keys')).data });
  const refresh = () => client.invalidateQueries({ queryKey: ['api-keys'] });
  const save = useMutation({ mutationFn: async () => { const body={name:form.name,quota:form.quota ? Number(form.quota) : null}; return editing === 'new' ? apiClient.post('/api-keys',body) : apiClient.put(`/api-keys/${(editing as ApiKey).id}`,body); }, onSuccess:(response)=>{refresh();setEditing(null);if(response.data.key)setCreatedKey(response.data.key);} });
  const toggle = useMutation({ mutationFn: (id: number) => apiClient.patch(`/api-keys/${id}/toggle`), onSuccess: refresh });
  const remove = useMutation({ mutationFn: (id: number) => apiClient.delete(`/api-keys/${id}`), onSuccess: refresh });
  function open(item:ApiKey|'new'){setEditing(item);setForm(item === 'new' ? {name:'',quota:''}:{name:item.name,quota:item.quota?.toString() ?? ''});}
  function submit(e:FormEvent){e.preventDefault();save.mutate();}
  return <div className="page"><PageHeader eyebrow="ACCESS / API KEYS" title="API Keys" description="Tao, sua quota, bat/tat va thu hoi key OpenAI-compatible." action={<button className="button primary" onClick={()=>open('new')}><Plus/> Tao API Key</button>} />
    {createdKey && <article className="new-secret"><div><p className="eyebrow">COPY NOW / SHOWN ONCE</p><code>{createdKey}</code></div><button className="button primary" onClick={()=>navigator.clipboard.writeText(createdKey)}><Copy/> Copy key</button><button className="icon-button" onClick={()=>setCreatedKey('')}>×</button></article>}
    <section className="key-list">{data.map((key) => <article className="card key-card" key={key.id}><span className="key-icon"><KeyRound /></span><div className="key-info"><div><h3>{key.name}</h3><Badge tone={key.status === 'active' ? 'success' : 'neutral'}>{key.status === 'active' ? 'HOAT DONG' : 'VO HIEU'}</Badge>{key.quota === null ? <Badge tone="violet">UNLIMITED</Badge> : <Badge>{key.quota.toLocaleString('vi-VN')} TOKEN</Badge>}</div><code>{key.prefix}••••••••</code><small>TAO {key.createdAt} · LAN CUOI {key.lastUsed ?? 'CHUA SU DUNG'}</small></div><div className="key-actions"><button className="button ghost" onClick={()=>open(key)}><Edit3/> Sua</button><button className="button ghost" onClick={() => toggle.mutate(key.id)}><Power/> {key.status === 'active' ? 'Vo hieu' : 'Bat'}</button><button className="button danger" onClick={() => confirm(`Xoa API key ${key.name}?`) && remove.mutate(key.id)}><Trash2/> Xoa</button></div></article>)}</section>
    {editing && <div className="modal-layer" onClick={()=>setEditing(null)}><form className="modal" onSubmit={submit} onClick={(e)=>e.stopPropagation()}><p className="eyebrow">API KEY POLICY</p><h2>{editing === 'new' ? 'Tao API key' : 'Sua API key'}</h2><label>Ten key<input value={form.name} onChange={(e)=>setForm({...form,name:e.target.value})} required/></label><label>Quota token (de trong = unlimited)<input type="number" min="1" value={form.quota} onChange={(e)=>setForm({...form,quota:e.target.value})}/></label><div className="modal-actions"><button type="button" className="button ghost" onClick={()=>setEditing(null)}>Huy</button><button className="button primary">Luu API key</button></div></form></div>}
  </div>;
}
