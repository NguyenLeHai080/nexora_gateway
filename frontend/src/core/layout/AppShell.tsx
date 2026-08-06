import { useState } from 'react';
import { CircleHelp, LogOut, Menu, PanelLeftClose, Zap } from 'lucide-react';
import { NavLink, Outlet } from 'react-router-dom';
import { navigation, type NavigationItem } from '../config/navigation';
import { useAuth } from '../../modules/auth/hooks/useAuth';

export function AppShell() {
  const [open, setOpen] = useState(false);
  const [helpItem, setHelpItem] = useState<NavigationItem | null>(null);
  const { user, logout } = useAuth();
  const items = navigation.filter((item) => user && item.roles.includes(user.role));

  return (
    <div className="app-shell">
      <button className="mobile-menu" onClick={() => setOpen(true)}><Menu /></button>
      <aside className={`sidebar ${open ? 'open' : ''}`}>
        <div className="sidebar-head"><div className="brand"><span className="brand-mark"><Zap /></span><span>NEXORA<small>GATEWAY</small></span></div><button className="close-menu" onClick={() => setOpen(false)}><PanelLeftClose /></button></div>
        <p className="nav-label">WORKSPACE</p>
        <nav>{items.slice(0, -2).map((item) => { const Icon=item.icon; return <div className="nav-entry" key={item.path}><NavLink to={item.path} onClick={() => setOpen(false)}><Icon />{item.label}</NavLink><button className="nav-help" title={`Hướng dẫn ${item.label}`} onClick={()=>setHelpItem(item)}><CircleHelp/></button></div>; })}</nav>
        <p className="nav-label">ACCOUNT</p>
        <nav>{items.slice(-2).map((item) => { const Icon=item.icon; return <div className="nav-entry" key={item.path}><NavLink to={item.path} onClick={() => setOpen(false)}><Icon />{item.label}</NavLink><button className="nav-help" title={`Hướng dẫn ${item.label}`} onClick={()=>setHelpItem(item)}><CircleHelp/></button></div>; })}</nav>
        <div className="sidebar-user"><span className="avatar">{user?.name.slice(0, 2).toUpperCase()}</span><div><b>{user?.name}</b><small>{user?.role === 'super_admin' ? 'SUPER ADMIN' : 'CLIENT'}</small></div><button onClick={logout} title="Dang xuat"><LogOut /></button></div>
      </aside>
      {open && <div className="backdrop" onClick={() => setOpen(false)} />}
      <section className="workspace"><Outlet /></section>
      {helpItem && <div className="modal-layer" onClick={()=>setHelpItem(null)}><article className="modal guide-modal" onClick={(event)=>event.stopPropagation()}><p className="eyebrow">HƯỚNG DẪN SỬ DỤNG</p><h2>{helpItem.guide.title}</h2><p>{helpItem.guide.description}</p><ol>{helpItem.guide.steps.map((step,index)=><li key={step}><span>{index+1}</span>{step}</li>)}</ol><div className="modal-actions"><button className="button primary" onClick={()=>setHelpItem(null)}>Đã hiểu</button></div></article></div>}
    </div>
  );
}
