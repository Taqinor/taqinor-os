// @vitest-environment jsdom
// CÂBLAGES du lot 2 (Groupe CALX), seconde passe — MÊME contrat que `cablageLot2.test.ts` :
// chaque fonction prouvée ici existait déjà et n'avait AUCUN appelant ; il manquait la
// ligne qui l'appelle. Ce fichier ne prouve que ces lignes-là, jamais une fonctionnalité
// neuve. Les assertions sur un SOURCE ne portent jamais sur plusieurs lignes à la fois
// (CRLF local).
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import { anneauObstacle, anneauxObstruction, type ObstacleEtendu } from './types';
import { TEINTE_ALLEE, poserSourceCellulesSurAllees, teinterAllees, type BufferTeinte } from './teinteAllees';
import {
  ecrireOptimisationDansDocument,
  lireOptimisationDuDocument,
  semerOptimisationDepuisDocument,
} from './optimisationDocument';
import { choixOptimisationCourant, poserChoixOptimisation, poserCibleOptimisation } from './optimizer';
import { LIBELLE_MODE, motifGesteIndisponible, resoudreRaccourci } from './clavier';
import { ID_INFO_BULLE_OMBRAGE, creerInfoBulleOmbrage } from './infoBulleOmbrage';
import { type Ctx } from './context';

/** Les SOURCES câblés ici (pages à effets de bord, non importables en test). Chemins
 *  depuis le dossier de travail (`apps/web`), comme `cablageLot2.test.ts`. */
function source(chemin: string): string {
  return readFileSync(resolve(process.cwd(), chemin), 'utf8');
}
const SOURCE_ENTREE = source('src/scripts/roof-tool-pro11.ts');
const SOURCE_SCENE = source('src/scripts/roofPro11/scene3d.ts');

describe('CALX103/CALX104 câblage — le pavage évite la FORME réelle, plus la boîte', () => {
  const cercle: ObstacleEtendu = {
    id: 'obs-1',
    centerLng: -7.6,
    centerLat: 33.59,
    lengthM: 4,
    widthM: 4,
    forme: 'cercle',
    rayonM: 2,
  };
  const rectangle: ObstacleEtendu = {
    id: 'obs-2',
    centerLng: -7.601,
    centerLat: 33.591,
    lengthM: 2,
    widthM: 1,
  };

  it('un disque rend son anneau dessiné, un rectangle son anneau historique', () => {
    const anneaux = anneauxObstruction([cercle, rectangle]);
    expect(anneaux).toHaveLength(2);
    // Le disque n'est PLUS un quadrilatère : c'est là tout l'intérêt du câblage.
    expect(anneaux[0].length).toBeGreaterThan(4);
    expect(anneaux[0]).toEqual(anneauObstacle(cercle));
    // ÉQUIVALENCE : sans forme saisie, exactement l'anneau d'avant.
    expect(anneaux[1]).toEqual(anneauObstacle(rectangle));
    expect(anneaux[1]).toHaveLength(4);
  });

  it('l’entrée passe les obstacles par `anneauxObstruction` (et plus par `obstacleRing`)', () => {
    expect(SOURCE_ENTREE).toContain('...anneauxObstruction(obstacles), // CALX103/104 câblage');
    expect(SOURCE_ENTREE).not.toContain('...obstacles.map(obstacleRing),');
  });
});

