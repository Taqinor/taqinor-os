/**
 * ADEV97 (L3 lien public, 24/10/2026) — l'EXEMPLAIRE SIGNÉ d'une proposition acceptée
 * (raison sociale, ICE, signature) ne se télécharge qu'avec le code de lecture quand un code
 * peut partir vers le client. La page reste lisible au jeton ; seul le PDF est gardé.
 *
 * Au clic sur un lien « Télécharger » (même `/pdf/` que d'habitude) d'une proposition
 * acceptée, la page demande au serveur (`/api/proposition-otp`, mode `lecture`) : soit
 * `code_requis: false` (lien sans garde, ou déjà déverrouillé dans l'heure — dont le
 * signataire qui vient de signer) et le PDF s'ouvre ; soit un code part par e-mail et le
 * bloc `#pdf-otp-block` le demande. Ouverture dans l'onglet courant (`location.assign`) :
 * jamais une fenêtre bloquée par le navigateur après un appel réseau.
 */
type Langue = 'fr' | 'en' | 'ar';

const MSG: Record<'envoye' | 'incorrect' | 'erreur', Record<Langue, string>> = {
  envoye: {
    fr: 'Pour protéger votre exemplaire signé, un code vous a été envoyé par e-mail. Saisissez-le ci-dessous.',
    en: 'To protect your signed copy, a code has been sent to you by email. Enter it below.',
    ar: 'لحماية نسختكم الموقّعة، أُرسل إليكم رمز عبر البريد الإلكتروني. أدخلوه أدناه.',
  },
  incorrect: {
    fr: 'Code incorrect ou expiré. Vérifiez le code reçu et réessayez.',
    en: 'Incorrect or expired code. Check the code you received and try again.',
    ar: 'الرمز غير صحيح أو منتهي الصلاحية. تحققوا من الرمز وأعيدوا المحاولة.',
  },
  erreur: {
    fr: 'Service momentanément indisponible. Veuillez réessayer.',
    en: 'Service temporarily unavailable. Please try again.',
    ar: 'الخدمة غير متاحة مؤقتاً. يرجى إعادة المحاولة.',
  },
};

export interface ReponseAccesPdf {
  ok: boolean;
  codeRequis: boolean;
  detail: string;
}

/** Lit la réponse du proxy `/api/proposition-otp` (mode lecture) — fonction pure. */
export function lireReponseAccesPdf(status: number, payload: unknown): ReponseAccesPdf {
  const p = (payload ?? {}) as { ok?: unknown; code_requis?: unknown; detail?: unknown };
  return {
    ok: status >= 200 && status < 300 && p.ok !== false,
    codeRequis: p.code_requis !== false,
    detail: typeof p.detail === 'string' ? p.detail : '',
  };
}

async function demanderAcces(token: string, code = ''): Promise<ReponseAccesPdf> {
  try {
    const res = await fetch('/api/proposition-otp', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ token, mode: 'lecture', ...(code ? { code } : {}) }),
    });
    return lireReponseAccesPdf(res.status, await res.json().catch(() => ({})));
  } catch {
    return { ok: false, codeRequis: true, detail: '' };
  }
}

export interface GardePdfSigne {
  token: string;
  /** URL du flux `/pdf/` de la proposition (sans paramètre). */
  pdfUrl: string;
  /** Vrai quand la proposition est acceptée (au chargement OU juste signée ici). */
  estAccepte: () => boolean;
  langue: () => Langue;
}

/** Installe la garde au clic sur tout lien vers le PDF de la proposition. */
export function installerGardePdfSigne(g: GardePdfSigne): void {
  if (!g.pdfUrl) return;
  const bloc = document.getElementById('pdf-otp-block');
  const saisie = document.getElementById('pdf-otp-code') as HTMLInputElement | null;
  const valider = document.getElementById('pdf-otp-valider');
  const statut = document.getElementById('pdf-otp-status');
  let cible = g.pdfUrl;
  const dire = (texte: string): void => {
    if (!statut) return;
    statut.textContent = texte;
    statut.hidden = false;
  };
  document.addEventListener('click', async (ev) => {
    const lien = (ev.target as Element | null)?.closest?.('a[href]') as HTMLAnchorElement | null;
    if (!lien || !g.estAccepte() || !lien.href.startsWith(g.pdfUrl)) return;
    ev.preventDefault();
    cible = lien.href;
    const r = await demanderAcces(g.token);
    if (r.ok && !r.codeRequis) {
      window.location.assign(cible);
      return;
    }
    if (bloc) {
      bloc.hidden = false;
      bloc.scrollIntoView({ block: 'nearest' });
    }
    // CPRW27 — `detail` est un texte FR du serveur : jamais montré dans une autre langue.
    dire(r.ok ? MSG.envoye[g.langue()] : (g.langue() === 'fr' && r.detail) || MSG.erreur[g.langue()]);
    saisie?.focus();
  });
  valider?.addEventListener('click', async () => {
    const code = saisie?.value.trim() ?? '';
    if (!code) return;
    const r = await demanderAcces(g.token, code);
    if (r.ok) {
      if (bloc) bloc.hidden = true;
      window.location.assign(cible);
      return;
    }
    dire(MSG.incorrect[g.langue()]);
  });
}
