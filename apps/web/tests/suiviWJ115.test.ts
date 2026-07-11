// WJ115 — /suivi/<token> post-sign status page (web half of the already-landed
// backend QX34). Deux volets, même convention que le reste de ce dossier :
//  (1) `lib/suivi.ts` est un module PURE (aucun DOM, aucun réseau) testé
//      directement — endpoint URL, garde-fou date ISO, construction de la
//      timeline (done/current/date) à chaque étape du cycle de vie.
//  (2) le fichier `.astro` est vérifié par lecture SOURCE en texte (même
//      convention que propositionFoldWJ114.test.ts / propositionNeverBlankWJ81
//      .test.ts : un montage DOM complet d'un fichier .astro n'est pas
//      praticable ici) — on confirme noindex, prerender=false, les états
//      d'erreur FR+AR et l'affordance de partage WhatsApp.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { buildTimeline, isIsoDateString, suiviEndpoint, type SuiviResponse } from '../src/lib/suivi';

const root = (rel: string) => fileURLToPath(new URL(rel, import.meta.url));
const read = (rel: string) => readFileSync(root(rel), 'utf-8');
const SUIVI_PAGE = read('../src/pages/suivi/[token].astro');

describe('WJ115 — suiviEndpoint', () => {
  it('construit l’URL backend avec la base API par défaut', () => {
    expect(suiviEndpoint('', 'abc123')).toBe('https://api.taqinor.ma/api/django/ventes/suivi/abc123/');
  });

  it('respecte une base API fournie et retire les slashs finaux', () => {
    expect(suiviEndpoint('https://staging.example.com///', 'xyz')).toBe(
      'https://staging.example.com/api/django/ventes/suivi/xyz/',
    );
  });

  it('encode le token (segment de chemin)', () => {
    expect(suiviEndpoint('https://api.taqinor.ma', 'a b/c?d')).toBe(
      'https://api.taqinor.ma/api/django/ventes/suivi/a%20b%2Fc%3Fd/',
    );
  });
});

describe('WJ115 — isIsoDateString (garde-fou « une chaîne de statut n’est jamais une date »)', () => {
  it('accepte une date ISO simple', () => {
    expect(isIsoDateString('2026-06-01')).toBe(true);
  });

  it('accepte un horodatage ISO complet', () => {
    expect(isIsoDateString('2026-07-11T09:00:00+00:00')).toBe(true);
  });

  it('rejette une chaîne de STATUT chantier (cas de la clé installation)', () => {
    expect(isIsoDateString('planifie')).toBe(false);
    expect(isIsoDateString('en_cours')).toBe(false);
    expect(isIsoDateString('termine')).toBe(false);
  });

  it('rejette null/undefined/vide', () => {
    expect(isIsoDateString(null)).toBe(false);
    expect(isIsoDateString(undefined)).toBe(false);
    expect(isIsoDateString('')).toBe(false);
  });
});

// ── Fixtures : un devis à chaque étape du cycle de vie (contrat backend QX34) ─

function makeSuivi(over: Partial<SuiviResponse> = {}): SuiviResponse {
  return {
    reference: 'DEV-2026-042',
    generated_at: '2026-07-11T09:00:00+00:00',
    milestones: [
      { key: 'accepte', label: 'Proposition acceptée', done: true, date: '2026-06-01T10:00:00+00:00' },
      { key: 'acompte', label: 'Acompte reçu', done: false, date: null },
      { key: 'materiel', label: 'Matériel commandé', done: false, date: null },
      { key: 'installation', label: 'Installation', done: false, date: null },
      { key: 'facture', label: 'Facturé', done: false, date: null },
    ],
    ...over,
  };
}

