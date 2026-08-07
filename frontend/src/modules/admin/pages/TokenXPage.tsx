import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Activity, CircleDollarSign, Cloud, KeyRound, Link2, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { ChangeEvent, FormEvent, useMemo, useState } from 'react';
import { apiClient } from '../../../core/api/client';
import { Badge } from '../../../shared/components/Badge';
import { PageHeader } from '../../../shared/components/PageHeader';
import { formatVnd } from '../../../shared/utils/format';

type Json = Record<string, unknown>;
type Overview = Json & { configured?: boolean; gatewayConfigured?: boolean; error?: string; apiKeys?: unknown; wallet?: unknown; reconciliation?: Json };
const initialPool = { model_id:'', display_name:'', input_price:2000, output_price:3000, max_concurrency:10, per_user_concurrency:2, cooldown_seconds:60 };

function rows(value: unknown): Json[] {
  if (Array.isArray(value)) return value.filter((item): item is Json => !!item && typeof item === 'object');
  if (value && typeof value === 'object') for (const key of ['items','data','results','api_keys','keys']) { const item=(value as Json)[key]; if(Array.isArray(item)) return rows(item); }
  return [];
}
function numberFrom(value: unknown, keys: string[]): number | null {
  if (!value || typeof value !== 'object') return null;
  for (const [key,item] of Object.entries(value as Json)) if(keys.includes(key.toLowerCase()) && Number.isFinite(Number(item))) return Number(item);
  for (const item of Object.values(value as Json)) { const found=numberFrom(item,keys); if(found!==null)return found; }
  return null;
}
const pick=(row:Json,...keys:string[])=>keys.map(key=>row[key]).find(value=>value!==undefined&&value!==null);

export function TokenXPage() {
  const qc=useQueryClient(); const [keyModal,setKeyModal]=useState(false); const [keyName,setKeyName]=useState('Nexora Gateway'); const [secret,setSecret]=useState(''); const [poolModal,setPoolModal]=useState(false); const [pool,setPool]=useState(initialPool);
  const query=useQuery({queryKey:['tokenx-overview'],queryFn:async()=>(await apiClient.get<Overview>('/admin/tokenx/overview')).data,refetchInterval:30000});
  const data=query.data; const usage=data?.reconciliation??{}; const apiKeys=useMemo(()=>rows(data?.apiKeys),[data?.apiKeys]); const balance=numberFrom(data?.wallet,['balance','available_balance','wallet_balance']);
  const createKey=useMutation({mutationFn:async()=>(await apiClient.post<Json>('/admin/tokenx/api-keys',{name:keyName})).data,onSuccess:r=>{setSecret(String(pick(r,'secret','key','api_key','token')??''));qc.invalidateQueries({queryKey:['tokenx-overview']});}});
  const revoke=useMutation({mutationFn:(id:string)=>apiClient.delete(`/admin/tokenx/api-keys/${encodeURIComponent(id)}`),onSuccess:()=>qc.invalidateQueries({queryKey:['tokenx-overview']})});
  const mapPool=useMutation({mutationFn:()=>apiClient.post('/admin/tokenx/pools',pool),onSuccess:()=>{setPoolModal(false);setPool(initialPool);}});
  const accuracy=pick(usage,'tokenAccuracyPercent');
  return <div className="page tokenx-page">
    <PageHeader eyebrow="INTEGRATION / TOKENX" title="TokenX Control Center" description="Quản lý upstream, API key, routing pool và đối soát dữ liệu TokenX." action={<button className="button primary" onClick={()=>query.refetch()} disabled={query.isFetching}><RefreshCw/> {query.isFetching?'Đang đồng bộ...':'Đồng bộ dữ liệu'}</button>}/>
    {!data?.configured&&<section className="card tokenx-warning"><Cloud/><div><b>Chưa cấu hình TokenX trên server</b><span>{data?.error??'Thiếu biến môi trường TokenX.'}</span></div></section>}
    <section className="stats-grid tokenx-stats">
      <article className="stat-card"><span className="stat-icon"><CircleDollarSign/></span><p>SỐ DƯ TOKENX</p><strong>{balance===null?'—':formatVnd(balance)}</strong><small>Số dư upstream</small></article>
      <article className="stat-card"><span className="stat-icon"><KeyRound/></span><p>API KEY</p><strong>{apiKeys.length}</strong><small>{data?.gatewayConfigured?'Gateway đã có key':'Gateway chưa có key'}</small></article>
      <article className="stat-card"><span className="stat-icon"><Link2/></span><p>ĐỘ KHỚP TOKEN 24H</p><strong>{accuracy==null?'—':`${accuracy}%`}</strong><small>Nexora so với TokenX</small></article>
      <article className="stat-card"><span className="stat-icon"><Activity/></span><p>LỢI NHUẬN GỘP 24H</p><strong>{pick(usage,'grossMargin')==null?'—':formatVnd(Number(pick(usage,'grossMargin')))}</strong><small>Doanh thu - upstream</small></article>
    </section>
    <section className="tokenx-grid">
      <article className="card table-card"><div className="table-section-heading"><div><p className="eyebrow">UPSTREAM ACCESS</p><h3>API keys TokenX</h3></div><button className="button ghost" onClick={()=>setKeyModal(true)}><Plus/> Tạo key</button></div><div className="table-wrap"><table><thead><tr><th>Tên</th><th>ID / prefix</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>{apiKeys.length?apiKeys.map((key,index)=>{const id=String(pick(key,'id','uuid')??'');return <tr key={id||index}><td><b>{String(pick(key,'name','label')??`Key ${index+1}`)}</b></td><td><code>{String(pick(key,'prefix','key_prefix','id')??'—')}</code></td><td><Badge tone="success">ACTIVE</Badge></td><td><button className="icon-button danger-text" disabled={!id} onClick={()=>id&&confirm('Thu hồi API key này?')&&revoke.mutate(id)}><Trash2/></button></td></tr>}):<tr><td colSpan={4}>Chưa có API key hoặc chưa tải được dữ liệu.</td></tr>}</tbody></table></div></article>
      <article className="card tokenx-reconcile"><div className="table-section-heading"><div><p className="eyebrow">RECONCILIATION / 24H</p><h3>Đối soát sử dụng</h3></div><Link2/></div><dl><div><dt>Request Nexora</dt><dd>{Number(pick(usage,'localRequests')??0).toLocaleString('vi-VN')}</dd></div><div><dt>Token Nexora</dt><dd>{Number(pick(usage,'localTokens')??0).toLocaleString('vi-VN')}</dd></div><div><dt>Token TokenX</dt><dd>{pick(usage,'upstreamTokens')==null?'Chưa có':Number(pick(usage,'upstreamTokens')).toLocaleString('vi-VN')}</dd></div><div><dt>Doanh thu</dt><dd>{formatVnd(Number(pick(usage,'localRevenue')??0))}</dd></div><div><dt>Chi phí upstream</dt><dd>{pick(usage,'upstreamCost')==null?'Chưa có':formatVnd(Number(pick(usage,'upstreamCost')))}</dd></div></dl><button className="button primary full-button" onClick={()=>setPoolModal(true)}><Plus/> Map model vào pool</button></article>
    </section>
    {keyModal&&<div className="modal-layer" onClick={()=>setKeyModal(false)}><form className="modal" onClick={e=>e.stopPropagation()} onSubmit={e=>{e.preventDefault();createKey.mutate();}}><p className="eyebrow">TOKENX API KEY</p><h2>Tạo khóa upstream</h2><label>Tên khóa<input value={keyName} onChange={e=>setKeyName(e.target.value)} minLength={2} required/></label>{secret&&<div className="new-secret"><div><p>Chỉ hiển thị một lần</p><code>{secret}</code></div><button type="button" className="button ghost" onClick={()=>navigator.clipboard.writeText(secret)}>Sao chép</button></div>}<div className="modal-actions"><button type="button" className="button ghost" onClick={()=>setKeyModal(false)}>Đóng</button><button className="button primary" disabled={createKey.isPending}>Tạo khóa</button></div></form></div>}
    {poolModal&&<PoolModal pool={pool} setPool={setPool} close={()=>setPoolModal(false)} submit={()=>mapPool.mutate()} pending={mapPool.isPending} error={mapPool.isError}/>} 
  </div>;
}

