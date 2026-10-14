// VNT102 (patron SPL212) — sélection multiple, actions en masse et sélection
// encaissable de la liste des factures : déplacés tels quels (move only) depuis
// FactureList.jsx. Aucun flux modifié, aucune valeur transformée.
import { useMemo, useState } from 'react'
import ventesApi from '../../../api/ventesApi'
import { fetchFactures } from '../../../features/ventes/store/ventesSlice'
import { toast } from '../../../ui'

export default function useFactureLot({ factures, dispatch }) {
  // WR2b — sélection multiple pour la barre d'actions en masse (FG43).
  const [selectedIds, setSelectedIds] = useState([])
  const toggleSelect = (id) => setSelectedIds(prev =>
    prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])
  const clearSelection = () => setSelectedIds([])
  const [bulkBusy, setBulkBusy] = useState(false)

  // FG43/WR2b — actions en masse sur la sélection courante.
  const BULK_LABELS = {
    emettre: 'Émettre', relancer: 'Relancer',
    'envoyer-email': 'Envoyer par email', 'generer-pdf': 'Générer le PDF',
  }
  const handleBulkAction = async (action) => {
    if (!selectedIds.length) return
    setBulkBusy(true)
    try {
      const { data } = await ventesApi.bulkFactures(action, selectedIds)
      const entries = Object.values(data || {})
      const ok = entries.filter(r => r.ok).length
      const ko = entries.length - ok
      if (ko === 0) {
        toast.success(`${BULK_LABELS[action] ?? action} : ${ok} facture(s) traitée(s).`)
      } else {
        toast.error(`${BULK_LABELS[action] ?? action} : ${ok} réussie(s), ${ko} échec(s).`)
      }
      dispatch(fetchFactures())
      clearSelection()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Action en masse impossible.')
    } finally {
      setBulkBusy(false)
    }
  }

  // ── WIR183/ZFAC6 — encaissement groupé sur la SÉLECTION courante ───────────
  // Le serveur exige un client UNIQUE : la barre de masse ne propose donc
  // l'action que si toutes les factures sélectionnées appartiennent au même
  // client (sinon le bouton explique pourquoi il est désactivé, plutôt que de
  // laisser partir une requête vouée au 400).
  const facturesSelectionnees = useMemo(
    () => factures.filter(f => selectedIds.includes(f.id)),
    [factures, selectedIds])
  // AFAC10 — seules les factures que le SERVEUR déclare encaissables partent
  // à l'encaissement groupé ; les autres sont écartées ET nommées.
  const facturesEncaissables = useMemo(
    () => facturesSelectionnees.filter(f => f.encaissable !== false),
    [facturesSelectionnees])
  const facturesEcartees = useMemo(
    () => facturesSelectionnees.filter(f => f.encaissable === false),
    [facturesSelectionnees])
  const clientSelectionUnique = useMemo(() => {
    const ids = [...new Set(facturesEncaissables.map(f => f.client))]
    return ids.length === 1 ? ids[0] : null
  }, [facturesEncaissables])

  return {
    selectedIds, setSelectedIds, toggleSelect, clearSelection, bulkBusy,
    BULK_LABELS, handleBulkAction,
    facturesSelectionnees, facturesEncaissables, facturesEcartees, clientSelectionUnique,
  }
}
