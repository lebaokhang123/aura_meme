import React, { useState } from 'react';
import { auth } from '../auth.js';
import { useCopy, ErrorMessage } from './account-ui.jsx';

export function EditProfile({ profile, onSaved, onCancel }) {
  const t = useCopy();
  const [name, setName] = useState(profile.display_name || '');
  const [bio, setBio] = useState(profile.bio || '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (busy) return;

    const trimmedName = name.trim();
    if (!trimmedName) {
      setError({
        message: t(
          'Tên hiển thị không được để trống hoặc chỉ có khoảng trắng.',
          'Display name cannot be empty or whitespace only.'
        ),
      });
      return;
    }
    if (trimmedName.length > 50) {
      setError({
        message: t(
          'Tên hiển thị không được vượt quá 50 ký tự.',
          'Display name cannot exceed 50 characters.'
        ),
      });
      return;
    }

    const trimmedBio = bio.trim() || null;
    if (trimmedBio && trimmedBio.length > 300) {
      setError({
        message: t(
          'Tiểu sử không được vượt quá 300 ký tự.',
          'Bio cannot exceed 300 characters.'
        ),
      });
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const response = await auth.write('PATCH', '/users/me', {
        display_name: trimmedName,
        bio: trimmedBio,
      });
      await auth.refresh();
      onSaved({
        display_name: response.display_name,
        bio: response.bio,
      });
    } catch (err) {
      if (err.status === 401) {
        location.replace('/login?next=%2Fprofile');
      } else {
        setError(err);
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="profile-edit" onSubmit={handleSubmit}>
      <div className="profile-field-wrap" style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <label htmlFor="profile-display-name">{t('Tên hiển thị', 'Display name')}</label>
          <span
            className="profile-char-counter"
            aria-hidden="true"
            style={{ fontSize: '11px', color: 'var(--am-on-surface-variant, #94a3b8)', fontFamily: "'JetBrains Mono', monospace" }}
          >
            {name.length}/50
          </span>
        </div>
        <input
          id="profile-display-name"
          autoFocus
          required
          maxLength={50}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </div>

      <div className="profile-field-wrap" style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <label htmlFor="profile-bio">{t('Tiểu sử', 'Bio')}</label>
          <span
            className="profile-char-counter"
            aria-hidden="true"
            style={{ fontSize: '11px', color: 'var(--am-on-surface-variant, #94a3b8)', fontFamily: "'JetBrains Mono', monospace" }}
          >
            {bio.length}/300
          </span>
        </div>
        <textarea
          id="profile-bio"
          maxLength={300}
          rows={5}
          value={bio}
          onChange={(e) => setBio(e.target.value)}
        />
      </div>

      <ErrorMessage error={error} />

      <div className="account-actions">
        <button className="account-button primary" disabled={busy}>
          {busy ? t('Đang lưu...', 'Saving...') : t('Lưu thay đổi', 'Save changes')}
        </button>
        <button
          type="button"
          className="account-button"
          disabled={busy}
          onClick={onCancel}
        >
          {t('Hủy', 'Cancel')}
        </button>
      </div>
    </form>
  );
}
