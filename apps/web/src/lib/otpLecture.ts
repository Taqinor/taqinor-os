/**
 * Écran de code de LECTURE (OTP) — logique client PARTAGÉE par /proposition
 * (PREVIEW-V3-FIX, audit C5) et /suivi (ADOC133). Une seule copie : la garde
 * ACAL345 (scripts/check_duplicats_litteraux.py) refuse la recopie.
 *
 * N'agit que sur `#otp-lecture` (la garde `if (!section) return;` est la
 * porte) : sans cet écran, l'appel est sans effet. UN SEUL chemin réseau, le
 * proxy same-origin `/api/proposition-otp`, qui relaie `demander` (sans code)
 * ou `verifier` (avec code) avec le MÊME jeton ShareLink. Une vérification
 * réussie déverrouille la lecture de CE lien côté serveur (une heure) : la
 * même URL est rechargée, rien ne voyage dans l'URL.
 */

/** Ce que la page ouvre une fois le code vérifié (« votre proposition »…). */
export function brancherOtpLecture(ouverture: string): void {
  const section = document.getElementById('otp-lecture');
  if (!section) return;
  const token = section.getAttribute('data-token') || '';
  const form = document.getElementById('otp-lecture-form') as HTMLFormElement | null;
  const demander = document.getElementById('otp-lecture-demander') as HTMLButtonElement | null;
  const valider = document.getElementById('otp-lecture-valider') as HTMLButtonElement | null;
  const champ = document.getElementById('otp-lecture-code') as HTMLInputElement | null;
  const message = document.getElementById('otp-lecture-message');

  function dire(texte: string): void {
    if (message) message.textContent = texte;
  }

  async function appeler(code: string): Promise<{ ok: boolean; detail: string }> {
    try {
      const res = await fetch('/api/proposition-otp', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(code ? { token, mode: 'lecture', code } : { token, mode: 'lecture' }),
      });
      const body = (await res.json().catch(() => ({}))) as { ok?: boolean; detail?: string };
      return {
        ok: res.ok && body.ok !== false,
        detail: typeof body.detail === 'string' ? body.detail : '',
      };
    } catch {
      return { ok: false, detail: 'Service momentanément indisponible. Veuillez réessayer.' };
    }
  }

  demander?.addEventListener('click', async () => {
    demander.disabled = true;
    dire('Envoi du code…');
    const r = await appeler('');
    demander.disabled = false;
    dire(r.ok
      ? 'Code envoyé. Saisissez-le ci-dessous — il est valable 10 minutes.'
      : (r.detail || 'Le code n’a pas pu être envoyé. Réessayez dans un instant.'));
    champ?.focus();
  });

  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const code = (champ?.value || '').trim();
    if (!code) {
      dire('Saisissez le code reçu.');
      champ?.focus();
      return;
    }
    if (valider) valider.disabled = true;
    dire('Vérification…');
    const r = await appeler(code);
    if (r.ok) {
      dire(`Code vérifié — ouverture de ${ouverture}…`);
      window.location.reload();
      return;
    }
    if (valider) valider.disabled = false;
    dire(r.detail || 'Code incorrect. Vérifiez le code reçu et réessayez.');
    champ?.select();
  });
}
