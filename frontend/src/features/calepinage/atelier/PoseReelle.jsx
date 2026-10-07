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
function saisieDe(ligne) {
  return {
    modules: ligne.modules_poses === null || ligne.modules_poses === undefined
      ? ''
      : String(ligne.modules_poses),
    position: ligne.ecarts_position || '',
    // ACAL246 - la date de releve est PAR LIGNE, prefillee depuis le serveur ;
    // `dateModifiee` : l'utilisateur l'a changee (seule alors elle est envoyee).
    date: ligne.releve_le || '',
    dateModifiee: false,
    brouillon: false,
  }
}

const VIDE = { modules: '', position: '', date: '', dateModifiee: false, brouillon: false }

/* ACAL268 — une ligne est indexée par l'identifiant STABLE de son pan
   (`zone_id`, contrat `calepinage_asbuilt_ecarts.json`) : deux pans de même
   libellé sont deux lignes indépendantes, et un pan renommé garde sa saisie.
   Le libellé n'est qu'un affichage. */
const cleDe = (ligne) => String(ligne?.zone_id ?? ligne?.pan ?? '')
const libelleDe = (ligne) => ligne?.libelle || ligne?.pan || cleDe(ligne)

function saisiesDe(lignes) {
  const saisies = {}
  for (const ligne of lignes || []) saisies[cleDe(ligne)] = saisieDe(ligne)
  return saisies
}

