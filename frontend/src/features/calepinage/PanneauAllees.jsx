/* eslint-disable react-refresh/only-export-components --
   `suggestionAlleeGratuite` est une fonction PURE (une réponse du moteur →
   la suggestion `ALLEE_GRATUITE`, ou `null`) : la tâche exige de VÉRIFIER
   que la règle « ne jamais publier l'allée minimale quand une allée large
   est gratuite » tient, ce qui demande de l'appeler sans monter React —
   même dérogation que `RemplissageProuve.jsx` (CAL79) du même module. */
import { useEffect, useState } from 'react'
import calepinageApi from '../../api/calepinageApi'

/* ============================================================================
   CAL70 — DÉCLARER LES ALLÉES ET PASSAGES DE MAINTENANCE DANS L'ATELIER.
   ----------------------------------------------------------------------------
   Constat de la tâche : le moteur sait DÉJÀ chercher la plus grande allée à
   compte constant (`core/calepinage/allee_gratuite.py`, AOF50) et la publie
   comme une suggestion `ALLEE_GRATUITE` dans la réponse de
   `POST /calepinage/moteur/calculer/` (`suggestions[].code`, `action.patch.
   allee_m`, CAL2/CAL22) — mais AUCUN écran calepinage ne la lisait. Ce
   panneau ne réimplémente rien : il lit la MÊME suggestion que le moteur a
   déjà calculée pour ce relevé.

   LA LARGEUR D'ALLÉE EST UN RÉGLAGE SOCIÉTÉ (section « dégagements » de
   `ParametresCalepinage`, CAL45/CAL71) : elle alimente `Parametres.allee_m`
   du moteur pour TOUS les calepinages de la société, pas seulement celui-ci.
   AUCUN DÉFAUT INVENTÉ — à vide, `allee_technique` (backend) dit
   explicitement que l'allée par défaut du moteur s'applique : ce panneau
   reprend cette même discipline plutôt que de proposer un chiffre à sa place.

   « NE JAMAIS PUBLIER L'ALLÉE MINIMALE QUAND UNE ALLÉE LARGE EST GRATUITE » —
   la règle produit du moteur (AOF50). Ce panneau la rend VÉRIFIABLE à
   l'écran : `augmenter l'allée jusqu'au plateau gratuit publié` ne fait
   PERDRE AUCUN MODULE, et l'écran le dit avec les deux comptes MESURÉS,
   jamais une promesse en l'air.
   ========================================================================== */

/**
 * CAL70 — la suggestion `ALLEE_GRATUITE` d'une réponse du moteur, ou `null`.
 * Fonction PURE : elle ne calcule rien, elle LIT ce que le moteur a déjà
 * publié dans `suggestions[]` (contrat `moteur_calculer.json`).
 */
export function suggestionAlleeGratuite(resultat) {
  const suggestions = resultat?.suggestions
  if (!Array.isArray(suggestions)) return null
  const trouvee = suggestions.find((s) => s?.code === 'ALLEE_GRATUITE'
    && Number.isFinite(s?.action?.patch?.allee_m))
  if (!trouvee) return null
  return {
    alleeM: trouvee.action.patch.allee_m,
    titre: trouvee.titre ?? null,
    gainModules: trouvee.gain_modules ?? null,
    gainKwc: trouvee.gain_kwc ?? null,
    confiance: trouvee.confiance ?? null,
  }
}

/** Une grandeur du serveur, ou le tiret — jamais un zéro de remplacement. */
function valeur(brut, suffixe = '') {
  if (brut === null || brut === undefined || brut === '') return '—'
  return `${brut}${suffixe}`
}

