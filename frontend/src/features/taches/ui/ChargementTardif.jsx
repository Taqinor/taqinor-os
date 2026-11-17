import { useEffect, useState } from 'react'

/* ============================================================================
   Raccord F2 — l'état « chargement » commun aux écrans de Tâches (spec-7 « Partout » : squelette après 1 s, jamais
   sur une liste déjà affichée ; textes.md §2.19 : annonce « Chargement »). Rien pendant la première seconde (pas de
   clignotement), puis trois lignes « os » comme etat-chargement.html. L'écran le monte tant qu'il n'a RIEN à montrer.
   ========================================================================== */

const DELAI_MS = 1000
const LIGNES = [['72%', '44%'], ['84%', '38%'], ['64%', '']]

export default function ChargementTardif({ actif = true }) {
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    if (!actif) return undefined
    const minuteur = setTimeout(() => setVisible(true), DELAI_MS)
    return () => { clearTimeout(minuteur); setVisible(false) }
  }, [actif])
  if (!actif || !visible) return null
  return (
    <div className="squelette" role="status" aria-label="Chargement">
      {LIGNES.map(([l1, l2], rang) => (
        <div key={rang} className="ligne" aria-hidden="true">
          <span className="case"><span className="os cercle" /></span>
          <div className="ligne-corps">
            <span className="os l1" style={{ width: l1 }} />
            {l2 ? <span className="os l2" style={{ width: l2 }} /> : null}
          </div>
          <div className="ligne-fin" />
        </div>
      ))}
    </div>
  )
}
