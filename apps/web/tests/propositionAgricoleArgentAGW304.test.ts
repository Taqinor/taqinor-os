// AGW304 — jumeau web du document agricole (2/2) : argent déclaré, énergie actuelle,
// règle de l'aide FDA, garanties pompe/variateur, options du kit et formalités, LUS dans
// `synthese_agricole` (contrat partagé `proposal_data.json` › `exemple_agricole`).
//
//  - bloc absent → `null` ; énergie non déclarée → pas de carte ;
//  - aucune valeur numérique dans l'aide FDA en dehors des plafonds de la règle servie ;
//  - garanties jamais complétées par une constante (la garantie de pose codée en dur
//    n'apparaît pas en agricole) ;
//  - jamais « gratuit », « à vie », « illimité », « jusqu'à 30 % ».
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  AGR_ARGENT_LBL,
  AGR_ENERGIE_LBL,
  AGR_NON_INCLUS_LBL,
  dureeGarantie,
  libelleGarantie,
  syntheseAgricoleArgent,
  type ProposalResponse,
} from '../src/lib/proposition';
import { garantiesCodeesEnDurAffichees } from '../src/lib/propositionPage';

const lire = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');
const contrat = JSON.parse(lire('../src/contract_samples/proposal_data.json')) as {
  exemple_agricole: { synthese_agricole: Record<string, any> };
};
const SERVIE = contrat.exemple_agricole.synthese_agricole;

function payload(synthese?: unknown, mode = 'agricole'): ProposalResponse {
  return {
    reference: 'DEV-2026-0001',
    mode_installation: mode,
    quote: { ref: 'DEV-2026-0001', mode_installation: mode },
    ...(synthese === undefined ? {} : { synthese_agricole: synthese }),
  } as unknown as ProposalResponse;
}
const sans = (cle: string) => {
  const { [cle]: _omis, ...reste } = SERVIE;
  return reste;
};

describe('AGW304 — syntheseAgricoleArgent : lecture défensive', () => {
  it('lit l’exemple agricole du contrat partagé', () => {
    const a = syntheseAgricoleArgent(payload(SERVIE))!;
    expect(a).not.toBeNull();
    const e = a.economies!;
    expect(e.cas).toBe('carburant');
    expect(e.depenseActuelleMadAn).toBe(32871.45);
    expect(e.entretienMadAn).toBe(1500);
    expect(e.chargesSolairesMadAn).toBe(600);
    expect(e.economieNetteAn1).toBe(32271.45);
    expect(e.retourAns).toBe(3);
    expect(e.horizonAns).toBe(10);
    expect(e.coutM3).toEqual({ actuel: 1.55, solaire: 0.56 });
    // remplacement de la pompe en année 7 compté ; celui du variateur (sans montant) est OMIS
    expect(e.remplacements).toEqual([{ composant: 'pompe', annee: 7, montantTtc: 18000 }]);
    expect(e.declareLe).toBe('2026-09-12');
    expect(a.energieActuelle!.valeur).toBe('butane');
    expect(a.garanties).toHaveLength(2);
    expect(a.optionsKit).toEqual([{ ligneId: 90311, designation: 'Afficheur du variateur', totalTtc: 950 }]);
    expect(a.nonInclus).toEqual(['forage', 'genie_civil']);
    expect(a.formalites[0].cle).toBe('declaration_8221');
    expect(a.formalites[0].textes.ar.length).toBeGreaterThan(10);
  });

  it('hors agricole, sans synthèse ou synthèse vide → null', () => {
    expect(syntheseAgricoleArgent(payload(SERVIE, 'residentiel'))).toBeNull();
    expect(syntheseAgricoleArgent(payload(undefined))).toBeNull();
    expect(syntheseAgricoleArgent(payload({}))).toBeNull();
    expect(syntheseAgricoleArgent(null)).toBeNull();
  });

  it('bloc `economies` absent → null (le chapitre argent est OMIS, jamais un 0)', () => {
    expect(syntheseAgricoleArgent(payload(sans('economies')))!.economies).toBeNull();
  });

  it('bloc `economies` non calculé / non publiable → jamais affiché', () => {
    const eco = SERVIE.economies;
    expect(syntheseAgricoleArgent(payload({ ...SERVIE, economies: { ...eco, statut: 'omis' } }))!.economies).toBeNull();
    expect(syntheseAgricoleArgent(payload({ ...SERVIE, economies: { ...eco, publiable_client: false } }))!.economies).toBeNull();
  });

  it('chaque montant manquant reste null — jamais un 0 fabriqué', () => {
    const eco = { ...SERVIE.economies, depense_actuelle: {}, charges_solaires: {}, economie: {}, mad_par_m3: { actuel: 1.5 }, remplacements: [] };
    const e = syntheseAgricoleArgent(payload({ ...SERVIE, economies: eco }))!.economies!;
    expect(e.depenseActuelleMadAn).toBeNull();
    expect(e.chargesSolairesMadAn).toBeNull();
    expect(e.economieNetteAn1).toBeNull();
    expect(e.retourAns).toBeNull();
    expect(e.coutM3).toBeNull();
    expect(e.remplacements).toEqual([]);
  });

  it('énergie non déclarée (absente, sans valeur ou sans provenance) → pas de carte', () => {
    expect(syntheseAgricoleArgent(payload(sans('energie_actuelle')))!.energieActuelle).toBeNull();
    expect(syntheseAgricoleArgent(payload({ ...SERVIE, energie_actuelle: { valeur: 'butane' } }))!.energieActuelle).toBeNull();
    expect(syntheseAgricoleArgent(payload({ ...SERVIE, energie_actuelle: { provenance: SERVIE.energie_actuelle.provenance } }))!.energieActuelle).toBeNull();
  });

  it('les libellés d’énergie couvrent butane (bouteilles), diesel (gasoil + groupe), réseau (facture)', () => {
    expect(AGR_ENERGIE_LBL.butane.fr).toContain('bouteilles');
    expect(AGR_ENERGIE_LBL.diesel.fr).toContain('gasoil');
    expect(AGR_ENERGIE_LBL.diesel.fr).toContain('groupe');
    expect(AGR_ENERGIE_LBL.electrique.fr).toContain('facture');
  });
});