function PoolModal({pool,setPool,close,submit,pending,error}:{pool:typeof initialPool;setPool:(p:typeof initialPool)=>void;close:()=>void;submit:()=>void;pending:boolean;error:boolean}) {
  const field=(key:keyof typeof pool)=>(event:ChangeEvent<HTMLInputElement>)=>setPool({...pool,[key]:event.target.type==='number'?Number(event.target.value):event.target.value});
  return <div className="modal-layer" onClick={close}><form className="modal routing-pool-modal" onClick={e=>e.stopPropagation()} onSubmit={(e:FormEvent)=>{e.preventDefault();submit();}}><p className="eyebrow">TOKENX ROUTING</p><h2>Map model thành pool</h2><div className="form-columns"><label>Model ID<input value={pool.model_id} onChange={field('model_id')} placeholder="gpt-5.5" required/></label><label>Tên hiển thị<input value={pool.display_name} onChange={field('display_name')} required/></label><label>Giá input / 1M<input type="number" min="0" value={pool.input_price} onChange={field('input_price')}/></label><label>Giá output / 1M<input type="number" min="0" value={pool.output_price} onChange={field('output_price')}/></label><label>Tổng request đồng thời<input type="number" min="1" value={pool.max_concurrency} onChange={field('max_concurrency')}/></label><label>Mỗi user đồng thời<input type="number" min="1" value={pool.per_user_concurrency} onChange={field('per_user_concurrency')}/></label></div><label>Cooldown khi lỗi (giây)<input type="number" min="1" value={pool.cooldown_seconds} onChange={field('cooldown_seconds')}/></label><div className="confirm-note"><Activity/><span>Model công khai có tiền tố <b>tx/</b>. Backend tính phí input/output riêng và giới hạn tải theo pool.</span></div>{error&&<p className="form-error">Không thể tạo pool. Hãy kiểm tra kết nối và dữ liệu.</p>}<div className="modal-actions"><button type="button" className="button ghost" onClick={close}>Hủy</button><button className="button primary" disabled={pending}>Lưu và kích hoạt</button></div></form></div>;
}
