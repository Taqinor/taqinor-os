// QJW1 — `apps/web` ENTRE DANS PACT10 : la garde d'égalité avec le jumeau backend.
//
// CE QUE CETTE GARDE EXISTE POUR ATTRAPER. Le contrat PACT10 dit qu'une
// fonctionnalité à deux moitiés livre son contrat D'ABORD, en un seul fichier
// partagé, pour que deux lanes file-disjointes ne puissent pas inventer deux
// contrats. Jusqu'ici cette discipline s'arrêtait au backend :
// `scripts/check_api_shapes.py` ne connaît que `frontend/src/api/*.js`, et
// `find apps/web -name contract_samples` ne renvoyait RIEN — tout le site
// public était HORS PACT10. La page proposition lisait donc les payloads du
// backend en dictionnaire libre, sans forme partagée : un renommage de clé
// côté serveur restait INVISIBLE jusqu'à ce qu'une page s'affiche vide.
//
// La réponse est un répertoire d'échantillons dans `apps/web`, et CE test :
// chaque copie `apps/web/src/contract_samples/*.json` doit rester JSON-ÉGALE à
// son jumeau `backend/django_core/apps/ventes/contract_samples/*.json`. Toucher
// une moitié sans l'autre fait ROUGIR ce fichier — les deux moitiés ne peuvent
// plus dériver en silence.
//
// LECTURE SEULE HORS `apps/web`. Ce test LIT le fichier backend par chemin
// relatif ; il n'écrit rien en dehors de `apps/web`, et c'est le seul endroit
// du site où un chemin remonte hors du répertoire.
//
// POURQUOI JSON-ÉGAL ET PAS OCTET-ÉGAL. La copie est faite octet à octet, mais
// l'assertion porte sur la VALEUR : c'est le contrat qui doit être identique,
// pas ses fins de ligne — sur Windows, une normalisation CRLF au checkout
// rendrait une garde d'octets rouge sans qu'aucun contrat n'ait bougé. Le
// deuxième test ci-dessous épingle quand même la forme brute (mêmes clés de
// premier niveau, dans le même ordre) pour qu'une réécriture cosmétique du
// jumeau ne passe pas non plus inaperçue.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const lire = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

/** Les échantillons que la moitié `apps/web` du parcours devis consomme. */
const ECHANTILLONS = ['taille_detail.json', 'proposal_data.json'] as const;

const copieWeb = (nom: string) => lire(`../src/contract_samples/${nom}`);
const jumeauBackend = (nom: string) =>
  lire(`../../../backend/django_core/apps/ventes/contract_samples/${nom}`);

describe('QJW1 — les échantillons de contrat de `apps/web` sont les jumeaux du backend', () => {
  it.each(ECHANTILLONS)('%s — la copie `apps/web` est JSON-ÉGALE au fichier backend', (nom) => {
    const web = JSON.parse(copieWeb(nom));
    const backend = JSON.parse(jumeauBackend(nom));
    expect(web).toEqual(backend);
  });

  it.each(ECHANTILLONS)('%s — mêmes clés de premier niveau, dans le même ordre', (nom) => {
    expect(Object.keys(JSON.parse(copieWeb(nom)))).toEqual(
      Object.keys(JSON.parse(jumeauBackend(nom))),
    );
  });

  it('les deux échantillons sont bien du JSON objet non vide (pas un fichier tronqué)', () => {
    for (const nom of ECHANTILLONS) {
      const doc = JSON.parse(copieWeb(nom));
      expect(doc && typeof doc === 'object' && !Array.isArray(doc)).toBe(true);
      expect(Object.keys(doc).length).toBeGreaterThan(0);
    }
  });
});
