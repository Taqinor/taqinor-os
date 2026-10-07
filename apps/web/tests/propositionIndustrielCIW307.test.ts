// CIW307 — Carte industrielle de /proposition : plus « le solaire produit aux heures les plus
// chères » ni « lissez votre puissance souscrite » ; décarbonation conditionnelle (CBAM sur
// drapeau servi), sans CO₂ chiffré.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { carteIndustrielleCi, syntheseCi, type ProposalResponse } from '../src/lib/proposition';

const TEXTES_PUISSANCE = {
  fr: "La centrale réduit l'énergie achetée ; la puissance souscrite et la prime fixe ne changent pas.",
  en: 'The plant reduces the energy you buy; the subscribed power and the fixed charge do not change.',
  ar: 'تقلص المحطة الطاقة المشتراة؛ القدرة المكتتبة والإتاوة الثابتة لا تتغيران.',
};
const TEXTES_POINTE = {
  fr: "La pointe (soir/nuit) n'est sécurisée qu'avec un stockage — non promise sans batterie.",
  en: 'The evening/night peak is only secured with storage — not promised without a battery.',
  ar: 'لا تُؤمَّن فترة الذروة (المساء/الليل) إلا بالتخزين — غير موعودة دون بطارية.',
};
const DECARB_GENERIQUE = {
  fr: 'Vos clients vous demandent de plus en plus le bilan carbone de votre électricité : une part produite par le soleil sur votre site est un élément de réponse.',
  en: 'Your customers increasingly ask for the carbon footprint of your electricity: a share produced by the sun on your site is part of the answer.',
  ar: 'يطلب منكم زبناؤكم بشكل متزايد البصمة الكربونية لكهربائكم: جزء منتج بالطاقة الشمسية في موقعكم عنصر من عناصر الجواب.',
};
const DECARB_CBAM = {
  fr: "Vous exportez du ciment ou des engrais vers l'Union européenne : pour ces produits, le mécanisme d'ajustement carbone aux frontières (CBAM) compte aussi les émissions de l'électricité consommée.",
  en: 'You export cement or fertilisers to the European Union: the carbon border adjustment mechanism (CBAM) also counts electricity emissions.',
  ar: 'تصدرون الإسمنت أو الأسمدة إلى الاتحاد الأوروبي: تحتسب آلية CBAM أيضا انبعاثات الكهرباء.',
};

function fixture(decarbonation: unknown, hypotheses = true): ProposalResponse {
  return {
    reference: 'DEV-2026-307',
    date: '07/10/2026',
    client_name: 'Usine Exemple',
    statut: 'envoye',
    mode_installation: 'industriel',
    quote: {},
    synthese_ci: {
      segment: 'industriel',
      hypotheses: hypotheses
        ? [
            { cle: 'autoconsommation', textes: { fr: 'Autoconsommation heure par heure.', en: 'Hourly.', ar: 'ساعة بساعة.' }, source: 's', date: null },
            { cle: 'puissance_souscrite', textes: TEXTES_PUISSANCE, source: 'convention', date: null },
            { cle: 'pointe', textes: TEXTES_POINTE, source: 'moteur C&I', date: null },
          ]
        : [],
      decarbonation,
    },
  } as unknown as ProposalResponse;
}

const INTERDITS = [
  /heures les plus chères/i,
  /écrêtez/i,
  /lissez/i,
  /most expensive hours/i,
  /shave your/i,
  /smooth your subscribed/i,
  /أغلى الساعات/,
  /تقلّصون/,
  /تُنعّمون/,
];

describe('CIW307 — carteIndustrielleCi lit les textes SERVIS (mêmes que le PDF)', () => {
  it('reprend puissance souscrite + pointe, dans cet ordre, et rien d\'autre', () => {
    const carte = carteIndustrielleCi(syntheseCi(fixture({ cbam: false, textes: DECARB_GENERIQUE })))!;
    expect(carte.hypotheses.map((h) => h.cle)).toEqual(['puissance_souscrite', 'pointe']);
    expect(carte.hypotheses[0].textes).toEqual(TEXTES_PUISSANCE);
    expect(carte.hypotheses[1].textes).toEqual(TEXTES_POINTE);
  });

  it('contenu construit (3 langues) : aucune des phrases supprimées, aucun « t CO₂ », aucun CBAM sans drapeau', () => {
    const carte = carteIndustrielleCi(syntheseCi(fixture({ cbam: false, textes: DECARB_GENERIQUE })))!;
    const html = JSON.stringify([carte.hypotheses.map((h) => h.textes), carte.decarbonation]);
    for (const re of INTERDITS) expect(html).not.toMatch(re);
    expect(html).not.toMatch(/CBAM/);
    expect(html).not.toMatch(/t CO₂|t CO2/);
    expect(carte.decarbonation?.cbam).toBe(false);
    expect(carte.decarbonation?.textes).toEqual(DECARB_GENERIQUE);
  });

  it('CBAM seulement quand le serveur lève le drapeau (phrase servie telle quelle)', () => {
    const carte = carteIndustrielleCi(syntheseCi(fixture({ cbam: true, textes: DECARB_CBAM })))!;
    expect(carte.decarbonation?.cbam).toBe(true);
    expect(carte.decarbonation?.textes.fr).toContain('CBAM');
  });

  it('sans hypothèses ni décarbonation servies → carte vide ; hors industriel → null', () => {
    const vide = carteIndustrielleCi(syntheseCi(fixture(undefined, false)))!;
    expect(vide.hypotheses).toEqual([]);
    expect(vide.decarbonation).toBeNull();
    const commercial = { ...fixture(undefined), mode_installation: 'commercial' } as unknown as ProposalResponse;
    (commercial as unknown as { synthese_ci: Record<string, unknown> }).synthese_ci.segment = 'commercial';
    expect(carteIndustrielleCi(syntheseCi(commercial))).toBeNull();
    expect(carteIndustrielleCi(null)).toBeNull();
  });
});

describe('CIW307 — la page n\'écrit plus ces phrases et ne calcule plus de CO₂ en C&I', () => {
  const page = readFileSync(fileURLToPath(new URL('../src/pages/proposition/[...token].astro', import.meta.url)), 'utf-8');
  it('aucune phrase interdite dans la page (FR / EN / AR)', () => {
    for (const re of INTERDITS) expect(page).not.toMatch(re);
  });
  it('plus de promesse CBAM / ISO codée dans la page : la carte lit la décarbonation servie', () => {
    expect(page).not.toMatch(/Décarbonation, CBAM et ISO/);
    expect(page).not.toMatch(/ISO 14001/);
    expect(page).toContain('const ciCarteInd = ok && installMode === \'industriel\' ? carteIndustrielleCi(ci) : null;');
    expect(page).toContain('data-ci-decarbonation');
  });
  it('enviro (CO₂ au facteur « source à préciser ») vaut null en C&I', () => {
    expect(page).toContain('const enviro = ok && !isAgricole && !isAutoconso ? environmentalImpact(prodKwh) : null;');
  });
});
