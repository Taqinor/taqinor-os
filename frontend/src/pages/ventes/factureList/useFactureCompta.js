// SPL212 — exports comptables de la liste des factures (export comptable,
// journal des ventes, audit de numérotation, sondage du job d'export) : déplacés
// tels quels (move only) depuis FactureList.jsx. Les confirmations
// (`useConfirmDialog`) restent dans FactureList.jsx.
import { useState } from 'react'
import ventesApi from '../../../api/ventesApi'
import api from '../../../api/axios'
import { downloadXlsx } from '../../../api/importApi'
import { toast } from '../../../ui'
import { openPdfBlob } from '../../../utils/pdfBlob'

// FE-SCA41 — au-delà du seuil (2 000 lignes par défaut, `VENTES_EXPORT_
// ASYNC_ROW_THRESHOLD` côté serveur), journal-ventes / export-comptable
// répondent 202 (job Celery accepté) au lieu du .xlsx synchrone habituel.
// `asyncExportPayload` détecte ce cas — le JSON du 202 arrive encapsulé dans
// un Blob puisque les deux appels utilisent `responseType: 'blob'` pour le
// chemin synchrone — et `pollExportJobAndDownload` interroge le statut
// jusqu'à `ready` (déclenche alors le téléchargement via l'URL MinIO
// pré-signée renvoyée) ou `error`. Sous le seuil, `res.status` reste 200 et
// `asyncExportPayload` renvoie `null` : rien ne change pour l'appelant.
const EXPORT_POLL_INTERVAL_MS = 2000
const EXPORT_POLL_TIMEOUT_MS = 5 * 60 * 1000

async function asyncExportPayload(res) {
  if (res.status !== 202) return null
  try {
    return JSON.parse(await res.data.text())
  } catch {
    return null
  }
}

async function pollExportJobAndDownload(jobId, fallbackFilename) {
  const started = Date.now()
  for (;;) {
    if (Date.now() - started > EXPORT_POLL_TIMEOUT_MS) {
      throw new Error('export-timeout')
    }
    await new Promise(resolve => setTimeout(resolve, EXPORT_POLL_INTERVAL_MS))
    const { data } = await ventesApi.exportStatus(jobId)
    if (data.status === 'ready') {
      const a = document.createElement('a')
      a.href = data.download_url
      a.download = data.filename || fallbackFilename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      return
    }
    if (data.status === 'error') {
      throw new Error('export-failed')
    }
    // 'pending' → on continue de sonder.
  }
}