export default function PoseReelle({ calepinageId: idPropose } = {}) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl

  const [etat, setEtat] = useState(null)
  const [saisies, setSaisies] = useState({})
  const [erreurLecture, setErreurLecture] = useState(null)
  // `{ pan, champs: {champ: message} }` — le pan dont la saisie a été refusée.
  const [refus, setRefus] = useState(null)
  const [enCours, setEnCours] = useState(null)
  const [message, setMessage] = useState(null)

  // `pan` : seule CETTE ligne est rehydratee (les brouillons des autres pans
  // survivent a un enregistrement) ; `null` : aucune ; absent : toute la grille.
  const appliquer = useCallback((res, pan) => {
    const donnees = res?.data && typeof res.data === 'object' ? res.data : {}
    setEtat(donnees)
    if (pan === undefined) {
      setSaisies(saisiesDe(donnees.lignes))
    } else if (pan !== null) {
      const ligne = (donnees.lignes || []).find((l) => cleDe(l) === pan)
      if (ligne) setSaisies((s) => ({ ...s, [pan]: saisieDe(ligne) }))
    }
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
    ...s,
    [pan]: {
      ...(s[pan] || VIDE),
      [champ]: valeur,
      brouillon: true,
      ...(champ === 'date' ? { dateModifiee: true } : {}),
    },
  }))

  const corpsRefus = (err, repli) => {
    const corps = err?.response?.data
    return corps && typeof corps === 'object' && !Array.isArray(corps) ? corps : { detail: repli }
  }

  const enregistrer = (ligne) => {
    const pan = cleDe(ligne)
    const libelle = libelleDe(ligne)
    const saisie = saisies[pan] || VIDE
    setEnCours(pan)
    setRefus(null)
    setMessage(null)
    const corps = {
      // ACAL268 — le pan est désigné par son identifiant STABLE.
      pan,
      modules_poses: saisie.modules,
      ecarts_position: saisie.position,
    }
    // La date n'est envoyee que si modifiee : une correction du texte conserve
    // la date et l'auteur du releve (ACAL245).
    if (saisie.dateModifiee) corps.releve_le = saisie.date
    Promise.resolve(calepinageApi.calepinages.enregistrerPoseReelle(calepinageId, corps))
      .then((res) => {
        appliquer(res, pan)
        setMessage(`Pose du pan ${libelle} enregistrée.`)
      })
      .catch((err) => setRefus({ pan, libelle, champs: corpsRefus(err, 'La saisie a été refusée par le serveur.') }))
      .finally(() => setEnCours(null))
  }

  /* ACAL268 — retirer le relevé d'un pan ORPHELIN (supprimé du document) :
     DELETE pose-reelle/<zone_id>/, puis relecture. Le refus (404) est rendu
     sur la ligne. */
  const retirer = (ligne) => {
    const pan = cleDe(ligne)
    setEnCours(pan)
    setRefus(null)
    setMessage(null)
    Promise.resolve(calepinageApi.calepinages.supprimerPoseReelle(calepinageId, pan))
      .then(() => {
        setMessage(`Relevé du pan ${libelleDe(ligne)} retiré.`)
        return charger()
      })
      .catch((err) => setRefus({ pan, libelle: libelleDe(ligne), champs: corpsRefus(err, 'Le retrait a été refusé par le serveur.') }))
      .finally(() => setEnCours(null))
  }

  const creerVersion = () => {
    setEnCours('version')
    setRefus(null)
    setMessage(null)
    Promise.resolve(calepinageApi.calepinages.creerVersionPoseReelle(calepinageId))
      .then((res) => {
        // Les brouillons sont conservés : la version ne rehydrate aucune ligne.
        const donnees = appliquer(res, null)
        let texte = 'Aucune version n’a été gelée.'
        if (donnees.version_creee) {
          texte = res?.status === 200
            ? `Version n° ${donnees.version_creee} déjà gelée (écarts inchangés).`
            : `Version n° ${donnees.version_creee} gelée depuis les écarts.`
        }
        setMessage(texte)
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
            ? `Saisie refusée — pan ${refus.libelle || refus.pan} : ${champsRefus.join(', ')}`
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

          <p className="mt-2 text-xs text-lune-faint" data-testid="cal-pose-brouillon-note">
            Les saisies non enregistrées ne sont pas conservées si vous quittez la page.
          </p>

          <table className="mt-4 w-full text-sm" role="grid" data-testid="cal-pose-grille">
            <thead>
              <tr className="text-left text-lune-faint">
                <th scope="col">Pan</th>
                <th scope="col">Prévu</th>
                <th scope="col">Posé</th>
                <th scope="col">Écart</th>
                <th scope="col">Relevé le</th>
                <th scope="col">Écarts de position</th>
                <th scope="col"><span className="sr-only">Action</span></th>
              </tr>
            </thead>
            <tbody>
              {lignes.map((ligne) => {
                const cle = cleDe(ligne)
                const libelle = libelleDe(ligne)
                const saisie = saisies[cle] || VIDE
                const erreurDate = erreurDe(cle, 'releve_le')
                const erreurPan = erreurDe(cle, 'pan')
                const erreurModules = erreurDe(cle, 'modules_poses')
                return (
                  <tr key={cle} data-testid={`cal-pose-ligne-${cle}`} className="align-top">
                    <td className="py-2 text-white">
                      {libelle}
                      {ligne.orphelin && (
                        <p className="mt-1 text-xs text-brass-300" data-testid={`cal-pose-orphelin-${cle}`}>
                          Pan supprimé du document — hors totaux
                        </p>
                      )}
                      {erreurPan && (
                        <p role="alert" data-testid={`cal-pose-erreur-pan-${cle}`} className="mt-1 text-xs text-red-300">
                          {erreurPan}
                        </p>
                      )}
                    </td>
                    <td className="py-2" data-testid={`cal-pose-prevu-${cle}`}>
                      {ligne.modules_prevus ?? ''}
                    </td>
                    <td className="py-2">
                      <input
                        type="number"
                        step="any"
                        min="0"
                        aria-label={`Modules posés — ${libelle}`}
                        data-testid={`cal-pose-modules-${cle}`}
                        value={saisie.modules}
                        onChange={(e) => majSaisie(cle, 'modules', e.target.value)}
                        className="w-20 rounded border border-white/15 bg-black/30 px-2 py-1 text-white"
                      />
                      {erreurModules && (
                        <p role="alert" data-testid={`cal-pose-erreur-modules-${cle}`} className="mt-1 text-xs text-red-300">
                          {erreurModules}
                        </p>
                      )}
                    </td>
                    <td className="py-2">
                      <span data-testid={`cal-pose-ecart-${cle}`}>{ecartLisible(ligne.ecart)}</span>
                      {ligne.mention && (
                        <p className="mt-1 text-xs text-lune-faint" data-testid={`cal-pose-mention-${cle}`}>
                          {ligne.mention}
                        </p>
                      )}
                    </td>
                    <td className="py-2">
                      <input
                        type="date"
                        aria-label={`Relevé le — ${libelle}`}
                        data-testid={`cal-pose-date-${cle}`}
                        value={saisie.date}
                        onChange={(e) => majSaisie(cle, 'date', e.target.value)}
                        className="rounded border border-white/15 bg-black/30 px-2 py-1 text-white"
                      />
                      {ligne.releve_par?.nom_complet && (
                        <p className="mt-1 text-xs text-lune-faint" data-testid={`cal-pose-auteur-${cle}`}>
                          {`par ${ligne.releve_par.nom_complet}`}
                        </p>
                      )}
                      {erreurDate && (
                        <p role="alert" data-testid={`cal-pose-erreur-releve_le-${cle}`} className="mt-1 text-xs text-red-300">
                          {erreurDate}
                        </p>
                      )}
                      {saisie.brouillon && (
                        <p className="mt-1 text-xs text-brass-300" data-testid={`cal-pose-brouillon-${cle}`}>
                          Brouillon non enregistré
                        </p>
                      )}
                    </td>
                    <td className="py-2">
                      <textarea
                        aria-label={`Écarts de position — ${libelle}`}
                        data-testid={`cal-pose-position-${cle}`}
                        value={saisie.position}
                        onChange={(e) => majSaisie(cle, 'position', e.target.value)}
                        className="w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-white"
                      />
                    </td>
                    <td className="py-2">
                      {ligne.orphelin
                        ? (
                          <button
                            type="button"
                            onClick={() => retirer(ligne)}
                            disabled={enCours !== null}
                            data-testid={`cal-pose-retirer-${cle}`}
                            className="rounded bg-red-500/20 px-3 py-1 text-xs font-semibold text-red-200 disabled:opacity-50"
                          >
                            {enCours === cle ? 'Retrait…' : 'Retirer'}
                          </button>
                        )
                        : (
                          <button
                            type="button"
                            onClick={() => enregistrer(ligne)}
                            disabled={enCours !== null}
                            data-testid={`cal-pose-enregistrer-${cle}`}
                            className="rounded bg-brass-500/20 px-3 py-1 text-xs font-semibold text-brass-200 disabled:opacity-50"
                          >
                            {enCours === cle ? 'Envoi…' : 'Enregistrer'}
                          </button>
                        )}
                      {erreurDe(cle, 'detail') && (
                        <p role="alert" data-testid={`cal-pose-erreur-detail-${cle}`} className="mt-1 text-xs text-red-300">
                          {String(erreurDe(cle, 'detail'))}
                        </p>
                      )}
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
