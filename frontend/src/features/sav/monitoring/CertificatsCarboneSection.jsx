// ASAV102 (D-ASAV-4 option (b), ASAV93) — registre des certificats carbone.
// Émission pour un système et une période : les tCO₂ sont CALCULÉES par le
// serveur depuis la production mesurée (jamais saisies), la référence est
// posée par le serveur, un doublon exact est refusé (anti-double-comptage).
// Contrat : `apps/monitoring/contract_samples/certificats_carbone.json`.
import { useState } from 'react'
import { Leaf } from 'lucide-react'
import monitoringApi from '../../../api/monitoringApi'
import { getApiError } from '../../../lib/apiError'
import { formatDate, formatNumber } from '../../../lib/format'
import { Card, Button, Input, toast } from '../../../ui'
import SystemPicker from '../../../pages/monitoring/SystemPicker'
import ListeOuVide from './ListeOuVide'
import useDroitMetier from '../useDroitMetier'
import { libelleSysteme, useListeServeur } from './partage'

const FORM_VIDE = { systeme: '', periode_debut: '', periode_fin: '' }

export default function CertificatsCarboneSection({ systems, loadingSystems }) {
  const peutEcrire = useDroitMetier('sav_gerer') // ADRG47 — écriture du monitoring = palier sav
  const { rows, loading, load } = useListeServeur(monitoringApi.getCertificatsCarbone)
  const [form, setForm] = useState(FORM_VIDE)
  const [busy, setBusy] = useState(false)
  const [erreur, setErreur] = useState(null)
  // AMON93 — annulation d'un certificat (motif obligatoire).
  const [aAnnuler, setAAnnuler] = useState(null)
  const [motif, setMotif] = useState('')
  const [erreurAnnulation, setErreurAnnulation] = useState(null)

  const annuler = async (certificat) => {
    setBusy(true)
    setErreurAnnulation(null)
    try {
      await monitoringApi.annulerCertificatCarbone(certificat.id, motif.trim())
      toast.success(`Certificat ${certificat.reference} annulé`)
      setAAnnuler(null)
      setMotif('')
      load()
    } catch (e) {
      setErreurAnnulation(getApiError(e, 'Annulation impossible.').message)
    } finally { setBusy(false) }
  }

  // AMON94 — téléchargement du PDF du certificat.
  const telechargerPdf = async (certificat) => {
    try {
      const r = await monitoringApi.getCertificatCarbonePdf(certificat.id)
      const url = URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }))
      const a = document.createElement('a')
      a.href = url
      a.download = `${certificat.reference}.pdf`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch {
      toast.error('Téléchargement du PDF impossible.')
    }
  }

  const cible = (c) => (c.installation_id
    ? libelleSysteme(systems, c.installation_id, c.installation_reference)
    :`Client #${c.client_id} (consolidé)`)

  const emettre = async () => {
    const systeme = systems.find((s) => String(s.id) === form.systeme)
    if (!systeme) return
    setBusy(true)
    setErreur(null)
    try {
      const r = await monitoringApi.emettreCertificatCarbone({
        installation_id: systeme.installation,
        periode_debut: form.periode_debut,
        periode_fin: form.periode_fin,
      })
      toast.success(`Certificat ${r.data?.reference ?? ''} émis`)
      setForm(FORM_VIDE)
      load()
    } catch (e) {
      setErreur(getApiError(e, 'Émission du certificat impossible.').message)
    } finally { setBusy(false) }
  }

  return (
    <Card role="region" className="flex flex-col gap-3 p-4" aria-label="Certificats carbone">
      <h2 className="text-lg font-semibold">Certificats carbone</h2>
      <p className="text-xs text-muted-foreground">
        Les tonnes de CO₂ évitées sont calculées depuis la production mesurée de la période.
      </p>

      <div className="grid gap-3 sm:grid-cols-4">
        <div className="sm:col-span-2">
          <SystemPicker systems={systems} loading={loadingSystems} value={form.systeme}
                        onChange={(v) => setForm((f) => ({ ...f, systeme: v }))} />
        </div>
        <Input aria-label="Début de période" type="date" value={form.periode_debut}
               onChange={(e) => setForm((f) => ({ ...f, periode_debut: e.target.value }))} />
        <Input aria-label="Fin de période" type="date" value={form.periode_fin}
               onChange={(e) => setForm((f) => ({ ...f, periode_fin: e.target.value }))} />
        {peutEcrire && <Button type="button" size="sm" loading={busy}
                disabled={!form.systeme || !form.periode_debut || !form.periode_fin}
                onClick={emettre}>
          Émettre le certificat
        </Button>}
      </div>
      {erreur && <p role="alert" className="text-sm text-destructive">{erreur}</p>}

      <ListeOuVide loading={loading} rows={rows} icon={Leaf} title="Aucun certificat émis"
                   description="Le registre des certificats carbone est vide.">
        <ul className="flex flex-col gap-2">
          {rows.map((c) => (
            <li key={c.id} className="rounded-lg border border-border bg-card p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`font-medium ${c.statut === 'annule' ? 'line-through' : ''}`}>{c.reference}</span>
                <span className="text-sm text-muted-foreground">{cible(c)}</span>
                <span className="text-sm">{formatNumber(c.tco2_evitees, { decimals: 3 })} tCO₂ évitées</span>
                <Button size="sm" variant="ghost" onClick={() => telechargerPdf(c)}>PDF</Button>
                {peutEcrire && c.statut !== 'annule' && aAnnuler !== c.id && (
                  <Button size="sm" variant="outline" onClick={() => { setAAnnuler(c.id); setMotif(''); setErreurAnnulation(null) }}>
                    Annuler
                  </Button>
                )}
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Période {formatDate(c.periode_debut)} → {formatDate(c.periode_fin)} · émis le {formatDate(c.created_at)}
                {c.statut === 'annule' && ` · annulé le ${formatDate(c.annule_le)}${c.annule_par_nom ? ` par ${c.annule_par_nom}` : ''}${c.motif_annulation ? ` (${c.motif_annulation})` : ''}`}
              </p>
              {aAnnuler === c.id && (
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <Input aria-label="Motif de l’annulation" className="w-72" placeholder="Motif de l’annulation"
                         value={motif} onChange={(e) => setMotif(e.target.value)} />
                  <Button size="sm" variant="destructive" loading={busy} disabled={!motif.trim()} onClick={() => annuler(c)}>
                    Confirmer l’annulation
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setAAnnuler(null)}>Fermer</Button>
                  {erreurAnnulation && <p role="alert" className="w-full text-sm text-destructive">{erreurAnnulation}</p>}
                </div>
              )}
            </li>
          ))}
        </ul>
      </ListeOuVide>
    </Card>
  )
}