export default function PanneauAllees({ entree = null, lectureSeule = false }) {
  const [parametres, setParametres] = useState(null)
  const [chargement, setChargement] = useState(true)
  const [champ, setChamp] = useState('')
  const [enregistrement, setEnregistrement] = useState(false)
  const [message, setMessage] = useState(null)

  const [recherche, setRecherche] = useState(null) // {enCours, resultat, refus}

  useEffect(() => {
    let annule = false
    Promise.resolve(calepinageApi.parametres.get())
      .then((res) => {
        if (annule) return
        const reglages = res?.data ?? null
        setParametres(reglages)
        const actuelle = reglages?.degagements?.allee_technique_m
        setChamp(Number.isFinite(actuelle) ? String(actuelle) : '')
      })
      .catch(() => { if (!annule) setParametres(null) })
      .finally(() => { if (!annule) setChargement(false) })
    return () => { annule = true }
  }, [])

  const alleeActuelle = parametres?.degagements?.allee_technique_m
  const alleeConnue = Number.isFinite(alleeActuelle)

  const rechercher = () => {
    if (!entree) {
      setRecherche({ enCours: false, resultat: null,
        refus: 'Aucune surface à analyser : dessinez d’abord un pan de toit.' })
      return
    }
    setRecherche({ enCours: true, resultat: null, refus: null })
    Promise.resolve(calepinageApi.moteur.calculer(entree))
      .then((res) => {
        const donnees = res?.data ?? null
        if (donnees?.job_id) {
          setRecherche({ enCours: false, resultat: null,
            refus: 'Ce relevé dépasse le calcul synchrone : relancez la '
              + 'recherche depuis le remplissage automatique une fois le '
              + 'calcul de fond terminé.' })
          return
        }
        setRecherche({ enCours: false, resultat: donnees, refus: null })
      })
      .catch((e) => setRecherche({ enCours: false, resultat: null,
        refus: e?.response?.data?.entree
          || 'Le moteur n’a pas pu chercher l’allée gratuite.' }))
  }

  const suggestion = suggestionAlleeGratuite(recherche?.resultat)

  const appliquerSuggestion = () => {
    if (!suggestion) return
    setChamp(String(suggestion.alleeM))
  }

  const enregistrer = () => {
    setEnregistrement(true)
    setMessage(null)
    const nombre = champ === '' ? null : Number(champ)
    if (champ !== '' && !Number.isFinite(nombre)) {
      setMessage('L’allée technique doit être un nombre de mètres.')
      setEnregistrement(false)
      return
    }
    const section = { ...(parametres?.degagements ?? {}) }
    if (nombre === null) {
      delete section.allee_technique_m
    } else {
      section.allee_technique_m = nombre
    }
    Promise.resolve(calepinageApi.parametres.update({ degagements: section }))
      .then((res) => {
        // La réponse du PUT EST la vérité fraîche (même forme que GET) : pas
        // besoin d'une seconde lecture pour la refléter.
        setParametres(res?.data ?? null)
        setMessage('Allée technique enregistrée pour votre société.')
      })
      .catch((e) => setMessage(
        e?.response?.data?.['degagements.allee_technique_m']
        || e?.response?.data?.degagements
        || 'L’allée technique n’a pas pu être enregistrée.'))
      .finally(() => setEnregistrement(false))
  }

  return (
    <div className="cine-card mt-6 p-6" data-testid="cal-panneau-allees">
      <p className="tech-label rule-brass text-brass-300">
        Allées et passages de maintenance
      </p>

      <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
        <div data-testid="cal-allees-actuelle">
          <dd className="fig text-lg text-white">
            {alleeConnue ? valeur(alleeActuelle, ' m') : '—'}
          </dd>
          <dt className="tech-label mt-0.5 text-lune-faint">
            Allée technique — réglage société
          </dt>
        </div>
      </dl>
      {!alleeConnue && !chargement && (
        <p className="mt-2 text-xs text-lune-faint" data-testid="cal-allees-non-reglee">
          Aucune allée technique n’est réglée pour votre société : le moteur
          applique son allée par défaut — comportement d’aujourd’hui, inchangé.
        </p>
      )}

      {!lectureSeule && (
        <>
          <label className="mt-4 block max-w-xs" data-testid="cal-allees-champ">
            <span className="tech-label text-lune-faint">
              Largeur d’allée technique (m)
            </span>
            <input
              type="number"
              step="any"
              min="0"
              id="cal-allees-largeur"
              value={champ}
              onChange={(e) => setChamp(e.target.value)}
              className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white"
            />
          </label>

          <div className="mt-3 flex flex-wrap gap-3">
            <button type="button" onClick={enregistrer} disabled={enregistrement}
              data-testid="cal-allees-enregistrer"
              className="rounded bg-brass-500/20 px-4 py-2 text-sm font-semibold text-brass-200">
              Enregistrer
            </button>
            <button type="button" onClick={rechercher} disabled={recherche?.enCours}
              data-testid="cal-allees-rechercher"
              className="rounded border border-white/15 px-4 py-2 text-sm font-semibold text-white">
              {recherche?.enCours ? 'Recherche en cours…' : 'Chercher l’allée gratuite'}
            </button>
          </div>
        </>
      )}

      {recherche?.refus && (
        <p className="mt-3 text-sm text-red-300" role="alert"
          data-testid="cal-allees-refus">{recherche.refus}</p>
      )}

      {/* La règle produit AOF50, VÉRIFIABLE à l'écran : le plateau publié ne
          perd AUCUN module par rapport au relevé actuel — deux comptes
          MESURÉS, jamais une promesse. */}
      {suggestion && (
        <div className="mt-4 border-t border-white/10 pt-4" data-testid="cal-allees-suggestion">
          <p className="text-sm font-semibold text-emerald-300">
            {suggestion.titre ?? `Allée gratuite jusqu’à ${suggestion.alleeM} m`}
          </p>
          <p className="mt-1 text-xs text-lune-faint">
            Élargir l’allée jusqu’à {valeur(suggestion.alleeM, ' m')} ne fait
            perdre aucun module ({valeur(suggestion.gainModules)} module(s) de
            marge{suggestion.gainKwc ? `, ${suggestion.gainKwc} kWc` : ''}
            {suggestion.confiance ? ` — confiance ${suggestion.confiance}` : ''}).
          </p>
          {!lectureSeule && (
            <button type="button" onClick={appliquerSuggestion}
              data-testid="cal-allees-appliquer-suggestion"
              className="mt-2 rounded border border-white/15 px-3 py-1.5 text-xs font-semibold text-white">
              Reprendre {valeur(suggestion.alleeM, ' m')} dans le champ
            </button>
          )}
        </div>
      )}
      {recherche?.resultat && !suggestion && (
        <p className="mt-3 text-sm text-lune-soft" data-testid="cal-allees-sans-plateau">
          Le moteur n’a trouvé aucune allée plus large à compte constant pour
          ce relevé : l’allée réglée reste la meilleure connue.
        </p>
      )}

      {message && (
        <p className="mt-3 text-sm text-lune-soft" role="status"
          data-testid="cal-allees-message">{message}</p>
      )}
    </div>
  )
}
