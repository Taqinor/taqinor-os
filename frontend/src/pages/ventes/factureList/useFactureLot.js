// VNT102 — sélection multiple, actions en masse et encaissement groupé de la liste
// des factures, déplacés tels quels (move only) depuis FactureList.jsx. Le serveur
// exige un client UNIQUE pour l'encaissement groupé (WIR183/ZFAC6).
import { useMemo, useState } from 'react'
import { fetchFactures } from '../../../features/ventes/store/ventesSlice'
import ventesApi from '../../../api/ventesApi'
import { toast } from '../../../ui'
import { toNumber } from '../../../lib/format'
import { today } from './factureHelpers.js'

export default function useFactureLot({ factures, dispatch, setWir183Busy, erreurServeur }) {
  // WR2b — sélection multiple pour la barre d'actions en masse (FG43).
  const [selectedIds, setSelectedIds] = useState([])
  const toggleSelect = (id) => setSelectedIds(prev =>
    prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])
  const clearSelection = () => setSelectedIds([])
  const [bulkBusy, setBulkBusy] = useState(false)

  // ZFAC6 — un règlement client réparti sur PLUSIEURS factures. Répartition
  // FIFO par échéance par défaut ; `repartition` (montant par facture) la
  // force quand l'utilisateur la renseigne.
  const [encaissementOpen, setEncaissementOpen] = useState(false)
  const [encaissementForm, setEncaissementForm] = useState({
    montant: '', mode: 'virement', date: today, reference: '',
  })
  const [encaissementRepartition, setEncaissementRepartition] = useState({})

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
  const openEncaissementGroupe = () => {
    setEncaissementRepartition({})
    setEncaissementForm({
      montant: String(facturesEncaissables.reduce(
        (s, f) => s + toNumber(f.montant_du ?? 0), 0)),
      mode: 'virement', date: today, reference: '',
    })
    setEncaissementOpen(true)
  }
  const handleEncaissementGroupe = async () => {
    const repartition = Object.fromEntries(
      Object.entries(encaissementRepartition)
        .filter(([, v]) => toNumber(v) > 0))
    setWir183Busy(true)
    try {
      const { data } = await ventesApi.encaissementGroupeFactures({
        client: clientSelectionUnique,
        montant: encaissementForm.montant,
        mode: encaissementForm.mode,
        date: encaissementForm.date,
        reference: encaissementForm.reference,
        factures: facturesEncaissables.map(f => f.id),
        ...(Object.keys(repartition).length ? { repartition } : {}),
      })
      const n = Array.isArray(data) ? data.length : 0
      toast.success(`Encaissement réparti sur ${n} facture(s).`
        + (facturesEcartees.length
          ? ` Écartée(s) car non encaissable(s) : ${facturesEcartees.map(f => f.reference).join(', ')}.`
          : ''))
      setEncaissementOpen(false)
      clearSelection()
      dispatch(fetchFactures())
    } catch (err) {
      erreurServeur(err, 'Encaissement groupé impossible.')
    } finally { setWir183Busy(false) }
  }

  return {
    selectedIds, setSelectedIds, toggleSelect, clearSelection, bulkBusy,
    BULK_LABELS, handleBulkAction,
    facturesEncaissables, facturesEcartees, clientSelectionUnique,
    encaissementOpen, setEncaissementOpen, encaissementForm, setEncaissementForm,
    encaissementRepartition, setEncaissementRepartition,
    openEncaissementGroupe, handleEncaissementGroupe,
  }
}
