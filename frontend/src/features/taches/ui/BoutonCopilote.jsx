import { useEffect, useState } from 'react'
import { Sparkles } from 'lucide-react'
import { EVENEMENT_OUVRIR } from '../../ia/copilotMessages'
import { useEnLigne } from '../lib/enLigne'

/* ============================================================================
   TCH45 — Bouton « Copilote » de l'en-tête (spec-7 §2) : ouvre le panneau de l'ERP avec le
   contexte de l'écran, par l'événement `taqinor:assistant:ouvrir` (jamais un import du
   panneau). Les quatre demandes prêtes (Planifie ma journée, Aide-moi à prioriser, Range
   ma liste, Où j'en suis ?) marchent SANS clé d'IA : le panneau s'ouvre donc toujours en
   ligne ; seule la conversation libre manque, et le bouton le DIT en une phrase.
   Hors ligne : rien ne s'ouvre, une phrase explique (textes.md §5.2, « Le Copilote »).
   Maquette : docs/taches/maquettes/composants-5.html (puce « Copilote », 36 px, cible 44).
   ========================================================================== */

export const PHRASE_SANS_CLE = "La conversation libre n'est pas branchée sur ce serveur. Les quatre demandes ci-dessus marchent sans elle."
export const PHRASE_HORS_LIGNE = 'Le Copilote a besoin du réseau. Ajouter, cocher et reporter marchent hors ligne.'
const DELAI_PHRASE_MS = 8000

export default function BoutonCopilote({ ecran, question, envoyer = false, libre = true }) {
  const enLigne = useEnLigne()
  const [phrase, setPhrase] = useState('')

  useEffect(() => {
    if (!phrase) return undefined
    const minuteur = setTimeout(() => setPhrase(''), DELAI_PHRASE_MS)
    const surEchap = (e) => { if (e.key === 'Escape') setPhrase('') }
    document.addEventListener('keydown', surEchap)
    return () => { clearTimeout(minuteur); document.removeEventListener('keydown', surEchap) }
  }, [phrase])

  const ouvrir = () => {
    if (!enLigne) { setPhrase(PHRASE_HORS_LIGNE); return }
    window.dispatchEvent(new CustomEvent(EVENEMENT_OUVRIR, {
      detail: { ecran: ecran ?? window.location.pathname, question, envoyer },
    }))
    setPhrase(libre ? '' : PHRASE_SANS_CLE)
  }

  return (
    <span className="copilote-groupe">
      <button type="button" className="copilote" aria-disabled={!enLigne || undefined} onClick={ouvrir}>
        <Sparkles className="i i-16" aria-hidden="true" />Copilote
      </button>
      {phrase ? <span className="copilote-phrase" role="status">{phrase}</span> : null}
    </span>
  )
}
