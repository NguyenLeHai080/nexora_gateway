import { Inbox } from 'lucide-react';

export function TableEmpty({ message = 'Khong co du lieu phu hop.' }: { message?: string }) {
  return <div className="table-empty"><span><Inbox/></span><b>Chua co du lieu</b><p>{message}</p></div>;
}
