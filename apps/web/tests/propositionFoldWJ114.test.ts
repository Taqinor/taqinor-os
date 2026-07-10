// WJ114 — Proposition : premier écran « décider en 10 secondes » + note
// personnelle du vendeur. Recherche Storydoc (1,3 M sessions) : 31 % de
// rebond en 10 s ; 82 % de ceux qui atteignent la section 4 vont au bout ;
// le prix est la section la plus regardée ; la personnalisation complète
// relève l'engagement de +47 %.
//
// Deux volets, même convention que le reste de ce dossier :
//  (1) `sellerNote` est une fonction PURE (lib/proposition.ts) testée
//      directement — lecture défensive, dégrade à `null` si le backend ne
//      fournit encore rien (aucune intégration ERP livrée aujourd'hui).
//  (2) le bloc « au-dessus du pli » de la page Astro est vérifié par lecture
//      SOURCE en texte (même convention que propositionNeverBlankWJ81.test.ts :
//      un montage DOM complet d'un fichier .astro n'est pas praticable ici) —
//      on confirme que les 4 chiffres CANONIQUES + le nom + le CTA sont bien
//      dans le bloc mobile-first, et que la note vendeur est conditionnée à
//      `seller` (donc absente sans donnée backend).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { sellerNote, type ProposalResponse } from '../src/lib/proposition';

const root = (rel: string) => fileURLToPath(new URL(rel, import.meta.url));
const read = (rel: string) => readFileSync(root(rel), 'utf-8');
const PROPOSITION = read('../src/pages/proposition/[token].astro');

function makeProposal(over: Partial<ProposalResponse> = {}): ProposalResponse {
  const base: ProposalResponse = {
    reference: 'DEV-2026-042',
    date: '22/06/2026',
    client_name: 'Reda Kasri',
    statut: 'envoye',
    quote: {
      ref: 'DEV-2026-042',
      date: '22/06/2026',
      client_name: 'Reda Kasri',
      inst_type: 'residentiel',
      puissance_kwc: 6.48,
      nb_panneaux: 9,
      watt_par_panneau: 720,
      prod_kwh: 10000,
      eco_s_ann: 12000,
      eco_a_ann: 15000,
      recommended: 'avec_batterie',
      totaux_sans: { ht_brut: 50000, remise: 0, ht_net: 50000, tva: 10000, ttc: 60000 },
      totaux_avec: { ht_brut: 80000, remise: 0, ht_net: 80000, tva: 16000, ttc: 96000 },
      nb_options: 2,
    },
    roof_image_url: null,
    option_totals: { sans_batterie: 60000, avec_batterie: 96000, display_total: 96000, nb_options: 2 },
    accepted: false,
  };
  return { ...base, ...over, quote: { ...base.quote, ...(over.quote ?? {}) } };
}

describe('WJ114 — sellerNote (lecture défensive, backend pas encore livré)', () => {
  it('absent → null (rien à rendre, jamais un placeholder)', () => {
    expect(sellerNote(makeProposal())).toBeNull();
    expect(sellerNote(makeProposal({ seller: null }))).toBeNull();
    expect(sellerNote(makeProposal({ seller: {} }))).toBeNull();
  });

  it('note + nom + photo fournis → renvoyés tels quels', () => {
    const p = makeProposal({
      seller: { note: 'Ravi de vous accompagner sur ce projet !', name: 'Yassine El Amrani', photo_url: 'https://cdn.taqinor.ma/team/yassine.jpg' },
    });
    expect(sellerNote(p)).toEqual({
      note: 'Ravi de vous accompagner sur ce projet !',
      name: 'Yassine El Amrani',
      photoUrl: 'https://cdn.taqinor.ma/team/yassine.jpg',
    });
  });

  it('un seul champ fourni (ex. juste un nom) → toujours renvoyé, jamais rejeté', () => {
    expect(sellerNote(makeProposal({ seller: { name: 'Sami' } }))).toEqual({
      note: null,
      name: 'Sami',
      photoUrl: null,
    });
  });

  it('chaînes vides/espaces → traitées comme absentes (jamais une bulle vide)', () => {
    expect(sellerNote(makeProposal({ seller: { note: '   ', name: '', photo_url: undefined } }))).toBeNull();
  });

  it('ne fabrique jamais un champ non fourni', () => {
    const result = sellerNote(makeProposal({ seller: { note: 'Bonjour !' } }));
    expect(result?.name).toBeNull();
    expect(result?.photoUrl).toBeNull();
  });
});

