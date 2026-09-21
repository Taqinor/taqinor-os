// CALX109 — LE MODULE POSÉ SUR CHAQUE PAN, AVEC SES VRAIES COTES.
//
// CE QUE CE FICHIER PROUVE :
//   1. L'ÉCHANTILLON COMMITTÉ EST LU TEL QUEL. Le contrat
//      `backend/.../contract_samples/calepinage_modules_disponibles.json` est le MÊME
//      fichier que le test backend affirme (PACT10) : il est lu ici depuis le dépôt, jamais
//      recopié ni paraphrasé — une divergence entre les deux moitiés rougit des DEUX côtés.
//   2. AUCUN MODULE CHOISI ⇒ PAVAGE IDENTIQUE À CELUI D'AUJOURD'HUI. C'est la garantie de
//      non-régression : le module par défaut de l'atelier reste le repli, et il est NOMMÉ.
//   3. UN MODULE DE 2,0 × 1,0 m CHANGE LE NOMBRE DE RANGÉES. C'est la garantie que les
//      vraies cotes sont bien celles qui pavent — pas une décoration d'écran.
//
// Aucun DOM, aucun Three, aucun réseau : tout est pur.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  ID_MODULE_PAR_DEFAUT,
  MODULE_PAR_DEFAUT_ATELIER,
  cotesDeModule,
  cotesPourPan,
  estRefus,
  lireModulesDisponibles,
  resoudreModuleDuPan,
  type ModuleDocument,
} from './moduleSelect';
import {
  MODULE_ATELIER_PAR_DEFAUT,
  PANEL2_LONG_M,
  PANEL2_SHORT_M,
  PANEL2_WATT,
  layoutProRows2,
  type ProLayout2,
} from '../../lib/roofPro2';
import { type LngLat } from '../../lib/roof';

/** L'échantillon de contrat, LU dans le dépôt (jamais recopié ici). */
const CONTRAT = JSON.parse(readFileSync(fileURLToPath(new URL(
  '../../../../../backend/django_core/apps/calepinage/contract_samples/calepinage_modules_disponibles.json',
  import.meta.url,
)), 'utf-8')) as {
  endpoint: string;
  exemple: { modules: unknown[]; champs_requis: string[]; motif_liste_vide: string | null };
  exemple_vide: { modules: unknown[]; motif_liste_vide: string | null };
};

function carre(cote: number, lng0 = -7.6, lat0 = 33.5): LngLat[] {
  const dLat = cote / 111320;
  const dLng = cote / (111320 * Math.cos((lat0 * Math.PI) / 180));
  return [
    [lng0 - dLng / 2, lat0 - dLat / 2],
    [lng0 + dLng / 2, lat0 - dLat / 2],
    [lng0 + dLng / 2, lat0 + dLat / 2],
    [lng0 - dLng / 2, lat0 + dLat / 2],
  ];
}

/** Le nombre de RANGÉES d'un pavage : les centres projetés sur l'axe de montée. */
function nombreDeRangees(layout: ProLayout2): number {
  const sx = -Math.sin(layout.rowAngleRad);
  const sy = Math.cos(layout.rowAngleRad);
  return new Set(layout.panels.map((p) => Math.round((p.cx * sx + p.cy * sy) * 1000))).size;
}

function module(partiel: Partial<ModuleDocument> & { id: string }): ModuleDocument {
  return {
    produitId: null,
    libelle: `Module ${partiel.id}`,
    longueurMm: 2000,
    largeurMm: 1000,
    epaisseurMm: 30,
    poidsKg: 22,
    pmaxWc: 400,
    source: 'fiche produit',
    ...partiel,
  };
}

describe("CALX109 — l'échantillon de contrat est lu tel qu'il est committé", () => {
  it("l'endpoint du contrat est celui que l'atelier appellera", () => {
    expect(CONTRAT.endpoint).toBe(
      'GET /api/django/calepinage/calepinages/<int:pk>/modules-disponibles/');
  });

  it('les fiches complètes sont choisissables, les incomplètes restent listées', () => {
    const catalogue = lireModulesDisponibles(CONTRAT.exemple);
    expect(catalogue.choisissables.map((m) => m.id)).toEqual(['produit-4112']);
    expect(catalogue.grises.map((g) => g.module.id)).toEqual(['produit-4130']);
    expect(catalogue.grises[0].motif).toContain('puissance crête');
    expect(catalogue.motifListeVide).toBeNull();
  });

  it('les cotes arrivent dans la forme du document, en millimètres', () => {
    const [premier] = lireModulesDisponibles(CONTRAT.exemple).choisissables;
    expect(premier.longueurMm).toBe(2278);
    expect(premier.largeurMm).toBe(1134);
    expect(premier.pmaxWc).toBe(580);
    expect(premier.source).toBe('fiche produit');
  });

  it('un catalogue vide rend le motif DU SERVEUR, jamais un motif inventé', () => {
    const catalogue = lireModulesDisponibles(CONTRAT.exemple_vide);
    expect(catalogue.choisissables).toEqual([]);
    expect(catalogue.motifListeVide).toBe(CONTRAT.exemple_vide.motif_liste_vide);
  });

  it('les champs requis du serveur sont ceux qui décident du pavage', () => {
    expect(CONTRAT.exemple.champs_requis).toEqual(['longueurMm', 'largeurMm', 'pmaxWc']);
    for (const champ of CONTRAT.exemple.champs_requis) {
      const incomplet = module({ id: 'x', [champ]: null } as Partial<ModuleDocument> & { id: string });
      const cotes = cotesDeModule(incomplet);
      expect(estRefus(cotes)).toBe(true);
      expect((cotes as { champ: string }).champ).toBe(champ);
    }
  });

  it('une réponse absente ou mal formée ne jette jamais', () => {
    for (const brut of [null, undefined, 42, 'oui', {}, { modules: 'non' }]) {
      expect(lireModulesDisponibles(brut).choisissables).toEqual([]);
    }
  });
});

