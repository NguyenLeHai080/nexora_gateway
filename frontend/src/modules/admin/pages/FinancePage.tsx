import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ArrowDownLeft, ArrowUpRight, Calculator, History, Landmark, LayoutDashboard, Server, TrendingUp, WalletCards } from 'lucide-react';
import { apiClient } from '../../../core/api/client';
import type { Model } from '../../../core/types';
import { PageHeader } from '../../../shared/components/PageHeader';
import { Badge } from '../../../shared/components/Badge';
import { formatVnd } from '../../../shared/utils/format';
import { usePagination } from '../../../shared/hooks/usePagination';
import { TablePagination } from '../../../shared/components/TablePagination';
import { TableEmpty } from '../../../shared/components/TableEmpty';

interface Finance { revenue: number; deposits?: number; usageRevenue?: number; gatewayCost: number; profit: number; pending: number; costMethod?: string; tokenxReserved?: number; ownerAmount?: number; reservePercent?: number }
interface AdminTransaction { id:number;userName:string;userEmail:string;type:'credit'|'debit';amount:number;description:string;createdAt:string }
type Json=Record<string,unknown>;
function remoteRows(value:unknown):Json[]{if(Array.isArray(value))return value as Json[];if(value&&typeof value==='object')for(const key of ['data','items','transactions','results']){const row=(value as Json)[key];if(Array.isArray(row))return row as Json[];}return[];}
function remoteNumber(value:unknown,names:string[]):number{if(!value||typeof value!=='object')return 0;for(const [key,item] of Object.entries(value as Json))if(names.includes(key.toLowerCase())&&Number.isFinite(Number(item)))return Number(item);for(const item of Object.values(value as Json)){const found=remoteNumber(item,names);if(found)return found;}return 0;}
const remoteValue=(row:Json,...keys:string[])=>keys.map(key=>row[key]).find(value=>value!==undefined&&value!==null);

