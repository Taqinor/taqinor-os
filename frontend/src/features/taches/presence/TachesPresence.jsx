import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { useHasPermission } from '../../../hooks/useHasPermission'
import { cibleDepuisEcran, EVENEMENT_SAISIR, libelleDeCible } from './cibleEcran'

/* ============================================================================
   TCH102 — Hôte `TachesPresence` : « Créer une tâche » depuis n'importe quel écran de l'ERP
   (spec-6a-erp.md « Écrans », arbitrage A10). Monté UNE FOIS dans la coquille de l'ERP (TCH123) ;
   ici il n'est que construit et exporté.

   - Il écoute `taqinor:quick-create` (`type: 'tache'`, la palette) et le traduit en
     `taqinor:taches:saisir` — l'événement de saisie UNIQUE, déjà écouté par la feuille de saisie
     (`c t` le déclenche directement, `shortcuts.js`). Aucun second mécanisme de saisie.
   - Il lit l'écran À L'INSTANT (`useLocation` → `cibleDepuisEcran`) : sur la fiche d'un lead, d'un
     client ou d'un devis, la feuille s'ouvre avec la puce « Lié à : … » (retirable) ; ailleurs, sans lien.
   - Hors `/taches` seulement : la coquille de Tâches porte déjà sa propre feuille et reçoit le même événement.
   - Sans le droit `taches_voir` (lu dans `state.auth.permissions`, jamais un repli) : rien n'est monté,
     rien n'écoute, `c t` ne fait rien.
   La feuille est chargée à part (`lazy`) : l'ERP des comptes sans Tâches ne paie pas son poids.
   - Parce qu'elle est chargée à part, c'est L'HÔTE qui écoute l'événement et qui REMET la demande à la feuille
     (`demandes.abonner` : la feuille s'abonne à son montage et reçoit aussitôt la demande arrivée pendant son
     chargement) : un geste fait à ce moment-là ne perd ni la phrase tapée ni le lien de l'écran (acceptation de la
     fusion 4, P142.3 et P142.4).
   - Il répond « reçu » en annulant l'événement (`preventDefault`) : un écran qui envoie une phrase (Activités,
     TCH159) ne vide son champ que si quelqu'un l'a prise.
   ========================================================================== */

const QUICK_CREATE_EVENT = 'taqinor:quick-create'
const FeuilleSaisie = lazy(() => import('../saisie/FeuilleSaisie'))
const ZoneAnnonces = lazy(() => import('../coquille/CoquilleTaches').then((m) => ({ default: m.ZoneAnnonces })))

const dansTaches = (pathname) => pathname === '/taches' || pathname.startsWith('/taches/')

function PresenceActive() {
  const lieu = useLocation()
  // la feuille est ouverte POUR un écran : si l'on change d'écran (ou qu'on entre dans /taches), elle n'est plus ouverte
  const [ouverteSur, setOuverteSur] = useState(null)
  const chemin = useRef(lieu.pathname)
  useEffect(() => { chemin.current = lieu.pathname })
  const ouverte = ouverteSur === lieu.pathname
  const cible = cibleDepuisEcran(lieu)
  const horsTaches = !dansTaches(lieu.pathname)
  // ce que l'écran a demandé (le `detail` de l'événement) : remis à la feuille si elle écoute, gardé sinon
  const boite = useRef({ lire: null, enAttente: null })
  const demandes = useMemo(() => ({
    abonner(lire) {
      const { enAttente } = boite.current
      boite.current = { lire, enAttente: null }
      if (enAttente) lire(enAttente)
      return () => { if (boite.current.lire === lire) boite.current.lire = null }
    },
  }), [])

  // la palette « Créer une tâche » rejoint l'événement de saisie (la feuille ouverte, qu'elle soit la nôtre ou celle de /taches)
  useEffect(() => {
    const surPalette = (e) => {
      if (e?.detail?.type === 'tache') window.dispatchEvent(new CustomEvent(EVENEMENT_SAISIR, { detail: {} }))
    }
    window.addEventListener(QUICK_CREATE_EVENT, surPalette)
    return () => window.removeEventListener(QUICK_CREATE_EVENT, surPalette)
  }, [])

  useEffect(() => {
    const ouvrir = (e) => {
      if (dansTaches(chemin.current)) return // dans /taches, la coquille a sa propre feuille, qui écoute elle-même
      e?.preventDefault?.() // « reçu »
      const detail = e?.detail ?? {}
      if (boite.current.lire) boite.current.lire(detail)
      else boite.current.enAttente = detail
      setOuverteSur(chemin.current)
    }
    window.addEventListener(EVENEMENT_SAISIR, ouvrir)
    return () => window.removeEventListener(EVENEMENT_SAISIR, ouvrir)
  }, [])

  const fermer = useCallback(() => setOuverteSur(null), [])
  if (!horsTaches) return null
  const lienParDefaut = cible ? { ...cible, libelle: libelleDeCible(cible.cible) } : null
  return (
    <div className="tch" data-presence="taches">
      <Suspense fallback={null}>
        <FeuilleSaisie ouverte={ouverte} onFermer={fermer} lienParDefaut={lienParDefaut} demandes={demandes} />
        <ZoneAnnonces />
      </Suspense>
    </div>
  )
}

/** L'hôte : rien du tout sans `taches_voir`. */
export default function TachesPresence() {
  const peutVoir = useHasPermission('taches_voir')
  return peutVoir ? <PresenceActive /> : null
}
