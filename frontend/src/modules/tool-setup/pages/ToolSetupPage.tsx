import { useMutation, useQuery } from '@tanstack/react-query';
import { Check, ChevronRight, Clipboard, Code2, KeyRound, Laptop, TerminalSquare } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiClient } from '../../../core/api/client';
import type { ApiKey, Model } from '../../../core/types';
import { PageHeader } from '../../../shared/components/PageHeader';

type Tool = 'claude' | 'codex';
type OperatingSystem = 'windows' | 'macos' | 'linux';
const money = new Intl.NumberFormat('vi-VN');
const shellQuote = (value: string) => `'${value.replaceAll("'", "'\\''")}'`;
const psQuote = (value: string) => `'${value.replaceAll("'", "''")}'`;

export function ToolSetupPage() {
  const [tool, setTool] = useState<Tool>('claude');
  const [os, setOs] = useState<OperatingSystem>('windows');
  const [secret, setSecret] = useState('');
  const [selectedKeyId, setSelectedKeyId] = useState('');
  const [generated, setGenerated] = useState(false);
  const [copied, setCopied] = useState(false);
  const { data: keys = [], isLoading: loadingKeys } = useQuery({ queryKey: ['api-keys'], queryFn: async () => (await apiClient.get<ApiKey[]>('/api-keys')).data });
  const { data: models = [], isLoading: loadingModels } = useQuery({ queryKey: ['models'], queryFn: async () => (await apiClient.get<Model[]>('/models')).data });
  const activeKeys = keys.filter((key) => key.status === 'active');
  const base = window.location.origin;
  const defaultModel = models[0]?.id ?? 'gpt-5.5';
  const validate = useMutation({
    mutationFn: async () => (await apiClient.post<{ valid: boolean }>('/api-keys/validate', { key_id: Number(selectedKeyId), secret: secret.trim() })).data,
    onSuccess: () => { setGenerated(true); setCopied(false); },
  });
  const command = useMemo(() => {
    const key = secret.trim();
    if (!key) return '';
    if (os === 'windows') {
      return `$env:NEXORA_KEY=${psQuote(key)};$env:NEXORA_TOOL='${tool}';irm '${base}/api/tools/setup.ps1'|iex`;
    }
    return `curl -fsSL '${base}/api/tools/setup.sh' | NEXORA_KEY=${shellQuote(key)} NEXORA_TOOL=${tool} NEXORA_MODEL=${shellQuote(defaultModel)} bash`;
  }, [base, defaultModel, os, secret, tool]);

  async function copyCommand() {
    await navigator.clipboard.writeText(command);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  }

  return <div className="page tool-setup-page">
    <PageHeader eyebrow="GUIDE // TOOL SETUP" title="Cài đặt công cụ" description="Kết nối Claude Code hoặc Codex CLI với Nexora Gateway bằng một lệnh duy nhất." />
    <div className="tool-layout">
      <section className="card setup-card setup-card-compact">
        <div className="setup-card-head"><div><p className="eyebrow">QUICK SETUP</p><h2>Cài đặt trong 1 bước</h2><p>Chọn công cụ và API key, sau đó sao chép lệnh vào terminal.</p></div><span>01 STEP</span></div>
        <div className="setup-fields">
          <div className="setup-two-columns">
            <label>Công cụ<select value={tool} onChange={(event) => { setTool(event.target.value as Tool); setGenerated(false); }}><option value="claude">Claude Code</option><option value="codex">Codex CLI</option></select></label>
            <label>Hệ điều hành<select value={os} onChange={(event) => { setOs(event.target.value as OperatingSystem); setGenerated(false); }}><option value="windows">Windows PowerShell</option><option value="macos">macOS Terminal</option><option value="linux">Linux Terminal</option></select></label>
          </div>
          <label>API key đang hoạt động<select value={selectedKeyId} onChange={(event) => { setSelectedKeyId(event.target.value); setGenerated(false); }} disabled={loadingKeys}><option value="">{loadingKeys ? 'Đang tải API key...' : 'Chọn API key'}</option>{activeKeys.map((key) => <option key={key.id} value={key.id}>{key.name} · {key.prefix}••••••</option>)}</select></label>
          {!loadingKeys && activeKeys.length === 0 && <div className="setup-warning"><KeyRound/><span>Bạn chưa có API key hoạt động.</span><Link to="/api-keys">Tạo API key <ChevronRight/></Link></div>}
          <label>Secret API key<input type="password" value={secret} onChange={(event) => { setSecret(event.target.value); setGenerated(false); }} placeholder="Dán khóa nx-... đã sao chép khi tạo" autoComplete="off"/><small>Secret chỉ dùng để tạo lệnh trên trình duyệt và được xác minh với API key đã chọn.</small></label>
          <button className="button primary generate-command" disabled={!secret.trim() || !selectedKeyId || validate.isPending} onClick={() => validate.mutate()}><TerminalSquare/> {validate.isPending ? 'Đang xác minh...' : 'Tạo lệnh nhanh'}</button>
          {validate.isError && <p className="setup-error">Secret không khớp hoặc API key không còn hoạt động.</p>}
          {generated && command && <div className="command-result command-result-compact">
            <div><div><span className="command-success"><Check/> Sẵn sàng sử dụng</span><h3>Lệnh cài đặt Nexora</h3><p>Lệnh sẽ tự cài CLI, lưu cấu hình gateway và khởi chạy công cụ.</p></div><button className="button primary copy-command" onClick={copyCommand}><Clipboard/> {copied ? 'Đã sao chép' : 'Sao chép'}</button></div>
            <pre><code>{command}</code></pre>
            <div className="endpoint-note"><Code2/><span><b>Kết nối tự động</b><code>{base} · model mặc định: {defaultModel}</code></span></div>
            <p className="command-security">Không chia sẻ lệnh này vì có chứa API key của bạn.</p>
          </div>}
        </div>
      </section>
      <section className="card pricing-card">
        <div className="pricing-title"><div><p className="eyebrow">PRICING</p><h2>Bảng giá model</h2></div><Laptop/></div>
        <p>Giá lấy trực tiếp từ model được cấp cho tài khoản. Input và output được tính riêng trên mỗi 1 triệu token.</p>
        <div className="pricing-head"><span>MODEL</span><span>INPUT</span><span>OUTPUT</span></div>
        <div className="pricing-list">{loadingModels ? <div className="pricing-empty">Đang tải bảng giá...</div> : models.length ? models.map((model) => <article key={model.id}><div><strong>{model.id}</strong><small>{model.provider} · / 1M token</small></div><b>{money.format(model.inputPrice)}đ</b><b>{money.format(model.outputPrice)}đ</b></article>) : <div className="pricing-empty">Tài khoản chưa được cấp model.</div>}</div>
      </section>
    </div>
  </div>;
}
