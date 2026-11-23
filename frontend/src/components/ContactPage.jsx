import React, {useState, useSyncExternalStore} from 'react';
import {auth} from '../auth.js';
import {usePreferences} from '../PreferencesContext.jsx';
import {loginUrl} from '../return-url.js';
import {icon} from './social-ui.jsx';
import {GithubIcon} from './SiteShell.jsx';
import '../contact-page.css';

function GoogleGIcon() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" style={{display:'block'}}>
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
    </svg>
  );
}

export function ContactPage() {
  const {language} = usePreferences();
  const t = (vi, en) => language === 'en' ? en : vi;
  const user = useSyncExternalStore(auth.subscribe, auth.snapshot).user;
  const name = user?.display_name || user?.username || '';
  const email = user?.email || '';
  const identityReady = Boolean(name && email);
  const [subject, setSubject] = useState('Góp ý tính năng');
  const [body, setBody] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [sent, setSent] = useState(false);
  const topics = [['Góp ý tính năng', 'Feature suggestion'], ['Báo lỗi kỹ thuật', 'Technical issue'], ['Hợp tác & Bản quyền', 'Partnership & Copyright'], ['Khác', 'Other']];

  async function submit(event) {
    event.preventDefault();
    if (busy || !identityReady) return;
    setBusy(true);
    setError(null);
    setSent(false);
    try {
      await auth.write('POST', '/contact', {name: name.trim(), email: email.trim(), subject, body: body.trim()});
      setSent(true);
      setBody('');
    } catch (error) {
      if (error.status === 401) { location.replace(loginUrl()); return; }
      setError(error);
    } finally {
      setBusy(false);
    }
  }

  const errorText = !error ? '' : error.status === 429
    ? t('Quá nhiều lần thử. Vui lòng thử lại sau.', 'Too many attempts. Please try again later.')
    : error.status === 403
      ? t('Không có quyền hoặc phiên xác thực đã thay đổi. Vui lòng thử lại.', 'Permission denied or authentication changed. Please try again.')
      : error.status === 422
        ? t('Thông tin chưa hợp lệ. Vui lòng kiểm tra các trường.', 'Invalid details. Please check the fields.')
        : t('Không kết nối hoặc lưu được dữ liệu. Vui lòng thử lại.', 'Unable to connect or save. Please try again.');

  return <main className="am-contact">
    <div className="am-contact-inner">
      <header className="am-contact-heading">
        <h1>{t('Liên hệ', 'Contact')} <span>AuraMeme</span></h1>
        <p>{t('Gửi ý kiến đóng góp, báo cáo lỗi kỹ thuật hoặc đề xuất hợp tác sáng tạo.', 'Share feedback, report technical issues or propose a creative partnership.')}</p>
      </header>
      <form className="am-contact-form" onSubmit={submit} aria-busy={busy}>
        <div className="am-contact-fields">
          <div className="am-contact-field">
            <label htmlFor="contact-name">{t('Họ và tên / Nickname', 'Full name / Nickname')} <span className="am-contact-required">*</span></label>
            <div className="am-contact-input am-contact-input--locked">{icon('badge')}<input id="contact-name" name="name" required maxLength={100} value={name} readOnly aria-readonly="true" autoComplete="name" placeholder={t('Ví dụ: KhangDev, KienDev', 'For example: KhangDev, KienDev')}/><span className="material-symbols-outlined am-contact-lock-icon" aria-hidden="true" title={t('Liên kết cố định với tài khoản', 'Locked to your account')}>lock</span></div>
          </div>
          <div className="am-contact-field">
            <label htmlFor="contact-email">{t('Email phản hồi', 'Reply email')} <span className="am-contact-required">*</span></label>
            <div className="am-contact-input am-contact-input--locked">{icon('mail')}<input id="contact-email" name="email" type="email" required maxLength={254} value={email} readOnly aria-readonly="true" autoComplete="email" placeholder="name@example.com"/><span className="material-symbols-outlined am-contact-lock-icon" aria-hidden="true" title={t('Liên kết cố định với tài khoản', 'Locked to your account')}>lock</span></div>
          </div>
        </div>
        <fieldset className="am-contact-topics">
          <legend>{t('Loại yêu cầu / Chủ đề', 'Request type / Subject')} <span className="am-contact-required">*</span></legend>
          <div>{topics.map(([vi, en]) => <button key={vi} type="button" aria-pressed={subject === vi} onClick={() => setSubject(vi)}><span aria-hidden="true"/>{t(vi, en)}</button>)}</div>
        </fieldset>
        <div className="am-contact-field">
          <div className="am-contact-message-label"><label htmlFor="contact-message">{t('Nội dung tin nhắn', 'Message')} <span className="am-contact-required">*</span></label><span id="contact-counter">{body.length} / 4000 {t('ký tự', 'characters')}</span></div>
          <textarea id="contact-message" name="body" rows={5} required maxLength={4000} aria-describedby="contact-counter" value={body} onChange={event => setBody(event.target.value)} placeholder={t('Mô tả ngắn gọn điều bạn muốn gửi gắm tới AuraMeme (ý tưởng meme mới, lỗi font, giao diện, ý tưởng BXH...)...', 'Briefly describe what you would like to share with AuraMeme (new meme ideas, font or interface bugs, leaderboard ideas...)...')}/>
        </div>
        {error && <p className="am-contact-error" role="alert">{errorText}</p>}
        <div className="am-contact-actions">
          <button type="submit" className="am-contact-submit" disabled={busy || !identityReady}><span>{busy ? t('Đang gửi...', 'Sending...') : t('Gửi tin nhắn ngay', 'Send message')}</span>{icon('send')}</button>
          <div className="am-contact-channels">
            <a href="https://github.com/lebaokhang123/aura_meme" target="_blank" rel="noopener noreferrer" aria-label="GitHub AuraMeme" title="GitHub"><GithubIcon/></a>
            <a href="mailto:thothayvtv38@gmail.com" className="am-contact-gmail-link" aria-label="Gmail: thothayvtv38@gmail.com" title="thothayvtv38@gmail.com"><GoogleGIcon/></a>
          </div>
        </div>
        {sent && <div role="status" className="am-contact-success">{icon('task_alt')}<p>{t('Đã gửi tin nhắn tới ban quản trị.', 'Message sent to the administrators.')}</p></div>}
      </form>
    </div>
  </main>;
}
