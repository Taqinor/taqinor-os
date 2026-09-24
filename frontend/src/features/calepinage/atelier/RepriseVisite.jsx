import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import { formatDateTime } from '../../../lib/format'

/* ============================================================================
   CALX365 — LA REPRISE DE LA VISITE TECHNIQUE, EN ONGLET DE L'ATELIER.
   ----------------------------------------------------------------------------
   CONSTAT. `PhotoSiteCalage.jsx` affichait un état vide invitant à « déposer
   une photo » sans contrôle de dépôt, et rien ne disait au concepteur qu'une
   visite technique VALIDÉE portait déjà des mesures et des photos du toit : il
   les ressaisissait. Parité Scoop Solar — partage bureau/terrain en temps
   réel (https://www.scoop.solar/apps/commercial-solar-site-survey-app/).

   LE CONTRAT EST CELUI DU SERVEUR : `contract_samples/
   calepinage_releve_visite.json` (CALX336), servi par
   `GET/POST calepinages/<pk>/releve-visite/` (CALX364). GET et POST rendent
   la MÊME forme : ce panneau n'enchaîne aucun second appel.

   CE QUE CE PANNEAU NE FAIT JAMAIS
     * convertir ou compléter une mesure (D7) : chaque valeur s'affiche telle
       que saisie sur le toit, avec l'unité DÉCLARÉE par la checklist, ou sans
       unité quand la checklist n'en déclare aucune ;
     * inventer un motif : sans visite validée, il affiche `motif_absence` TEL
       QUEL (le serveur nomme ce qui manque — visite non faite, ou pas encore
       validée, ou calepinage sans lead) ;
     * présenter une autre date à la place du feu vert : `validee_le` peut
       valoir `null` (la visite n'horodate pas encore sa validation), l'écran
       le dit plutôt que d'afficher une date de réalisation à sa place.
   Une reprise DÉJÀ faite désactive le bouton, AVEC sa raison ; le bandeau
   dit la date et l'auteur de la reprise. Un refus du serveur s'affiche SOUS
   le bouton, et le bandeau NOMME le champ fautif (règle du 08/09/2026).
   ========================================================================== */

/** Repli quand le serveur n'a servi AUCUN motif (réponse vide, hors contrat). */
const MOTIF_PAR_DEFAUT = 'Aucune visite technique validée n’est disponible pour ce calepinage.'

/** `AAAA-MM-JJ` → `JJ/MM/AAAA`, sans fuseau (une date n'a pas d'heure). */
function dateLisible(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso ?? ''))
  return m ? `${m[3]}/${m[2]}/${m[1]}` : (iso || '—')
}

/** La valeur SAISIE, lisible, avec son unité déclarée — jamais convertie. */
function valeurLisible(mesure) {
  const { valeur, unite } = mesure ?? {}
  let texte
  if (valeur === true) texte = 'oui'
  else if (valeur === false) texte = 'non'
  else texte = String(valeur)
  return unite ? `${texte} ${unite}` : texte
}

/** La raison pour laquelle « Reprendre » est désactivé — `null` s'il ne l'est pas. */
function raisonDesactivation(etat) {
  if (!etat || etat.visite_id === null || etat.visite_id === undefined) {
    return etat?.motif_absence || MOTIF_PAR_DEFAUT
  }
  if (etat.deja_repris) {
    return 'Cette visite est déjà reprise dans ce calepinage : une seconde reprise ne créerait rien.'
  }
  return null
}

function BandeauReprise({ releve }) {
  if (!releve) return null
  const auteur = releve.releve_par ? ` par ${releve.releve_par}` : ''
  return (
    <p
      role="status"
      data-testid="cal-reprise-bandeau"
      className="mt-3 rounded border border-emerald-400/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-100"
    >
      {`Visite reprise le ${dateLisible(releve.releve_le)}${auteur} — relevé n° ${releve.id}, `
        + `${(releve.photos || []).length} photo(s) rattachée(s).`}
    </p>
  )
}

