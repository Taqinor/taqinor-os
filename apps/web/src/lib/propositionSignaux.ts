/**
 * ADEV98 (L3 lien public, 24/10/2026) — deux signaux clients FIABLES de la proposition.
 *
 * 1. « Lu pour de vrai » : le rendu serveur de la page (que les scanners de liens des
 *    messageries d'entreprise — SafeLinks, Proofpoint, Mimecast… — déclenchent autant qu'un
 *    humain) n'est plus qu'un APERÇU côté ERP. La lecture humaine est la balise
 *    `POST /api/proposition-vu`, émise une fois par chargement après 3 s de visibilité
 *    cumulée (jamais depuis un aperçu interne).
 * 2. « Décliner / demander un délai » : un motif fermé (prix, délai, concurrent, projet
 *    reporté, autre + texte) posté à `/api/proposition-decliner` ; l'ERP le consigne au
 *    chatter du devis et du lead et prévient le conseiller — aucun statut ne change.
 */
type Langue = 'fr' | 'en' | 'ar';

/** URL backend de la balise de lecture (proxy serveur uniquement). */
export function vuEndpoint(apiBase: string, token: string): string {
  const base = (apiBase || 'https://api.taqinor.ma').replace(/\/+$/, '');
  return `${base}/api/django/ventes/proposal/${encodeURIComponent(token)}/vu/`;
}

/** URL backend du déclin (proxy serveur uniquement). */
export function declinerEndpoint(apiBase: string, token: string): string {
  const base = (apiBase || 'https://api.taqinor.ma').replace(/\/+$/, '');
  return `${base}/api/django/ventes/proposal/${encodeURIComponent(token)}/decliner/`;
}

/** Délai de visibilité cumulée avant de compter une lecture humaine. */
export const DELAI_LECTURE_MS = 3000;

/** Les motifs fermés du déclin (mêmes clés que `domain/declin_client.MOTIFS_DECLIN`). */
export const MOTIFS_DECLIN = ['prix', 'delai', 'concurrent', 'projet_reporte', 'autre'] as const;
export type MotifDeclin = (typeof MOTIFS_DECLIN)[number];

/** Corps relayé au backend, ou `null` si invalide (motif inconnu, « autre » sans texte). */
export function corpsDeclin(motif: unknown, texte: unknown): { motif: MotifDeclin; texte: string } | null {
  const m = typeof motif === 'string' ? (motif.trim() as MotifDeclin) : null;
  const t = typeof texte === 'string' ? texte.trim().slice(0, 2000) : '';
  if (!m || !MOTIFS_DECLIN.includes(m)) return null;
  if (m === 'autre' && !t) return null;
  return { motif: m, texte: t };
}

/** Balise « lu » : une fois par chargement, après `DELAI_LECTURE_MS` de visibilité cumulée. */
export function installerBaliseVu(token: string, apercuInterne: boolean): void {
  if (!token || apercuInterne) return;
  let cumule = 0;
  let depuis = document.visibilityState === 'visible' ? Date.now() : 0;
  let envoye = false;
  const verifier = (): void => {
    if (envoye) return;
    const total = cumule + (depuis ? Date.now() - depuis : 0);
    if (total < DELAI_LECTURE_MS) return;
    envoye = true;
    fetch('/api/proposition-vu', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      keepalive: true,
      body: JSON.stringify({ token }),
    }).catch(() => undefined);
  };
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      depuis = Date.now();
    } else if (depuis) {
      cumule += Date.now() - depuis;
      depuis = 0;
    }
    verifier();
  });
  const minuteur = window.setInterval(() => {
    verifier();
    if (envoye) window.clearInterval(minuteur);
  }, 500);
}

const MSG_DECLIN: Record<'merci' | 'invalide' | 'erreur', Record<Langue, string>> = {
  merci: {
    fr: 'Merci, votre réponse a bien été transmise à votre conseiller.',
    en: 'Thank you, your answer has been passed on to your advisor.',
    ar: 'شكراً، تم إرسال ردكم إلى مستشاركم.',
  },
  invalide: {
    fr: 'Choisissez un motif (précisez « Autre »).',
    en: 'Choose a reason (please specify “Other”).',
    ar: 'اختاروا سبباً (يرجى توضيح «أخرى»).',
  },
  erreur: {
    fr: 'Service momentanément indisponible. Veuillez réessayer.',
    en: 'Service temporarily unavailable. Please try again.',
    ar: 'الخدمة غير متاحة مؤقتاً. يرجى إعادة المحاولة.',
  },
};

/** Formulaire « Décliner / demander un délai » (`#declin-form`). */
export function installerDeclin(token: string, langue: () => Langue): void {
  const form = document.getElementById('declin-form') as HTMLFormElement | null;
  const statut = document.getElementById('declin-status');
  if (!form || !token) return;
  const dire = (texte: string): void => {
    if (!statut) return;
    statut.textContent = texte;
    statut.hidden = false;
  };
  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const motif = (form.querySelector('input[name="motif"]:checked') as HTMLInputElement | null)?.value;
    const texte = (document.getElementById('declin-texte') as HTMLTextAreaElement | null)?.value ?? '';
    const corps = corpsDeclin(motif, texte);
    if (!corps) {
      dire(MSG_DECLIN.invalide[langue()]);
      return;
    }
    try {
      const res = await fetch('/api/proposition-decliner', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ token, ...corps }),
      });
      dire(res.ok ? MSG_DECLIN.merci[langue()] : MSG_DECLIN.erreur[langue()]);
      if (res.ok) (form.querySelector('button[type="submit"]') as HTMLButtonElement | null)?.setAttribute('disabled', '');
    } catch {
      dire(MSG_DECLIN.erreur[langue()]);
    }
  });
}