export default function useFactureCompta() {
  const [auditBusy, setAuditBusy] = useState(false)
  // VX142(a) — Journal comptable : petit Dialog mois/trimestre à la place du
  // window.prompt() texte libre (regroupé dans le menu « Exporter »).
  const [journalOpen, setJournalOpen] = useState(false)
  const [journalMode, setJournalMode] = useState('mois') // 'mois' | 'trimestre'
  const [journalMois, setJournalMois] = useState(() => new Date().toISOString().slice(0, 7))
  const [journalAnnee, setJournalAnnee] = useState(() => String(new Date().getFullYear()))
  const [journalTrimestre, setJournalTrimestre] = useState('1')
  const [journalBusy, setJournalBusy] = useState(false)
  // VX142(a) — Export comptable : même traitement, deux champs date au lieu
  // de deux window.prompt() successifs.
  const [exportComptableOpen, setExportComptableOpen] = useState(false)
  const [exportStart, setExportStart] = useState(() => new Date().toISOString().slice(0, 8) + '01')
  const [exportEnd, setExportEnd] = useState(() => new Date().toISOString().slice(0, 10))
  const [exportComptableBusy, setExportComptableBusy] = useState(false)
  // VX172 — pending visible sur « Exporter Excel » (VX49 pose déjà le toast
  // d'erreur ; ceci ajoute juste l'état chargement manquant).
  const [xlsxBusy, setXlsxBusy] = useState(false)


  // VX142(a) — Export comptable DGI (groundwork) : factures validées d'une
  // plage, en .xlsx ET .csv (ventilation TVA par ligne + ICE + totaux).
  // Borné société. Plage saisie via le petit Dialog `exportComptableOpen`
  // (deux champs date), plus de window.prompt().
  const handleExportComptable = async () => {
    const start = exportStart
    const end = exportEnd
    if (!start || !end) return
    setExportComptableBusy(true)
    const dl = async (fmt, ext) => {
      const res = await api.get('/ventes/export-comptable/', {
        params: { start, end, fmt }, responseType: 'blob',
      })
      const filename = `export-comptable-${start}_${end}.${ext}`
      // FE-SCA41 — export volumineux : le xlsx part en tâche de fond (202) ;
      // le CSV reste toujours synchrone (aucun 202 possible pour lui).
      const job = await asyncExportPayload(res)
      if (job) {
        toast.info('Export volumineux — génération en arrière-plan.')
        await pollExportJobAndDownload(job.job_id, filename)
        return
      }
      openPdfBlob(res.data, filename)
    }
    try {
      await dl('xlsx', 'xlsx')
      await dl('csv', 'csv')
      setExportComptableOpen(false)
    } catch {
      toast.error('Export comptable impossible.')
    } finally {
      setExportComptableBusy(false)
    }
  }

  // VX142(a) — Journal des ventes + résumé TVA : plus de window.prompt(), la
  // période (mois ou trimestre) vient du Dialog `journalOpen`.
  const handleJournalComptable = async () => {
    const v = journalMode === 'trimestre'
      ? `${journalAnnee}-${journalTrimestre}`
      : journalMois
    const isQuarter = journalMode === 'trimestre'
    const params = isQuarter ? { quarter: v } : { month: v }
    setJournalBusy(true)
    try {
      const r = await ventesApi.journalVentes(params)
      const filename = `journal-ventes-${v}.xlsx`
      // FE-SCA41 — journal volumineux : bascule 202 → sonde le statut puis
      // télécharge via l'URL pré-signée dès que prêt.
      const job = await asyncExportPayload(r)
      if (job) {
        toast.info('Export volumineux — génération en arrière-plan.')
        await pollExportJobAndDownload(job.job_id, filename)
      } else {
        downloadXlsx(r.data, filename)
      }
      setJournalOpen(false)
    } catch {
      toast.error('Journal comptable indisponible.')
    } finally {
      setJournalBusy(false)
    }
  }

  // N31 — audit admin de la numérotation : résumé des trous/doublons.
  const handleAuditNumerotation = async () => {
    setAuditBusy(true)
    try {
      const { data } = await ventesApi.auditNumerotation()
      if (data.conforme) {
        toast.success('Numérotation conforme : aucun trou ni doublon détecté.')
      } else {
        const lignes = []
        const labels = { devis: 'Devis', facture: 'Factures',
          avoir: 'Avoirs', bon_commande: 'Bons de commande' }
        for (const cle of Object.keys(labels)) {
          for (const g of (data[cle] || [])) {
            const parts = []
            if (g.manquants.length) parts.push(`manquants : ${g.manquants.join(', ')}`)
            if (g.doublons.length) parts.push(`doublons : ${g.doublons.join(', ')}`)
            lignes.push(`${labels[cle]} ${g.radical} → ${parts.join(' ; ')}`)
          }
        }
        toast.error(`Anomalies de numérotation détectées :\n\n${lignes.join('\n')}\n\n`
          + `(${data.total_manquants} numéro(s) manquant(s), `
          + `${data.total_doublons} doublon(s)). Aucune renumérotation automatique.`)
      }
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? "Audit de numérotation impossible.")
    } finally {
      setAuditBusy(false)
    }
  }


  return {
    auditBusy,
    journalOpen, setJournalOpen,
    journalMode, setJournalMode,
    journalMois, setJournalMois,
    journalAnnee, setJournalAnnee,
    journalTrimestre, setJournalTrimestre,
    journalBusy,
    exportComptableOpen, setExportComptableOpen,
    exportStart, setExportStart,
    exportEnd, setExportEnd,
    exportComptableBusy,
    xlsxBusy, setXlsxBusy,
    handleExportComptable,
    handleJournalComptable,
    handleAuditNumerotation,
  }
}