describe('CALX403 câblage — les modules en travers d’une allée sont nommés puis teintés', () => {
  /** Un buffer `instanceColor` minimal : on note qui a été peint et avec quoi. */
  function buffer(): BufferTeinte & { peints: Map<number, [number, number, number]> } {
    const peints = new Map<number, [number, number, number]>();
    return {
      peints,
      needsUpdate: false,
      setXYZ(i: number, x: number, y: number, z: number) {
        peints.set(i, [x, y, z]);
      },
    };
  }

  function ctxNu(): Ctx {
    return {} as unknown as Ctx;
  }

  it('sans source déposée, la scène n’est PAS touchée (comportement d’aujourd’hui)', () => {
    const buf = buffer();
    expect(teinterAllees(ctxNu(), { instanceColor: buf }, [0, 1, 2])).toBe(0);
    expect(buf.peints.size).toBe(0);
    expect(buf.needsUpdate).toBe(false);
  });

  it('seules les instances dont la CELLULE est sur une allée prennent la teinte', () => {
    const ctx = ctxNu();
    poserSourceCellulesSurAllees(ctx, () => [7, 9]);
    const buf = buffer();
    // instance 0 → cellule 7 (sur allée), 1 → 8, 2 → 9 (sur allée), 3 → 10
    expect(teinterAllees(ctx, { instanceColor: buf }, [7, 8, 9, 10])).toBe(2);
    expect([...buf.peints.keys()].sort()).toEqual([0, 2]);
    expect(buf.peints.get(0)).toEqual([TEINTE_ALLEE.r, TEINTE_ALLEE.g, TEINTE_ALLEE.b]);
    // Les autres instances ne sont pas remises à blanc : ce module n’efface le
    // surlignage de personne.
    expect(buf.peints.has(1)).toBe(false);
    expect(buf.needsUpdate).toBe(true);
  });

  it('une source qui jette, ou une allée vide, ne teinte RIEN (jamais un module au hasard)', () => {
    const ctx = ctxNu();
    poserSourceCellulesSurAllees(ctx, () => {
      throw new Error('source cassée');
    });
    expect(teinterAllees(ctx, { instanceColor: buffer() }, [0, 1])).toBe(0);
    poserSourceCellulesSurAllees(ctx, () => []);
    expect(teinterAllees(ctx, { instanceColor: buffer() }, [0, 1])).toBe(0);
    poserSourceCellulesSurAllees(ctx, null);
    expect(teinterAllees(ctx, { instanceColor: buffer() }, [0, 1])).toBe(0);
  });

  it('sans mesh (ou sans instance), la fonction ne fait rien plutôt que de jeter', () => {
    const ctx = ctxNu();
    poserSourceCellulesSurAllees(ctx, () => [0]);
    expect(teinterAllees(ctx, null, [0])).toBe(0);
    expect(teinterAllees(ctx, { instanceColor: null }, [0])).toBe(0);
    expect(teinterAllees(ctx, { instanceColor: buffer() }, [])).toBe(0);
  });

  it('l’entrée donne ses modules posés à `obstaclesUi` et sa source de teinte à la scène', () => {
    expect(SOURCE_ENTREE).toContain('modulesPoses: () => modulesPosesPourAllees(), // CALX403 câblage');
    expect(SOURCE_ENTREE).toContain('poserSourceCellulesSurAllees(ctx, () => cellulesSurAlleesCourantes()); // CALX403 câblage');
    // Le repère d'un module posé est CELUI DU DOCUMENT (CALX111), pas un index maison.
    expect(SOURCE_ENTREE).toContain('etiquette(registreAtelier.modules(panId)[rang], registreAtelier.convention(panId))');
  });

  it('la scène appelle la teinte sur le buffer d’instances de la zone ACTIVE', () => {
    expect(SOURCE_SCENE).toContain('teinterAllees(ctx, panelIM, panelCellIndices); // CALX403 câblage');
  });
});

