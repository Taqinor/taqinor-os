import { useState } from 'react'
import { FileCode, Download } from 'lucide-react'
import einvoiceApi from '../api/einvoiceApi'
import { Button } from '../ui'
import { downloadBlob } from '../utils/downloadBlob'

/* WIR106 — Action « Générer e-facture (dry-run) » sur une facture existante.
   Réutilise apps/einvoice (générateur UBL DGI, NTMAR). La génération est gated
   serveur (EINVOICE_ENABLED) : un 204 affiche « e-facturation désactivée ». La
   transmission LIVE reste bloquée tant qu'aucune crédential DGI n'est
   configurée — non exposée ici (dry-run uniquement). */
export default function EinvoiceActions({ factureId }) {
  const [busy, setBusy] = useState(false)
  const [state, setState] = useState(null) // { disabled?, fe?, error? }

  const generer = async () => {
    setBusy(true)
    setState(null)
    try {
      const res = await einvoiceApi.generer(factureId, 'dry_run')
      if (res.status === 204 || !res.data) {
        setState({ disabled: true })
      } else {
        setState({ fe: res.data })
      }
    } catch (err) {
      setState({ error: err?.response?.data?.detail || 'La génération a échoué.' })
    } finally {
      setBusy(false)
    }
  }

  const telecharger = async () => {
    if (!state?.fe?.id) return
    try {
      const res = await einvoiceApi.telecharger(state.fe.id)
      downloadBlob(res.data, `e-facture-${factureId}.xml`)
    } catch {
      setState((s) => ({ ...s, error: 'Le téléchargement du XML a échoué.' }))
    }
  }

  return (
    <div className="border-t border-border pt-4">
      <p className="mb-2 text-sm font-semibold text-foreground">
        Facturation électronique DGI
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" size="sm" variant="outline" disabled={busy} onClick={generer}>
          <FileCode size={16} /> Générer e-facture (dry-run)
        </Button>
        {state?.fe && (
          <Button type="button" size="sm" variant="outline" onClick={telecharger}>
            <Download size={16} /> Télécharger XML
          </Button>
        )}
      </div>
      {state?.disabled && (
        <p className="mt-2 text-sm text-muted-foreground">
          E-facturation désactivée pour cette société (EINVOICE_ENABLED).
        </p>
      )}
      {state?.fe && (
        <p className="mt-2 text-sm text-muted-foreground">
          E-facture générée (dry-run) — version {state.fe.version}. La transmission
          à la DGI reste bloquée tant qu'aucune crédential n'est configurée.
        </p>
      )}
      {state?.error && (
        <p className="mt-2 form-error" role="alert">{state.error}</p>
      )}
    </div>
  )
}
