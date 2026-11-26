// ADEP19 — écran « Hors ligne » du démarrage : `fetchMe` a échoué SANS refus
// d'authentification (aucune réponse, 5xx) — on ne renvoie pas vers /login (la
// session peut être valide). Nouvel essai au clic et au retour du réseau
// (événement `online`) : les loaders de la route sont rejoués.
// J3 — un serveur LENT (délai dépassé ou 5xx, navigateur en ligne : donnée de loader
// `lent`) n'est pas « hors ligne » : l'écran le dit (« Le serveur met du temps à
// répondre ») et réessaie seul toutes les 15 s, avec un « Réessayer » visible.
import { useEffect, useRef } from 'react'
import { useLoaderData, useLocation, useRevalidator } from 'react-router-dom'

const TEXTES_DEMARRAGE = {
  horsLigne: {
    titre: 'Hors ligne',
    phrase: 'Impossible de joindre le serveur. Vos données restent sur cet appareil.',
    bouton: 'Hors ligne — réessayer',
  },
  lent: {
    titre: 'Le serveur met du temps à répondre',
    phrase: 'Nouvel essai automatique dans quelques secondes. Vos données restent sur cet appareil.',
    bouton: 'Réessayer',
  },
}
const DELAI_NOUVEL_ESSAI_MS = 15000
// T4-X8-002 — rechargé hors ligne sur le relevé de visite au téléphone : l'écran ne peut pas se rouvrir sans
// session ni calepinage (l'API n'est jamais en cache), mais le brouillon et la file des photos sont sur le
// téléphone — la phrase dit ce qu'il en advient au lieu d'un « vos données » vague.
const RELEVE_VISITE = /^\/calepinage\/[^/]+\/releve\/?$/
const PHRASE_RELEVE = 'Vos mesures et vos photos sont gardées sur ce téléphone. '
  + 'Elles s’afficheront et partiront au retour du réseau.'

export default function HorsLigneDemarrage() {
  const revalidator = useRevalidator()
  const lent = useLoaderData()?.lent === true
  const { pathname } = useLocation()
  const textes = lent ? TEXTES_DEMARRAGE.lent
    : RELEVE_VISITE.test(pathname) ? { ...TEXTES_DEMARRAGE.horsLigne, phrase: PHRASE_RELEVE } : TEXTES_DEMARRAGE.horsLigne
  const reessayer = () => revalidator.revalidate()
  // Dernier `reessayer` (le revalidator change à chaque rendu) : l'écouteur
  // `online` est posé une seule fois et appelle toujours la version à jour.
  const reessayerRef = useRef(reessayer)
  useEffect(() => { reessayerRef.current = reessayer })

  useEffect(() => {
    const surRetourReseau = () => reessayerRef.current()
    window.addEventListener('online', surRetourReseau)
    return () => window.removeEventListener('online', surRetourReseau)
  }, [])

  // J3 — serveur lent : nouvel essai en arrière-plan (jamais hors ligne : le navigateur dirait `online`).
  const enCours = revalidator.state === 'loading'
  useEffect(() => {
    if (!lent || enCours) return undefined
    const t = setTimeout(() => reessayerRef.current(), DELAI_NOUVEL_ESSAI_MS)
    return () => clearTimeout(t)
  }, [lent, enCours])

  return (
    <div
      role="alert"
      data-etat-demarrage={lent ? 'lent' : 'hors-ligne'}
      style={{
        minHeight: '100vh', display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', gap: 12, padding: 24,
        textAlign: 'center',
      }}
    >
      <h1 style={{ fontSize: 20, margin: 0 }}>{textes.titre}</h1>
      <p style={{ margin: 0 }}>{textes.phrase}</p>
      {lent && enCours && <p role="status" style={{ margin: 0 }}>Nouvel essai en cours…</p>}
      <button type="button" onClick={reessayer} disabled={enCours} style={{ minHeight: 44 }}>
        {textes.bouton}
      </button>
    </div>
  )
}