describe('WJ115 — buildTimeline (FR)', () => {
  it('« seulement accepté » : accepté done, acompte est l’étape courante, le reste futur', () => {
    const steps = buildTimeline(makeSuivi(), 'fr');
    expect(steps.map((s) => s.key)).toEqual(['accepte', 'acompte', 'materiel', 'installation', 'facture']);
    expect(steps[0].done).toBe(true);
    expect(steps[0].current).toBe(false);
    expect(steps[0].dateLabel).toBe('01/06/2026');
    expect(steps[1].done).toBe(false);
    expect(steps[1].current).toBe(true);
    expect(steps[2].current).toBe(false);
    expect(steps[3].current).toBe(false);
    expect(steps[4].current).toBe(false);
  });

  it('« accepté + acompte » : acompte devient done, matériel devient l’étape courante', () => {
    const data = makeSuivi({
      milestones: [
        { key: 'accepte', label: 'Proposition acceptée', done: true, date: '2026-06-01' },
        { key: 'acompte', label: 'Acompte reçu', done: true, date: '2026-06-03' },
        { key: 'materiel', label: 'Matériel commandé', done: false, date: null },
        { key: 'installation', label: 'Installation', done: false, date: null },
        { key: 'facture', label: 'Facturé', done: false, date: null },
      ],
    });
    const steps = buildTimeline(data, 'fr');
    expect(steps[0].done).toBe(true);
    expect(steps[1].done).toBe(true);
    expect(steps[1].current).toBe(false);
    expect(steps[2].current).toBe(true);
    expect(steps[2].done).toBe(false);
  });

  it('« jusqu’à facturé » : tout done, AUCUNE étape courante (rien à sur-affirmer)', () => {
    const data = makeSuivi({
      milestones: [
        { key: 'accepte', label: 'Proposition acceptée', done: true, date: '2026-06-01' },
        { key: 'acompte', label: 'Acompte reçu', done: true, date: '2026-06-03' },
        { key: 'materiel', label: 'Matériel commandé', done: true, date: '2026-06-10' },
        { key: 'installation', label: 'Installation', done: true, date: 'termine' },
        { key: 'facture', label: 'Facturé', done: true, date: null },
      ],
    });
    const steps = buildTimeline(data, 'fr');
    expect(steps.every((s) => s.done)).toBe(true);
    expect(steps.every((s) => !s.current)).toBe(true);
  });

  it('« tout vide » (milestones: []) : tableau vide — jamais une timeline inventée', () => {
    const steps = buildTimeline(makeSuivi({ milestones: [] }), 'fr');
    expect(steps).toEqual([]);
  });

  it('milestones absent (payload dégradé) : tableau vide, jamais un crash', () => {
    const steps = buildTimeline({ milestones: undefined as unknown as SuiviResponse['milestones'] }, 'fr');
    expect(steps).toEqual([]);
  });

  it('un `date` non-ISO sur la clé installation (statut chantier) n’est JAMAIS rendu comme une date', () => {
    const data = makeSuivi({
      milestones: [
        { key: 'accepte', label: 'Proposition acceptée', done: true, date: '2026-06-01' },
        { key: 'acompte', label: 'Acompte reçu', done: true, date: '2026-06-03' },
        { key: 'materiel', label: 'Matériel commandé', done: true, date: '2026-06-10' },
        { key: 'installation', label: 'Installation', done: false, date: 'planifie' },
        { key: 'facture', label: 'Facturé', done: false, date: null },
      ],
    });
    const steps = buildTimeline(data, 'fr');
    const install = steps.find((s) => s.key === 'installation')!;
    expect(install.dateLabel).toBeNull();
    expect(install.current).toBe(true);
  });
});

describe('WJ115 — buildTimeline (AR)', () => {
  it('utilise les libellés arabes par clé (pas les libellés FR backend)', () => {
    const steps = buildTimeline(makeSuivi(), 'ar');
    expect(steps.find((s) => s.key === 'accepte')?.label).toBe('تم قبول العرض');
    expect(steps.find((s) => s.key === 'facture')?.label).toBe('تمت الفوترة');
    expect(steps.every((s) => s.label !== 'Proposition acceptée')).toBe(true);
  });

  it('une clé inconnue retombe sur le libellé FR backend (jamais un texte arabe inventé)', () => {
    const data = makeSuivi({
      milestones: [{ key: 'nouvelle_etape', label: 'Nouvelle étape', done: false, date: null }],
    });
    const steps = buildTimeline(data, 'ar');
    expect(steps[0].label).toBe('Nouvelle étape');
  });

  it('même logique done/current qu’en FR (indépendante de la langue)', () => {
    const stepsFr = buildTimeline(makeSuivi(), 'fr');
    const stepsAr = buildTimeline(makeSuivi(), 'ar');
    expect(stepsAr.map((s) => s.done)).toEqual(stepsFr.map((s) => s.done));
    expect(stepsAr.map((s) => s.current)).toEqual(stepsFr.map((s) => s.current));
  });
});

// ── Vérifications SOURCE sur la page .astro ──────────────────────────────────

describe('WJ115 — [token].astro', () => {
  it('est bien SSR (prerender = false)', () => {
    expect(SUIVI_PAGE).toContain('export const prerender = false;');
  });

  it('est marquée noindex (lien tokenisé privé)', () => {
    expect(SUIVI_PAGE).toContain('noindex={true}');
  });

  it('rate-limite le SSR sur un bucket dédié suivi-view', () => {
    expect(SUIVI_PAGE).toContain('suivi-view:');
    expect(SUIVI_PAGE).toContain('rateLimit(');
  });

  it('a la copie d’erreur/vide en FR ET en AR', () => {
    expect(SUIVI_PAGE).toContain('Ce lien de suivi est introuvable ou a expiré.');
    expect(SUIVI_PAGE).toContain('رابط المتابعة هذا غير موجود أو انتهت صلاحيته.');
    expect(SUIVI_PAGE).toContain('Aucune étape n’est disponible pour le moment');
    expect(SUIVI_PAGE).toContain('لا توجد أي مرحلة متاحة حاليًا');
  });

  it('a un bouton « Réessayer » (pure link) pour les états retryables', () => {
    expect(SUIVI_PAGE).toContain('href={Astro.url.href}');
    expect(SUIVI_PAGE).toContain('Réessayer');
  });

  it('a une affordance de partage WhatsApp', () => {
    expect(SUIVI_PAGE).toContain('waShareLink');
    // WJ115 — message de partage dédié au SUIVI (jamais « proposition »).
    expect(SUIVI_PAGE).toContain('Voici le suivi de mon projet solaire Taqinor');
    expect(SUIVI_PAGE).toContain('Partager ce suivi sur WhatsApp');
  });

  it('n’est jamais linkée dans la nav/footer (page privée)', () => {
    expect(SUIVI_PAGE).not.toContain('href="/suivi"');
  });
});
