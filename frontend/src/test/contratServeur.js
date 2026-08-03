import { existsSync, readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import process from 'node:process'

/* ============================================================================
   GARDE DE CONTRAT — un mock ne doit pas pouvoir inventer sa propre réponse.
   ----------------------------------------------------------------------------
   Constat de production du 03/08/2026 : les lanes front et back du module
   Appels d'offres ont été construites en parallèle avec deux contrats
   différents. Neuf chemins appelés par `aoApi.js` n'existaient sous AUCUNE
   route (404 sur la Bibliothèque), et plusieurs écrans lisaient des champs
   qu'aucun sérialiseur n'a jamais produits. Les tests étaient VERTS : ils
   mockaient la forme SUPPOSÉE par le front. Un test qui invente sa propre
   réponse ne prouve rien — il prouve qu'il est d'accord avec lui-même.

   Ces helpers relisent la SOURCE serveur (routeur DRF, `Meta.fields` des
   sérialiseurs) pour qu'une fixture ne puisse plus diverger en silence.
   Ils lisent des fichiers Python en texte : aucun runtime Python n'est requis,
   donc aucun coût pour la CI front.
   ========================================================================== */

function racineDepot() {
  let dossier = resolve(process.cwd())
  for (let i = 0; i < 6; i += 1) {
    if (existsSync(join(dossier, 'backend', 'django_core'))) return dossier
    dossier = dirname(dossier)
  }
  throw new Error(`Racine du dépôt introuvable depuis ${process.cwd()}`)
}

/** Chemin absolu d'un fichier de `backend/django_core/apps/ao/`. */
export const fichierAo = (nom) =>
  join(racineDepot(), 'backend', 'django_core', 'apps', 'ao', nom)

/** Les champs déclarés par le `Meta.fields = [...]` d'un sérialiseur DRF. */
export function champsServeur(nomClasse, fichier = 'serializers.py') {
  const source = readFileSync(fichierAo(fichier), 'utf8')
  const debut = source.indexOf(`class ${nomClasse}(`)
  if (debut < 0) throw new Error(`Sérialiseur introuvable côté serveur : ${nomClasse}`)
  const bloc = source.slice(debut, debut + 4000)
  const champs = bloc.match(/\n\s+fields = \[([\s\S]*?)\]/)
  if (!champs) throw new Error(`Meta.fields introuvable pour ${nomClasse}`)
  return new Set([...champs[1].matchAll(/'([^']+)'/g)].map((m) => m[1]))
}

/** Les préfixes de ressource RÉELLEMENT enregistrés par le routeur AO. */
export function ressourcesRoutees() {
  const source = readFileSync(fichierAo('urls.py'), 'utf8')
    + readFileSync(fichierAo('calepinage_urls.py'), 'utf8')
  return new Set(
    [...source.matchAll(/router\.register\(\s*r'([^']+)'/g)].map((m) => m[1]),
  )
}
