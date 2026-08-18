// Tunnel /devis/mon-toit — les trois chantiers du lot, épinglés sur les TROIS
// variantes de langue (FR / EN / AR), qui partagent le même contrat DOM+payload :
//
//  1. La question « Mode de financement envisagé » est RETIRÉE (décision
//     fondateur) — du DOM comme du corps envoyé — sans casser le contrat
//     backend, qui continue d'accepter `financing_intent` d'autres sources.
//  2. Plus rien de collecté ne se perd en route : la surface des catégories
//     commerciales, les champs qui étaient gatés sur le profil ACTIF au moment
//     de l'envoi, les jetons de dédoublonnage, et le nombre de panneaux annoncé.
//  3. Repérer son toit est un CHOIX explicite (pointer / dessiner), et le geste
//     « pointer » se termine par une confirmation visuelle.
//
// On lit les SOURCES .astro : ces trois pages ne sont pas montables en unité
// (script Astro inline + import lazy de MapLibre), mais leurs invariants de
// contrat sont textuels et doivent rester vrais sur les trois à la fois — c'est
// exactement le genre de divergence FR/EN/AR qui passe inaperçue autrement.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { COMMERCIAL_QUESTION_WEBHOOK_KEY } from '../src/lib/commercialCategories';
import { validateLead } from '../src/lib/lead';

const read = (rel: string) =>
  readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

const LOCALES: Array<[string, string]> = [
  ['FR', '../src/pages/devis/mon-toit.astro'],
  ['EN', '../src/pages/en/devis/mon-toit.astro'],
  ['AR', '../src/pages/ar/devis/mon-toit.astro'],
];

/** Retire les commentaires HTML : un id cité dans un commentaire d'explication
 *  ne doit jamais faire passer (ni échouer) une épingle de contrat. */
const stripHtmlComments = (s: string) => s.replace(/<!--[\s\S]*?-->/g, '');
/** Idem côté script : une clé RETIRÉE est justement expliquée par un commentaire
 *  qui la NOMME — sans ce filtrage, l'épingle « la clé ne part plus » se
 *  déclencherait sur sa propre explication. */
const stripLineComments = (s: string) => s.replace(/^[ \t]*\/\/.*$/gm, '');

/** Texte entre deux bornes (bornes incluses), ou '' si l'ouverture manque. */
function slice(src: string, open: string, close: string): string {
  const a = src.indexOf(open);
  if (a < 0) return '';
  const b = src.indexOf(close, a + open.length);
  return b < 0 ? src.slice(a) : src.slice(a, b + close.length);
}

/** L'objet littéral construit par buildBody() — le corps RÉELLEMENT envoyé. */
const payloadSrc = (src: string) =>
  stripLineComments(slice(src, 'const body: Record<string, unknown> = {', "website_url: val('mt-hp'),"));

/** La ligne du payload qui porte `key:` (une seule par corps). */
function payloadLine(src: string, key: string): string {
  const m = payloadSrc(src).match(new RegExp(`^[ \\t]*${key}: .*$`, 'm'));
  return m ? m[0] : '';
}

const detailsFinancing = (src: string) =>
  stripHtmlComments(slice(src, '<details id="mt-more-financing"', '</details>'));

