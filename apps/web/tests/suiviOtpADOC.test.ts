// ADOC133 — /suivi : le refus 403 `otp_required` ouvre l'écran de saisie du code
// (proxy /api/proposition-otp, même jeton) au lieu de « Ce suivi n’est pas
// accessible ». Le détail machine vient de l'exemple du contrat (ADOC112).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { etatErreurSuivi, SUIVI_OTP_DETAIL } from '../src/lib/suivi';

const lire = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');
const contrat = JSON.parse(
  lire('../../../backend/django_core/apps/ventes/contract_samples/suivi_public.json'),
) as { exemple_403_otp: { detail: string }; exemple_404: { detail: string } };
const PAGE = lire('../src/pages/suivi/[token].astro');

describe('ADOC133 — etatErreurSuivi', () => {
  it('403 otp_required (exemple du contrat) ⇒ otp', () => {
    expect(SUIVI_OTP_DETAIL).toBe(contrat.exemple_403_otp.detail);
    expect(etatErreurSuivi(403, contrat.exemple_403_otp.detail)).toBe('otp');
  });

  it('404 (exemple du contrat) ⇒ introuvable', () => {
    expect(etatErreurSuivi(404, contrat.exemple_404.detail)).toBe('introuvable');
    expect(etatErreurSuivi(404, '')).toBe('introuvable');
  });

  it('tout le reste ⇒ indisponible (autre 403, 5xx, 429, détail absent)', () => {
    expect(etatErreurSuivi(403, 'autre')).toBe('indisponible');
    expect(etatErreurSuivi(403, null)).toBe('indisponible');
    expect(etatErreurSuivi(500, 'otp_required')).toBe('indisponible');
    expect(etatErreurSuivi(429, undefined)).toBe('indisponible');
  });
});

describe('ADOC133 — la page /suivi', () => {
  it('route le refus par etatErreurSuivi et rend l’écran de code', () => {
    expect(PAGE).toContain('etatErreurSuivi(res.status, detail)');
    expect(PAGE).toContain('id="otp-lecture"');
    expect(PAGE).toContain('Ce suivi est protégé par un code à usage unique');
  });

  it('utilise le proxy existant /api/proposition-otp, mode lecture, même jeton', () => {
    expect(PAGE).toContain("fetch('/api/proposition-otp'");
    expect(PAGE).toContain("mode: 'lecture'");
    expect(PAGE).toContain('window.location.reload()');
  });
});