describe('CALX114 câblage — l’objectif d’optimisation survit au rechargement', () => {
  // État de MODULE partagé (`optimizer.ts`) : on le remet à neuf après chaque cas, sans
  // quoi l'objectif d'un test déborderait sur le suivant.
  afterEach(() => poserChoixOptimisation(null));

  const SOURCE_PREFILL = source('src/scripts/roofPro11/prefill.ts');

  it('aucun objectif saisi ⇒ AUCUNE clé (document d’hier, octet pour octet)', () => {
    poserChoixOptimisation(null);
    const doc: Record<string, unknown> = { version: 2, zones: [] };
    expect(ecrireOptimisationDansDocument(doc)).toBe(false);
    expect('optimisation' in doc).toBe(false);
  });

  it('l’objectif choisi à l’écran est ÉCRIT, puis relu à l’ouverture suivante', () => {
    poserChoixOptimisation({ priorite: 'faitage' });
    poserCibleOptimisation('compte');
    const doc: Record<string, unknown> = { version: 2, zones: [] };
    expect(ecrireOptimisationDansDocument(doc)).toBe(true);
    expect(doc.optimisation).toEqual({ priorite: 'faitage', cible: 'compte' });

    // Rechargement : l'optimiseur repart de zéro, le document le re-sème.
    poserChoixOptimisation(null);
    expect(choixOptimisationCourant()).toBeNull();
    expect(semerOptimisationDepuisDocument(doc)).toEqual({ priorite: 'faitage', cible: 'compte' });
    expect(choixOptimisationCourant()).toEqual({ priorite: 'faitage', cible: 'compte' });
  });

  it('le document écrit est une COPIE : le modifier ne touche pas l’optimiseur', () => {
    poserCibleOptimisation('kwc');
    const doc: Record<string, unknown> = {};
    ecrireOptimisationDansDocument(doc);
    (doc.optimisation as Record<string, unknown>).cible = 'energie';
    expect(choixOptimisationCourant()).toEqual({ cible: 'kwc' });
  });

  it('rouvrir un document SANS objectif efface celui du dossier précédent', () => {
    poserCibleOptimisation('ombrage');
    expect(semerOptimisationDepuisDocument({ version: 2, zones: [] })).toBeNull();
    expect(choixOptimisationCourant()).toBeNull();
  });

  it('un fragment qui n’est pas un objet est IGNORÉ (jamais traduit en objectif)', () => {
    for (const brut of [null, undefined, 'energie', 42, ['energie']]) {
      expect(lireOptimisationDuDocument({ optimisation: brut })).toBeNull();
    }
    // Une cible HORS contrat est déposée telle quelle : c'est `resoudreCibleOptimisation`
    // qui la refuse en la nommant, pas ce module qui la remplace.
    expect(semerOptimisationDepuisDocument({ optimisation: { cible: 'zzz' } })).toEqual({ cible: 'zzz' });
  });

  it('`prefill.ts` porte les DEUX lignes d’appel (lecture et écriture)', () => {
    expect(SOURCE_PREFILL).toContain('semerOptimisationDepuisDocument(json); // CALX114 câblage');
    expect(SOURCE_PREFILL).toContain('ecrireOptimisationDansDocument(layout); // CALX114 câblage');
  });
});

describe('CALX128 câblage — le plan clavier suit l’outil réellement actif', () => {
  it('les gestes de MESURE sont enregistrés auprès de `mapDraw`', () => {
    expect(SOURCE_ENTREE).toContain(
      "mapDraw.enregistrerGestesClavier('mesure', gestesMesure(mesureUi, mapDraw.curseurClavier)); // CALX128 câblage",
    );
  });

  it('le mode est DÉDUIT de l’état de l’atelier, jamais mémorisé à part', () => {
    expect(SOURCE_ENTREE).toContain("if (mesureUi.isActive()) return 'mesure';");
    expect(SOURCE_ENTREE).toContain("if (ctx.obstacleMode) return ctx.pendingZoneNature ? 'zone' : 'obstacle';");
    expect(SOURCE_ENTREE).toContain('mapDraw.setModeClavier(modeClavierCourant()); // CALX128 câblage');
  });

  it('la synchronisation passe en CAPTURE (avant le dispatcher de `mapDraw`)', () => {
    expect(SOURCE_ENTREE).toContain("document.addEventListener('keydown', syncModeClavier, true);");
  });

  it('changer de mode change RÉELLEMENT ce qu’une frappe résout', () => {
    // La même flèche est du plan dans les deux modes, mais l'aide (et donc le refus)
    // NOMME le mode : c'est bien `setModeClavier` qui décide, pas un hasard.
    const flecheEnMesure = resoudreRaccourci({ key: 'ArrowUp' }, 'mesure');
    const flecheEnObstacle = resoudreRaccourci({ key: 'ArrowUp' }, 'obstacle');
    expect(flecheEnMesure).not.toBeNull();
    // Obstacles et zones n'ont AUCUN jeu de gestes dans le dépôt : rien n'est enregistré
    // pour eux, et `mapDraw` annonce alors proprement l'indisponibilité — jamais un geste
    // inventé ici, et jamais un silence.
    if (flecheEnObstacle) {
      expect(motifGesteIndisponible(flecheEnObstacle, 'obstacle')).toContain(LIBELLE_MODE.obstacle);
      expect(motifGesteIndisponible(flecheEnObstacle, 'mesure')).toContain(LIBELLE_MODE.mesure);
    }
  });
});

