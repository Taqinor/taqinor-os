import { useEffect } from 'react'
import { Smartphone } from 'lucide-react'
import { annoncer } from '../lib/gestes'

/* ============================================================================
   TCH46 — Bandeau de conflit entre appareils (A16-N8, 409 `conflit_version`) : « Modifiée sur
   ton autre appareil à 10:42 · Garder la mienne · Prendre l'autre ». SANS PERTE : la saisie en
   cours reste là tant que la personne n'a pas choisi. `Garder la mienne` renvoie la saisie avec
   le `lock_version` de `actuel` ; `Prendre l'autre` adopte la tâche `actuel`.
   Annonce lue une fois à l'apparition (textes.md §2.19, « Conflit »).
   Maquette : docs/taches/maquettes/etat-conflit.html.
   ========================================================================== */

export const PHRASE_CONFLIT = "Modifiée sur ton autre appareil : choisis Garder la mienne ou Prendre l'autre"

export default function BandeauConflit({ heure = '', onGarder, onPrendre }) {
  useEffect(() => { annoncer(PHRASE_CONFLIT) }, [])
  return (
    <div className="conflit" role="group" aria-label="Conflit entre appareils">
      <p>
        <Smartphone className="i i-16" aria-hidden="true" />
        <span className="chiffres">{heure ? `Modifiée sur ton autre appareil à ${heure}` : 'Modifiée sur ton autre appareil'}</span>
      </p>
      <div className="carte-actions">
        <button type="button" className="bouton plein-accent" onClick={onGarder}>Garder la mienne</button>
        <button type="button" className="bouton second" onClick={onPrendre}>Prendre l'autre</button>
      </div>
    </div>
  )
}
