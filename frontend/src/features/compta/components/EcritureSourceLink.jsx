import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BookOpen } from 'lucide-react'
import comptaApi from '../../../api/comptaApi'
import { unwrap } from './useComptaList.js'

/* ============================================================================
   WIR24 — Lien « écriture comptable » d'un document source.
   ----------------------------------------------------------------------------
   Composant réutilisable, propriété du module Comptabilité : rendu sur le
   détail d'une facture / paiement / avoir pour POINTER vers l'écriture au
   grand livre auto-générée (quand le réglage société
   ``comptabilite_auto_ecritures`` est actif — WIR24). Il interroge
   ``GET /compta/ecritures/?source_type=&source_id=`` (company-scoped côté API)
   et n'affiche RIEN tant qu'aucune écriture n'existe (auto-génération OFF, ou
   pas encore passée) — aucune régression pour les sociétés qui n'ont pas
   activé le réglage.
   ========================================================================== */

export default function EcritureSourceLink({ sourceType, sourceId }) {
  const [ecriture, setEcriture] = useState(null)

  useEffect(() => {
    if (!sourceType || !sourceId) return undefined
    let alive = true
    comptaApi.ecritures
      .list({ source_type: sourceType, source_id: sourceId })
      .then((res) => {
        if (alive) setEcriture(unwrap(res)[0] || null)
      })
      .catch(() => { if (alive) setEcriture(null) })
    return () => { alive = false }
  }, [sourceType, sourceId])

  if (!ecriture) return null

  return (
    <Link
      to={`/comptabilite/ecritures?source_type=${sourceType}&source_id=${sourceId}`}
      className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
      data-testid="ecriture-source-link"
    >
      <BookOpen className="h-4 w-4" aria-hidden="true" />
      Voir l’écriture comptable
      {ecriture.numero ? ` (${ecriture.numero})` : ''}
    </Link>
  )
}
