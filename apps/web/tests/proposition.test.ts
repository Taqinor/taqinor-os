// W116 / W117 — Logique pure de la proposition client en ligne.
// Aucune dépendance DOM ni réseau : on teste le formatage, le choix d'option,
// la validation/mise en forme de la requête d'acceptation, et la normalisation
// des réponses backend.
import { describe, expect, it } from 'vitest';
import {
  formatMAD,
  formatNumber,
  formatPercent,
  formatPayback,
  optionCount,
  hasTwoOptions,
  recommendedOption,
  optionTtc,
  hasRealPrice,
  optionLabel,
  optionItems,
  optionTotaux,
  defaultSelectedOption,
  isAccepted,
  validateSign,
  buildAcceptBody,
  acceptEndpoint,
  proposalEndpoint,
  normalizeAcceptResponse,
  type ProposalResponse,
} from '../src/lib/proposition';

function makeProposal(over: Partial<ProposalResponse> = {}): ProposalResponse {
  const base: ProposalResponse = {
    reference: 'DEV-2026-001',
    date: '22/06/2026',
    client_name: 'Reda Kasri',
    statut: 'envoye',
    quote: {
      ref: 'DEV-2026-001',
      date: '22/06/2026',
      client_name: 'Reda Kasri',
      inst_type: 'residentiel',
      puissance_kwc: 6.48,
      nb_panneaux: 9,
      watt_par_panneau: 720,
      prod_kwh: 10800,
      eco_s_ann: 12000,
      eco_a_ann: 15000,
      roi_s: 6.5,
      roi_a: 7.2,
      recommended: 'avec_batterie',
      sans_items: [
        { designation: 'Panneau 720W', quantite: 9, prix_unit_ht: 1000, prix_unit_ttc: 1200, remise: 0, marque: 'Canadian Solar', taux_tva: 20 },
      ],
      avec_items: [
        { designation: 'Panneau 720W', quantite: 9, prix_unit_ht: 1000, prix_unit_ttc: 1200, remise: 0, marque: 'Canadian Solar', taux_tva: 20 },
        { designation: 'Batterie 5kWh', quantite: 1, prix_unit_ht: 20000, prix_unit_ttc: 24000, remise: 0, marque: 'Pylontech', taux_tva: 20 },
      ],
      totaux_sans: { ht_brut: 50000, remise: 5000, ht_net: 45000, tva: 9000, ttc: 54000 },
      totaux_avec: { ht_brut: 80000, remise: 8000, ht_net: 72000, tva: 14400, ttc: 86400 },
      display_total: 86400,
      nb_options: 2,
    },
    roof_image_url: 'https://api.taqinor.ma/media/roof/abc.png',
    option_totals: { sans_batterie: 54000, avec_batterie: 86400, display_total: 86400, nb_options: 2 },
    accepted: false,
  };
  return { ...base, ...over, quote: { ...base.quote, ...(over.quote ?? {}) } };
}

describe('formatage', () => {
  it('formatMAD — espace de milliers, devise après, arrondi', () => {
    expect(formatMAD(12500)).toBe('12 500 MAD');
    expect(formatMAD(1234567)).toBe('1 234 567 MAD');
    expect(formatMAD(999)).toBe('999 MAD');
    expect(formatMAD(86399.6)).toBe('86 400 MAD');
  });

  it('formatMAD — null/NaN → 0 MAD (jamais d’affichage cassé)', () => {
    expect(formatMAD(null)).toBe('0 MAD');
    expect(formatMAD(undefined)).toBe('0 MAD');
    expect(formatMAD(NaN)).toBe('0 MAD');
  });

  it('formatNumber — entier groupé, décimales virgule', () => {
    expect(formatNumber(10800)).toBe('10 800');
    expect(formatNumber(6.48, 2)).toBe('6,48');
    expect(formatNumber(7.2, 2)).toBe('7,2');
    expect(formatNumber(1000, 0)).toBe('1 000');
  });

  it('formatPercent — espace avant %', () => {
    expect(formatPercent(30)).toBe('30 %');
    expect(formatPercent(12.5, 1)).toBe('12,5 %');
  });

  it('formatPayback — accepte nombre (ans) ou chaîne déjà formatée', () => {
    expect(formatPayback(6.5)).toBe('6,5 ans');
    expect(formatPayback('7 ans 3 mois')).toBe('7 ans 3 mois');
    expect(formatPayback(0)).toBeNull();
    expect(formatPayback(null)).toBeNull();
    expect(formatPayback('')).toBeNull();
  });
});

