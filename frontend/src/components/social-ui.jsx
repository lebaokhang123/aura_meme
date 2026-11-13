import React from 'react';
import {useLocalized} from '../localize.jsx';
export const icon=(name,size=20)=><span className="material-symbols-outlined leading-none" style={{fontSize:size}} aria-hidden="true">{name}</span>;
export const pillClass='flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-container hover:bg-surface-container-high border border-surface-container-high hover:border-secondary/40 transition-all cursor-pointer active:scale-95';
export function SocialMessage({error}) {
  const render=useLocalized();
  if(!error)return null;
  const messages={NETWORK_ERROR:'Không kết nối được máy chủ. Vui lòng thử lại.',PROTOCOL_ERROR:'Phản hồi máy chủ không hợp lệ.',FORBIDDEN:'Bạn không có quyền thực hiện thao tác này.',CSRF_INVALID:'Phiên xác thực đã thay đổi. Vui lòng thử lại.',CONFLICT:'Yêu cầu đã thay đổi hoặc bị trùng. Hãy tải lại trước khi gửi.',NOT_FOUND:'Nội dung không còn hiển thị.',RATE_LIMITED:'Quá nhiều lần thử. Vui lòng thử lại sau.',VALIDATION_ERROR:'Thông tin hoặc ảnh chưa hợp lệ. Vui lòng kiểm tra lại.'};
  if(messages[error])return render(<div role="alert" className="font-body-sm text-body-sm text-error mt-2">{messages[error]}</div>);
  return render(<div role="alert" className="font-body-sm text-body-sm text-error mt-2">{(error==='LOGIN_REQUIRED'||error==='UNAUTHORIZED')?<><a href="/login" className="text-secondary underline">Đăng nhập</a> để tương tác.</>:error==='AUTH_DEMO_ONLY'?'Social đang dùng dữ liệu demo, chưa kết nối máy chủ.':error==='INVALID_COMMENT'?'Bình luận cần từ 1 đến 2000 ký tự.':error==='NOT_OWNER'?'Bạn chỉ được xóa bình luận của mình.':'Không lưu được thay đổi. Vui lòng thử lại; dữ liệu chưa được cập nhật.'}</div>);
}
