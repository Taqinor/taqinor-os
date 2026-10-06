/**
 * CIW405 (D-CIQ-8) — étape « Affiner », FACULTATIVE, APRÈS la porte de contact.
 * Une seule copie pour les trois tunnels FR/EN/AR (ACAL345) ; chaque page garde le
 * garde « commercial / industriel » et l'appel unique après un succès.
 *
 * Le clic appelle le proxy same-origin /api/lead-affiner avec l'idempotencyKey DÉJÀ
 * envoyée (jamais une seconde soumission), puis ouvre /questionnaire/<jeton>. Échec
 * ou 404 : le bouton se retire sans message alarmant.
 */
export function brancherAffiner(btn: HTMLButtonElement | null, idempotencyKey: string): void {
  if (!btn || !idempotencyKey) return;
  btn.hidden = false;
  btn.addEventListener('click', async () => {
    btn.disabled = true;
    try {
      const res = await fetch('/api/lead-affiner', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ key: idempotencyKey }),
        signal: AbortSignal.timeout(6000),
      });
      const data = (await res.json().catch(() => null)) as { ok?: boolean; url?: string } | null;
      if (data?.ok && typeof data.url === 'string' && data.url.startsWith('/questionnaire/')) {
        window.location.href = data.url;
        return;
      }
    } catch {
      // silencieux : repli ci-dessous.
    }
    btn.hidden = true; // échec / 404 : le bouton se retire, sans alarme.
  });
}
