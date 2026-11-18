import { useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ChevronLeft } from 'lucide-react'
import { lireReglages, modifierReglages } from '../../api/tachesApi'
import { frenchError } from '../../lib/frenchError'
import CoquilleTaches from '../../features/taches/coquille/CoquilleTaches'
import { configurerGestes } from '../../features/taches/lib/gestes'
import ListeRubriques, { Avance, MesDonnees, titreRubrique } from '../../features/taches/reglages/Rubriques'
import { naviguerApresFeuille } from '../../features/taches/ui/FeuilleACrans'
import ViePrivee from '../../features/taches/reglages/ViePrivee'
import { ReglageSuggestions } from '../../features/taches/atrier/Suggestions'
import { FAMILLES_SUGGESTIONS, accord } from '../../features/taches/lib/textes'
import MonIphone from '../../features/taches/iphone/MonIphone'
import Notifications, { CoupeCircuit } from '../../features/taches/reglages/Notifications'

/* ============================================================================
   TCH108 — Écran « Réglages » (routes /taches/reglages et /taches/reglages/:rubrique ; atteignable
   par le menu ⋯ de la coquille). Rubriques construites : `notifications`, `iphone`, `vie-privee`, `suggestions` (TCH167), `donnees`, `avance`.
   Lecture : `GET reglages/` (`contract_samples/reglages.json`) ; chaque interrupteur envoie
   `PATCH reglages/` (liste blanche) et adopte la valeur rendue ; l'erreur du serveur s'affiche
   sous le réglage. Un échec de lecture dit « Pas à jour » et garde l'écran.
   Textes : textes.md §2.14, §6. Maquettes : reglages*.html.
   ========================================================================== */

const messageDe = (err, champ) => {
  const brut = err?.response?.data?.[champ]
  return Array.isArray(brut) && brut.length > 0 ? String(brut[0]) : frenchError(err, 'Réessaie dans un instant.')
}

// Sous la largeur bureau des styles Tâches (768 px), une rubrique s'ouvre en sous-page.
const ETROIT = '(max-width: 767px)'
const lireEtroit = () => typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia(ETROIT).matches

function useEtroit() {
  const [etroit, setEtroit] = useState(lireEtroit)
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return undefined
    const requete = window.matchMedia(ETROIT)
    const suivre = () => setEtroit(requete.matches)
    requete.addEventListener?.('change', suivre)
    return () => requete.removeEventListener?.('change', suivre)
  }, [])
  return etroit
}

// `/taches/reglages/iphone?etape=calendrier` ouvre d'emblée l'étape « calendrier » (« Mes agendas » y vit)
const ETAPES_IPHONE = { notifications: 0, calendrier: 1, siri: 2, tuile: 3, accueil: 4 }

function Contenu({ rubrique, reglages, erreur, basculer, navigate, etape }) {
  if (rubrique === 'iphone') {
    return <MonIphone reglages={reglages} onReglage={basculer} erreur={erreur} etapeDemandee={ETAPES_IPHONE[etape] ?? null} />
  }
  if (rubrique === 'notifications') return <Notifications reglages={reglages} onReglage={basculer} erreur={erreur} />
  if (rubrique === 'vie-privee') {
    return (
      <ViePrivee
        allume={Boolean(reglages?.comprendre_mon_rythme)}
        onBasculer={(valeur) => basculer('comprendre_mon_rythme', valeur)}
        onMesDonnees={() => navigate('/taches/reglages/donnees')}
        erreur={erreur.comprendre_mon_rythme}
      />
    )
  }
  if (rubrique === 'suggestions') return <ReglageSuggestions reglages={reglages} onReglage={basculer} erreur={erreur} />
  if (rubrique === 'donnees') return <MesDonnees onEfface={() => naviguerApresFeuille(navigate, '/taches/aujourdhui')} />
  if (rubrique === 'avance') {
    return (
      <>
        <Avance
          sansDelai={Boolean(reglages?.messages_sans_delai)}
          onSansDelai={(valeur) => basculer('messages_sans_delai', valeur)}
          erreur={erreur.messages_sans_delai}
        />
        <CoupeCircuit estAdmin={Boolean(reglages?.est_admin)} />
      </>
    )
  }
  return null
}

export default function Reglages() {
  const { rubrique } = useParams()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [reglages, setReglages] = useState(null)
  const [echec, setEchec] = useState(false)
  const [erreur, setErreur] = useState({})
  const [essai, setEssai] = useState(0)
  const etroit = useEtroit()

  useEffect(() => {
    let actif = true
    lireReglages()
      .then((reponse) => {
        if (!actif) return
        setReglages(reponse.data)
        setEchec(false)
        configurerGestes({ sansDelai: Boolean(reponse.data.messages_sans_delai) })
      })
      .catch(() => { if (actif) setEchec(true) })
    return () => { actif = false }
  }, [essai])

  const basculer = async (champ, valeur) => {
    setErreur((anciennes) => ({ ...anciennes, [champ]: '' }))
    try {
      await modifierReglages({ [champ]: valeur })
      setReglages((actuels) => ({ ...actuels, [champ]: valeur }))
      if (champ === 'messages_sans_delai') configurerGestes({ sansDelai: valeur })
    } catch (err) {
      setErreur((anciennes) => ({ ...anciennes, [champ]: messageDe(err, champ) }))
    }
  }

  // Passe visuelle n° 47 — sur iPhone, une rubrique est une SOUS-PAGE (reglages-donnees.html) : son nom en titre,
  // « ‹ Réglages » pour revenir, la liste des rubriques cachée (CSS, `.es-ouverte`). Au bureau : maître-détail, la
  // liste reste à gauche et le panneau porte le nom de la rubrique.
  const nom = titreRubrique(rubrique)
  const sousPage = Boolean(nom) && etroit
  return (
    <CoquilleTaches ecran="reglages" titre={sousPage ? nom : 'Réglages'}>
      {sousPage ? (
        <div className="ep-barre es-barre-sous-page">
          <button type="button" className="ep-retour" onClick={() => navigate('/taches/reglages')}>
            <ChevronLeft className="i" aria-hidden="true" />Réglages
          </button>
        </div>
      ) : null}
      {echec ? (
        <div className="bandeau" role="status">
          <span className="bandeau-texte"><span className="bandeau-titre">Pas à jour</span></span>
          <button type="button" className="bouton lien" onClick={() => setEssai((n) => n + 1)}>Réessayer</button>
        </div>
      ) : null}
      <div className={`es-reglages-grille${nom ? ' es-ouverte' : ''}`}>
        <ListeRubriques
          courante={rubrique}
          onOuvrir={(cle) => navigate(`/taches/reglages/${cle}`)}
          resumes={reglages ? { suggestions: `${accord(reglages.familles_suggestions?.length ?? 0, 'suggestion')} sur ${FAMILLES_SUGGESTIONS.length}` } : undefined}
        />
        <div className="es-panneau">
          {nom && !sousPage ? <h2 className="es-panneau-titre">{nom}</h2> : null}
          <Contenu rubrique={rubrique} reglages={reglages} erreur={erreur} basculer={basculer} navigate={navigate} etape={params.get('etape')} />
        </div>
      </div>
    </CoquilleTaches>
  )
}
