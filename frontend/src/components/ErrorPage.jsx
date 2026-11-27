import React from 'react';
import { usePreferences } from '../PreferencesContext.jsx';

const ERROR_COPY = {
  403: {
    icon: 'lock',
    viTitle: 'Không có quyền truy cập',
    enTitle: 'Access denied',
    viDesc: 'Bạn không có quyền xem nội dung này.',
    enDesc: 'You do not have permission to view this page.',
  },
  404: {
    icon: 'explore_off',
    viTitle: 'Trang không tồn tại',
    enTitle: 'Page not found',
    viDesc: 'Liên kết bạn truy cập không tồn tại hoặc đã bị gỡ bỏ.',
    enDesc: 'The page you requested does not exist or has been moved.',
  },
  500: {
    icon: 'error_outline',
    viTitle: 'Hệ thống gặp sự cố',
    enTitle: 'Something went wrong',
    viDesc: 'Đã xảy ra lỗi không mong muốn. Vui lòng thử tải lại trang.',
    enDesc: 'An unexpected error occurred. Please try reloading the page.',
  },
  503: {
    icon: 'cloud_off',
    viTitle: 'Dịch vụ tạm thời không khả dụng',
    enTitle: 'Service temporarily unavailable',
    viDesc: 'Không kết nối được máy chủ lúc này. Vui lòng thử lại sau.',
    enDesc: 'Unable to reach the server right now. Please try again shortly.',
  },
};

export default function ErrorPage({ status = 404, onRetry = null }) {
  const { language } = usePreferences();
  const isEn = language === 'en';
  const code = ERROR_COPY[status] ? status : 404;
  const copy = ERROR_COPY[code];

  return (
    <main className="am-error-page" role="alert" aria-labelledby="am-error-title" data-error-status={code}>
      <section className="am-error-card">
        <div className="am-error-badge" aria-hidden="true">
          <span className="material-symbols-outlined">{copy.icon}</span>
        </div>
        <p className="am-error-code">{code}</p>
        <h1 id="am-error-title" className="am-error-title">
          {isEn ? copy.enTitle : copy.viTitle}
        </h1>
        <p className="am-error-desc">
          {isEn ? copy.enDesc : copy.viDesc}
        </p>
        <div className="am-error-actions">
          {typeof onRetry === 'function' && (
            <button type="button" className="am-error-btn am-error-btn--secondary" onClick={onRetry}>
              <span className="material-symbols-outlined" aria-hidden="true">refresh</span>
              <span>{isEn ? 'Try again' : 'Thử lại'}</span>
            </button>
          )}
          <a href="/" className="am-error-btn am-error-btn--primary">
            <span className="material-symbols-outlined" aria-hidden="true">home</span>
            <span>{isEn ? 'Back to Home' : 'Về Trang chủ'}</span>
          </a>
        </div>
      </section>
    </main>
  );
}
