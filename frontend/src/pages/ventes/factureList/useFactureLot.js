// VNT102 (patron SPL212) — sélection multiple, actions en masse et sélection
// encaissable de la liste des factures : déplacés tels quels (move only) depuis
// FactureList.jsx. Aucun flux modifié, aucune valeur transformée.
import { useMemo, useState } from 'react'
import ventesApi from '../../../api/ventesApi'
import { relireApresGeste } from './useFactureGestes.js'
import { toast } from '../../../ui'

export default function useFactureLot({ factures, dispatch, relire = () => relireApresGeste(dispatch), confirm = () => Promise.resolve(true) }) {
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
  // AERR7 — actions à effet client (numéro légal, relance, e-mail) : confirmation
  // maison qui dit le nombre et les références ; « Générer le PDF » part sans question.
  const BULK_QUESTIONS = { emettre: 'Émettre', relancer: 'Relancer', 'envoyer-email': 'Envoyer' }
  const handleBulkAction = async (action) => {
    if (!selectedIds.length) return
    if (BULK_QUESTIONS[action]) {
      const n = selectedIds.length
      const refs = factures.filter(f => selectedIds.includes(f.id)).map(f => f.reference).join(', ')
      const ok = await confirm({
        title: `${BULK_QUESTIONS[action]} ${n} facture${n > 1 ? 's' : ''}${action === 'envoyer-email' ? ' par e-mail' : ''} ?`,
        description: refs, confirmLabel: 'Confirmer', cancelLabel: 'Annuler',
      })
      if (!ok) return
    }
    setBulkBusy(true)
    try {
      const { data } = await ventesApi.bulkFactures(action, selectedIds)
      // AERR8 — chaque refusée est nommée avec la raison servie et reste cochée.
      const entries = Object.entries(data || {})
      const refusees = entries.filter(([, r]) => !r.ok)
      const ok = entries.length - refusees.length
      if (refusees.length === 0) {
        toast.success(`${BULK_LABELS[action] ?? action} : ${ok} facture(s) traitée(s).`)
      } else {
        const refDe = (id) => factures.find(f => String(f.id) === id)?.reference ?? `#${id}`
        toast.error(`${BULK_LABELS[action] ?? action} : ${ok} réussie(s), ${refusees.length} refusée(s) — `
          + refusees.map(([id, r]) => `${refDe(id)} : ${r.detail || 'refusée'}`).join(' ; '))
      }
      relire()
      setSelectedIds(selectedIds.filter(id => refusees.some(([k]) => k === String(id))))
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
