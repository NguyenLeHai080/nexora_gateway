import { Activity, ArrowDownToLine, ArrowUpFromLine, CircleDollarSign, Cpu, Radio, Wallet } from 'lucide-react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useAuth } from '../../auth/hooks/useAuth';
import { PageHeader } from '../../../shared/components/PageHeader';
import { formatNumber, formatVnd } from '../../../shared/utils/format';
import { useDashboard } from '../hooks/useDashboard';

export function DashboardPage() {
  const { user } = useAuth();
  const { data, isLoading } = useDashboard();
  if (isLoading || !data) return <div className="page loading-page">Dang tong hop du lieu...</div>;
  const admin = user?.role === 'super_admin';
  return <div className="page">
    <PageHeader eyebrow={admin ? 'CONTROL CENTER / LIVE' : 'OVERVIEW / 24H'} title={admin ? 'Trung tam dieu hanh' : `Chao ${user?.name.split(' ').at(-1) ?? ''}`} description={admin ? 'Theo doi dong tien, tai khoan va suc khoe 9Router tren mot man hinh.' : 'So du, token va hoat dong gan nhat cua tai khoan.'} action={<span className="live-pill"><Radio size={13} /> LIVE SYSTEM</span>} />
    <section className="hero-balance"><div><p className="eyebrow">{admin ? 'TONG DOANH THU' : 'SO DU KHA DUNG'}</p><strong>{formatVnd(data.balance)}</strong><span>Cap nhat vua xong</span></div><div className="hero-orb"><Wallet /></div></section>
    <section className="metric-grid">
      <Metric icon={<Activity />} label="Tong request" value={formatNumber(data.requests)} note={`${formatNumber(data.successRequests)} thanh cong`} />
      <Metric icon={<Cpu />} label={admin?'Token da xu ly':'Token con lai'} value={formatNumber(admin?data.inputTokens+data.outputTokens:data.tokenRemaining)} note={admin?`${formatNumber(data.outputTokens)} output`:`Da dung ${formatNumber(data.tokenUsed)} / quota ${formatNumber(data.tokenQuota)}`} />
      <Metric icon={<ArrowDownToLine />} label="Da nap" value={formatVnd(data.deposited)} note="Tong giao dich credit" />
      <Metric icon={<ArrowUpFromLine />} label={data.source === '9router' ? 'Chi phi 9Router' : 'Da chi'} value={data.source === '9router' ? `$${Number(data.spent).toFixed(4)}` : formatVnd(data.spent)} note={data.source === '9router' ? 'Usage & Analytics / 24h' : 'Theo gia model'} />
    </section>
    <section className="chart-grid">
      <article className="card chart-card"><div className="card-heading"><div><p className="eyebrow">{data.source === '9router' ? 'UPSTREAM COST' : 'REQUEST TRAFFIC'}</p><h3>{data.source === '9router' ? 'Chi phi 9Router theo gio' : 'Luot goi thanh cong'}</h3></div><BadgeDot text="24 gio" /></div><ResponsiveContainer width="100%" height={260}><AreaChart data={data.chart}><defs><linearGradient id="success" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#14b8a6" stopOpacity={.35}/><stop offset="100%" stopColor="#14b8a6" stopOpacity={0}/></linearGradient></defs><CartesianGrid strokeDasharray="4 4" vertical={false} stroke="#dce3ed"/><XAxis dataKey="time" axisLine={false} tickLine={false}/><YAxis axisLine={false} tickLine={false}/><Tooltip/><Area type="monotone" dataKey={data.source === '9router' ? 'cost' : 'success'} stroke="#0f9f8f" strokeWidth={3} fill="url(#success)"/></AreaChart></ResponsiveContainer></article>
      <article className="card chart-card"><div className="card-heading"><div><p className="eyebrow">TOKEN FLOW</p><h3>Token theo thoi gian</h3></div><BadgeDot text="real-time" /></div><ResponsiveContainer width="100%" height={260}><AreaChart data={data.chart}><defs><linearGradient id="tokens" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#ff6b35" stopOpacity={.35}/><stop offset="100%" stopColor="#ff6b35" stopOpacity={0}/></linearGradient></defs><CartesianGrid strokeDasharray="4 4" vertical={false} stroke="#dce3ed"/><XAxis dataKey="time" axisLine={false} tickLine={false}/><YAxis axisLine={false} tickLine={false}/><Tooltip/><Area type="monotone" dataKey="tokens" stroke="#ff6b35" strokeWidth={3} fill="url(#tokens)"/></AreaChart></ResponsiveContainer></article>
    </section>
  </div>;
}

function Metric({ icon, label, value, note }: { icon: React.ReactNode; label: string; value: string; note: string }) { return <article className="metric-card"><span className="metric-icon">{icon}</span><p>{label}</p><strong>{value}</strong><small>{note}</small></article>; }
function BadgeDot({ text }: { text: string }) { return <span className="mini-status"><CircleDollarSign size={12}/>{text}</span>; }
