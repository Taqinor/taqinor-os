/**
 * ACAL472 — proposer le cheminement d'un câble entre deux organes : plus court
 * chemin (Dijkstra) sur un graphe dont les arêtes suivent l'axe de chaque rangée
 * de modules et la rive du toit. Fonction PURE, en mètres (repère ENU) : jamais
 * une droite supposée — sans chemin possible, le motif le dit.
 */
export type Pt = [number, number];
export interface EntreeCheminement {
  de: Pt;
  vers: Pt;
  /** L'axe de chaque rangée : [début, fin]. */
  rangees: ReadonlyArray<readonly [Pt, Pt]>;
  /** La rive (anneau) du toit, retraitée par l'appelant. */
  rive: readonly Pt[];
}
export type ResultatCheminement = { ok: true; points: Pt[] } | { ok: false; motif: string };

const dist = (a: Pt, b: Pt): number => Math.hypot(a[0] - b[0], a[1] - b[1]);

/** Projection de `p` sur le segment [a, b] : point et paramètre t dans [0, 1]. */
function projeter(p: Pt, a: Pt, b: Pt): { q: Pt; t: number } {
  const [dx, dy] = [b[0] - a[0], b[1] - a[1]];
  const long2 = dx * dx + dy * dy;
  const t = long2 === 0 ? 0 : Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / long2));
  return { q: [a[0] + t * dx, a[1] + t * dy], t };
}

export function proposerPointsCheminement(e: EntreeCheminement): ResultatCheminement {
  const m = e.rive.length;
  if (m < 3) return { ok: false, motif: 'Aucune rive de toit exploitable : le tracé ne peut suivre ni rangée ni rive.' };
  const noeuds: Pt[] = [e.de, e.vers, ...e.rive];
  const adj: Array<Array<[number, number]>> = noeuds.map(() => []);
  const lier = (i: number, j: number): void => {
    const w = dist(noeuds[i], noeuds[j]);
    adj[i].push([j, w]);
    adj[j].push([i, w]);
  };
  const sur: Array<Array<[number, number]>> = e.rive.map(() => []); // par arête de rive : [t, noeud]
  const poser = (p: Pt): number => { noeuds.push(p); adj.push([]); return noeuds.length - 1; };
  const accrocher = (i: number): void => {
    let best = { k: 0, q: noeuds[i], t: 0, d: Infinity };
    for (let k = 0; k < m; k++) {
      const pr = projeter(noeuds[i], e.rive[k], e.rive[(k + 1) % m]);
      const d = dist(noeuds[i], pr.q);
      if (d < best.d) best = { k, ...pr, d };
    }
    const j = poser(best.q);
    sur[best.k].push([best.t, j]);
    lier(i, j);
  };
  accrocher(0);
  accrocher(1);
  for (const [a, b] of e.rangees) {
    const [ia, ib] = [poser(a), poser(b)];
    lier(ia, ib);
    accrocher(ia);
    accrocher(ib);
  }
  for (let k = 0; k < m; k++) {
    const chaine = [[0, 2 + k], ...sur[k].sort((x, y) => x[0] - y[0]), [1, 2 + ((k + 1) % m)]];
    for (let i = 1; i < chaine.length; i++) lier(chaine[i - 1][1], chaine[i][1]);
  }
  const cout = noeuds.map(() => Infinity);
  const prec = noeuds.map(() => -1);
  const vu = noeuds.map(() => false);
  cout[0] = 0;
  for (;;) {
    let u = -1;
    for (let i = 0; i < noeuds.length; i++) if (!vu[i] && cout[i] < Infinity && (u < 0 || cout[i] < cout[u])) u = i;
    if (u < 0 || u === 1) break;
    vu[u] = true;
    for (const [v, w] of adj[u]) if (cout[u] + w < cout[v]) { cout[v] = cout[u] + w; prec[v] = u; }
  }
  if (cout[1] === Infinity) return { ok: false, motif: 'Aucun chemin entre les deux organes le long des rangées et de la rive.' };
  const points: Pt[] = [];
  for (let i = 1; i >= 0; i = prec[i]) {
    if (!points.length || dist(points[0], noeuds[i]) > 1e-9) points.unshift(noeuds[i]);
    if (i === 0) break;
  }
  return { ok: true, points };
}