// ———————————————————————————————————————————————————————————————————————————
describe('Chantier 1 — la question de financement a quitté le tunnel', () => {
  for (const [lang, rel] of LOCALES) {
    const src = read(rel);

    it(`${lang} — le <select> mt-financing-intent n'existe plus dans le DOM`, () => {
      expect(stripHtmlComments(src)).not.toContain('id="mt-financing-intent"');
      expect(stripHtmlComments(src)).not.toContain('name="financingIntent"');
    });

    it(`${lang} — l'accordéon garde ses DEUX autres questions`, () => {
      const block = detailsFinancing(src);
      expect(block).toContain('id="mt-occupant-type"');
      expect(block).toContain('id="mt-project-timing"');
      expect(block).not.toContain('mt-financing-intent');
    });

    it(`${lang} — son intitulé ne parle plus de financement`, () => {
      const summary = stripHtmlComments(slice(detailsFinancing(src), '<summary', '</summary>'));
      expect(summary.length).toBeGreaterThan(0);
      // Ni « financement » (FR), ni « financing » (EN), ni « تمويل » (AR).
      expect(summary).not.toMatch(/financ/i);
      expect(summary).not.toMatch(/تمويل/);
    });

    it(`${lang} — la clé financingIntent ne part plus dans le corps du lead`, () => {
      expect(payloadSrc(src)).not.toContain('financingIntent');
    });

    it(`${lang} — le champ disparu n'est plus persisté dans le brouillon`, () => {
      const persisted = stripLineComments(slice(src, 'const PERSISTED_TEXT_FIELDS = [', '];'));
      expect(persisted).toContain("'mt-occupant-type'");
      expect(persisted).not.toContain("'mt-financing-intent'");
    });
  }

  it("le CONTRAT BACKEND est intact : validateLead accepte toujours financingIntent", () => {
    // Le champ ERP `financing_intent` vit encore (d'autres sources l'alimentent) :
    // retirer la question du site ne doit RIEN casser côté serveur.
    const r = validateLead({
      fullName: 'Karim Benali',
      phone: '06 12 34 56 78',
      city: 'Casablanca',
      roofType: 'villa',
      billRange: '1500-3000',
      consent: true,
      financingIntent: 'comptant',
    });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.financingIntent).toBe('comptant');
  });
});

// ———————————————————————————————————————————————————————————————————————————
describe('Chantier 2 — tout ce qui est collecté atteint bien l’ERP', () => {
  const base = {
    fullName: 'Karim Benali',
    phone: '06 12 34 56 78',
    city: 'Casablanca',
    roofType: 'villa',
    billRange: '1500-3000',
    consent: true,
  };

  it('la surface des catégories commerciales a enfin une destination webhook', () => {
    expect(COMMERCIAL_QUESTION_WEBHOOK_KEY.surface_m2).toBe('surfaceM2');
    const r = validateLead({ ...base, surfaceM2: 240 });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.surfaceM2).toBe(240);
  });

  it('les jetons de dédoublonnage traversent la validation (format crypto.randomUUID)', () => {
    // `crypto.randomUUID()` produit exactement la forme que valide lib/lead.ts
    // (^[A-Za-z0-9_-]{8,64}$) : on le prouve avec un vrai UUID généré ici.
    const idempotencyKey = crypto.randomUUID();
    const eventId = crypto.randomUUID();
    expect(idempotencyKey).not.toBe(eventId); // deux systèmes, deux jetons
    const r = validateLead({ ...base, idempotencyKey, eventId });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.idempotencyKey).toBe(idempotencyKey);
    expect(r.lead.eventId).toBe(eventId);
  });

  it("le nombre de panneaux annoncé entre dans la liste blanche d'estimateShown", () => {
    const r = validateLead({ ...base, estimateShown: { kwc: 6.4, nbPanneaux: 9 } });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.estimateShown?.nbPanneaux).toBe(9);
    // …et la liste reste une VRAIE liste blanche : rien d'autre ne passe.
    const r2 = validateLead({ ...base, estimateShown: { kwc: 6.4, margeInterne: 4200 } });
    expect(r2.ok).toBe(true);
    if (!r2.ok) return;
    expect(r2.lead.estimateShown).not.toHaveProperty('margeInterne');
  });

  for (const [lang, rel] of LOCALES) {
    const src = read(rel);

    it(`${lang} — les jetons de dédoublonnage sont bien ENVOYÉS et persistés`, () => {
      expect(payloadSrc(src)).toContain('idempotencyKey:');
      expect(payloadSrc(src)).toContain('eventId:');
      // …et repris du brouillon, sinon un rafraîchissement fabriquerait un
      // second jeton pour la même saisie — le doublon qu'ils doivent empêcher.
      expect(src).toContain('idempotencyKey: dedupIdempotencyKey');
      expect(src).toContain('eventId: dedupEventId');
      expect(src).toContain("savedWizard?.idempotencyKey ||");
      expect(src).toContain("savedWizard?.eventId ||");
    });

    // Un visiteur qui a décrit son site industriel puis rebasculé sur un autre
    // profil ne doit plus perdre ses réponses : ce qui est SAISI part, point.
    const UNGATED = [
      'equipes', 'weekend', 'cosPhiConnu', 'groupeKva', 'dieselDhMois',
      'surfaceToitureM2', 'ombriere', 'terrain', 'heuresPompage',
    ];
    for (const key of UNGATED) {
      it(`${lang} — ${key} ne dépend plus du profil actif au moment de l'envoi`, () => {
        const line = payloadLine(src, key);
        expect(line.length).toBeGreaterThan(0);
        expect(line).not.toContain("mode === 'industriel'");
        expect(line).not.toContain("mode === 'professionnel'");
        expect(line).not.toContain("mode === 'agricole'");
        expect(line).not.toContain('isProMode(mode)');
      });
    }

    it(`${lang} — mais le gate SÉMANTIQUE sur le type de surface est conservé`, () => {
      // surface_toiture_m2 = surface de TOIT au sens strict : une ombrière ou un
      // terrain ne doit jamais être décrit comme une toiture.
      expect(payloadLine(src, 'surfaceToitureM2')).toContain("surfaceType === 'bac_acier'");
      expect(payloadLine(src, 'ombriere')).toContain("surfaceType === 'ombriere'");
      expect(payloadLine(src, 'terrain')).toContain("surfaceType === 'terrain'");
    });
  }
});

