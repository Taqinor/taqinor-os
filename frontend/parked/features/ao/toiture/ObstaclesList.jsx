/* AOF90 — Liste d'obstacles synchronisée avec le canvas + garde de publication.
   ----------------------------------------------------------------------------
   Trois choses que cet écran fait et qu'un simple tableau ne fait pas :

   1. IL EST SYNCHRONE AVEC LE CANVAS. Survoler une ligne allume l'emprise sur la
      planche et réciproquement (`survolId` piloté par le parent). Sur 28 emprises
      lettrées, retrouver « celle du milieu à gauche » sans cette liaison prend
      plus de temps que de la remesurer.

   2. IL COMPTE EN PERMANENCE, ET IL COMPTE LES ÉCARTÉS À PART. « 28 obstacles —
      26 mesurés, 2 à confirmer, 0 deviné » est affiché en tête, jamais replié :
      c'est la phrase qu'on relit avant de s'engager sur un nombre de panneaux.
      Les écartés restent listés et filtrables AVEC leur décision — sans requête
      sur les écartés, on ne peut plus chiffrer ce que chaque décision a rapporté.

   3. IL BLOQUE. Tant qu'un obstacle non engageable (relevé sur plan, deviné,
      déclaré par le client, provenance vide) pèse sur le compte, la toiture ne
      peut pas être marquée prête à publier. Le message NOMME les fautifs — un
      « des obstacles sont incertains » n'a jamais fait bouger personne — et
      propose le geste qui débloque : poser la question au client, pré-remplie.

   Toute la règle vit dans `gardePublication.js` (pur, testé hors React) ; cet
   écran ne fait que la rendre. */
import { useCallback, useMemo, useState } from 'react'
import { Button } from '../../../ui/Button'
import {
  PROVENANCES,
  PROVENANCE_ECARTE,
  TRIS,
  compterProvenances,
  evaluerGardePublication,
  filtrerObstacles,
  libelleCompteur,
  provenanceInfo,
  surfaceObstacle,
  trierObstacles,
} from './gardePublication'
import { natureParCle } from './repereLettre'

/* WIR205 — écarter/réintégrer sont des ACTIONS SERVEUR (`ObstacleAOViewSet`) :
   elles n'existent que pour un obstacle DÉJÀ enregistré. Un obstacle tracé à
   l'instant n'a qu'un id local (`obs-A-169…`) — le dire est plus honnête qu'un
   bouton qui produirait un 404. */
const MSG_NON_ENREGISTRE =
  'Obstacle pas encore enregistré : « Enregistrer » d’abord, puis écarter.'

const estEnregistre = (o) =>
  typeof o?.id === 'number' || (typeof o?.id === 'string' && /^\d+$/.test(o.id))

