import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { GitCompare } from 'lucide-react'
import calepinageApi from '../../../api/calepinageApi'
import { EmptyState, Spinner } from '../../../ui'
import { formatDateTime } from '../../../lib/format'
import { PARAM_ONGLET } from './onglets'

/* ============================================================================
   CALX346 — MONTER LE DIFFÉRENTIEL DE VERSIONS EN ONGLET DE L'ATELIER.
   ----------------------------------------------------------------------------
   Constat : `calepinageApi.js:94-96` déclare déjà `versions`/`restaurerVersion`
   (CALX36, `atelier/PanneauVersions.jsx`) — SEUL le COMPTE de versions y est
   utile, aucun écran ne confronte deux versions champ par champ, alors que
   `GET .../versions/<id>/diff/?contre=<id>` (CALX345, contrat
   `calepinage_versions_diff.json`) rend déjà ce différentiel, LECTURE PURE.

   « GAUCHE » = la version choisie à gauche ; « DROITE », SANS choix explicite,
   est l'ÉTAT COURANT du calepinage (`id: null`, CALX345 : « qu'est-ce qui a
   changé depuis cette version ? ») — l'option par défaut du second sélecteur.

   LA RESTAURATION N'EST PAS DUPLIQUÉE ICI (elle appartient à
   `PanneauVersions.jsx`, CALX36, seul point d'écriture) : ce panneau ne fait
   qu'y renvoyer par un lien profond (`?onglet=versions`) — LECTURE PURE, zéro
   bouton d'écriture sur cet onglet.
   ========================================================================== */

const ETAT_COURANT = '' // valeur du sélecteur de droite pour « état courant »

export default function DiffVersions({ calepinageId: idPropose } = {}) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl

  const [versions, setVersions] = useState(null)
  const [erreurListe, setErreurListe] = useState(null)
  const [gaucheId, setGaucheId] = useState('')
  const [droiteId, setDroiteId] = useState(ETAT_COURANT)
  const [diff, setDiff] = useState(null)
  const [chargement, setChargement] = useState(false)
  const [erreurDiff, setErreurDiff] = useState(null)

  useEffect(() => {
    if (!calepinageId) return
    Promise.resolve(calepinageApi.calepinages.versions(calepinageId))
      .then((res) => {
        const liste = Array.isArray(res?.data) ? res.data : []
        setVersions(liste)
        // Par défaut : la version la PLUS ANCIENNE des deux dernières contre
        // l'état courant — le cas le plus souvent utile à l'ouverture.
        setGaucheId((precedent) => precedent || (liste.length ? String(liste[liste.length > 1 ? 1 : 0].id) : ''))
      })
      .catch(() => setErreurListe('L’historique des versions n’a pas pu être chargé.'))
  }, [calepinageId])

  const comparer = useCallback(() => {
    if (!calepinageId || !gaucheId) return undefined
    // Aucun setState SYNCHRONE sur le chemin de l'effet (react-hooks v7) :
    // les marqueurs de départ passent par la microtâche, comme le reste.
    return Promise.resolve()
      .then(() => { setChargement(true); setErreurDiff(null) })
      .then(() => calepinageApi.calepinages.versionsDiff(calepinageId, gaucheId, droiteId || undefined))
      .then((res) => setDiff(res?.data || null))
      .catch(() => { setErreurDiff('Le différentiel n’a pas pu être calculé.'); setDiff(null) })
      .finally(() => setChargement(false))
  }, [calepinageId, gaucheId, droiteId])

  useEffect(() => { comparer() }, [comparer])

  const libelleVersion = (v) =>
    `${v.libelle || `Version ${v.id}`} — ${formatDateTime(v.cree_le)}`

  return (
    <div className="mt-6" data-testid="cal-diff-versions">
      <p className="tech-label rule-brass text-brass-300">Comparer les versions</p>
      <p className="mt-2 text-xs text-lune-faint" data-testid="cal-diff-versions-rappel">
        Le différentiel est borné aux grandeurs comptables du document (modules,
        kWc, pans, obstacles, orientation et inclinaison par pan, empreinte,
        version du moteur) — jamais un diff de JSON brut. Pour restaurer une
        version, ouvrez l’onglet{' '}
        <Link
          to={`/calepinage/${calepinageId}?${PARAM_ONGLET}=versions`}
          className="underline"
          data-testid="cal-diff-versions-lien-versions"
        >
          Versions
        </Link>.
      </p>

      {erreurListe && (
        <p role="alert" className="mt-3 text-sm text-destructive" data-testid="cal-diff-versions-erreur-liste">
          {erreurListe}
        </p>
      )}

      {versions === null ? (
        <div className="mt-3 flex items-center gap-2 text-sm text-lune-faint">
          <Spinner />
          Chargement des versions…
        </div>
      ) : versions.length < 1 ? (
        <EmptyState
          icon={GitCompare}
          title="Aucune version à comparer"
          description="Un instantané apparaît ici à chaque écriture sur la conception."
        />
      ) : (
        <>
          <div className="mt-3 flex flex-wrap gap-4">
            <label className="flex flex-col gap-1 text-xs text-lune-soft">
              Version de gauche
              <select
                className="rounded border border-border/60 bg-transparent px-2 py-1 text-sm text-white"
                value={gaucheId}
                onChange={(e) => setGaucheId(e.target.value)}
                data-testid="cal-diff-versions-gauche"
              >
                {versions.map((v) => (
                  <option key={v.id} value={v.id}>{libelleVersion(v)}</option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs text-lune-soft">
              Version de droite
              <select
                className="rounded border border-border/60 bg-transparent px-2 py-1 text-sm text-white"
                value={droiteId}
                onChange={(e) => setDroiteId(e.target.value)}
                data-testid="cal-diff-versions-droite"
              >
                <option value={ETAT_COURANT}>État courant</option>
                {versions.map((v) => (
                  <option key={v.id} value={v.id}>{libelleVersion(v)}</option>
                ))}
              </select>
            </label>
          </div>

          {chargement && (
            <div className="mt-3 flex items-center gap-2 text-sm text-lune-faint">
              <Spinner />
              Calcul du différentiel…
            </div>
          )}

          {erreurDiff && (
            <p role="alert" className="mt-3 text-sm text-destructive" data-testid="cal-diff-versions-erreur">
              {erreurDiff}
            </p>
          )}

          {!chargement && diff && (
            diff.ecarts.length === 0 ? (
              <EmptyState
                icon={GitCompare}
                title="Aucun écart"
                description="Ces deux versions sont identiques sur les grandeurs comparées."
              />
            ) : (
              <table className="mt-3 w-full text-sm" data-testid="cal-diff-versions-tableau">
                <thead>
                  <tr className="text-left text-xs text-lune-faint">
                    <th className="pb-1 pr-3">Champ</th>
                    <th className="pb-1 pr-3">Avant</th>
                    <th className="pb-1">Après</th>
                  </tr>
                </thead>
                <tbody>
                  {diff.ecarts.map((ecart) => (
                    <tr key={ecart.champ} data-testid={`cal-diff-versions-ligne-${ecart.champ}`}>
                      <td className="py-1 pr-3 text-white">{ecart.libelle}</td>
                      <td className="py-1 pr-3 text-muted-foreground">
                        {ecart.avant ?? '—'}
                      </td>
                      <td className="py-1 text-muted-foreground">
                        {ecart.apres ?? '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )
          )}
        </>
      )}
    </div>
  )
}
