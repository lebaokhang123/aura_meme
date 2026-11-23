import React, {useState, useSyncExternalStore} from 'react';
import {auth} from '../auth.js';
import {usePreferences} from '../PreferencesContext.jsx';
import {loginUrl} from '../return-url.js';
import {icon} from './social-ui.jsx';
import {GithubIcon} from './SiteShell.jsx';
import '../contact-page.css';

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
        <p className="am-contact-acknowledgment">{t('Tin nhắn được lưu riêng, gửi tới ban quản trị và một email xác nhận tiếp nhận tự động sẽ được gửi về địa chỉ email tài khoản của bạn.', 'Messages are stored privately, sent to administrators, and an automatic confirmation email will be sent to your account email address.')}</p>
        {error && <p className="am-contact-error" role="alert">{errorText}</p>}
        <div className="am-contact-actions">
          <button type="submit" className="am-contact-submit" disabled={busy || !identityReady}><span>{busy ? t('Đang gửi...', 'Sending...') : t('Gửi tin nhắn ngay', 'Send message')}</span>{icon('send')}</button>
          <div className="am-contact-channels"><a href="https://github.com/lebaokhang123/aura_meme" target="_blank" rel="noopener noreferrer" aria-label="GitHub AuraMeme" title="GitHub"><GithubIcon/></a></div>
        </div>
        {sent && <div role="status" className="am-contact-success">{icon('task_alt')}<p>{t('Đã gửi tin nhắn tới ban quản trị.', 'Message sent to the administrators.')}</p></div>}
      </form>
    </div>
  </main>;
}