describe('CALX99 câblage — un azimut pris sur une arête RE-POSE le pavage', () => {
  it('`redraw` appelle la même re-résolution qu’un bouton cardinal', () => {
    expect(SOURCE_ENTREE).toContain("if (roofType === 'pitched' && closed) pitchedRecompute(); // CALX99 câblage");
  });
});

describe('CALX122 câblage — l’ombrage d’un module s’affiche au survol', () => {
  afterEach(() => {
    document.getElementById(ID_INFO_BULLE_OMBRAGE)?.remove();
  });

  it('crée son propre `div` (la page hôte n’en fournit aucun)', () => {
    const bulle = creerInfoBulleOmbrage();
    const el = bulle.element();
    expect(el).not.toBeNull();
    expect(el?.id).toBe(ID_INFO_BULLE_OMBRAGE);
    expect(el?.getAttribute('role')).toBe('status');
    // Rien n'est survolé au départ : elle est cachée, pas vide-et-visible.
    expect(el?.hidden).toBe(true);
    expect(bulle.texte()).toBe('');
  });

  it('un seul `div` pour tout l’atelier (deux créations le réutilisent)', () => {
    const a = creerInfoBulleOmbrage();
    const b = creerInfoBulleOmbrage();
    expect(b.element()).toBe(a.element());
    expect(document.querySelectorAll(`#${ID_INFO_BULLE_OMBRAGE}`)).toHaveLength(1);
  });

  it('affiche EXACTEMENT le texte donné — y compris « non renseigné »', () => {
    const bulle = creerInfoBulleOmbrage();
    // C'est `moduleShadeTooltip` qui produit cette phrase quand aucune obstruction n'est
    // saisie : l'info-bulle la DIT au lieu d'afficher un chiffre.
    const absente = 'Ombrage : non renseigné — aucune obstruction n’a été saisie.';
    expect(bulle.montrer(absente, 100, 200)).toBe(true);
    expect(bulle.texte()).toBe(absente);
    expect(bulle.element()?.hidden).toBe(false);
  });

  it('un module hors plan (texte null) la CACHE, il n’affiche pas « 0 »', () => {
    const bulle = creerInfoBulleOmbrage();
    bulle.montrer('Ombrage : aucune heure masquée pour ce module.', 10, 10);
    expect(bulle.montrer(null, 10, 10)).toBe(false);
    expect(bulle.texte()).toBe('');
    expect(bulle.element()?.hidden).toBe(true);
    // Une chaîne blanche vaut une absence, pas une bulle vide.
    expect(bulle.montrer('   ', 10, 10)).toBe(false);
  });

  it('l’entrée l’alimente avec la cellule SURVOLÉE et le texte de `shadingUi`', () => {
    expect(SOURCE_ENTREE).toContain('const cellule = layoutEditor.layoutPanelAt(e.point);');
    expect(SOURCE_ENTREE).toContain('shadingUi.moduleShadeTooltip(cellule), // CALX122 câblage');
    expect(SOURCE_ENTREE).toContain("map.on('mouseout', () => infoBulleOmbrage.cacher());");
    // Le hit-test est exposé par l'éditeur (interface, append-only).
    const editeur = source('src/scripts/roofPro11/layoutEditor.ts');
    expect(editeur).toContain('layoutPanelAt, // CALX122 câblage');
  });
});

describe('CALX111 câblage — la vue 2D lit les numéros du pan actif', () => {
  it('l’entrée publie le pan ACTIF sur son API', () => {
    expect(SOURCE_ENTREE).toContain("panActifId: () => ctx.activeAreaId ?? '', // CALX111 câblage");
  });
});
