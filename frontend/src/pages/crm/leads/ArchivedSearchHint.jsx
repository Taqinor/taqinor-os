import { Button } from '../../../ui'

/* Incident 02/10/2026 — la recherche des leads filtre la liste CHARGÉE, qui
   exclut les archivés par défaut : « aucun résultat » laissait croire le lead
   disparu. Quand une recherche ne trouve AUCUN lead actif, on propose
   d'élargir à « Tous » (même dimension serveur `archived` que le bouton
   « Archivés » de FilterBar). Muet dans tous les autres cas. */
export default function ArchivedSearchHint({ q, archived, count, loading, onWiden }) {
  const texte = String(q || '').trim()
  if (loading || !texte || count > 0 || (archived ?? 'actifs') !== 'actifs') return null
  return (
    <div className="lp-archived-hint" role="status">
      Aucun lead actif ne correspond à « {texte} ».{' '}
      <Button type="button" variant="link" size="sm" onClick={onWiden}>
        Chercher aussi dans les leads archivés
      </Button>
    </div>
  )
}
