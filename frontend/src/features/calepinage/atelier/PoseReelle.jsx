import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'

/* ============================================================================
   CALX367 — LA POSE RÉELLE (AS-BUILT), EN ONGLET DE L'ATELIER.
   ----------------------------------------------------------------------------
   CONSTAT. Aucun composant de `features/calepinage/` ne parlait de pose
   réelle ni d'écart de chantier : le chantier savait LIRE le calepinage
   (`apps/installations/tests_cal245_bloc_calepinage.py`), jamais lui
   répondre. Parité SolarGrade — suivi des réserves et rapports de terrain
   (https://solargrade.io/).

   LE CONTRAT EST CELUI DU SERVEUR : `contract_samples/
   calepinage_asbuilt_ecarts.json` (CALX337), servi par
   `GET/POST calepinages/<pk>/pose-reelle/` (CALX366). GET et POST rendent la
   MÊME forme : chaque réponse remplace la grille, aucun second appel.

   AUCUN CALCUL ICI. L'écart affiché est celui du SERVEUR (posé − prévu, deux
   saisies réelles). Un pan SANS saisie affiche un écart VIDE et la mention du
   serveur — jamais `0`, qui dirait « conforme » alors que personne n'a
   compté. Un refus s'affiche SOUS le champ du pan fautif, et le bandeau NOMME
   le pan et le champ (règle du 08/09/2026) — jamais un « non enregistré »
   générique.
   ========================================================================== */

/** L'écart publié, signé — `''` quand le serveur n'en publie aucun. */
function ecartLisible(ecart) {
  if (ecart === null || ecart === undefined) return ''
  return ecart > 0 ? `+${ecart}` : String(ecart)
}

/** Les champs de saisie d'une réponse du serveur, pan par pan. */
function saisiesDe(lignes) {
  const saisies = {}
  for (const ligne of lignes || []) {
    saisies[ligne.pan] = {
      modules: ligne.modules_poses === null || ligne.modules_poses === undefined
        ? ''
        : String(ligne.modules_poses),
      position: ligne.ecarts_position || '',
    }
  }
  return saisies
}

