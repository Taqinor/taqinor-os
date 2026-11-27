import { useState } from 'react'
import { Badge, Button } from '../../ui'
import stockApi from '../../api/stockApi'
import { frenchError } from '../../lib/frenchError'
import { usePermissionAchats } from '../../features/stock/useVoitPrixAchat'
import {
  DROIT_PANNEAU_PAR_DEFAUT, LIBELLE_DEFAUT_INUTILISABLE, panneauDefautInutilisable, usePanneauParDefaut,
} from '../../features/stock/panneauParDefaut'

/* ============================================================================
   D-ACAL-169 (fondateur, 26/11/2026) — LE panneau par défaut de la société,
   sur la fiche d'un PANNEAU : la pastille « Panneau par défaut » pour tous
   (Technicien compris — un nom n'est pas un prix) et « Définir comme panneau
   par défaut » / « Retirer » pour qui porte le droit du serveur
   (`catalogue_prix_modifier`). La ligne en tête du catalogue est rendue par
   `CatalogueTable` (`LignePanneauParDefaut`). Contrat partagé :
   `backend/django_core/apps/stock/contract_samples/panneau_par_defaut.json`.
   Aucun prix ici.
   ========================================================================== */

export function ActionPanneauParDefaut({ produit, onChange }) {
  const peutDesigner = usePermissionAchats(DROIT_PANNEAU_PAR_DEFAUT)
  const [estDefaut, setEstDefaut] = useState(Boolean(produit?.panneau_par_defaut))
  const [busy, setBusy] = useState(false)
  const [erreur, setErreur] = useState(null)
  // D-ACAL-169 (rejeu) — l'état servi : un désigné inutilisable le dit ici comme sur la ligne du catalogue
  // (au plus un désigné par société : si CE produit l'est, le résumé parle de lui).
  const [resume, relire] = usePanneauParDefaut()
  const inutilisable = estDefaut && panneauDefautInutilisable(resume)
  const estPanneau = produit?.role_devis_effectif === 'panneau'
  if (!produit || (!estPanneau && !estDefaut)) return null

  const basculer = async () => {
    setBusy(true)
    setErreur(null)
    try {
      const r = estDefaut
        ? await stockApi.retirerPanneauParDefaut(produit.id)
        : await stockApi.definirPanneauParDefaut(produit.id)
      setEstDefaut(r?.data?.produit_id === produit.id)
      relire()
      onChange?.(r?.data ?? null)
    } catch (err) {
      setErreur(err?.response?.data?.panneau_par_defaut?.[0] ?? frenchError(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div data-testid="panneau-par-defaut-action" className="mb-3 flex flex-col gap-1">
      <div className="flex flex-wrap items-center gap-2">
        {estDefaut && (inutilisable
          ? <Badge tone="warning" title={resume.motif}>{LIBELLE_DEFAUT_INUTILISABLE}</Badge>
          : <Badge tone="success">Panneau par défaut</Badge>)}
        {peutDesigner && (
          <Button type="button" size="sm" variant="outline" loading={busy} onClick={basculer}>
            {estDefaut ? 'Retirer' : 'Définir comme panneau par défaut'}
          </Button>
        )}
      </div>
      {inutilisable && resume.motif && <p className="text-xs text-muted-foreground">{resume.motif}</p>}
      {erreur && <p role="alert" className="text-xs text-destructive">{erreur}</p>}
    </div>
  )
}

export default ActionPanneauParDefaut
