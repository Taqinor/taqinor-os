import { beforeEach, describe, expect, it } from 'vitest';
import { compterLignes, executer, LIGNES_MAX, tropLongs } from '../scripts/check-file-size.mjs';
import { LIMITE_PAR_MINUTE, masquer, reinitialiserLimite, TAILLE_MAX, traiterRapport } from '../src/lib/clientError';

describe('YBW20 — limite de taille des fichiers', () => {
  it('cas négatif : un fichier de 801 lignes est refusé, 800 accepté', () => {
    const fichier = (n: number) => Array.from({ length: n }, (_, i) => `ligne ${i}`).join('\n') + '\n';
    expect(LIGNES_MAX).toBe(800);
    expect(compterLignes(fichier(800))).toBe(800);
    expect(tropLongs([{ fichier: 'src/gros.astro', contenu: fichier(801) }])).toEqual([{ fichier: 'src/gros.astro', lignes: 801 }]);
    expect(tropLongs([{ fichier: 'src/ok.ts', contenu: fichier(800) }])).toEqual([]);
  });

  it('le site réel : aucun fichier au-delà de la limite', () => {
    expect(executer()).toEqual([]);
  });
});

const URL_API = 'https://site.test/api/client-error';
const poster = (corps: string, entetes: Record<string, string> = {}) =>
  new Request(URL_API, { method: 'POST', body: corps, headers: { 'content-type': 'application/json', 'sec-fetch-site': 'same-origin', ...entetes } });

describe('YBW20 — rapport d’erreurs client (journal seulement, sans donnée personnelle)', () => {
  beforeEach(() => reinitialiserLimite());

  it('un rapport valide est journalisé nettoyé : 204', async () => {
    const lignes: string[] = [];
    const r = await traiterRapport(
      poster(
        JSON.stringify({
          type: 'error',
          message: 'x is undefined — contact jean.dupont@exemple.fr au +33 6 12 34 56 78',
          fichier: 'https://site.test/_astro/a.js?v=1',
          ligne: 3,
          colonne: 7,
          page: '/rendez-vous/?email=jean@exemple.fr#f',
          ip: '1.2.3.4',
          agent: 'Mozilla',
        }),
      ),
      (l) => lignes.push(l),
    );
    expect(r.status).toBe(204);
    expect(lignes).toHaveLength(1);
    const j = JSON.parse(lignes[0]);
    expect(j).toEqual({ type: 'error', message: expect.any(String), fichier: '/_astro/a.js', ligne: 3, colonne: 7, page: '/rendez-vous/' });
    expect(lignes[0]).not.toMatch(/jean|exemple\.fr|12 34|1\.2\.3\.4|Mozilla/);
  });

  it('cas négatifs : autre origine 403, trop gros 413, JSON invalide 400, GET 405', async () => {
    const rien = () => undefined;
    expect((await traiterRapport(poster('{}', { 'sec-fetch-site': 'cross-site' }), rien)).status).toBe(403);
    expect((await traiterRapport(poster('x'.repeat(TAILLE_MAX + 1)), rien)).status).toBe(413);
    expect((await traiterRapport(poster('pas du json'), rien)).status).toBe(400);
    expect((await traiterRapport(poster('[1]'), rien)).status).toBe(400);
    expect((await traiterRapport(new Request(URL_API), rien)).status).toBe(405);
  });

  it('limite par isolat : au-delà de la limite par minute → 429, puis remise à zéro', async () => {
    const t = 1_000_000_000_000;
    for (let i = 0; i < LIMITE_PAR_MINUTE; i++) expect((await traiterRapport(poster('{}'), () => undefined, t)).status).toBe(204);
    expect((await traiterRapport(poster('{}'), () => undefined, t)).status).toBe(429);
    expect((await traiterRapport(poster('{}'), () => undefined, t + 60_000)).status).toBe(204);
  });

  it('masquer borne et masque', () => {
    expect(masquer('a'.repeat(500))).toHaveLength(300);
    expect(masquer('mail a@b.co tel 0612345678')).toBe('mail [masqué] tel [masqué]');
  });
});
