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

/* ============================================================================
   CIQ138 — CONTRAINTES DE SITE DU PROJET (assureur, dégagements, îlots).
   ----------------------------------------------------------------------------
   Champ serveur `Calepinage.contraintes_site` (CIQ136, contrat
   `calepinage_detail.json`) : VIDE par défaut ; le préréglage FM Global
   DS 1-15 (avril 2026) ne se charge QUE sur clic, QUE pour l'assureur FM ;
   une valeur sans SOURCE est refusée (comme le serveur). Les règles affichées
   à côté des obstacles sont celles que le serveur publie (`regles`), jamais
   recomposées ici. Saisie libre : `step="any"`, aucun nombre n'est arrondi.
   ========================================================================== */

/** Le préréglage FM Global DS 1-15 — MÊMES valeurs que
 *  `services/degagements.py PRESET_FM_DS_1_15` (verrouillé par un test sur le
 *  contrat committé `calepinage_detail.json`). */
export const PRESET_FM_DS_1_15 = {
  assureur: 'fm_global',
  degagements_m: { lanterneau: 1.8, joint_dilatation: 1.2 },
  ilot_max_m: { longueur: 46.0, largeur: 46.0 },
  allee_ilot_m: 1.2,
  source: {
    document: 'FM Global Data Sheet 1-15 « Roof-Mounted Solar Photovoltaic Panels » (avril 2026)',
    date: '2026-04',
    reference: '§2.1.1.4 B-E',
  },
  regles: {
    lanterneau: 'DS 1-15 §2.1.1.4 — 1,8 m des lanterneaux',
    joint_dilatation: 'DS 1-15 §2.1.1.4 — 1,2 m des joints de dilatation',
    ilot_max_m: 'DS 1-15 §2.1.1.4 — champs ≤ 46 × 46 m',
    allee_ilot_m: 'DS 1-15 §2.1.1.4 — allées de 1,2 m entre champs',
  },
}

const ASSUREURS = [
  ['aucun', 'Aucun'], ['fm_global', 'FM Global'], ['apsad', 'APSAD'], ['autre', 'Autre'],
]
const DEGAGEMENTS = [
  ['lanterneau', 'Lanterneau'], ['exutoire', 'Exutoire de fumée'],
  ['joint_dilatation', 'Joint de dilatation'], ['rive', 'Rive'],
]
export const MESSAGE_SANS_SOURCE = 'Une contrainte de site exige sa source '
  + '(document, date, référence) — jamais une valeur sans source.'

const texte = (n) => (n === null || n === undefined ? '' : String(n))

/** Objet serveur → champs de saisie (chaînes). */
function versChamps(c) {
  const o = c || {}
  return {
    assureur: o.assureur || 'aucun',
    deg: Object.fromEntries(DEGAGEMENTS.map(([k]) => [k, texte(o.degagements_m?.[k])])),
    longueur: texte(o.ilot_max_m?.longueur),
    largeur: texte(o.ilot_max_m?.largeur),
    allee: texte(o.allee_ilot_m),
    document: o.source?.document || '',
    date: o.source?.date || '',
    reference: o.source?.reference || '',
  }
}

const nombreOuNull = (t) => {
  if (String(t).trim() === '') return null
  const n = Number(String(t).replace(',', '.'))
  return Number.isFinite(n) ? n : NaN
}

/** Champs de saisie → objet serveur ({} = aucune contrainte). */
function versObjet(ch, initiales) {
  const deg = {}
  for (const [k] of DEGAGEMENTS) {
    const n = nombreOuNull(ch.deg[k])
    if (n !== null) deg[k] = n
  }
  const longueur = nombreOuNull(ch.longueur)
  const largeur = nombreOuNull(ch.largeur)
  const allee = nombreOuNull(ch.allee)
  const aDesValeurs = Object.keys(deg).length > 0 || longueur !== null
    || largeur !== null || allee !== null
  if (!aDesValeurs && ch.assureur === 'aucun') return {}
  const sortie = {
    assureur: ch.assureur,
    degagements_m: deg,
    ilot_max_m: longueur !== null || largeur !== null ? { longueur, largeur } : null,
    allee_ilot_m: allee,
    source: { document: ch.document.trim(), date: ch.date.trim() || null, reference: ch.reference.trim() },
  }
  // Les règles publiées par le serveur restent attachées tant qu'on n'a pas
  // changé de contraintes (elles sont relues du serveur au rechargement).
  if (initiales?.regles) sortie.regles = initiales.regles
  return sortie
}

