export const formatVnd = (value: number) => `${new Intl.NumberFormat('vi-VN').format(value)} d`;
export const formatNumber = (value: number) => new Intl.NumberFormat('vi-VN').format(value);