export function FinancePage() {
  const [section,setSection]=useState<'overview'|'simulator'|'history'>('overview');
  const { data } = useQuery({ queryKey: ['finance'], queryFn: async () => (await apiClient.get<Finance>('/admin/finance')).data });
  const {data:transactions=[]}=useQuery({queryKey:['admin-transactions'],queryFn:async()=>(await apiClient.get<AdminTransaction[]>('/admin/transactions')).data});
  const {data:models=[]}=useQuery({queryKey:['admin-models'],queryFn:async()=>(await apiClient.get<Model[]>('/admin/router/models')).data});
  const {data:tokenx}=useQuery({queryKey:['tokenx-finance'],queryFn:async()=>(await apiClient.get<Json>('/admin/tokenx/overview')).data,refetchInterval:30000});
  const {data:tokenxFunding}=useQuery({queryKey:['tokenx-funding'],queryFn:async()=>(await apiClient.get<Json>('/admin/tokenx/funding')).data,refetchInterval:30000});
  const {data:tokenxTransactions}=useQuery({queryKey:['tokenx-transactions'],queryFn:async()=>(await apiClient.get('/admin/tokenx/transactions')).data,refetchInterval:30000});
  const [mode,setMode]=useState<'subscription'|'api'>('subscription');
  const [modelId,setModelId]=useState('gpt-5.5');
  const [capital,setCapital]=useState(50000);
  const [billingPeriod,setBillingPeriod]=useState<'monthly'|'annual'>('monthly');
  const [accountCount,setAccountCount]=useState(1);
  const [inputMillions,setInputMillions]=useState(10);
  const [outputMillions,setOutputMillions]=useState(3);
  const [apiInputCost,setApiInputCost]=useState(700);
  const [apiOutputCost,setApiOutputCost]=useState(900);
  const selected=models.find(item=>item.id===modelId)||models[0];
  const projection=useMemo(()=>{
    const revenue=inputMillions*(selected?.inputPrice||0)+outputMillions*(selected?.outputPrice||0);
    const monthlyCapital=billingPeriod==='annual'?capital/12:capital;
    const cost=mode==='subscription'?monthlyCapital*accountCount:inputMillions*apiInputCost+outputMillions*apiOutputCost;
    const profit=revenue-cost;
    const margin=revenue>0?profit/revenue*100:0;
    const weightedRevenue=inputMillions*(selected?.inputPrice||0)+outputMillions*(selected?.outputPrice||0);
    const totalMillions=inputMillions+outputMillions;
    const averageSell=totalMillions>0?weightedRevenue/totalMillions:0;
    const breakEven=mode==='subscription'&&averageSell>0?cost/averageSell:0;
    return {revenue,cost,profit,margin,breakEven};
  },[mode,capital,billingPeriod,accountCount,inputMillions,outputMillions,apiInputCost,apiOutputCost,selected]);
  const pagination=usePagination(transactions,10);

  return <div className="page">
    <PageHeader eyebrow="SUPER ADMIN / FINANCE" title="Dòng tiền & lợi nhuận" description="Tách riêng số liệu thực tế, mô phỏng giá và lịch sử để dễ kiểm soát."/>
    <div className="finance-tabs"><button className={section==='overview'?'active':''} onClick={()=>setSection('overview')}><LayoutDashboard/> Tổng quan thực tế</button><button className={section==='simulator'?'active':''} onClick={()=>setSection('simulator')}><Calculator/> Mô phỏng giá</button><button className={section==='history'?'active':''} onClick={()=>setSection('history')}><History/> Lịch sử giao dịch</button></div>
    {section==='overview'&&<>
    <section className="metric-grid finance-grid"><FinanceMetric icon={<ArrowDownLeft/>} label="Tiền khách đã nạp" value={formatVnd(data?.deposits ?? data?.revenue ?? 0)}/><FinanceMetric icon={<ArrowUpRight/>} label="Doanh thu sử dụng" value={formatVnd(data?.usageRevenue ?? 0)}/><FinanceMetric icon={<Landmark/>} label="Lãi gộp ước tính" value={formatVnd(data?.profit ?? 0)}/><FinanceMetric icon={<WalletCards/>} label="Số dư TokenX" value={formatVnd(remoteNumber(tokenx?.wallet,['balance','available_balance','wallet_balance']))}/><FinanceMetric icon={<Server/>} label="Chi phí TokenX" value={formatVnd(Number((tokenx?.reconciliation as Json)?.upstreamCost??0))}/><FinanceMetric icon={<TrendingUp/>} label="Lãi gộp TokenX" value={formatVnd(Number((tokenx?.reconciliation as Json)?.grossMargin??0))}/></section>
    <section className="finance-summary-grid"><article className="card"><p className="eyebrow">NEXORA LEDGER</p><h3>Hiệu quả bán token</h3><dl><div><dt>Doanh thu đã sử dụng</dt><dd>{formatVnd(data?.usageRevenue??0)}</dd></div><div><dt>Giá vốn gateway ước tính</dt><dd>{formatVnd(data?.gatewayCost??0)}</dd></div><div><dt>Lãi gộp ước tính</dt><dd className={(data?.profit??0)>=0?'positive':'negative'}>{formatVnd(data?.profit??0)}</dd></div></dl><p className="finance-method-note">Giá vốn gateway hiện ước tính bằng 62% doanh thu sử dụng; không lấy tiền nạp làm lợi nhuận.</p></article><article className="card tokenx-funding-card"><p className="eyebrow">TOKENX FUNDING QR</p><h3>Lệnh nạp TokenX đang chờ</h3><strong>{formatVnd(Number(tokenxFunding?.pendingAmount??0))}</strong>{tokenxFunding?.configured&&Number(tokenxFunding?.pendingAmount??0)>0?<><img src={String(tokenxFunding.qrUrl)} alt="QR nạp tiền TokenX"/><code>{String(tokenxFunding.paymentContent??'')}</code><small>Quét QR để xác nhận chuyển khoản. SePay sẽ đối soát giao dịch tiền ra.</small></>:<p>QR TokenX đã lưu. Khi có tiền dự phòng, hệ thống tự tạo QR đúng số tiền.</p>}</article><article className="card"><p className="eyebrow">DEPOSIT ALLOCATION</p><h3>Phân bổ tiền nạp tự động</h3><dl><div><dt>Dự phòng nạp TokenX ({data?.reservePercent??62}%)</dt><dd>{formatVnd(data?.tokenxReserved??0)}</dd></div><div><dt>Phần thuộc Nexora</dt><dd>{formatVnd(data?.ownerAmount??0)}</dd></div><div><dt>Trạng thái chuyển tiền</dt><dd>Chờ xác nhận ngân hàng</dd></div></dl><p className="finance-method-note">Hệ thống tự tạo lệnh và QR; ngân hàng vẫn yêu cầu xác nhận để trừ tiền.</p></article><article className="card"><p className="eyebrow">TOKENX UPSTREAM</p><h3>Nguồn cung API</h3><dl><div><dt>Số dư khả dụng</dt><dd>{formatVnd(remoteNumber(tokenx?.wallet,['balance','available_balance','wallet_balance']))}</dd></div><div><dt>Chi phí đối soát</dt><dd>{formatVnd(Number((tokenx?.reconciliation as Json)?.upstreamCost??0))}</dd></div><div><dt>Lãi gộp nguồn</dt><dd className={Number((tokenx?.reconciliation as Json)?.grossMargin??0)>=0?'positive':'negative'}>{formatVnd(Number((tokenx?.reconciliation as Json)?.grossMargin??0))}</dd></div></dl></article></section>
    </>}

    {section==='simulator'&&<section className="profit-calculator card">
      <div className="profit-calculator-head"><div><p className="eyebrow">PROFIT SIMULATOR</p><h2>Bảng tính vốn và lợi nhuận</h2><p>Tính theo giá bán thật trong Model Catalog.</p></div><span className="router-icon"><Calculator/></span></div>
      <div className="profit-mode"><button className={mode==='subscription'?'active':''} onClick={()=>setMode('subscription')}>GPT Plus / AI Subscription</button><button className={mode==='api'?'active':''} onClick={()=>setMode('api')}>API trả theo usage</button></div>
      <div className="profit-layout">
        <div className="profit-form">
          <label>Model<select value={selected?.id||''} onChange={event=>setModelId(event.target.value)}>{models.filter(item=>item.enabled).map(item=><option key={item.id} value={item.id}>{item.displayName} · {item.id}</option>)}</select></label>
          {mode==='subscription'?<><label>Chu kỳ vốn<select value={billingPeriod} onChange={event=>setBillingPeriod(event.target.value as 'monthly'|'annual')}><option value="monthly">Theo tháng · GPT Plus / Codex</option><option value="annual">Theo năm · ATI / Antigravity</option></select></label><div className="form-columns"><label>Vốn / tài khoản / {billingPeriod==='annual'?'năm':'tháng'}<input type="number" min="0" value={capital} onChange={event=>setCapital(Number(event.target.value))}/></label><label>Số tài khoản provider<input type="number" min="1" value={accountCount} onChange={event=>setAccountCount(Number(event.target.value))}/></label></div></>:<div className="form-columns"><label>Giá vốn API input / 1M<input type="number" min="0" value={apiInputCost} onChange={event=>setApiInputCost(Number(event.target.value))}/></label><label>Giá vốn API output / 1M<input type="number" min="0" value={apiOutputCost} onChange={event=>setApiOutputCost(Number(event.target.value))}/></label></div>}
          <div className="form-columns"><label>Dự kiến input (triệu token)<input type="number" min="0" step="0.1" value={inputMillions} onChange={event=>setInputMillions(Number(event.target.value))}/></label><label>Dự kiến output (triệu token)<input type="number" min="0" step="0.1" value={outputMillions} onChange={event=>setOutputMillions(Number(event.target.value))}/></label></div>
          <div className="selling-price"><span>Giá bán catalog</span><b>Input {formatVnd(selected?.inputPrice||0)} / 1M</b><b>Output {formatVnd(selected?.outputPrice||0)} / 1M</b></div>
        </div>
        <div className="profit-results">
          <div><span>Doanh thu dự kiến</span><strong>{formatVnd(projection.revenue)}</strong></div>
          <div><span>Tổng giá vốn</span><strong>{formatVnd(projection.cost)}</strong></div>
          <div className={projection.profit>=0?'positive':'negative'}><span>Lợi nhuận</span><strong>{formatVnd(projection.profit)}</strong></div>
          <div><span>Biên lợi nhuận</span><strong>{projection.margin.toLocaleString('vi-VN',{maximumFractionDigits:1})}%</strong></div>
          {mode==='subscription'&&<div><span>Điểm hòa vốn</span><strong>{projection.breakEven.toLocaleString('vi-VN',{maximumFractionDigits:2})}M token</strong></div>}
          <p className={projection.profit>=0?'profit-advice good':'profit-advice bad'}><TrendingUp/>{projection.profit>=0?'Kịch bản đang có lời.':'Kịch bản đang lỗ; cần tăng giá hoặc giảm vốn.'}</p>
        </div>
      </div>
    </section>}

    {section==='history'&&<div className="finance-history-stack">
    <article className="card table-card"><div className="table-section-heading"><div><p className="eyebrow">IMMUTABLE LEDGER</p><h3>Lịch sử dòng tiền</h3></div><span>{transactions.length} giao dịch</span></div>{transactions.length?<div className="table-wrap"><table><thead><tr><th>Thời gian</th><th>Tài khoản</th><th>Loại</th><th>Số tiền</th><th>Nội dung</th></tr></thead><tbody>{pagination.paginatedItems.map(tx=><tr key={tx.id}><td>{tx.createdAt}</td><td><b>{tx.userName}</b><small className="block">{tx.userEmail}</small></td><td><Badge tone={tx.type==='credit'?'success':'warning'}>{tx.type.toUpperCase()}</Badge></td><td className={tx.type}>{tx.type==='credit'?'+':'-'}{formatVnd(tx.amount)}</td><td>{tx.description}</td></tr>)}</tbody></table></div>:<TableEmpty/>}<TablePagination page={pagination.page} pageSize={pagination.pageSize} totalItems={pagination.totalItems} totalPages={pagination.totalPages} onPageChange={pagination.setPage} onPageSizeChange={pagination.changePageSize}/></article>
    <article className="card table-card tokenx-ledger"><div className="table-section-heading"><div><p className="eyebrow">TOKENX / UPSTREAM LEDGER</p><h3>Lịch sử ví nguồn TokenX</h3></div><span>{remoteRows(tokenxTransactions).length} giao dịch</span></div>{remoteRows(tokenxTransactions).length?<div className="table-wrap"><table><thead><tr><th>Thời gian</th><th>Mã giao dịch</th><th>Loại</th><th>Số tiền</th><th>Nội dung</th></tr></thead><tbody>{remoteRows(tokenxTransactions).map((tx,index)=><tr key={String(remoteValue(tx,'id','transaction_id')??index)}><td>{String(remoteValue(tx,'created_at','createdAt','timestamp')??'—')}</td><td><code>{String(remoteValue(tx,'id','transaction_id','reference')??'—')}</code></td><td><Badge tone={String(remoteValue(tx,'type','direction')??'debit').includes('credit')?'success':'warning'}>{String(remoteValue(tx,'type','direction')??'USAGE').toUpperCase()}</Badge></td><td>{formatVnd(Number(remoteValue(tx,'amount','value','cost')??0))}</td><td>{String(remoteValue(tx,'description','note','reason')??'TokenX')}</td></tr>)}</tbody></table></div>:<TableEmpty message="TokenX chưa có giao dịch hoặc chưa tải được dữ liệu."/>}</article>
    </div>}
  </div>;
}

function FinanceMetric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) { return <article className="metric-card"><span className="metric-icon">{icon}</span><p>{label}</p><strong>{value}</strong><small>CẬP NHẬT REAL-TIME</small></article>; }