describe('comptage et choix d’options', () => {
  it('optionCount — fait confiance à nb_options', () => {
    expect(optionCount(makeProposal())).toBe(2);
    const one = makeProposal({
      option_totals: { sans_batterie: 54000, avec_batterie: 0, display_total: 54000, nb_options: 1 },
      quote: { totaux_avec: undefined },
    });
    expect(optionCount(one)).toBe(1);
  });

  it('optionCount — repli sur la présence des deux blocs de totaux', () => {
    const noCount = makeProposal({
      option_totals: { sans_batterie: 54000, avec_batterie: 86400, display_total: 86400, nb_options: 0 as unknown as number },
    });
    expect(optionCount(noCount)).toBe(2);
  });

  it('hasTwoOptions', () => {
    expect(hasTwoOptions(makeProposal())).toBe(true);
    const one = makeProposal({
      option_totals: { sans_batterie: 54000, avec_batterie: 0, display_total: 54000, nb_options: 1 },
    });
    expect(hasTwoOptions(one)).toBe(false);
  });

  it('recommendedOption — respecte le champ, défaut sensé', () => {
    expect(recommendedOption(makeProposal())).toBe('avec_batterie');
    expect(recommendedOption(makeProposal({ quote: { recommended: 'sans_batterie' } }))).toBe('sans_batterie');
    // recommended absent + avec présent → avec_batterie
    expect(recommendedOption(makeProposal({ quote: { recommended: undefined } }))).toBe('avec_batterie');
    // recommended absent + avec absent → sans_batterie
    const onlySans = makeProposal({ quote: { recommended: undefined, totaux_avec: undefined } });
    expect(recommendedOption(onlySans)).toBe('sans_batterie');
  });

  it('optionTtc — lit les totaux, repli sur option_totals', () => {
    const p = makeProposal();
    expect(optionTtc(p, 'sans_batterie')).toBe(54000);
    expect(optionTtc(p, 'avec_batterie')).toBe(86400);
    const noTotaux = makeProposal({ quote: { totaux_avec: undefined } });
    expect(optionTtc(noTotaux, 'avec_batterie')).toBe(86400); // repli option_totals
  });

  // WJ83 — un payload totaux-less retombe sur `optionTtc() === 0` (le `?? 0`
  // défensif) ; `hasRealPrice` distingue ce repli d'un vrai prix pour que la
  // page n'affiche jamais "0 MAD TTC, clé en main" comme un prix réel.
  it('hasRealPrice — vrai avec un TTC positif, faux sur un payload totaux-less (0)', () => {
    const p = makeProposal();
    expect(hasRealPrice(p, 'sans_batterie')).toBe(true);
    expect(hasRealPrice(p, 'avec_batterie')).toBe(true);

    const degenerate = makeProposal({
      quote: { totaux_sans: undefined, totaux_avec: undefined },
      option_totals: { sans_batterie: 0, avec_batterie: 0, display_total: 0, nb_options: 1 },
    });
    expect(hasRealPrice(degenerate, 'sans_batterie')).toBe(false);
    expect(hasRealPrice(degenerate, 'avec_batterie')).toBe(false);
  });

  it('optionLabel / optionItems / optionTotaux', () => {
    const p = makeProposal();
    expect(optionLabel('sans_batterie')).toBe('Sans batterie');
    expect(optionLabel('avec_batterie')).toBe('Avec batterie');
    expect(optionItems(p, 'avec_batterie')).toHaveLength(2);
    expect(optionItems(p, 'sans_batterie')).toHaveLength(1);
    expect(optionItems(makeProposal({ quote: { avec_items: undefined } }), 'avec_batterie')).toEqual([]);
    expect(optionTotaux(p, 'sans_batterie')?.ttc).toBe(54000);
    expect(optionTotaux(makeProposal({ quote: { totaux_avec: undefined } }), 'avec_batterie')).toBeNull();
  });

  it('defaultSelectedOption — recommandée si 2 options, sinon la seule', () => {
    expect(defaultSelectedOption(makeProposal())).toBe('avec_batterie');
    const onlySans = makeProposal({
      option_totals: { sans_batterie: 54000, avec_batterie: 0, display_total: 54000, nb_options: 1 },
      quote: { totaux_avec: undefined },
    });
    expect(defaultSelectedOption(onlySans)).toBe('sans_batterie');
    const onlyAvec = makeProposal({
      option_totals: { sans_batterie: 0, avec_batterie: 86400, display_total: 86400, nb_options: 1 },
      quote: { totaux_sans: undefined },
    });
    expect(defaultSelectedOption(onlyAvec)).toBe('avec_batterie');
  });

  it('isAccepted — flag booléen ou statut', () => {
    expect(isAccepted(makeProposal())).toBe(false);
    expect(isAccepted(makeProposal({ accepted: true }))).toBe(true);
    expect(isAccepted(makeProposal({ statut: 'accepte' }))).toBe(true);
  });
});

