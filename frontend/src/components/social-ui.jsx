import React from 'react';
import {useLocalized} from '../localize.jsx';
export const icon=(name,size=20)=><span className="material-symbols-outlined leading-none" style={{fontSize:size}} aria-hidden="true">{name}</span>;
export const pillClass='flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-container hover:bg-surface-container-high border border-surface-container-high hover:border-secondary/40 transition-all cursor-pointer active:scale-95';
export function SocialMessage({error}) {
  const render=useLocalized();
  if(!error)return null;
  return render(<div role="alert" className="font-body-sm text-body-sm text-error mt-2">{error==='LOGIN_REQUIRED'?<><a href="/login" className="text-secondary underline">Đăng nhập</a> để tương tác.</>:error==='INVALID_COMMENT'?'Bình luận cần từ 1 đến 2000 ký tự.':error==='NOT_OWNER'?'Bạn chỉ được xóa bình luận của mình.':'Không lưu được thay đổi. Vui lòng thử lại; dữ liệu chưa được cập nhật.'}</div>);
}
