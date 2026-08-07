import { useMutation, useQuery } from '@tanstack/react-query';
import { Activity, CircleDollarSign, Cloud, KeyRound, Link2, Plus, RefreshCw, ScrollText, UserRound, WalletCards } from 'lucide-react';
import { ChangeEvent, FormEvent, useMemo, useState } from 'react';
import { apiClient } from '../../../core/api/client';
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
  const [poolModal,setPoolModal]=useState(false); const [pool,setPool]=useState(initialPool);
  const query=useQuery({queryKey:['tokenx-overview'],queryFn:async()=>(await apiClient.get<Overview>('/admin/tokenx/overview')).data,refetchInterval:30000});
  const pricingQuery=useQuery({queryKey:['tokenx-pricing-rules'],queryFn:async()=>(await apiClient.get('/admin/tokenx/pricing-rules')).data,refetchInterval:60000});
  const data=query.data; const usage=data?.reconciliation??{}; const apiKeys=useMemo(()=>rows(data?.apiKeys),[data?.apiKeys]); const pricing=useMemo(()=>rows(pricingQuery.data),[pricingQuery.data]); const account=(data?.account&&typeof data.account==='object'?data.account:{}) as Json; const balance=numberFrom(data?.wallet,['balance','available_balance','wallet_balance']);
  const mapPool=useMutation({mutationFn:()=>apiClient.post('/admin/tokenx/pools',pool),onSuccess:()=>{setPoolModal(false);setPool(initialPool);}});
  const accuracy=pick(usage,'tokenAccuracyPercent');
  return <div className="page tokenx-page">
    <PageHeader eyebrow="INTEGRATION / TOKENX" title="Trung tâm điều hành TokenX" description="Theo dõi nguồn cung, khóa truy cập, routing pool và độ chính xác dữ liệu trên một màn hình." action={<button className="button primary" onClick={()=>query.refetch()} disabled={query.isFetching}><RefreshCw/> {query.isFetching?'Đang đồng bộ...':'Đồng bộ dữ liệu'}</button>}/>
    {!data?.configured&&<section className="card tokenx-warning"><Cloud/><div><b>Chưa cấu hình TokenX trên server</b><span>{data?.error??'Thiếu biến môi trường TokenX.'}</span></div></section>}
    <section className="metric-grid tokenx-stats">
      <article className="metric-card tokenx-metric balance"><span className="metric-icon"><CircleDollarSign/></span><p>SỐ DƯ TOKENX</p><strong>{balance===null?'—':formatVnd(balance)}</strong><small>Nguồn vốn còn khả dụng trên upstream</small></article>
      <article className="metric-card tokenx-metric keys"><span className="metric-icon"><KeyRound/></span><p>KHÓA KẾT NỐI</p><strong>{apiKeys.length}</strong><small>{apiKeys.length?'Gateway tự chọn khóa đang hoạt động':'Chưa có khóa sẵn sàng'}</small></article>
      <article className="metric-card tokenx-metric accuracy"><span className="metric-icon"><Link2/></span><p>ĐỘ KHỚP TOKEN 24H</p><strong>{accuracy==null?'—':`${accuracy}%`}</strong><small>Đối chiếu Nexora với TokenX</small></article>
      <article className="metric-card tokenx-metric margin"><span className="metric-icon"><Activity/></span><p>LỢI NHUẬN GỘP 24H</p><strong>{pick(usage,'grossMargin')==null?'—':formatVnd(Number(pick(usage,'grossMargin')))}</strong><small>Doanh thu bán ra trừ chi phí nguồn</small></article>
    </section>
    <section className="tokenx-grid">
      <article className="card tokenx-map-card"><div><p className="eyebrow">INTEGRATED MANAGEMENT</p><h3>TokenX đã được phân bổ vào hệ thống</h3><p>Trang này chỉ giữ cấu hình kết nối và routing pool. Các nghiệp vụ được quản lý tại đúng module chuyên trách.</p></div><nav><a href="/admin/user-api-keys"><KeyRound/><span><b>API key & TokenX</b><small>Tạo, thu hồi và kiểm tra khóa nguồn</small></span></a><a href="/admin/finance"><WalletCards/><span><b>Dòng tiền & lợi nhuận</b><small>Số dư, chi phí và lịch sử ví nguồn</small></span></a><a href="/logs"><ScrollText/><span><b>Nhật ký sử dụng</b><small>Request Nexora và TokenX upstream</small></span></a></nav></article>
      <article className="card tokenx-reconcile"><div className="table-section-heading"><div><p className="eyebrow">RECONCILIATION / 24H</p><h3>Đối soát sử dụng</h3></div><Link2/></div><dl><div><dt>Request Nexora</dt><dd>{Number(pick(usage,'localRequests')??0).toLocaleString('vi-VN')}</dd></div><div><dt>Token Nexora</dt><dd>{Number(pick(usage,'localTokens')??0).toLocaleString('vi-VN')}</dd></div><div><dt>Token TokenX</dt><dd>{pick(usage,'upstreamTokens')==null?'Chưa có':Number(pick(usage,'upstreamTokens')).toLocaleString('vi-VN')}</dd></div><div><dt>Doanh thu</dt><dd>{formatVnd(Number(pick(usage,'localRevenue')??0))}</dd></div><div><dt>Chi phí upstream</dt><dd>{pick(usage,'upstreamCost')==null?'Chưa có':formatVnd(Number(pick(usage,'upstreamCost')))}</dd></div></dl><button className="button primary full-button" onClick={()=>setPoolModal(true)}><Plus/> Map model vào pool</button></article>
    </section>
    <section className="tokenx-detail-grid">
      <article className="card tokenx-account-card"><div className="table-section-heading"><div><p className="eyebrow">TOKENX ACCOUNT</p><h3>Tài khoản nguồn đang kết nối</h3></div><UserRound/></div><dl><div><dt>Tên đăng nhập</dt><dd>{String(pick(account,'username','name')??'—')}</dd></div><div><dt>Email</dt><dd>{String(pick(account,'email')??'—')}</dd></div><div><dt>Vai trò</dt><dd>{String(pick(account,'role')??'user')}</dd></div><div><dt>Trạng thái</dt><dd>{String(pick(account,'status')??'active')}</dd></div></dl><p>TokenX hiện chỉ cung cấp quản lý tài khoản đang đăng nhập, không có API tạo nhiều user từ Nexora.</p></article>
      <article className="card table-card"><div className="table-section-heading"><div><p className="eyebrow">TOKENX MODELS</p><h3>Model và bảng giá upstream</h3></div><span>{pricing.length} model</span></div>{pricing.length?<div className="table-wrap"><table><thead><tr><th>Model</th><th>Input / 1M</th><th>Output / 1M</th><th>Trạng thái</th></tr></thead><tbody>{pricing.map((item,index)=><tr key={String(pick(item,'id','model','model_id')??index)}><td><b>{String(pick(item,'display_name','name','model','model_id')??'—')}</b><small className="block">{String(pick(item,'model_id','model')??'')}</small></td><td>{formatVnd(Number(pick(item,'input_price','input_cost','input')??0))}</td><td>{formatVnd(Number(pick(item,'output_price','output_cost','output')??0))}</td><td>{String(pick(item,'status','enabled')??'active')}</td></tr>)}</tbody></table></div>:<p className="tokenx-empty-copy">TokenX chưa trả dữ liệu pricing-rules.</p>}</article>
    </section>
    {poolModal&&<PoolModal pool={pool} setPool={setPool} close={()=>setPoolModal(false)} submit={()=>mapPool.mutate()} pending={mapPool.isPending} error={mapPool.isError}/>} 
  </div>;
}

