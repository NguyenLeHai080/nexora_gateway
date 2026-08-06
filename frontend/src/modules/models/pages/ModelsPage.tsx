import { useQuery } from '@tanstack/react-query';
import { Boxes, CheckCircle2 } from 'lucide-react';
import { apiClient } from '../../../core/api/client';
import type { Model } from '../../../core/types';
import { PageHeader } from '../../../shared/components/PageHeader';
import { formatVnd } from '../../../shared/utils/format';

export function ModelsPage() { const { data = [] } = useQuery({ queryKey: ['models'], queryFn: async () => (await apiClient.get<Model[]>('/models')).data }); return <div className="page"><PageHeader eyebrow="CATALOG / ENTITLEMENTS" title="Model duoc cap" description="Cac model tai khoan co the goi qua API key."/><section className="model-grid">{data.map((model) => <article className="card model-card" key={model.id}><span className="model-provider">{model.provider}</span><Boxes/><h3>{model.displayName}</h3><code>{model.id}</code><div><span>Input <b>{formatVnd(model.inputPrice)}</b></span><span>Output <b>{formatVnd(model.outputPrice)}</b></span></div><p><CheckCircle2/> San sang su dung</p></article>)}</section></div>; }