function ContraintesSite({ calepinageId, initiales, lectureSeule, onEnregistrees }) {
  const [champs, setChamps] = useState(() => versChamps(initiales))
  const [regles, setRegles] = useState(initiales?.regles || null)
  const [touche, setTouche] = useState(false)
  const [erreurs, setErreurs] = useState({})
  const [message, setMessage] = useState(null)
  const [occupe, setOccupe] = useState(false)

  const maj = (patch) => { setTouche(true); setMessage(null); setChamps((c) => ({ ...c, ...patch })) }
  const majDeg = (k, v) => maj({ deg: { ...champs.deg, [k]: v } })

  const chargerPreset = () => {
    setTouche(true)
    setMessage(null)
    setErreurs({})
    setChamps(versChamps(PRESET_FM_DS_1_15))
    setRegles(PRESET_FM_DS_1_15.regles)
  }

  const enregistrer = () => {
    setErreurs({})
    setMessage(null)
    // « Enregistrer → rouvrir → enregistrer sans toucher » = l'objet serveur
    // à l'identique : tant que rien n'a été touché, on renvoie l'objet lu.
    let corps = initiales || {}
    if (touche) {
      corps = versObjet(champs, regles ? { regles } : initiales)
      const erreurNombre = [
        ...DEGAGEMENTS.map(([k]) => [`deg.${k}`, nombreOuNull(champs.deg[k])]),
        ['longueur', nombreOuNull(champs.longueur)],
        ['largeur', nombreOuNull(champs.largeur)],
        ['allee', nombreOuNull(champs.allee)],
      ].filter(([, n]) => Number.isNaN(n)).map(([k]) => k)
      if (erreurNombre.length) {
        setErreurs(Object.fromEntries(erreurNombre.map((k) => [k, 'Saisissez un nombre de mètres.'])))
        return
      }
      const valeurs = Object.keys(corps).length > 0 && (
        Object.keys(corps.degagements_m || {}).length > 0
        || corps.ilot_max_m != null || corps.allee_ilot_m != null)
      if (valeurs && !corps.source.document) {
        setErreurs({ source: MESSAGE_SANS_SOURCE })
        return
      }
    }
    setOccupe(true)
    Promise.resolve(calepinageApi.calepinages.update(calepinageId, { contraintes_site: corps }))
      .then((res) => {
        const vu = res?.data?.contraintes_site
        if (vu) { setChamps(versChamps(vu)); setRegles(vu.regles || null) }
        setTouche(false)
        setMessage('Contraintes du site enregistrées pour ce projet.')
        onEnregistrees?.()
      })
      .catch((e) => {
        const d = e?.response?.data?.contraintes_site
        const t = Array.isArray(d) ? d[0] : d
        if (t) setErreurs(/source/i.test(String(t)) ? { source: t } : { general: t })
        else setErreurs({ general: 'Les contraintes du site n’ont pas pu être enregistrées.' })
      })
      .finally(() => setOccupe(false))
  }

  const champNombre = (id, etiquette, valeurChamp, onChange, cleErreur, regle) => (
    <label className="block" key={id}>
      <span className="tech-label text-lune-faint">{etiquette}</span>
      <input
        type="number" step="any" min="0" id={id} value={valeurChamp}
        disabled={lectureSeule}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white"
      />
      {regle && (
        <span className="mt-0.5 block text-xs text-lune-faint"
          data-testid={`ciq138-regle-${id}`}>{regle}</span>
      )}
      {erreurs[cleErreur] && (
        <span className="mt-0.5 block text-xs text-red-300" role="alert">{erreurs[cleErreur]}</span>
      )}
    </label>
  )

  return (
    <div className="mt-6 border-t border-white/10 pt-4" data-testid="ciq138-contraintes-site">
      <p className="tech-label rule-brass text-brass-300">Contraintes du site</p>
      <p className="mt-1 text-xs text-lune-faint">
        Propres à ce projet (assureur, sécurité incendie) : vides par défaut,
        jamais imposées. Toute valeur exige sa source.
      </p>

      <label className="mt-3 block max-w-xs">
        <span className="tech-label text-lune-faint">Assureur</span>
        <select
          id="ciq138-assureur" value={champs.assureur} disabled={lectureSeule}
          onChange={(e) => maj({ assureur: e.target.value })}
          className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white"
        >
          {ASSUREURS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </label>

      {champs.assureur === 'fm_global' && !lectureSeule && (
        <button type="button" onClick={chargerPreset} data-testid="ciq138-preset-fm"
          className="mt-3 rounded border border-white/15 px-3 py-1.5 text-xs font-semibold text-white">
          Charger le préréglage FM Global DS 1-15 (avril 2026)
        </button>
      )}

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {DEGAGEMENTS.map(([k, l]) => champNombre(
          `ciq138-deg-${k}`, `Dégagement — ${l} (m)`, champs.deg[k],
          (v) => majDeg(k, v), `deg.${k}`, k === 'lanterneau' || k === 'joint_dilatation' ? regles?.[k] : null))}
        {champNombre('ciq138-ilot-longueur', 'Îlot maximal — longueur (m)', champs.longueur,
          (v) => maj({ longueur: v }), 'longueur', regles?.ilot_max_m)}
        {champNombre('ciq138-ilot-largeur', 'Îlot maximal — largeur (m)', champs.largeur,
          (v) => maj({ largeur: v }), 'largeur', null)}
        {champNombre('ciq138-allee-ilot', 'Allée entre îlots (m)', champs.allee,
          (v) => maj({ allee: v }), 'allee', regles?.allee_ilot_m)}
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <label className="block">
          <span className="tech-label text-lune-faint">Source — document</span>
          <input type="text" id="ciq138-source-document" value={champs.document}
            disabled={lectureSeule} onChange={(e) => maj({ document: e.target.value })}
            className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white" />
        </label>
        <label className="block">
          <span className="tech-label text-lune-faint">Source — date</span>
          <input type="text" id="ciq138-source-date" value={champs.date}
            disabled={lectureSeule} onChange={(e) => maj({ date: e.target.value })}
            className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white" />
        </label>
        <label className="block">
          <span className="tech-label text-lune-faint">Source — référence</span>
          <input type="text" id="ciq138-source-reference" value={champs.reference}
            disabled={lectureSeule} onChange={(e) => maj({ reference: e.target.value })}
            className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white" />
        </label>
      </div>
      {erreurs.source && (
        <p className="mt-1 text-xs text-red-300" role="alert" data-testid="ciq138-erreur-source">
          {erreurs.source}
        </p>
      )}
      {erreurs.general && (
        <p className="mt-2 text-sm text-red-300" role="alert">{erreurs.general}</p>
      )}

      {!lectureSeule && (
        <div className="mt-3">
          <button type="button" onClick={enregistrer} disabled={occupe}
            data-testid="ciq138-enregistrer"
            className="rounded bg-brass-500/20 px-4 py-2 text-sm font-semibold text-brass-200">
            Enregistrer les contraintes
          </button>
        </div>
      )}
      {message && (
        <p className="mt-2 text-sm text-lune-soft" role="status">{message}</p>
      )}
    </div>
  )
}

export default function PanneauAllees({
  entree = null, lectureSeule = false,
  // CIQ138 — sans `calepinageId`, la section « Contraintes du site » n'est pas montée.
  calepinageId = null, contraintesSite = null, onContraintesEnregistrees = null,
}) {
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

      {calepinageId != null && (
        <ContraintesSite
          calepinageId={calepinageId} initiales={contraintesSite}
          lectureSeule={lectureSeule} onEnregistrees={onContraintesEnregistrees}
        />
      )}
    </div>
  )
}