export default function ObstaclesList({
  obstacles = [],
  survolId = null,
  onSurvol,
  onSelection,
  onPoserQuestion,
  onPretAPublier,
  onEcarter,
  onReintegrer,
}) {
  const [tri, setTri] = useState('repere')
  const [sens, setSens] = useState('asc')
  const [provenance, setProvenance] = useState('toutes')
  const [inclureEcartes, setInclureEcartes] = useState(true)
  const [recherche, setRecherche] = useState('')
  // WIR205 — écarter EXIGE un motif (le serveur renvoie 400 sans lui) : la
  // saisie s'ouvre sur la LIGNE concernée, jamais dans une boîte anonyme.
  const [ecartementId, setEcartementId] = useState(null)
  const [motif, setMotif] = useState('')
  const [erreur, setErreur] = useState(null)
  const [enCours, setEnCours] = useState(null)

  const confirmerEcartement = useCallback(async (obstacle) => {
    const texte = motif.trim()
    if (!texte) return
    setErreur(null)
    setEnCours(obstacle.id ?? obstacle.repere)
    try {
      await onEcarter?.(obstacle, texte)
      setEcartementId(null)
      setMotif('')
    } catch (e) {
      setErreur(e?.message || 'Le serveur a refusé l’écartement.')
    } finally {
      setEnCours(null)
    }
  }, [motif, onEcarter])

  const reintegrer = useCallback(async (obstacle) => {
    setErreur(null)
    setEnCours(obstacle.id ?? obstacle.repere)
    try {
      await onReintegrer?.(obstacle)
    } catch (e) {
      setErreur(e?.message || 'Le serveur a refusé la réintégration.')
    } finally {
      setEnCours(null)
    }
  }, [onReintegrer])

  const compte = useMemo(() => compterProvenances(obstacles), [obstacles])
  const compteur = useMemo(() => libelleCompteur(obstacles), [obstacles])
  const garde = useMemo(() => evaluerGardePublication(obstacles), [obstacles])

  const visibles = useMemo(
    () =>
      trierObstacles(
        filtrerObstacles(obstacles, { provenance, inclureEcartes, recherche }),
        tri,
        sens,
      ),
    [obstacles, provenance, inclureEcartes, recherche, tri, sens],
  )

  const changerTri = useCallback(
    (cle) => {
      if (cle === tri) {
        setSens((s) => (s === 'asc' ? 'desc' : 'asc'))
        return
      }
      setTri(cle)
      setSens('asc')
    },
    [tri],
  )

  const fautifs = new Set(garde.fautifs.map((o) => o.id ?? o.repere))

  return (
    <aside className="ao-obstacles-liste" data-ao-obstacles={compte.total}>
      <h3>Obstacles</h3>

      {/* Le compteur : permanent, jamais replié, jamais recalculé ailleurs. */}
      <p className="ao-obstacles-compteur" data-ao-compte={compte.total} aria-live="polite">
        {compteur}
      </p>

      <div className="ao-obstacles-filtres">
        <label className="ao-champ" htmlFor="ao-obstacles-recherche">
          <span>Rechercher</span>
          <input
            id="ao-obstacles-recherche"
            className="form-control"
            type="search"
            value={recherche}
            onChange={(e) => setRecherche(e.target.value)}
          />
        </label>

        <label className="ao-champ" htmlFor="ao-obstacles-provenance">
          <span>Provenance</span>
          <select
            id="ao-obstacles-provenance"
            className="form-select"
            value={provenance}
            onChange={(e) => setProvenance(e.target.value)}
          >
            <option value="toutes">Toutes les provenances</option>
            {PROVENANCES.map((p) => (
              <option key={p.cle} value={p.cle}>
                {p.libelle}
              </option>
            ))}
          </select>
        </label>

        <label className="ao-champ ao-champ-case" htmlFor="ao-obstacles-ecartes">
          <input
            id="ao-obstacles-ecartes"
            type="checkbox"
            checked={inclureEcartes}
            onChange={(e) => setInclureEcartes(e.target.checked)}
          />
          <span>Afficher les écartés (avec leur décision)</span>
        </label>
      </div>

      {/* La GARDE. Elle est au-dessus de la liste, pas en bas de page. */}
      <div
        className={`ao-obstacles-garde ${garde.pretAPublier ? 'est-ok' : 'est-bloquant'}`}
        data-ao-etat={garde.pretAPublier ? 'publiable' : 'bloque'}
        role={garde.pretAPublier ? 'status' : 'alert'}
      >
        <p data-ao-verdict={garde.pretAPublier ? 'publiable' : 'bloque'}>{garde.message}</p>
        {garde.pretAPublier ? (
          <Button type="button" onClick={() => onPretAPublier?.(garde)}>
            Marquer la toiture prête à publier
          </Button>
        ) : (
          <>
            <Button
              type="button"
              disabled
              title="Un obstacle non engageable pèse encore sur le compte."
            >
              Marquer la toiture prête à publier
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => onPoserQuestion?.(garde.question, garde.fautifs)}
              data-ao-poser-question={garde.question?.reperes.join(',')}
            >
              Poser la question au client
            </Button>
          </>
        )}
      </div>

      <table className="data-table ao-obstacles-table">
        <caption>
          {visibles.length} obstacle{visibles.length > 1 ? 's' : ''} affiché
          {visibles.length > 1 ? 's' : ''} sur {compte.lignes}
        </caption>
        <thead>
          <tr>
            {TRIS.map((t) => (
              <th
                key={t.cle}
                scope="col"
                aria-sort={tri === t.cle ? (sens === 'asc' ? 'ascending' : 'descending') : 'none'}
              >
                <button type="button" onClick={() => changerTri(t.cle)}>
                  {t.libelle}
                </button>
              </th>
            ))}
            <th scope="col">Décision</th>
            <th scope="col">Action</th>
          </tr>
        </thead>
        <tbody>
          {visibles.map((o) => {
            const cle = o.id ?? o.repere
            const info = provenanceInfo(o.provenance)
            // L'écartement se lit du drapeau posé par l'atelier (WIR205) OU de
            // la provenance serveur elle-même : une seule table de
            // correspondance (`provenanceInfo`), jamais un test de chaîne ici.
            const ecarte = Boolean(o.ecarte) || info.cle === PROVENANCE_ECARTE
            const enregistre = estEnregistre(o)
            const occupe = enCours === cle
            return (
              <tr
                key={cle}
                data-ao-repere={o.repere}
                data-ao-provenance={info.jeton}
                data-ao-ecarte={ecarte ? 'oui' : undefined}
                data-ao-survole={survolId === cle ? 'oui' : undefined}
                data-ao-fautif={fautifs.has(cle) ? 'oui' : undefined}
                className={survolId === cle ? 'est-survole' : undefined}
                onMouseEnter={() => onSurvol?.(cle)}
                onMouseLeave={() => onSurvol?.(null)}
                onFocus={() => onSurvol?.(cle)}
                onBlur={() => onSurvol?.(null)}
              >
                <th scope="row">
                  <button type="button" onClick={() => onSelection?.(cle)}>
                    {o.repere}
                  </button>
                </th>
                <td>{o.designation || natureParCle(o.nature)?.libelle || '—'}</td>
                <td>{natureParCle(o.nature)?.libelle ?? '—'}</td>
                <td>{info.libelle}</td>
                <td>{surfaceObstacle(o).toFixed(2)} m²</td>
                <td>{o.decision || '—'}</td>
                <td>
                  {ecarte ? (
                    <Button
                      type="button"
                      variant="outline"
                      disabled={!enregistre || occupe}
                      title={enregistre ? undefined : MSG_NON_ENREGISTRE}
                      onClick={() => reintegrer(o)}
                      data-ao-reintegrer={o.repere}
                    >
                      Réintégrer
                    </Button>
                  ) : (
                    <Button
                      type="button"
                      variant="outline"
                      disabled={!enregistre || occupe}
                      title={enregistre ? undefined : MSG_NON_ENREGISTRE}
                      onClick={() => {
                        setErreur(null)
                        setMotif('')
                        setEcartementId(cle)
                      }}
                      data-ao-ecarter={o.repere}
                    >
                      Écarter
                    </Button>
                  )}

                  {ecartementId === cle && (
                    <div className="ao-obstacle-ecartement" data-ao-ecartement={o.repere}>
                      <label className="ao-champ" htmlFor={`ao-motif-ecart-${cle}`}>
                        <span>Motif de l&apos;écartement</span>
                        <textarea
                          id={`ao-motif-ecart-${cle}`}
                          className="form-control"
                          value={motif}
                          onChange={(e) => setMotif(e.target.value)}
                        />
                      </label>
                      <Button
                        type="button"
                        disabled={!motif.trim() || occupe}
                        onClick={() => confirmerEcartement(o)}
                        data-ao-ecarter-confirmer={o.repere}
                      >
                        Confirmer l&apos;écartement
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => setEcartementId(null)}
                      >
                        Annuler
                      </Button>
                    </div>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {erreur && (
        <p role="alert" data-ao-obstacles-erreur>
          {erreur}
        </p>
      )}

      {visibles.length === 0 && (
        <p data-ao-obstacles-vide>Aucun obstacle ne correspond à ce filtre.</p>
      )}
    </aside>
  )
}
