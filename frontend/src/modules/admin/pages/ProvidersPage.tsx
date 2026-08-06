import axios from 'axios';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Activity, Plus, Trash2 } from 'lucide-react';
import { FormEvent, useRef, useState } from 'react';
import { apiClient } from '../../../core/api/client';
import { Badge } from '../../../shared/components/Badge';
import { PageHeader } from '../../../shared/components/PageHeader';
import { TableEmpty } from '../../../shared/components/TableEmpty';
import { TablePagination } from '../../../shared/components/TablePagination';
import { usePagination } from '../../../shared/hooks/usePagination';

interface RouterConnection { id:string;provider:string;name:string;email?:string;authType:string;priority:number;isActive:boolean;testStatus:string;lastError?:string }
interface ProviderOption { id:string;name:string;authModes:Array<'apikey'|'oauth'>;authHint:string }
interface ConnectionTestResult { valid:boolean;error?:string|null;refreshed?:boolean }
const emptyProvider = { provider:'', name:'', apiKey:'', priority:1 };

function apiError(error: unknown): string {
  if (axios.isAxiosError(error)) return error.response?.data?.detail || error.message;
  if (error instanceof Error) return error.message;
  return 'Loi khong xac dinh';
}

export function ProvidersPage() {
  const queryClient=useQueryClient();
  const [adding,setAdding]=useState(false);
  const [addingOauth,setAddingOauth]=useState(false);
  const [oauthProvider,setOauthProvider]=useState('');
  const [wizardUrl,setWizardUrl]=useState('');
  const [testingId,setTestingId]=useState('');
  const [testResults,setTestResults]=useState<Record<string,{ok:boolean;message:string}>>({});
  const wizardFrame=useRef<HTMLIFrameElement>(null);
  const [form,setForm]=useState(emptyProvider);
  const {data:connections=[]}=useQuery({queryKey:['router-connections'],queryFn:async()=>(await apiClient.get<{connections:RouterConnection[]}>('/admin/router/connections')).data.connections,refetchInterval:15000});
  const {data:options=[]}=useQuery({queryKey:['router-provider-options'],queryFn:async()=>(await apiClient.get<{providers:ProviderOption[]}>('/admin/router/provider-options')).data.providers});
  const refresh=()=>queryClient.invalidateQueries({queryKey:['router-connections']});
  const create=useMutation({mutationFn:()=>apiClient.post('/admin/router/connections',{provider:form.provider,name:form.name,api_key:form.apiKey,priority:form.priority}),onSuccess:()=>{refresh();setAdding(false);setForm(emptyProvider);}});
  const toggle=useMutation({mutationFn:(item:RouterConnection)=>apiClient.patch(`/admin/router/connections/${encodeURIComponent(item.id)}/status`,{is_active:!item.isActive}),onSuccess:refresh});
  const test=useMutation({mutationFn:async(id:string)=>{setTestingId(id);const {data}=await apiClient.post<ConnectionTestResult>(`/admin/router/connections/${encodeURIComponent(id)}/test`);return{id,data};},onSuccess:({id,data})=>{setTestResults(previous=>({...previous,[id]:{ok:data.valid,message:data.valid?(data.refreshed?'Hop le - token da duoc lam moi':'Ket noi hop le'):data.error||'Ket noi khong hop le'}}));refresh();},onError:(error,id)=>setTestResults(previous=>({...previous,[id]:{ok:false,message:apiError(error)}})),onSettled:()=>setTestingId('')});
  const remove=useMutation({mutationFn:(id:string)=>apiClient.delete(`/admin/router/connections/${encodeURIComponent(id)}`),onSuccess:refresh});
  const openOauth=useMutation({mutationFn:async()=>{const {data}=await apiClient.post<{url:string}>('/admin/router/provider-wizard',{provider:oauthProvider});const target=new URL(data.url);target.searchParams.set('embed','1');const ssoPath=`/router-embed${target.pathname}${target.search}`;const response=await fetch(ssoPath,{credentials:'include'});if(!response.ok){let detail='';try{const body=await response.json();detail=body.error||body.detail||'';}catch{detail=await response.text().catch(()=> '');}throw new Error(detail||`Khong the khoi tao phien OAuth (HTTP ${response.status})`);}return `/router-embed/dashboard/providers/${encodeURIComponent(oauthProvider)}?source=nexora`;},onSuccess:(url)=>{setWizardUrl(url);setAddingOauth(false);setOauthProvider('');}});
  const pagination=usePagination(connections,10);
  const selected=options.find(item=>item.id===form.provider);
  function submit(event:FormEvent){event.preventDefault();create.mutate();}
  function repairWizardRoute():boolean{
    const frame=wizardFrame.current;
    if(!frame) return false;
    try {
      const location=frame.contentWindow?.location;
      if(!location) return false;
      const escaped=!location.pathname.startsWith('/router-embed/')&&(
        location.pathname.startsWith('/dashboard')||location.pathname==='/login'||location.pathname==='/callback'
      );
      if(escaped){
        const params=new URLSearchParams(location.search);
        params.set('source','nexora');
        frame.src=`/router-embed${location.pathname}?${params.toString()}${location.hash}`;
        return true;
      }
    } catch {
      // OAuth provider pages may temporarily be cross-origin; their own popup handles the callback.
    }
    return false;
  }
  function handleWizardLoad(){if(!repairWizardRoute()) refresh();}

  return <div className="page">
    <PageHeader eyebrow="9ROUTER / UPSTREAM" title="Provider Accounts" description="Quan ly tap trung API key va OAuth. Moi thay doi tren trang nay duoc ghi truc tiep vao 9Router." action={<div className="row-actions"><button className="button ghost" onClick={()=>setAddingOauth(true)}><Plus/> Ket noi OAuth</button><button className="button primary" onClick={()=>setAdding(true)}><Plus/> Them API key</button></div>}/>
    <article className="card table-card"><div className="table-section-heading"><div><p className="eyebrow">LIVE FROM 9ROUTER</p><h3>{connections.length} tai khoan provider</h3></div><span>{connections.filter(item=>item.isActive).length}/{connections.length} active</span></div>{connections.length?<div className="table-wrap"><table><thead><tr><th>Tai khoan</th><th>Provider</th><th>Auth</th><th>Uu tien</th><th>Kiem tra</th><th>Trang thai</th><th>Thao tac</th></tr></thead><tbody>{pagination.paginatedItems.map(item=><tr key={item.id}><td><b>{item.name}</b><small className="block">{item.email||item.id}</small>{item.lastError&&<small className="connection-error">{item.lastError}</small>}{testResults[item.id]&&<small className={`connection-test-result ${testResults[item.id].ok?'success':'error'}`}>{testResults[item.id].message}</small>}</td><td><Badge tone="violet">{item.provider.toUpperCase()}</Badge></td><td>{item.authType}</td><td>#{item.priority}</td><td><Badge tone={item.testStatus==='active'?'success':item.testStatus==='unavailable'?'danger':'neutral'}>{item.testStatus.toUpperCase()}</Badge></td><td><Badge tone={item.isActive?'success':'neutral'}>{item.isActive?'DANG DUNG':'TAM TAT'}</Badge></td><td><div className="row-actions"><button className="button ghost" disabled={testingId===item.id} onClick={()=>test.mutate(item.id)}><Activity/>{testingId===item.id?'Dang test...':'Test'}</button><button className="button ghost" onClick={()=>toggle.mutate(item)}>{item.isActive?'Tat':'Bat'}</button><button className="icon-button danger-text" title="Xoa provider" onClick={()=>confirm(`Xoa provider ${item.name} khoi 9Router?`)&&remove.mutate(item.id)}><Trash2/></button></div></td></tr>)}</tbody></table></div>:<TableEmpty message="9Router chua co provider account nao."/>}<TablePagination page={pagination.page} pageSize={pagination.pageSize} totalItems={pagination.totalItems} totalPages={pagination.totalPages} onPageChange={pagination.setPage} onPageSizeChange={pagination.changePageSize}/></article>
    {adding&&<div className="modal-layer" onClick={()=>setAdding(false)}><form className="modal" onSubmit={submit} onClick={(e)=>e.stopPropagation()}><p className="eyebrow">MAP TO 9ROUTER</p><h2>Them tai khoan API key</h2><label>Provider<select value={form.provider} onChange={(e)=>{const option=options.find(item=>item.id===e.target.value);setForm({...form,provider:e.target.value,name:form.name||option?.name||''});}} required><option value="">Chon provider tu 9Router</option>{options.filter(item=>item.authModes.includes('apikey')).map(item=><option key={item.id} value={item.id}>{item.name} ({item.id})</option>)}</select></label><label>Ten hien thi<input value={form.name} onChange={(e)=>setForm({...form,name:e.target.value})} required/></label><label>{selected?.authHint||'API key'}<input type="password" autoComplete="off" value={form.apiKey} onChange={(e)=>setForm({...form,apiKey:e.target.value})} required/><small>Credential duoc gui va luu tai 9Router, khong luu trong database Nexora.</small></label><label>Uu tien<input type="number" min="1" max="999" value={form.priority} onChange={(e)=>setForm({...form,priority:Number(e.target.value)})}/></label>{create.isError&&<p className="form-error">{apiError(create.error)}</p>}<div className="modal-actions"><button type="button" className="button ghost" onClick={()=>setAdding(false)}>Huy</button><button className="button primary" disabled={create.isPending||!form.provider}>{create.isPending?'Dang map vao 9Router...':'Them vao 9Router'}</button></div></form></div>}
    {addingOauth&&<div className="modal-layer" onClick={()=>setAddingOauth(false)}><form className="modal" onSubmit={(e)=>{e.preventDefault();openOauth.mutate();}} onClick={(e)=>e.stopPropagation()}><p className="eyebrow">NEXORA OAUTH</p><h2>Ket noi tai khoan OAuth</h2><label>Provider<select value={oauthProvider} onChange={(e)=>setOauthProvider(e.target.value)} required><option value="">Chon OAuth provider</option>{options.filter(item=>item.authModes.includes('oauth')).map(item=><option key={item.id} value={item.id}>{item.name} ({item.id})</option>)}</select></label><p>Trinh quan ly ket noi se mo ngay trong giao dien Nexora. Chi trang dang nhap chinh thuc cua provider duoc mo rieng.</p>{openOauth.isError&&<p className="form-error">{apiError(openOauth.error)}</p>}<div className="modal-actions"><button type="button" className="button ghost" onClick={()=>setAddingOauth(false)}>Huy</button><button className="button primary" disabled={!oauthProvider||openOauth.isPending}>{openOauth.isPending?'Dang khoi tao...':'Mo trinh ket noi'}</button></div></form></div>}
    {wizardUrl&&<div className="provider-wizard-layer"><div className="provider-wizard-shell"><div className="provider-wizard-head"><div><p className="eyebrow">NEXORA / OAUTH MANAGER</p><h3>Quan ly ket noi provider</h3></div><button className="button ghost" onClick={()=>{setWizardUrl('');refresh();}}>Dong va cap nhat</button></div><iframe ref={wizardFrame} src={wizardUrl} title="Nexora OAuth provider manager" onLoad={handleWizardLoad} /></div></div>}
  </div>;
}