export default function PoseReelle({ calepinageId: idPropose } = {}) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl

  const [etat, setEtat] = useState(null)
  const [saisies, setSaisies] = useState({})
  // La date du relevé est SAISIE (jamais la date du jour devinée) : vide tant
  // que personne ne l'a donnée — le serveur refuse alors en nommant `releve_le`.
  const [releveLe, setReleveLe] = useState('')
  const [erreurLecture, setErreurLecture] = useState(null)
  // `{ pan, champs: {champ: message} }` — le pan dont la saisie a été refusée.
  const [refus, setRefus] = useState(null)
  const [enCours, setEnCours] = useState(null)
  const [message, setMessage] = useState(null)

  const appliquer = useCallback((res) => {
    const donnees = res?.data && typeof res.data === 'object' ? res.data : {}
    setEtat(donnees)
    setSaisies(saisiesDe(donnees.lignes))
    return donnees
  }, [])

  const charger = useCallback(() => {
    if (!calepinageId) return Promise.resolve()
    return Promise.resolve(calepinageApi.calepinages.poseReelle(calepinageId))
      .then(appliquer)
      .catch(() => setErreurLecture('La pose réelle de ce calepinage n’a pas pu être lue.'))
  }, [calepinageId, appliquer])

  useEffect(() => { charger() }, [charger])

  const majSaisie = (pan, champ, valeur) => setSaisies((s) => ({
    ...s, [pan]: { ...(s[pan] || { modules: '', position: '' }), [champ]: valeur },
  }))

  const corpsRefus = (err, repli) => {
    const corps = err?.response?.data
    return corps && typeof corps === 'object' && !Array.isArray(corps) ? corps : { detail: repli }
  }

  const enregistrer = (pan) => {
    const saisie = saisies[pan] || { modules: '', position: '' }
    setEnCours(pan)
    setRefus(null)
    setMessage(null)
    Promise.resolve(calepinageApi.calepinages.enregistrerPoseReelle(calepinageId, {
      pan,
      modules_poses: saisie.modules,
      ecarts_position: saisie.position,
      releve_le: releveLe,
    }))
      .then((res) => {
        appliquer(res)
        setMessage(`Pose du pan ${pan} enregistrée.`)
      })
      .catch((err) => setRefus({ pan, champs: corpsRefus(err, 'La saisie a été refusée par le serveur.') }))
      .finally(() => setEnCours(null))
  }

  const creerVersion = () => {
    setEnCours('version')
    setRefus(null)
    setMessage(null)
    Promise.resolve(calepinageApi.calepinages.creerVersionPoseReelle(calepinageId))
      .then((res) => {
        const donnees = appliquer(res)
        setMessage(donnees.version_creee
          ? `Version n° ${donnees.version_creee} gelée depuis les écarts.`
          : 'Aucune version n’a été gelée.')
      })
      .catch((err) => setRefus({ pan: null, champs: corpsRefus(err, 'La version a été refusée par le serveur.') }))
      .finally(() => setEnCours(null))
  }

  const lignes = Array.isArray(etat?.lignes) ? etat.lignes : []
  const champsRefus = refus ? Object.keys(refus.champs) : []
  const erreurDe = (pan, champ) => (refus && refus.pan === pan ? refus.champs[champ] : undefined)

  return (
    <div className="cine-card mt-6 p-6" data-testid="cal-pose-reelle">
      <p className="tech-label rule-brass text-brass-300">Pose réelle (as-built)</p>

      {refus && champsRefus.length > 0 && (
        <p
          role="alert"
          data-testid="cal-pose-bandeau"
          className="mt-3 rounded border border-red-400/40 bg-red-500/10 px-3 py-2 text-sm text-red-200"
        >
          {refus.pan
            ? `Saisie refusée — pan ${refus.pan} : ${champsRefus.join(', ')}`
            : `Version refusée — ${champsRefus.join(', ')}`}
        </p>
      )}

      {erreurLecture && (
        <p role="alert" data-testid="cal-pose-erreur-lecture" className="mt-3 text-sm text-red-300">
          {erreurLecture}
        </p>
      )}

      {etat === null && !erreurLecture && (
        <p className="mt-3 text-sm text-lune-faint" data-testid="cal-pose-chargement">
          Lecture de la pose réelle…
        </p>
      )}

      {etat !== null && lignes.length === 0 && (
        <p className="mt-3 text-sm text-lune-soft" data-testid="cal-pose-vide">
          Aucun pan prévu dans ce calepinage : dessinez la conception (ou retenez
          une variante) avant de saisir la pose réelle.
        </p>
      )}

      {lignes.length > 0 && (
        <>
          <p className="mt-3 text-sm text-lune-soft" data-testid="cal-pose-source">
            {`Prévu lu dans : ${etat.source || '—'} · total prévu ${etat.total_prevu ?? '—'} · `}
            {etat.total_pose === null || etat.total_pose === undefined
              ? 'aucun pan relevé'
              : `total posé ${etat.total_pose}`}
          </p>

          <label className="mt-3 block" data-testid="cal-pose-champ-releve_le">
            <span className="tech-label text-lune-faint">Relevé le</span>
            <input
              type="date"
              value={releveLe}
              onChange={(e) => setReleveLe(e.target.value)}
              className="mt-1 rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white"
            />
          </label>
          {refus?.champs?.releve_le && (
            <p role="alert" data-testid="cal-pose-erreur-releve_le" className="mt-1 text-xs text-red-300">
              {refus.champs.releve_le}
            </p>
          )}

          <table className="mt-4 w-full text-sm" role="grid" data-testid="cal-pose-grille">
            <thead>
              <tr className="text-left text-lune-faint">
                <th scope="col">Pan</th>
                <th scope="col">Prévu</th>
                <th scope="col">Posé</th>
                <th scope="col">Écart</th>
                <th scope="col">Écarts de position</th>
                <th scope="col"><span className="sr-only">Action</span></th>
              </tr>
            </thead>
            <tbody>
              {lignes.map((ligne) => {
                const saisie = saisies[ligne.pan] || { modules: '', position: '' }
                const erreurPan = erreurDe(ligne.pan, 'pan')
                const erreurModules = erreurDe(ligne.pan, 'modules_poses')
                return (
                  <tr key={ligne.pan} data-testid={`cal-pose-ligne-${ligne.pan}`} className="align-top">
                    <td className="py-2 text-white">
                      {ligne.pan}
                      {erreurPan && (
                        <p role="alert" data-testid={`cal-pose-erreur-pan-${ligne.pan}`} className="mt-1 text-xs text-red-300">
                          {erreurPan}
                        </p>
                      )}
                    </td>
                    <td className="py-2" data-testid={`cal-pose-prevu-${ligne.pan}`}>
                      {ligne.modules_prevus ?? ''}
                    </td>
                    <td className="py-2">
                      <input
                        type="number"
                        step="any"
                        min="0"
                        aria-label={`Modules posés — ${ligne.pan}`}
                        data-testid={`cal-pose-modules-${ligne.pan}`}
                        value={saisie.modules}
                        onChange={(e) => majSaisie(ligne.pan, 'modules', e.target.value)}
                        className="w-20 rounded border border-white/15 bg-black/30 px-2 py-1 text-white"
                      />
                      {erreurModules && (
                        <p role="alert" data-testid={`cal-pose-erreur-modules-${ligne.pan}`} className="mt-1 text-xs text-red-300">
                          {erreurModules}
                        </p>
                      )}
                    </td>
                    <td className="py-2">
                      <span data-testid={`cal-pose-ecart-${ligne.pan}`}>{ecartLisible(ligne.ecart)}</span>
                      {ligne.mention && (
                        <p className="mt-1 text-xs text-lune-faint" data-testid={`cal-pose-mention-${ligne.pan}`}>
                          {ligne.mention}
                        </p>
                      )}
                    </td>
                    <td className="py-2">
                      <textarea
                        aria-label={`Écarts de position — ${ligne.pan}`}
                        data-testid={`cal-pose-position-${ligne.pan}`}
                        value={saisie.position}
                        onChange={(e) => majSaisie(ligne.pan, 'position', e.target.value)}
                        className="w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-white"
                      />
                    </td>
                    <td className="py-2">
                      <button
                        type="button"
                        onClick={() => enregistrer(ligne.pan)}
                        disabled={enCours !== null}
                        data-testid={`cal-pose-enregistrer-${ligne.pan}`}
                        className="rounded bg-brass-500/20 px-3 py-1 text-xs font-semibold text-brass-200 disabled:opacity-50"
                      >
                        {enCours === ligne.pan ? 'Envoi…' : 'Enregistrer'}
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          <button
            type="button"
            onClick={creerVersion}
            disabled={enCours !== null}
            data-testid="cal-pose-creer-version"
            className="mt-5 block rounded bg-brass-500/20 px-4 py-2 text-sm font-semibold text-brass-200 disabled:opacity-50"
          >
            {enCours === 'version' ? 'Gel en cours…' : 'Créer une version depuis les écarts'}
          </button>
          {refus && refus.pan === null && refus.champs.creer_version && (
            <p role="alert" data-testid="cal-pose-erreur-creer_version" className="mt-2 text-xs text-red-300">
              {refus.champs.creer_version}
            </p>
          )}
          {etat.version_creee !== null && etat.version_creee !== undefined && (
            <p className="mt-2 text-xs text-lune-soft" data-testid="cal-pose-version">
              {`Dernière version née des écarts : n° ${etat.version_creee}.`}
            </p>
          )}
        </>
      )}

      {refus?.champs?.detail && (
        <p role="alert" data-testid="cal-pose-erreur-detail" className="mt-2 text-xs text-red-300">
          {String(refus.champs.detail)}
        </p>
      )}

      {message && (
        <p role="status" data-testid="cal-pose-message" className="mt-3 text-sm text-lune-soft">
          {message}
        </p>
      )}
    </div>
  )
}
