export interface PasswordStrength {
  score: 0 | 1 | 2 | 3;
  label: 'None' | 'Weak' | 'Good' | 'Strong';
  color: string;
}

export function formatAuraNumber(num: number, useAbbreviation: boolean = false): string {
  if (useAbbreviation && num >= 1000) {
    if (num >= 1000000) {
      return (num / 1000000).toFixed(1).replace(/\.0$/, '') + 'M';
    }
    return (num / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
  }
  return num.toLocaleString('en-US');
}

/**
 * Password strength validator for registration flow
 */
export function evaluatePasswordStrength(password: string): PasswordStrength {
  if (!password || password.length === 0) {
    return { score: 0, label: 'None', color: 'text-outline' };
  }
  if (password.length < 6) {
    return { score: 1, label: 'Weak', color: 'text-error' };
  }
  if (password.length < 10) {
    return { score: 2, label: 'Good', color: 'text-primary' };
  }
  return { score: 3, label: 'Strong', color: 'text-secondary' };
}
