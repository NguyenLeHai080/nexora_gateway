import { FormEvent, useState } from 'react';
import { ArrowRight, Command, ShieldCheck, Sparkles } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export function LoginPage() {
  const [email, setEmail] = useState('admin@nexora.vn');
  const [password, setPassword] = useState('admin123');
  const [error, setError] = useState('');
  const { login, loading } = useAuth();
  const navigate = useNavigate();

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError('');
    try {
      await login(email, password);
      navigate('/dashboard');
    } catch {
      setError('Tai khoan hoac mat khau khong dung.');
    }
  }

  return (
    <main className="login-page">
      <section className="login-story">
        <div className="brand"><span className="brand-mark"><Command /></span><span>NEXORA<small>GATEWAY CONSOLE</small></span></div>
        <div className="story-copy">
          <span className="eyebrow"><Sparkles size={13} /> AI GATEWAY / CONTROL PLANE</span>
          <h1>Mot cong dieu khien.<br />Moi model AI.</h1>
          <p>Phan phoi token, kiem soat chi phi va cap quyen model tu 9Router cho tung khach hang.</p>
          <div className="story-stats"><div><b>99.9%</b><span>Gateway uptime</span></div><div><b>01 API</b><span>All providers</span></div><div><b>Real-time</b><span>Usage ledger</span></div></div>
        </div>
        <span className="login-version">NEXORA / V1.0 / 2026</span>
      </section>
      <section className="login-form-panel">
        <form onSubmit={submit} className="login-form">
          <span className="icon-chip"><ShieldCheck /></span>
          <p className="eyebrow">SECURE ACCESS</p>
          <h2>Dang nhap he thong</h2>
          <p className="muted">Su dung tai khoan do quan tri vien cap.</p>
          <label>Email<input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required /></label>
          <label>Mat khau<input value={password} onChange={(e) => setPassword(e.target.value)} type="password" required /></label>
          {error && <p className="form-error">{error}</p>}
          <button className="button primary wide" disabled={loading}>{loading ? 'Dang xac thuc...' : 'Dang nhap'} <ArrowRight size={17} /></button>
          <div className="demo-accounts"><button type="button" onClick={() => { setEmail('admin@nexora.vn'); setPassword('admin123'); }}>Super Admin</button><button type="button" onClick={() => { setEmail('user@nexora.vn'); setPassword('user123'); }}>Nguoi dung</button></div>
        </form>
      </section>
    </main>
  );
}

