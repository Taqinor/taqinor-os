import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
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

  // la palette « Créer une tâche » rejoint l'événement de saisie (la feuille ouverte, qu'elle soit la nôtre ou celle de /taches)
  useEffect(() => {
    const surPalette = (e) => {
      if (e?.detail?.type === 'tache') window.dispatchEvent(new CustomEvent(EVENEMENT_SAISIR, { detail: {} }))
    }
    window.addEventListener(QUICK_CREATE_EVENT, surPalette)
    return () => window.removeEventListener(QUICK_CREATE_EVENT, surPalette)
  }, [])

  useEffect(() => {
    const ouvrir = () => setOuverteSur(chemin.current)
    window.addEventListener(EVENEMENT_SAISIR, ouvrir)
    return () => window.removeEventListener(EVENEMENT_SAISIR, ouvrir)
  }, [])

  const fermer = useCallback(() => setOuverteSur(null), [])
  if (!horsTaches) return null
  const lienParDefaut = cible ? { ...cible, libelle: libelleDeCible(cible.cible) } : null
  return (
    <div className="tch" data-presence="taches">
      <Suspense fallback={null}>
        <FeuilleSaisie ouverte={ouverte} onFermer={fermer} lienParDefaut={lienParDefaut} />
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