describe('AGW304 — règle de l’aide FDA : plafonds, jamais un montant client', () => {
  it('lit la règle servie : conditions, QUATRE plafonds, édition, source, date, textes fr/en/ar', () => {
    const f = syntheseAgricoleArgent(payload(SERVIE))!.aideFda!;
    expect(Object.keys(f.plafonds).sort()).toEqual(['parHa', 'parKwc', 'parProjet', 'tauxPct']);
    expect(f.plafonds).toEqual({ tauxPct: 30, parHa: 3000, parKwc: 3000, parProjet: 30000 });
    expect(f.edition).toBe('Guide FDA 2024');
    expect(f.releveLe).toBe('2026-10-02');
    expect(f.textes!.fr).toContain('AVANT les travaux');
    expect(f.textes!.en).toContain('BEFORE the works');
    expect(f.textes!.ar).toContain('قبل الأشغال');
  });

  it('les textes servis ne promettent jamais « jusqu’à 30 % », « ≈ 30 % » ni un montant propre au client', () => {
    const t = syntheseAgricoleArgent(payload(SERVIE))!.aideFda!.textes!;
    for (const voix of [t.fr, t.en, t.ar]) {
      expect(voix).not.toMatch(/jusqu['’]à|up to|حتى|≈|pouvant atteindre/i);
    }
    // Aucun nombre ne figure dans le texte hors des plafonds de la règle (30, 3 000, 30 000).
    const nombres = (t.fr.match(/\d[\d  ]*/g) ?? []).map((n) => Number(n.replace(/\s| /g, '')));
    const permis = new Set([30, 3000, 30000, 2024, 20, 23]);
    for (const n of nombres) expect(permis.has(n), `nombre inattendu ${n}`).toBe(true);
  });

  it('règle absente ou malformée → null ; textes sans fr → null (jamais inventés)', () => {
    expect(syntheseAgricoleArgent(payload(sans('aide_fda')))!.aideFda).toBeNull();
    expect(syntheseAgricoleArgent(payload({ ...SERVIE, aide_fda: { ...SERVIE.aide_fda, textes: { en: 'x' } } }))!.aideFda!.textes).toBeNull();
    const nuls = syntheseAgricoleArgent(payload({ ...SERVIE, aide_fda: { plafonds: { taux_pct: 'trente' } } }))!.aideFda!;
    expect(nuls.plafonds.tauxPct).toBeNull();
  });
});

describe('AGW304 — garanties par composant : jamais complétées par une constante', () => {
  it('une durée servie est dite en mots, une durée non servie reste le libellé servi', () => {
    const [pompe, variateur] = syntheseAgricoleArgent(payload(SERVIE))!.garanties;
    expect(libelleGarantie(pompe)).toEqual({
      lbl: { fr: 'Garantie constructeur de la pompe : 2 ans', en: 'Pump manufacturer warranty: 2 years', ar: 'ضمان الصانع للمضخة: 2 سنوات' },
      avecDuree: true,
    });
    const v = libelleGarantie(variateur);
    expect(v.avecDuree).toBe(false);
    expect(v.lbl.fr).toBe('Garantie constructeur non renseignée');
    // aucune durée inventée à la place
    expect(v.lbl.fr).not.toMatch(/\d/);
  });

  it('dureeGarantie : 24 → 2 ans, 12 → 1 an, 18 → 18 mois', () => {
    expect(dureeGarantie(24).fr).toBe('2 ans');
    expect(dureeGarantie(12).fr).toBe('1 an');
    expect(dureeGarantie(18).fr).toBe('18 mois');
  });

  it('une durée nulle ou non entière est ignorée (jamais 0 mois)', () => {
    const a = syntheseAgricoleArgent(payload({ ...SERVIE, garanties: [
      { composant: 'pompe', mois: 0, libelle: 'x' },
      { composant: 'variateur', mois: 18.5, libelle: 'y' },
    ] }))!;
    expect(a.garanties.map((g) => g.mois)).toEqual([null, null]);
  });

  it('en agricole, le bloc de garanties codé en dur (30/10/2 ans) n’est PAS affiché', () => {
    expect(garantiesCodeesEnDurAffichees('agricole')).toBe(false);
    expect(garantiesCodeesEnDurAffichees('residentiel')).toBe(true);
    expect(garantiesCodeesEnDurAffichees('industriel')).toBe(true);
    expect(garantiesCodeesEnDurAffichees(undefined)).toBe(true);
  });
});

describe('AGW304 — options du kit, non-inclus, formalités', () => {
  it('une option sans désignation est écartée ; un supplément absent reste null', () => {
    const a = syntheseAgricoleArgent(payload({ ...SERVIE, options_kit: [
      { ligne_id: 1, designation: '', total_ttc: 10 },
      { ligne_id: 2, designation: 'Sonde de niveau' },
      'x',
    ] }))!;
    expect(a.optionsKit).toEqual([{ ligneId: 2, designation: 'Sonde de niveau', totalTtc: null }]);
  });
  it('clés absentes → listes vides (jamais un bloc fabriqué)', () => {
    const a = syntheseAgricoleArgent(payload({ ...SERVIE, options_kit: undefined, non_inclus: undefined, formalites: undefined, garanties: undefined }))!;
    expect(a.optionsKit).toEqual([]);
    expect(a.nonInclus).toEqual([]);
    expect(a.formalites).toEqual([]);
    expect(a.garanties).toEqual([]);
  });
  it('non inclus : forage et génie civil, dits en trois langues', () => {
    expect(AGR_NON_INCLUS_LBL.forage.en).toBe('the borehole');
    expect(AGR_NON_INCLUS_LBL.genie_civil.ar.length).toBeGreaterThan(3);
  });
});

describe('AGW304 — la page', () => {
  const page = lire('../src/pages/proposition/[...token].astro');
  const lib = lire('../src/lib/proposition.ts');

  it('chaque bloc argent est gaté sur sa donnée servie', () => {
    expect(page).toContain('{argent?.economies && (');
    expect(page).toContain('{argent?.energieActuelle && energieLbl && (');
    expect(page).toContain('{argent?.aideFda?.textes && (');
    expect(page).toContain('{argent && argent.optionsKit.length > 0 && (');
    expect(page).toContain('{argent && argent.formalites.length > 0 && (');
    expect(page).toContain('{isAgricole && argent && argent.garanties.length > 0 && (');
  });

  it('la carte FDA ne rend QUE les textes servis (aucun nombre écrit dans la page)', () => {
    const a = page.indexOf('data-agri-fda');
    const bloc = page.slice(a, page.indexOf('</div>', a));
    expect(bloc).toContain('argent.aideFda.textes.fr');
    // hors balises (classes CSS incluses), le texte de la carte ne contient aucun chiffre écrit en dur
    expect(bloc.replace(/<[^>]*>/g, ' ')).not.toMatch(/\d/);
  });

  it('le bloc de garanties codé en dur est gaté hors agricole', () => {
    expect(page).toContain('{garantiesCodeesEnDurAffichees(installMode) && (');
  });

  it('les options du kit sont en lecture seule (aucun bouton d’activation dans AGW304)', () => {
    const a = page.indexOf('data-agri-options-kit');
    const bloc = page.slice(a, page.indexOf('data-agri-non-inclus'));
    expect(bloc).not.toMatch(/<button/);
  });

  it('vocabulaire interdit : jamais « gratuit », « à vie », « illimité » ni « jusqu’à 30 % »', () => {
    const textes = JSON.stringify([AGR_ARGENT_LBL, AGR_ENERGIE_LBL, AGR_NON_INCLUS_LBL]);
    expect(textes).not.toMatch(/gratuit|à vie|illimité|free|lifetime|unlimited|jusqu['’]à 30|up to 30/i);
    const section = page.slice(page.indexOf('data-agri-argent'), page.indexOf('id="mode-autoconso"'));
    expect(section).not.toMatch(/gratuit|à vie|illimité|jusqu['’]à/i);
    // la lib ne contient pas non plus de constante de prix du carburant ni de % FDA
    const code = lib.replace(/^\s*\/\/.*$/gm, '').replace(/\/\*[\s\S]*?\*\//g, '');
    const zone = code.slice(code.indexOf('function lireEconomies'), code.indexOf('export function dureeGarantie'));
    expect(zone).not.toMatch(/\*\s*365|0\.3\b|prix_gaz|prix_butane|litres_par_cv/i);
  });
});