describe('validation de signature', () => {
  it('nom vide → invalide', () => {
    expect(validateSign({ nom: '', option: 'sans_batterie' }, false).valid).toBe(false);
    expect(validateSign({ nom: '   ', option: 'sans_batterie' }, false).valid).toBe(false);
  });

  it('deux options sans choix → invalide', () => {
    const r = validateSign({ nom: 'Reda', option: null }, true);
    expect(r.valid).toBe(false);
    expect(r.error).toMatch(/option/i);
  });

  it('deux options avec choix → valide', () => {
    expect(validateSign({ nom: 'Reda', option: 'avec_batterie' }, true).valid).toBe(true);
  });

  it('une option, nom rempli → valide même sans option', () => {
    expect(validateSign({ nom: 'Reda', option: null }, false).valid).toBe(true);
  });
});

describe('mise en forme de la requête d’acceptation', () => {
  it('buildAcceptBody — inclut option seulement si deux options', () => {
    expect(buildAcceptBody({ nom: ' Reda ', option: 'avec_batterie' }, true)).toEqual({
      nom: 'Reda',
      option: 'avec_batterie',
    });
    // une seule option → option omise même si fournie
    expect(buildAcceptBody({ nom: 'Reda', option: 'avec_batterie' }, false)).toEqual({ nom: 'Reda' });
    // deux options mais option nulle → option omise (le client doit valider avant)
    expect(buildAcceptBody({ nom: 'Reda', option: null }, true)).toEqual({ nom: 'Reda' });
  });

  it('acceptEndpoint / proposalEndpoint — construit l’URL, encode le token', () => {
    expect(acceptEndpoint('https://api.taqinor.ma', 'abc123')).toBe(
      'https://api.taqinor.ma/api/django/ventes/proposal/abc123/accept/',
    );
    expect(proposalEndpoint('https://api.taqinor.ma/', 'abc123')).toBe(
      'https://api.taqinor.ma/api/django/ventes/proposal/abc123/',
    );
    expect(acceptEndpoint('', 'a b')).toBe(
      'https://api.taqinor.ma/api/django/ventes/proposal/a%20b/accept/',
    );
  });
});

describe('normalisation des réponses backend', () => {
  it('200 → ok, reflète reference + accepte_par_nom', () => {
    const r = normalizeAcceptResponse(200, {
      detail: 'Devis accepté',
      reference: 'DEV-2026-001',
      statut: 'accepte',
      accepte_par_nom: 'Reda Kasri',
    });
    expect(r.ok).toBe(true);
    expect(r.reference).toBe('DEV-2026-001');
    expect(r.accepte_par_nom).toBe('Reda Kasri');
  });

  it('400/409/404 → not ok, reflète le detail backend', () => {
    expect(normalizeAcceptResponse(400, { detail: 'Nom requis' })).toMatchObject({ ok: false, detail: 'Nom requis' });
    expect(normalizeAcceptResponse(409, { detail: 'Déjà accepté' })).toMatchObject({ ok: false, detail: 'Déjà accepté' });
    expect(normalizeAcceptResponse(404, { detail: 'Token invalide' })).toMatchObject({ ok: false, detail: 'Token invalide' });
  });

  it('erreur sans detail → message FR de repli par code', () => {
    expect(normalizeAcceptResponse(404, {}).detail).toMatch(/introuvable|expir/i);
    expect(normalizeAcceptResponse(409, {}).detail).toMatch(/déjà/i);
    expect(normalizeAcceptResponse(400, {}).detail).toMatch(/invalide/i);
    expect(normalizeAcceptResponse(502, {}).detail).toMatch(/erreur/i);
  });
});
