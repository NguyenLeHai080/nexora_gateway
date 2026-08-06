export const formatVnd = (value: number) => `${new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 6 }).format(value)} đ`;
export const formatNumber = (value: number) => new Intl.NumberFormat('vi-VN').format(value);
