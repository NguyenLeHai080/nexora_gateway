import { useEffect, useMemo, useState } from 'react';

export function usePagination<T>(items: T[], initialPageSize = 10) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(initialPageSize);
  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const paginatedItems = useMemo(
    () => items.slice((page - 1) * pageSize, page * pageSize),
    [items, page, pageSize],
  );

  function changePageSize(size: number) {
    setPageSize(size);
    setPage(1);
  }

  return { page, pageSize, totalPages, totalItems: items.length, paginatedItems, setPage, changePageSize };
}

