import { FormEvent, useEffect, useState } from 'react';
import { ArrowRight, Command, ShieldCheck, Sparkles, UserPlus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export function LoginPage() {
  const [mode, setMode] = useState<'login'|'register'>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [error, setError] = useState('');
  const { login, register, loading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    const params = new URLSearchParams(window.location.hash.slice(1));
    const token = params.get('oauth_token');
    if (token) { localStorage.setItem('nexora_access_token', token); window.location.replace('/dashboard'); }
    if (params.get('oauth_error')) { setError('Không thể đăng nhập bằng Google. Vui lòng thử lại.'); window.history.replaceState(null, '', '/login'); }
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError('');
    try {
      if (mode === 'register') {
        if (password !== passwordConfirm) { setError('Mật khẩu xác nhận không khớp.'); return; }
        await register(name, email, password);
      } else {
        await login(email, password);
      }
      navigate('/dashboard');
    } catch (requestError: any) {
      if (requestError?.response?.status === 409) setError('Email này đã được đăng ký.');
      else setError(mode === 'login' ? 'Tài khoản hoặc mật khẩu không đúng.' : 'Không thể tạo tài khoản. Vui lòng kiểm tra thông tin.');
    }
  }

  return (
    <main className="login-page">
      <section className="login-story">
        <div className="brand"><span className="brand-mark"><Command /></span><span>NEXORA<small>GATEWAY CONSOLE</small></span></div>
        <div className="story-copy">
          <span className="eyebrow"><Sparkles size={13} /> AI GATEWAY / CONTROL PLANE</span>
          <h1>Một cổng điều khiển.<br />Mọi model AI.</h1>
          <p>Tự đăng ký, nạp tiền và tạo API key để sử dụng AI qua một gateway duy nhất.</p>
          <div className="story-stats"><div><b>99.9%</b><span>Gateway uptime</span></div><div><b>01 API</b><span>All providers</span></div><div><b>Real-time</b><span>Usage ledger</span></div></div>
        </div>
        <span className="login-version">NEXORA / V1.0 / 2026</span>
      </section>
      <section className="login-form-panel">
        <form onSubmit={submit} className="login-form">
          <span className="icon-chip">{mode === 'login' ? <ShieldCheck /> : <UserPlus />}</span>
          <p className="eyebrow">{mode === 'login' ? 'SECURE ACCESS' : 'CREATE ACCOUNT'}</p>
          <h2>{mode === 'login' ? 'Đăng nhập hệ thống' : 'Tạo tài khoản Nexora'}</h2>
          <p className="muted">{mode === 'login' ? 'Tiếp tục quản lý API key và số dư của bạn.' : 'Tài khoản mới luôn được tạo với quyền người dùng.'}</p>
          <div className="auth-tabs"><button type="button" className={mode==='login'?'active':''} onClick={()=>{setMode('login');setError('');}}>Đăng nhập</button><button type="button" className={mode==='register'?'active':''} onClick={()=>{setMode('register');setError('');}}>Đăng ký</button></div>
          {mode === 'register' && <label>Họ và tên<input value={name} onChange={(e) => setName(e.target.value)} minLength={2} required /></label>}
          <label>Email<input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required /></label>
          <label>Mật khẩu<input value={password} onChange={(e) => setPassword(e.target.value)} type="password" minLength={8} required /></label>
          {mode === 'register' && <label>Xác nhận mật khẩu<input value={passwordConfirm} onChange={(e) => setPasswordConfirm(e.target.value)} type="password" minLength={8} required /></label>}
          {error && <p className="form-error">{error}</p>}
          <button className="button primary wide" disabled={loading}>{loading ? 'Đang xử lý...' : mode === 'login' ? 'Đăng nhập' : 'Tạo tài khoản'} <ArrowRight size={17} /></button>
          <div className="oauth-divider"><span>hoặc tiếp tục bằng</span></div>
          <div className="oauth-buttons"><button type="button" onClick={()=>window.location.assign('/api/auth/oauth/google')}><b>G</b> Google</button><button type="button" disabled title="Cần cấu hình Facebook OAuth App"><b>f</b> Facebook</button></div>
        </form>
      </section>
    </main>
  );
}