// ———————————————————————————————————————————————————————————————————————————
describe('Chantier 3 — pointer OU dessiner, avec confirmation visuelle', () => {
  for (const [lang, rel] of LOCALES) {
    const src = read(rel);
    const dom = stripHtmlComments(src);

    it(`${lang} — les deux gestes sont proposés explicitement`, () => {
      expect(dom).toContain('id="mt-roof-mode-point"');
      expect(dom).toContain('id="mt-roof-mode-draw"');
      expect(dom).toContain('data-value="point"');
      expect(dom).toContain('data-value="draw"');
      // Repères visuels demandés (épingle/crayon) présents dans les deux libellés.
      expect(dom).toContain('📍');
      expect(dom).toContain('✏️');
    });

    it(`${lang} — la confirmation « C'est bien votre toit ? » existe avec sa sortie « ajuster »`, () => {
      expect(dom).toContain('id="mt-pin-confirm"');
      expect(dom).toContain('id="mt-pin-confirm-address"');
      expect(dom).toContain('id="mt-pin-confirm-yes"');
      expect(dom).toContain('id="mt-pin-confirm-adjust"');
    });

    it(`${lang} — le geste choisi est bien transmis à la carte`, () => {
      // La carte ne peut pas deviner le choix : il lui est passé en FONCTION
      // (relue à chaque clic — le visiteur peut changer d'avis en cours de route).
      expect(src).toContain('roofInputMode: () => roofInputMode');
      // …et le repère confirmé se resynchronise sur chaque notification carte,
      // car l'adresse arrive APRÈS le repère (géocodage inverse asynchrone).
      expect(src).toContain('setPinConfirmAddress(s.address)');
      expect(src).toContain('syncPinConfirm()');
    });
  }

  it('FR et AR portent les traductions arabes des nouveaux libellés (data-i18n)', () => {
    for (const rel of ['../src/pages/devis/mon-toit.astro', '../src/pages/ar/devis/mon-toit.astro']) {
      const src = read(rel);
      expect(src).toContain('data-ar="📍 تحديد سطحي بنقطة"');
      expect(src).toContain('data-ar="✏️ رسم سطحي"');
      expect(src).toContain('data-ar="هل هذا هو سطحكم؟"');
    }
  });

  it('EN porte ses libellés en anglais (cette route n’a pas de bascule data-i18n)', () => {
    const src = read('../src/pages/en/devis/mon-toit.astro');
    expect(src).toContain('📍 Point at my roof');
    expect(src).toContain('✏️ Draw my roof');
    expect(src).toContain('Is this your roof?');
  });

  it("l'option roofInputMode est bien exposée par le boot capture", () => {
    const boot = read('../src/scripts/roofPro11/captureBoot.ts');
    expect(boot).toContain('roofInputMode?: () =>');
    // Sans l'option, le flux historique reste intact (comportement par défaut) :
    // les deux branches sont gardées par `opts.roofInputMode?.()`.
    expect(boot).toContain("opts.roofInputMode?.() === 'draw'");
    expect(boot).toContain("opts.roofInputMode?.() === 'point'");
  });
});
