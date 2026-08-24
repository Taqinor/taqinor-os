// L-PCMP (ordre fondateur, 24/08/2026) — page de proposition publique : « le
// client doit pouvoir CHANGER son profil de consommation parmi les 3
// silhouettes d'occupation existantes et voir DIRECTEMENT les économies de
// chaque comportement, plus un message montrant L'INSTALLATION OPTIMALE pour
// chaque configuration. »
//
// LA GARANTIE QUE CES TESTS PROTÈGENT : aucune économie n'est calculée par la
// page. Les trois blocs sont CALCULÉS PAR LE MOTEUR côté serveur
// (`apps/ventes/profils_comparatifs.py` → `profils_comparatifs` du payload
// public), et la page se contente d'afficher celui que le visiteur choisit.
//
// `occupancyScenarios` est le parseur PUR (même discipline « zéro chiffre
// inventé » que `storageSweepInfo` / `batteryRegimeInfo`) : `null` sur une clé
// absente/malformée. Les tests « Source pin » pincent le câblage RÉEL dans
// [...token].astro (commentaires retirés — un commentaire ne doit jamais faire
// passer un test).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { occupancyScenarios } from '../src/lib/proposition';
import { OCCUPANCY_IDS } from '../src/lib/dayProfiles';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8');
const PAGE = read('../src/pages/proposition/[...token].astro').replace(/\r\n/g, '\n');
const CODE = PAGE
  .replace(/<!--[\s\S]*?-->/g, ' ')
  .replace(/\{\/\*[\s\S]*?\*\/\}/g, ' ')
  .replace(/\/\*[\s\S]*?\*\//g, ' ')
  .replace(/^[ \t]*\/\/.*$/gm, ' ');

// L'échantillon partagé porte l'enveloppe PACT10 {endpoint, pourquoi, exemple}
// exigée par check_api_shapes ; le payload vit sous exemple.profils_comparatifs.
const CONTRAT = JSON.parse(read(
  '../../../backend/django_core/apps/ventes/contract_samples/profils_comparatifs.json',
)).exemple.profils_comparatifs;

describe('occupancyScenarios — les 3 silhouettes, chiffres SERVEUR', () => {
  it('null quand `profils_comparatifs` est absent ou vide', () => {
    expect(occupancyScenarios({})).toBeNull();
    expect(occupancyScenarios({ profils_comparatifs: null })).toBeNull();
    expect(occupancyScenarios({ profils_comparatifs: {} })).toBeNull();
    expect(occupancyScenarios({ profils_comparatifs: { profils: [] } })).toBeNull();
  });

  it('lit le contrat PARTAGÉ tel quel (PACT10) — les 3 silhouettes servies', () => {
    const r = occupancyScenarios({ profils_comparatifs: CONTRAT });
    expect(r).not.toBeNull();
    expect(r!.scenarios.map((s) => s.occupancy)).toEqual([...OCCUPANCY_IDS]);
    expect(r!.profilReel).toBe('presence_jour');
    expect(r!.avecBatterie).toBe(true);
    // Les nombres sont ceux du contrat, RECOPIÉS — jamais recalculés.
    expect(r!.scenarios[0].economieSansMad).toBe(CONTRAT.profils[0].economie_sans_mad);
    expect(r!.scenarios[1].economieAvecMad).toBe(CONTRAT.profils[1].economie_avec_mad);
    expect(r!.scenarios[1].tauxAutoconsoAvecPct).toBe(CONTRAT.profils[1].taux_autoconso_avec_pct);
    expect(r!.scenarios[1].optimal).toEqual({
      kwc: CONTRAT.profils[1].optimal.kwc,
      panneaux: CONTRAT.profils[1].optimal.panneaux,
      batterieKwh: CONTRAT.profils[1].optimal.batterie_kwh,
      avecBatterie: true,
      economieMad: CONTRAT.profils[1].optimal.economie_mad,
      identiqueAuDevis: false,
    });
  });

  it('un seul profil porte « votre profil », celui déclaré par le client', () => {
    const r = occupancyScenarios({ profils_comparatifs: CONTRAT })!;
    const reels = r.scenarios.filter((s) => s.estProfilReel).map((s) => s.occupancy);
    expect(reels).toEqual([r.profilReel]);
  });

  it('une silhouette sans économie lisible est OMISE, jamais complétée', () => {
    const r = occupancyScenarios({
      profils_comparatifs: {
        profil_reel: 'presence_jour',
        profils: [
          { occupation: 'presence_jour', est_profil_reel: true, economie_sans_mad: 9000 },
          { occupation: 'absence_jour', economie_sans_mad: null },
          { occupation: 'inconnu_jour', economie_sans_mad: 1234 },
        ],
      },
    });
    expect(r!.scenarios.map((s) => s.occupancy)).toEqual(['presence_jour']);
  });

  it('`identiqueAuDevis` reste null quand le serveur n’a pas pu comparer', () => {
    const r = occupancyScenarios({
      profils_comparatifs: {
        profils: [{
          occupation: 'presence_jour', economie_sans_mad: 9000,
          optimal: { kwc: 6.39, identique_au_devis: null },
        }],
      },
    });
    expect(r!.scenarios[0].optimal!.identiqueAuDevis).toBeNull();
  });

  it('un `optimal` sans kWc exploitable devient null (aucune taille inventée)', () => {
    const r = occupancyScenarios({
      profils_comparatifs: {
        profils: [{ occupation: 'presence_jour', economie_sans_mad: 9000, optimal: { kwc: 0 } }],
      },
    });
    expect(r!.scenarios[0].optimal).toBeNull();
  });
});

describe('Source pin — la page CÂBLE bien le comparatif serveur', () => {
  it('lit `profils_comparatifs` par le parseur, jamais à la main', () => {
    expect(CODE).toContain('occupancyScenarios(data!)');
    expect(CODE).toMatch(/data-occ-compare/);
  });

  it('rend les TROIS blocs côté serveur, un seul visible', () => {
    expect(CODE).toMatch(/data-occ-panel=\{s\.occupancy\}/);
    expect(CODE).toMatch(/hidden=\{s\.occupancy !== occSelected\}/);
  });

  it('présélectionne le profil RÉELLEMENT déclaré par le client', () => {
    expect(CODE).toMatch(/scenarios\.find\(\(s\) => s\.estProfilReel\)/);
    expect(CODE).toContain('· votre profil');
    expect(CODE).toContain('· your profile');
  });

  it('porte le message d’installation optimale dans les trois langues', () => {
    expect(CODE).toContain('Installation optimale pour ce comportement');
    expect(CODE).toContain('Optimal system for this behaviour');
    expect(CODE).toContain('Votre devis est déjà optimal pour ce profil.');
    expect(CODE).toContain('Your quote is already optimal for this profile.');
  });

  it('les libellés du comparatif sont traduisibles (data-i18n fr/en/ar)', () => {
    const bloc = CODE.slice(CODE.indexOf('data-occ-compare'), CODE.indexOf('data-occ-compare') + 4000);
    expect(bloc).toContain('data-i18n');
    expect(bloc).toMatch(/data-ar=/);
  });

  it('AUCUNE arithmétique d’économie dans le script du sélecteur', () => {
    // Le bloc client L-PCMP ne fait que montrer/cacher et restyler : s'il se
    // met un jour à multiplier ou additionner des montants, c'est que la page
    // a recommencé à inventer des chiffres.
    const debut = CODE.indexOf("querySelector<HTMLElement>('[data-occ-compare]')");
    expect(debut).toBeGreaterThan(-1);
    const script = CODE.slice(debut, CODE.indexOf('})();', debut));
    expect(script).not.toMatch(/economie|Economie|\*\s*\d|\/\s*12\b/);
  });
});
