// @vitest-environment jsdom
// CÂBLAGES du lot 2 (Groupe CALX), seconde passe — MÊME contrat que `cablageLot2.test.ts` :
// chaque fonction prouvée ici existait déjà et n'avait AUCUN appelant ; il manquait la
// ligne qui l'appelle. Ce fichier ne prouve que ces lignes-là, jamais une fonctionnalité
// neuve. Les assertions sur un SOURCE ne portent jamais sur plusieurs lignes à la fois
// (CRLF local).
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { anneauObstacle, anneauxObstruction, type ObstacleEtendu } from './types';
import { TEINTE_ALLEE, poserSourceCellulesSurAllees, teinterAllees, type BufferTeinte } from './teinteAllees';
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
