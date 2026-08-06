import type { LucideIcon } from 'lucide-react';
import { Activity, Boxes, CircleDollarSign, Gauge, KeyRound, Landmark, Network, Route, ScrollText, Settings, ShieldCheck, TerminalSquare, UserRound, UsersRound, WalletCards } from 'lucide-react';
import type { Role } from '../types';

export interface NavigationItem {
  label: string;
  path: string;
  icon: LucideIcon;
  roles: Role[];
  guide: { title: string; description: string; steps: string[] };
}

export const navigation: NavigationItem[] = [
  { label: 'API key khách hàng', path: '/admin/user-api-keys', icon: KeyRound, roles: ['super_admin'], guide:{title:'API key theo tài khoản',description:'Quản lý khóa truy cập và quota riêng của từng khách hàng.',steps:['Chọn đúng tài khoản khách hàng.','Tạo hoặc điều chỉnh quota cho API key.','Khóa hoặc xóa key khi không còn sử dụng.']} },
  { label: 'Cài đặt tool', path: '/tool-setup', icon: TerminalSquare, roles: ['user'], guide:{title:'Cài đặt công cụ',description:'Sinh lệnh cấu hình Claude Code hoặc Codex CLI qua Nexora Gateway.',steps:['Chọn công cụ và hệ điều hành.','Chọn API key hoạt động rồi dán secret.','Tạo, sao chép và chạy lệnh trong terminal.']} },
  { label: 'Tong quan', path: '/dashboard', icon: Gauge, roles: ['user', 'super_admin'], guide:{title:'Tổng quan',description:'Theo dõi nhanh tình trạng vận hành và mức sử dụng.',steps:['Xem các chỉ số tổng hợp.','Dùng biểu đồ để nhận biết tải tăng.','Mở menu chi tiết để kiểm tra nguyên nhân.']} },
  { label: 'Vi & giao dich', path: '/wallet', icon: WalletCards, roles: ['user', 'super_admin'], guide:{title:'Ví & giao dịch',description:'Kiểm tra số dư và lịch sử cộng/trừ tiền.',steps:['Kiểm tra số dư hiện tại.','Đối chiếu từng giao dịch.','Báo quản trị khi có bất thường.']} },
  { label: 'API Keys', path: '/api-keys', icon: KeyRound, roles: ['user', 'super_admin'], guide:{title:'API Keys',description:'Tạo và thu hồi khóa gọi Nexora Gateway.',steps:['Tạo và sao chép khóa mới.','Gửi khóa bằng Authorization: Bearer.','Thu hồi khóa không còn dùng.']} },
  { label: 'Model duoc cap', path: '/models', icon: Boxes, roles: ['user'], guide:{title:'Model được cấp',description:'Danh sách model tài khoản được phép gọi.',steps:['Chọn đúng model ID.','Kiểm tra giá input và output.','Liên hệ quản trị nếu thiếu quyền.']} },
  { label: 'Nhat ky su dung', path: '/logs', icon: ScrollText, roles: ['user', 'super_admin'], guide:{title:'Nhật ký sử dụng',description:'Tra cứu request, token, chi phí và trạng thái.',steps:['Lọc theo thời gian.','Mở request lỗi để xem phản hồi.','Dùng số token để kiểm soát chi phí.']} },
  { label: 'Tai khoan', path: '/admin/users', icon: UsersRound, roles: ['super_admin'], guide:{title:'Tài khoản',description:'Quản lý khách hàng, hạn mức và quyền model.',steps:['Tạo hoặc sửa khách hàng.','Cấp đúng model.','Thiết lập hạn mức token.']} },
  { label: 'Dong tien', path: '/admin/finance', icon: CircleDollarSign, roles: ['super_admin'], guide:{title:'Dòng tiền',description:'Quản lý nạp tiền, số dư và doanh thu.',steps:['Chọn đúng tài khoản.','Nhập số tiền và nội dung.','Đối chiếu lịch sử sau khi lưu.']} },
  { label: 'Ngân hàng & QR', path: '/admin/banks', icon: Landmark, roles: ['super_admin'], guide:{title:'Ngân hàng & QR',description:'Thêm tài khoản nhận tiền và đặt tỷ lệ quy đổi token.',steps:['Thêm thông tin tài khoản ngân hàng.','Đặt giá tham chiếu cho 1M token.','Kết nối webhook SePay để tự động đối soát.']} },
  { label: 'Providers', path: '/admin/providers', icon: Network, roles: ['super_admin'], guide:{title:'Providers',description:'Quản lý API key và OAuth đang lưu tại 9Router.',steps:['Thêm API key hoặc kết nối OAuth.','Bấm Test để xác minh.','Tắt credential lỗi trước khi xử lý.']} },
  { label: 'Routing Pools', path: '/admin/routing-pools', icon: Route, roles: ['super_admin'], guide:{title:'Routing Pools',description:'Chống nhiều user dồn vào cùng model/provider.',steps:['Tạo một pool cho mỗi model.','Đặt giới hạn tổng và mỗi user.','Chọn tài khoản và thời gian cooldown.']} },
  { label: '9Router & Models', path: '/admin/router', icon: Activity, roles: ['super_admin'], guide:{title:'9Router & Models',description:'Đồng bộ model và cấu hình giá bán.',steps:['Kiểm tra kết nối 9Router.','Đồng bộ model.','Cập nhật giá và trạng thái.']} },
  { label: 'Audit quan tri', path: '/admin/audit', icon: ShieldCheck, roles: ['super_admin'], guide:{title:'Audit quản trị',description:'Theo dõi thay đổi do quản trị viên thực hiện.',steps:['Tìm theo tài khoản hoặc đối tượng.','Đối chiếu thời gian.','Dùng nhật ký để điều tra sự cố.']} },
  { label: 'Ho so', path: '/profile', icon: UserRound, roles: ['user', 'super_admin'], guide:{title:'Hồ sơ',description:'Xem thông tin nhận diện và vai trò hiện tại.',steps:['Kiểm tra email và vai trò.','Cập nhật thông tin được phép.','Bảo vệ thông tin đăng nhập.']} },
  { label: 'Cai dat', path: '/settings', icon: Settings, roles: ['user', 'super_admin'], guide:{title:'Cài đặt',description:'Thay đổi thiết lập cá nhân và bảo mật.',steps:['Cập nhật mật khẩu định kỳ.','Kiểm tra trước khi lưu.','Đăng nhập lại nếu phiên được làm mới.']} },
];