describe('WJ114 — bloc « décider en 10 secondes » (au-dessus du pli, mobile-first)', () => {
  const heroSection = PROPOSITION.slice(
    PROPOSITION.indexOf('id="prop-fold-figures"') - 800,
    PROPOSITION.indexOf('<dl class="cine-in cine-in-3 mt-7'),
  );

  it('le bloc figures existe et précède la grille référence/date existante', () => {
    expect(PROPOSITION.indexOf('id="prop-fold-figures"')).toBeGreaterThan(0);
    expect(PROPOSITION.indexOf('id="prop-fold-figures"')).toBeLessThan(
      PROPOSITION.indexOf('<dl class="cine-in cine-in-3 mt-7'),
    );
  });

  it('affiche les 4 chiffres CANONIQUES (kWc, production, TTC, économie/payback) — jamais recalculés', () => {
    expect(heroSection).toContain('formatNumber(puissance, 2)');
    expect(heroSection).toContain('kWc');
    expect(heroSection).toContain('formatNumber(prodKwh)');
    expect(heroSection).toContain('kWh');
    expect(heroSection).toContain('formatMAD(heroTtc)');
    expect(heroSection).toContain('ecoHero ? formatMAD(ecoHero) : paybackHero');
  });

  it('heroTtc réutilise le MÊME calcul que le CTA collant (optionTtc + hasRealPrice), jamais un nouveau calcul', () => {
    expect(PROPOSITION).toContain("const heroTtc = ok && heroHasRealPrice ? optionTtc(data!, reco ?? 'sans_batterie') : null;");
  });

  it('le nom du client est déjà affiché juste au-dessus (h1 "Bonjour {clientName}") — dans le même écran que le bloc figures', () => {
    const heroBlock = PROPOSITION.slice(PROPOSITION.indexOf('Bonjour ${clientName}'), PROPOSITION.indexOf('id="prop-fold-figures"'));
    expect(heroBlock.length).toBeGreaterThan(0);
    expect(heroBlock).toContain('clientName');
  });

  it('UN CTA principal (#prop-fold-cta), pointant vers la signature si un prix réel existe, sinon le conseiller', () => {
    const ctaSection = PROPOSITION.slice(
      PROPOSITION.indexOf('id="prop-fold-figures"'),
      PROPOSITION.indexOf('id="prop-seller-note"'),
    );
    const ctaMatches = ctaSection.match(/id="prop-fold-cta"/g) ?? [];
    // Deux branches JSX (heroHasRealPrice ? … : …) portent le même id — un seul est rendu à l'exécution.
    expect(ctaMatches.length).toBe(2);
    expect(ctaSection).toContain('href="#signer"');
    expect(ctaSection).toContain('href={waLink}');
  });
});

describe('WJ114 — note personnelle du vendeur (dégrade à rien si absente)', () => {
  it('le bloc est conditionné à `seller` (rendu uniquement quand sellerNote() a renvoyé quelque chose)', () => {
    const sellerSection = PROPOSITION.slice(
      PROPOSITION.indexOf('note personnelle du vendeur : dégrade'),
      PROPOSITION.indexOf('<dl class="cine-in cine-in-3 mt-7'),
    );
    expect(sellerSection).toContain('{seller ? (');
    expect(sellerSection).toContain('id="prop-seller-note"');
    expect(sellerSection).toContain(') : null}');
  });

  it('const seller est calculé via sellerNote(data!) — jamais une note fabriquée', () => {
    expect(PROPOSITION).toContain('const seller = ok ? sellerNote(data!) : null;');
  });

  it('le rendu affiche note, nom et photo indépendamment (chacun optionnel dans le JSX)', () => {
    const sellerSection = PROPOSITION.slice(
      PROPOSITION.indexOf('id="prop-seller-note"'),
      PROPOSITION.indexOf('<dl class="cine-in cine-in-3 mt-7'),
    );
    expect(sellerSection).toContain('seller.photoUrl ?');
    expect(sellerSection).toContain('seller.note ?');
    expect(sellerSection).toContain('seller.name ?');
  });
});