export default function RepriseVisite({ calepinageId: idPropose } = {}) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl

  const [etat, setEtat] = useState(null)
  const [erreurLecture, setErreurLecture] = useState(null)
  const [erreurs, setErreurs] = useState({})
  const [enCours, setEnCours] = useState(false)

  const charger = useCallback(() => {
    if (!calepinageId) return Promise.resolve()
    return Promise.resolve(calepinageApi.calepinages.releveVisite(calepinageId))
      .then((res) => setEtat(res?.data && typeof res.data === 'object' ? res.data : {}))
      .catch(() => setErreurLecture('La visite technique de ce calepinage n’a pas pu être lue.'))
  }, [calepinageId])

  useEffect(() => { charger() }, [charger])

  const reprendre = () => {
    if (!calepinageId) return
    setEnCours(true)
    setErreurs({})
    Promise.resolve(calepinageApi.calepinages.reprendreVisite(calepinageId))
      .then((res) => setEtat(res?.data && typeof res.data === 'object' ? res.data : {}))
      .catch((err) => {
        const corps = err?.response?.data
        setErreurs(corps && typeof corps === 'object' && !Array.isArray(corps)
          ? corps
          : { detail: 'La reprise a été refusée par le serveur.' })
      })
      .finally(() => setEnCours(false))
  }

  const champsFautifs = Object.keys(erreurs)
  const raison = raisonDesactivation(etat)
  const aVisite = Boolean(etat) && etat.visite_id !== null && etat.visite_id !== undefined

  return (
    <div className="cine-card mt-6 p-6" data-testid="cal-reprise-visite">
      <p className="tech-label rule-brass text-brass-300">Reprise de la visite technique</p>

      {champsFautifs.length > 0 && (
        <p
          role="alert"
          data-testid="cal-reprise-refus-bandeau"
          className="mt-3 rounded border border-red-400/40 bg-red-500/10 px-3 py-2 text-sm text-red-200"
        >
          {`Reprise refusée — champ en cause : ${champsFautifs.join(', ')}`}
        </p>
      )}

      {erreurLecture && (
        <p role="alert" data-testid="cal-reprise-erreur-lecture" className="mt-3 text-sm text-red-300">
          {erreurLecture}
        </p>
      )}

      {etat === null && !erreurLecture && (
        <p className="mt-3 text-sm text-lune-faint" data-testid="cal-reprise-chargement">
          Lecture de la visite technique…
        </p>
      )}

      {etat !== null && !aVisite && (
        <p className="mt-3 text-sm text-lune-soft" data-testid="cal-reprise-vide">
          {raison}
        </p>
      )}

      {aVisite && (
        <>
          <p className="mt-3 text-sm text-lune-soft" data-testid="cal-reprise-visite-entete">
            {`Visite technique n° ${etat.visite_id} — `}
            {etat.validee_le
              ? `validée le ${formatDateTime(etat.validee_le)}`
              : 'validée (la visite n’enregistre pas encore l’heure de sa validation)'}
          </p>

          <BandeauReprise releve={etat.releve} />

          <p className="tech-label mt-4 text-lune-faint">Mesures relevées sur le toit</p>
          {(etat.mesures || []).length === 0 ? (
            <p className="mt-1 text-sm text-lune-faint" data-testid="cal-reprise-mesures-vide">
              Aucune mesure saisie pendant la visite.
            </p>
          ) : (
            <ul className="mt-1 space-y-1" data-testid="cal-reprise-mesures">
              {etat.mesures.map((mesure) => (
                <li key={mesure.code} className="text-sm text-white" data-testid={`cal-reprise-mesure-${mesure.code}`}>
                  <span className="text-lune-soft">{mesure.libelle}</span>
                  {' : '}
                  <span>{valeurLisible(mesure)}</span>
                </li>
              ))}
            </ul>
          )}

          <p className="tech-label mt-4 text-lune-faint">Photos retenues</p>
          {(etat.photos || []).length === 0 ? (
            <p className="mt-1 text-sm text-lune-faint" data-testid="cal-reprise-photos-vide">
              Aucune photo retenue pendant la visite.
            </p>
          ) : (
            <ul className="mt-1 space-y-1" data-testid="cal-reprise-photos">
              {etat.photos.map((photo) => (
                <li
                  key={photo.attachment_id}
                  className="text-sm text-white"
                  data-testid={`cal-reprise-photo-${photo.attachment_id}`}
                >
                  {photo.libelle || photo.slot_code}
                </li>
              ))}
            </ul>
          )}

          <button
            type="button"
            onClick={reprendre}
            disabled={Boolean(raison) || enCours}
            data-testid="cal-reprise-bouton"
            className="mt-5 block rounded bg-brass-500/20 px-4 py-2 text-sm font-semibold text-brass-200 disabled:opacity-50"
          >
            {enCours ? 'Reprise en cours…' : 'Reprendre dans ce calepinage'}
          </button>
          {raison && (
            <p className="mt-2 text-xs text-lune-faint" data-testid="cal-reprise-raison">
              {raison}
            </p>
          )}
        </>
      )}

      {champsFautifs.map((champ) => (
        <p
          key={champ}
          role="alert"
          data-testid={`cal-reprise-erreur-${champ}`}
          className="mt-2 text-xs text-red-300"
        >
          {String(erreurs[champ])}
        </p>
      ))}
    </div>
  )
}
