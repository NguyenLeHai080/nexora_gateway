import { ChevronFirst, ChevronLast, ChevronLeft, ChevronRight } from 'lucide-react';

interface Props {
  page: number;
  pageSize: number;
  totalItems: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
}

export function TablePagination({ page, pageSize, totalItems, totalPages, onPageChange, onPageSizeChange }: Props) {
  const from = totalItems ? (page - 1) * pageSize + 1 : 0;
  const to = Math.min(page * pageSize, totalItems);
  const pages = Array.from({ length: Math.min(5, totalPages) }, (_, index) => {
    const start = Math.min(Math.max(1, page - 2), Math.max(1, totalPages - 4));
    return start + index;
  });

  return <footer className="table-pagination">
    <div className="pagination-summary">Hien thi <b>{from}-{to}</b> trong <b>{totalItems}</b> ket qua</div>
    <div className="pagination-size"><span>So dong</span><select value={pageSize} onChange={(e) => onPageSizeChange(Number(e.target.value))}><option value={10}>10</option><option value={20}>20</option><option value={50}>50</option></select></div>
    <nav className="pagination-controls" aria-label="Phan trang">
      <button disabled={page === 1} onClick={() => onPageChange(1)} title="Trang dau"><ChevronFirst/></button>
      <button disabled={page === 1} onClick={() => onPageChange(page - 1)} title="Trang truoc"><ChevronLeft/></button>
      {pages.map((number) => <button key={number} className={number === page ? 'active' : ''} onClick={() => onPageChange(number)}>{number}</button>)}
      <button disabled={page === totalPages} onClick={() => onPageChange(page + 1)} title="Trang sau"><ChevronRight/></button>
      <button disabled={page === totalPages} onClick={() => onPageChange(totalPages)} title="Trang cuoi"><ChevronLast/></button>
    </nav>
  </footer>;
}

