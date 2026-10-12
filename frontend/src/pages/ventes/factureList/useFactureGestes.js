// VNT102 — gestes sur UNE facture de la liste (note de débit, paiement en ligne,
// actions WIR183, avoir, encaissement, échéance inline, marquage sec « payée »),
// déplacés tels quels (move only) depuis FactureList.jsx. Même patron que
// useFactureCompta (SPL212) : l'état et les gestes sortent, le DOM reste.
import { useState } from 'react'
import { useSelector } from 'react-redux'
import { fetchFactures } from '../../../features/ventes/store/ventesSlice'
import ventesApi from '../../../api/ventesApi'
import { frenchError } from '../../../lib/frenchError'
import fetchAllPages from '../../../utils/fetchAllPages'
import { toast } from '../../../ui'
import { toNumber } from '../../../lib/format'
import { errorMessageFrom } from '../../../lib/toast'

export default function useFactureGestes({ dispatch, confirm }) {
  // ── WIR103/ZFAC4 — Note de débit (pendant de l'avoir) : modale de
  // création + téléchargement PDF. Le backend était complet et testé mais
  // n'avait aucun écran ; c'est ici qu'il en gagne un.
  const [noteDebitTarget, setNoteDebitTarget] = useState(null)
  const openNoteDebit = (f) => setNoteDebitTarget(f)

  // ── PACT121 — Demande de paiement carte au client (core.PaymentTransaction).
  // Sans compte marchand configuré, la création reste propre et sans effet :
  // la modale affiche « prestataire non configuré », jamais une erreur brute.
  const [paiementEnLigneTarget, setPaiementEnLigneTarget] = useState(null)
  const openPaiementEnLigne = (f) => setPaiementEnLigneTarget(f)

  /* ══ WIR183 — Six actions Facture COMPLÈTES côté serveur, sans aucune UI ══
     ZFAC1 (remettre-brouillon), XFAC13 (abandonner-solde), XPOS7
     (retour-client), XFAC6 (facturer-pénalités), XFAC11 (consolider) et ZFAC6
     (encaissement-groupe) vivaient toutes dans `apps/ventes/views/facture.py`
     sans qu'aucun écran ne puisse les déclencher.

     Toutes sont gardées `IsResponsableOrAdmin` côté serveur : les points
     d'entrée ne s'affichent donc qu'au palier responsable/admin, et TOUT
     message d'erreur serveur est affiché TEL QUEL (le serveur explique
     précisément pourquoi il refuse : paiement existant, période verrouillée,
     quantité retournée trop grande, aucun niveau de relance atteint… — un
     texte maison masquerait la cause). */
  const canManage = ['admin', 'responsable'].includes(
    useSelector(s => s.auth.role))
  const [wir183Busy, setWir183Busy] = useState(false)
  const erreurServeur = (err, repli) =>
    toast.error(err?.response?.data?.detail ?? repli)

  // ZFAC1 — retour au brouillon (référence CONSERVÉE).
  const handleRemettreBrouillon = async (f) => {
    const ok = await confirm({
      title: `Remettre la facture ${f.reference} en brouillon ?`,
      description: 'La référence est conservée. Le serveur refuse si un '
        + 'paiement ou un avoir existe, ou si la période comptable est '
        + 'verrouillée.',
    })
    if (!ok) return
    setWir183Busy(true)
    try {
      await ventesApi.remettreBrouillonFacture(f.id)
      toast.success(`Facture ${f.reference} remise en brouillon.`)
      dispatch(fetchFactures())
    } catch (err) {
      erreurServeur(err, 'Remise en brouillon impossible.')
    } finally { setWir183Busy(false) }
  }

  // XFAC6 — la pénalité de retard devient une facture de frais SÉPARÉE.
  const handleFacturerPenalites = async (f) => {
    const ok = await confirm({
      title: `Facturer les pénalités de retard de ${f.reference} ?`,
      description: 'Une facture de frais SÉPARÉE est créée au niveau de '
        + "relance courant. La facture d'origine n'est pas modifiée.",
    })
    if (!ok) return
    setWir183Busy(true)
    try {
      const { data } = await ventesApi.facturerPenalitesFacture(f.id)
      toast.success(`Facture de pénalités ${data?.reference ?? ''} créée.`)
      dispatch(fetchFactures())
    } catch (err) {
      erreurServeur(err, 'Facturation des pénalités impossible.')
    } finally { setWir183Busy(false) }
  }

  // XFAC13 — abandon du résiduel : le motif est OBLIGATOIRE côté serveur.
  const MOTIFS_ABANDON = [
    ['irrecouvrable', 'Irrécouvrable'],
    ['geste_commercial', 'Geste commercial'],
    ['ecart_reglement', 'Écart de règlement'],
    ['liquidation', 'Liquidation'],
  ]
  const [abandonTarget, setAbandonTarget] = useState(null)
  const [abandonMotif, setAbandonMotif] = useState('irrecouvrable')
  const openAbandonSolde = (f) => { setAbandonMotif('irrecouvrable'); setAbandonTarget(f) }
  const handleAbandonnerSolde = async () => {
    if (!abandonTarget) return
    setWir183Busy(true)
    try {
      await ventesApi.abandonnerSoldeFacture(abandonTarget.id, abandonMotif)
      toast.success(`Solde de ${abandonTarget.reference} abandonné.`)
      setAbandonTarget(null)
      dispatch(fetchFactures())
    } catch (err) {
      erreurServeur(err, 'Abandon du solde impossible.')
    } finally { setWir183Busy(false) }
  }

  // XPOS7 — retour client : l'avoir est créé contre la facture d'origine, avec
  // option de re-stockage. Le serveur n'accepte QUE des lignes portant un
  // produit (le re-stockage s'appuie dessus) : les lignes libres sont donc
  // exclues du tableau, jamais envoyées pour être refusées.
  const [retourTarget, setRetourTarget] = useState(null)
  const [retourMotif, setRetourMotif] = useState('')
  const [retourRestocker, setRetourRestocker] = useState(false)
  const [retourQtes, setRetourQtes] = useState({})
  const openRetourClient = async (f) => {
    setRetourMotif('')
    setRetourRestocker(false)
    setRetourQtes({})
    try {
      const res = await ventesApi.getFacture(f.id)
      setRetourTarget(res.data)
    } catch {
      setRetourTarget(f)
    }
  }
  const lignesRetournables = (retourTarget?.lignes ?? []).filter(l => l.produit)
  const handleRetourClient = async () => {
    if (!retourTarget) return
    const lignes = lignesRetournables
      .map(l => ({ produit: l.produit, quantite: retourQtes[l.id] }))
      .filter(l => toNumber(l.quantite) > 0)
    if (lignes.length === 0) {
      toast.error('Indiquez au moins une quantité retournée.')
      return
    }
    setWir183Busy(true)
    try {
      await ventesApi.retourClientFacture(retourTarget.id, {
        motif: retourMotif, restocker: retourRestocker, lignes,
      })
      toast.success(`Retour enregistré pour ${retourTarget.reference}.`)
      setRetourTarget(null)
      dispatch(fetchFactures())
    } catch (err) {
      erreurServeur(err, 'Retour client impossible.')
    } finally { setWir183Busy(false) }
  }

  // XFAC11 — consolidation : elle consomme des ids de DEVIS acceptés, PAS la
  // sélection de factures. La monter sur la barre de masse produirait un 400
  // garanti — elle vit donc dans les actions de l'écran, avec son propre
  // sélecteur de devis.
  const [consoliderOpen, setConsoliderOpen] = useState(false)
  const [consoliderDevis, setConsoliderDevis] = useState([])
  const [consoliderSel, setConsoliderSel] = useState([])
  const openConsolider = async () => {
    setConsoliderSel([])
    setConsoliderOpen(true)
    try {
      // ADEV70 — TOUTES les pages (jamais les 50 premiers devis acceptés).
      const res = await fetchAllPages((page) => ventesApi.getDevis({ statut: 'accepte', page, page_size: 200 }).then((r) => r.data))
      setConsoliderDevis(Array.isArray(res) ? res : (res?.results ?? []))
    } catch {
      setConsoliderDevis([])
    }
  }
  const handleConsolider = async () => {
    if (consoliderSel.length < 2) {
      toast.error('Sélectionnez au moins deux devis du même client.')
      return
    }
    setWir183Busy(true)
    try {
      const { data } = await ventesApi.consoliderFactures(consoliderSel)
      toast.success(`Facture consolidée ${data?.reference ?? ''} créée.`)
      setConsoliderOpen(false)
      dispatch(fetchFactures())
    } catch (err) {
      erreurServeur(err, 'Consolidation impossible.')
    } finally { setWir183Busy(false) }
  }

  // ── Avoir (note de crédit) : modale total OU partiel ──
  const [avoirTarget, setAvoirTarget] = useState(null) // facture ciblée
  const [avoirMotif, setAvoirMotif]   = useState('')
  const [avoirSaving, setAvoirSaving] = useState(false)
  // Quantités à créditer par ligne (clé = id de ligne) ; vide = avoir total.
  const [avoirQtes, setAvoirQtes]     = useState({})
  // ATOT36 (décision fondateur 10/10) — une CORRECTION est remise au solde de
  // l'échéancier ; un geste commercial réduit le dû de cette facture.
  const [avoirType, setAvoirType]     = useState('geste_commercial')

  const openAvoirModal = async (f) => {
    setAvoirMotif('')
    setAvoirQtes({})
    setAvoirType('geste_commercial')
    // Charge le détail des lignes pour permettre un avoir partiel.
    try {
      const res = await ventesApi.getFacture(f.id)
      setAvoirTarget(res.data)
    } catch {
      setAvoirTarget(f)
    }
  }

  const handleCreerAvoir = async (mode) => {
    if (!avoirTarget) return
    setAvoirSaving(true)
    try {
      const payload = { motif: avoirMotif, type: avoirType }
      if (mode === 'partiel') {
        const lignes = (avoirTarget.lignes || [])
          .map(l => ({ ...l, _qte: parseFloat(avoirQtes[l.id] ?? 0) }))
          .filter(l => l._qte > 0)
          .map(l => ({
            produit: l.produit ?? null,
            designation: l.designation,
            quantite: l._qte,
            prix_unitaire: l.prix_unitaire,
            remise: l.remise ?? 0,
            taux_tva: l.taux_tva,
          }))
        if (lignes.length === 0) {
          toast.error('Saisissez au moins une quantité à créditer.')
          setAvoirSaving(false)
          return
        }
        payload.lignes = lignes
      }
      await ventesApi.creerAvoir(avoirTarget.id, payload)
      setAvoirTarget(null)
      dispatch(fetchFactures())
      toast.success('Avoir créé. Retrouvez-le dans Ventes → Avoirs.')
    } catch (err) {
      toast.error(frenchError(err, "Création de l'avoir impossible."))
    } finally {
      setAvoirSaving(false)
    }
  }

  const [actionId, setActionId]       = useState(null)
  // ── Enregistrement de paiement (VX230 — modale extraite en PaiementDialog) ──
  // FactureList ne garde que la facture CIBLÉE ; tout l'état de saisie, l'arrondi
  // ZFAC11 et le chatter vivent désormais dans PaiementDialog (partagé avec
  // RelancesPage). `onSaved` rafraîchit la liste après chaque encaissement.
  const [payTarget, setPayTarget] = useState(null) // facture ciblée
  const openPayModal = (f) => setPayTarget(f)

  // ── Édition inline de la date d'échéance (facture émise) ──
  const [echeanceEditId, setEcheanceEditId] = useState(null)
  const [echeanceValue, setEcheanceValue]   = useState('')
  const [echeanceSaving, setEcheanceSaving] = useState(false)

  const startEditEcheance = (f) => {
    setEcheanceEditId(f.id)
    setEcheanceValue(f.date_echeance ?? '')
  }
  const saveEcheance = async (f) => {
    setEcheanceSaving(true)
    try {
      await ventesApi.patchFacture(f.id, { date_echeance: echeanceValue || null })
      setEcheanceEditId(null)
      dispatch(fetchFactures())
    } catch (err) {
      toast.error(frenchError(err, 'Mise à jour de l’échéance impossible.'))
    } finally {
      setEcheanceSaving(false)
    }
  }

  // APX17 — confirmation maison (AlertDialog Radix), jamais la popup du
  // système.
  const doAction = async (thunk, id, confirmMsg) => {
    if (confirmMsg && !(await confirm({ title: confirmMsg }))) return
    setActionId(id)
    try {
      await dispatch(thunk(id)).unwrap()
    } catch (err) {
      // VX63 — plus de JSON brut à l'écran : message FR lisible extrait du
      // payload d'erreur (le sweep alert→toast reste la propriété de VX19).
      toast.error(errorMessageFrom({ response: { data: err } }, 'Action impossible.'))
    } finally {
      setActionId(null)
    }
  }

  // EZ13 — marquage sec « payée » : facture ciblée par la confirmation qui
  // EXPLIQUE la perte (mode, date et référence du règlement ne seront pas
  // enregistrés). Jamais une popup « êtes-vous sûr ? ».
  const [payeeSecheTarget, setPayeeSecheTarget] = useState(null)
  // AUD124 — le marquage sec exige un MOTIF (le serveur refuse sans) : il est
  // tracé dans le chatter de la facture avec son auteur.
  const [payeeSecheMotif, setPayeeSecheMotif] = useState('')
  const openMarquerPayee = (f) => setPayeeSecheTarget(f)

  return {
    noteDebitTarget, setNoteDebitTarget, openNoteDebit,
    paiementEnLigneTarget, setPaiementEnLigneTarget, openPaiementEnLigne,
    canManage, wir183Busy, setWir183Busy, erreurServeur,
    handleRemettreBrouillon, handleFacturerPenalites,
    MOTIFS_ABANDON, abandonTarget, setAbandonTarget, abandonMotif, setAbandonMotif,
    openAbandonSolde, handleAbandonnerSolde,
    retourTarget, setRetourTarget, retourMotif, setRetourMotif, retourRestocker,
    setRetourRestocker, retourQtes, setRetourQtes, openRetourClient,
    lignesRetournables, handleRetourClient,
    consoliderOpen, setConsoliderOpen, consoliderDevis, consoliderSel, setConsoliderSel,
    openConsolider, handleConsolider,
    avoirTarget, setAvoirTarget, avoirMotif, setAvoirMotif, avoirSaving, avoirQtes,
    setAvoirQtes, avoirType, setAvoirType, openAvoirModal, handleCreerAvoir,
    actionId, payTarget, setPayTarget, openPayModal,
    echeanceEditId, setEcheanceEditId, echeanceValue, setEcheanceValue, echeanceSaving,
    startEditEcheance, saveEcheance, doAction,
    payeeSecheTarget, setPayeeSecheTarget, payeeSecheMotif, setPayeeSecheMotif, openMarquerPayee,
  }
}