describe('CALX109 — aucun module choisi : le pavage est celui d’aujourd’hui', () => {
  it('le repli est le module par défaut de l’atelier, et il est NOMMÉ', () => {
    const cotes = cotesPourPan([], undefined);
    expect(estRefus(cotes)).toBe(false);
    expect(cotes).toEqual(MODULE_ATELIER_PAR_DEFAUT);
    expect(MODULE_PAR_DEFAUT_ATELIER.id).toBe(ID_MODULE_PAR_DEFAUT);
    expect(MODULE_PAR_DEFAUT_ATELIER.libelle).toContain("l'atelier");
    expect(MODULE_PAR_DEFAUT_ATELIER.pmaxWc).toBe(PANEL2_WATT);
  });

  it('le pavage sans option est IDENTIQUE au pavage avec le module par défaut', () => {
    const ring = carre(28);
    const aujourdHui = layoutProRows2(ring, 'sud', 33.5);
    const explicite = layoutProRows2(ring, 'sud', 33.5, { module: MODULE_ATELIER_PAR_DEFAUT });
    expect(explicite).toEqual(aujourdHui);
    expect(aujourdHui.dims.alongRow).toBeCloseTo(PANEL2_LONG_M, 6);
    expect(aujourdHui.dims.slope).toBeCloseTo(PANEL2_SHORT_M, 6);
    expect(aujourdHui.kwc).toBeCloseTo((aujourdHui.count * PANEL2_WATT) / 1000, 9);
  });
});

describe('CALX109 — un module de 2,0 × 1,0 m change le nombre de rangées', () => {
  const ring = carre(28);
  const petit = { longM: 2.0, courtM: 1.0, epaisM: 0.03, watt: 450 };

  it('les cotes du module choisi remplacent les constantes', () => {
    const pave = layoutProRows2(ring, 'sud', 33.5, { module: petit });
    expect(pave.dims.alongRow).toBeCloseTo(2.0, 9);
    expect(pave.dims.slope).toBeCloseTo(1.0, 9);
  });

  it('le pas de rangée et le nombre de rangées suivent la cote du module', () => {
    const aujourdHui = layoutProRows2(ring, 'sud', 33.5);
    const pave = layoutProRows2(ring, 'sud', 33.5, { module: petit });
    // 1,0 m dans le sens de la pente au lieu de 1,303 : empreinte ET ombre plus courtes,
    // donc un pas plus serré — et donc PLUS de rangées sur le même toit.
    expect(pave.rowPitchM).toBeLessThan(aujourdHui.rowPitchM);
    expect(nombreDeRangees(pave)).toBeGreaterThan(nombreDeRangees(aujourdHui));
  });

  it('le kWc est celui du module posé, jamais la constante de l’atelier', () => {
    const pave = layoutProRows2(ring, 'sud', 33.5, { module: petit });
    expect(pave.kwc).toBeCloseTo((pave.count * 450) / 1000, 9);
  });
});

describe('CALX82 — un module introuvable est REFUSÉ en nommant le champ', () => {
  const catalogue = [module({ id: 'produit-1' })];

  it('un moduleId absent du catalogue nomme `moduleId`', () => {
    const refus = resoudreModuleDuPan(catalogue, 'mod-fantome');
    expect(estRefus(refus)).toBe(true);
    expect((refus as { champ: string }).champ).toBe('moduleId');
    expect((refus as { message: string }).message).toContain('mod-fantome');
  });

  it('une fiche sans puissance nomme `pmaxWc` et ne retombe sur rien', () => {
    const refus = cotesDeModule(module({ id: 'produit-2', pmaxWc: null }));
    expect(estRefus(refus)).toBe(true);
    expect((refus as { champ: string }).champ).toBe('pmaxWc');
    expect((refus as { message: string }).message).toContain('puissance crête');
  });

  it('le grand côté est la plus grande des deux cotes, quel que soit leur ordre', () => {
    const couche = cotesDeModule(module({ id: 'a', longueurMm: 1000, largeurMm: 2000 }));
    expect(couche).toMatchObject({ longM: 2, courtM: 1 });
  });
});
