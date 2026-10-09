// ADEP19 — écran « Hors ligne » du démarrage : `fetchMe` a échoué SANS refus
// d'authentification (aucune réponse, 5xx) — on ne renvoie pas vers /login (la
// session peut être valide). Nouvel essai au clic et au retour du réseau
// (événement `online`) : les loaders de la route sont rejoués.
import { useEffect } from 'react'
import { useRevalidator } from 'react-router-dom'

export default function HorsLigneDemarrage() {
  const revalidator = useRevalidator()
  const reessayer = () => revalidator.revalidate()

  useEffect(() => {
    window.addEventListener('online', reessayer)
    return () => window.removeEventListener('online', reessayer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div
      role="alert"
      style={{
        minHeight: '100vh', display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', gap: 12, padding: 24,
        textAlign: 'center',
      }}
    >
      <h1 style={{ fontSize: 20, margin: 0 }}>Hors ligne</h1>
      <p style={{ margin: 0 }}>
        Impossible de joindre le serveur. Vos données restent sur cet appareil.
      </p>
      <button type="button" onClick={reessayer} disabled={revalidator.state === 'loading'}>
        Hors ligne — réessayer
      </button>
    </div>
  )
}