function PoolModal({pool,setPool,close,submit,pending,error}:{pool:typeof initialPool;setPool:(p:typeof initialPool)=>void;close:()=>void;submit:()=>void;pending:boolean;error:boolean}) {
  const field=(key:keyof typeof pool)=>(event:ChangeEvent<HTMLInputElement>)=>setPool({...pool,[key]:event.target.type==='number'?Number(event.target.value):event.target.value});
  return <div className="modal-layer" onClick={close}><form className="modal routing-pool-modal" onClick={e=>e.stopPropagation()} onSubmit={(e:FormEvent)=>{e.preventDefault();submit();}}><p className="eyebrow">TOKENX ROUTING</p><h2>Map model thành pool</h2><div className="form-columns"><label>Model ID<input value={pool.model_id} onChange={field('model_id')} placeholder="gpt-5.5" required/></label><label>Tên hiển thị<input value={pool.display_name} onChange={field('display_name')} required/></label><label>Giá input / 1M<input type="number" min="0" value={pool.input_price} onChange={field('input_price')}/></label><label>Giá output / 1M<input type="number" min="0" value={pool.output_price} onChange={field('output_price')}/></label><label>Tổng request đồng thời<input type="number" min="1" value={pool.max_concurrency} onChange={field('max_concurrency')}/></label><label>Mỗi user đồng thời<input type="number" min="1" value={pool.per_user_concurrency} onChange={field('per_user_concurrency')}/></label></div><label>Cooldown khi lỗi (giây)<input type="number" min="1" value={pool.cooldown_seconds} onChange={field('cooldown_seconds')}/></label><div className="confirm-note"><Activity/><span>Model công khai có tiền tố <b>tx/</b>. Backend tính phí input/output riêng và giới hạn tải theo pool.</span></div>{error&&<p className="form-error">Không thể tạo pool. Hãy kiểm tra kết nối và dữ liệu.</p>}<div className="modal-actions"><button type="button" className="button ghost" onClick={close}>Hủy</button><button className="button primary" disabled={pending}>Lưu và kích hoạt</button></div></form></div>;
}
