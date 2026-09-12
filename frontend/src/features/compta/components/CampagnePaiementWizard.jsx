/* NTTRE25 — Assistant guidé « Créer une campagne de paiement ».
   ----------------------------------------------------------------------------
   À partir d'un filtre (fournisseur, échéance max, montant max), l'assistant
   pré-sélectionne les dettes éligibles — la MÊME sélection que le serveur
   applique ensuite (`payment-runs/apercu/` et `payment-runs/{id}/proposer/`
   partagent `services.dettes_eligibles_campagne`) — puis affiche l'impact
   prévisionnel sur le solde du compte payeur choisi.

   Si ce compte passerait SOUS son seuil d'alerte bas (NTTRE8), l'avertissement
   est BLOQUANT : le bouton de création reste désactivé tant que l'utilisateur
   n'a pas explicitement confirmé vouloir passer outre.

   Aucun nouveau modèle : la campagne est créée en `brouillon` par les routes
   existantes. Les montants affichés viennent TOUS du serveur. */
import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Search } from 'lucide-react'
import {
  Button, Input, Label, Checkbox, EmptyState, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
import ComptaTable from '../ComptaTable'
import comptaApi from '../../../api/comptaApi'

const MODES = [
  { value: 'virement', label: 'Virement bancaire' },
  { value: 'cheque', label: 'Chèque' },
  { value: 'especes', label: 'Espèces' },
]

function messageErreur(err, repli) {
  const d = err?.response?.data
  if (typeof d === 'string') return d
  if (d?.detail) return d.detail
  if (d && typeof d === 'object') {
    const [champ, valeur] = Object.entries(d)[0] || []
    if (champ) return `${champ} : ${Array.isArray(valeur) ? valeur[0] : valeur}`
  }
  return repli
}

export default function CampagnePaiementWizard({ onClose, onCreated }) {
  const [comptes, setComptes] = useState([])
  const [filtres, setFiltres] = useState({
    compte: '', date_paiement: '', mode_paiement: 'virement',
    date_limite: '', montant_max: '', fournisseur: '',
  })
  const [apercu, setApercu] = useState(null)
  const [outrepasser, setOutrepasser] = useState(false)
  const [busy, setBusy] = useState(false)
  const [erreurChamp, setErreurChamp] = useState('')

  useEffect(() => {
    let vivant = true
    comptaApi.tresorerie.list({ page_size: 200 })
      .then((res) => {
        if (!vivant) return
        const liste = Array.isArray(res.data) ? res.data : (res.data?.results || [])
        setComptes(liste)
      })
      .catch(() => { if (vivant) setComptes([]) })
    return () => { vivant = false }
  }, [])

  const set = (champ, valeur) => {
    setFiltres((f) => ({ ...f, [champ]: valeur }))
    // Tout changement de filtre périme l'aperçu ET la levée d'avertissement.
    setApercu(null)
    setOutrepasser(false)
  }

  const fournisseurs = useMemo(() => {
    const vus = new Map()
    for (const d of (apercu?.dettes || [])) {
      if (!vus.has(d.fournisseur_id)) vus.set(d.fournisseur_id, d.fournisseur_nom)
    }
    return [...vus.entries()].map(([id, nom]) => ({ id, nom }))
  }, [apercu])

  const charger = async () => {
    setBusy(true)
    try {
      const res = await comptaApi.paymentRuns.apercu({
        compte: filtres.compte || undefined,
        date_limite: filtres.date_limite || undefined,
        montant_max: filtres.montant_max || undefined,
        fournisseur: filtres.fournisseur || undefined,
      })
      setApercu(res.data)
      setOutrepasser(false)
    } catch (err) {
      toast.error(messageErreur(err, 'Aperçu de la campagne indisponible.'))
    } finally {
      setBusy(false)
    }
  }

  const alerte = apercu?.alerte_seuil || null
  const bloque = Boolean(alerte) && !outrepasser
  const rien = apercu && apercu.nb_dettes === 0

  const creer = async () => {
    if (!filtres.date_paiement) {
      setErreurChamp('date_paiement')
      toast.error('Renseignez la date de paiement de la campagne.')
      return
    }
    setErreurChamp('')
    setBusy(true)
    try {
      const run = await comptaApi.paymentRuns.create({
        date_paiement: filtres.date_paiement,
        mode_paiement: filtres.mode_paiement,
        compte_tresorerie: filtres.compte || null,
      })
      await comptaApi.paymentRuns.proposer(run.data.id, {
        date_limite: filtres.date_limite || undefined,
        fournisseur: filtres.fournisseur || undefined,
        montant_max: filtres.montant_max || undefined,
      })
      toast.success('Campagne créée en brouillon.')
      onCreated?.()
      onClose()
    } catch (err) {
      toast.error(messageErreur(err, 'Création de la campagne impossible.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Assistant — nouvelle campagne de paiement</DialogTitle>
        </DialogHeader>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor="cp-compte">Compte payeur</Label>
            <select
              id="cp-compte" value={filtres.compte}
              onChange={(e) => set('compte', e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">Choisir un compte…</option>
              {comptes.map((c) => (
                <option key={c.id} value={c.id}>{c.libelle}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="cp-date">Date de paiement</Label>
            <Input id="cp-date" type="date" value={filtres.date_paiement}
                   onChange={(e) => set('date_paiement', e.target.value)} />
            {erreurChamp === 'date_paiement' && (
              <span className="text-xs text-destructive">
                Date de paiement : champ obligatoire.
              </span>
            )}
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="cp-mode">Mode de paiement</Label>
            <select
              id="cp-mode" value={filtres.mode_paiement}
              onChange={(e) => set('mode_paiement', e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              {MODES.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="cp-echeance">Échéance maximum</Label>
            <Input id="cp-echeance" type="date" value={filtres.date_limite}
                   onChange={(e) => set('date_limite', e.target.value)} />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="cp-montant">Montant maximum par échéance</Label>
            <Input id="cp-montant" type="number" step="any"
                   value={filtres.montant_max}
                   onChange={(e) => set('montant_max', e.target.value)} />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="cp-fournisseur">Fournisseur</Label>
            <select
              id="cp-fournisseur" value={filtres.fournisseur}
              onChange={(e) => set('fournisseur', e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">Tous les fournisseurs</option>
              {fournisseurs.map((f) => (
                <option key={f.id} value={f.id}>{f.nom}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="mt-3">
          <Button variant="outline" size="sm" onClick={charger} disabled={busy}>
            <Search className="size-4" /> Prévisualiser la sélection
          </Button>
        </div>

        {apercu && (
          <div className="mt-3 flex flex-col gap-3">
            <div className="flex flex-wrap gap-4 rounded-lg border px-3 py-2 text-sm">
              <span>{apercu.nb_dettes} échéance(s) éligible(s)</span>
              <span>Total : <strong>{formatMAD(apercu.total)}</strong></span>
              {apercu.compte && (
                <>
                  <span>
                    Solde actuel : <strong>{formatMAD(apercu.compte.solde_actuel)}</strong>
                  </span>
                  <span>
                    Solde après campagne :{' '}
                    <strong>{formatMAD(apercu.compte.solde_projete)}</strong>
                  </span>
                </>
              )}
            </div>

            {alerte && (
              <div
                className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
                role="alert"
              >
                <p className="flex items-start gap-2">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                  <span>{alerte.message}</span>
                </p>
                <label className="mt-2 flex items-center gap-2 text-xs">
                  <Checkbox
                    checked={outrepasser}
                    onCheckedChange={(v) => setOutrepasser(Boolean(v))}
                  />
                  Je confirme vouloir créer cette campagne malgré l’alerte.
                </label>
              </div>
            )}

            {rien ? (
              <EmptyState
                title="Aucune échéance éligible"
                description="Aucune dette fournisseur ouverte ne correspond à ces filtres."
              />
            ) : (
              <ComptaTable
                aria-label="Échéances pré-sélectionnées"
                exportName="campagne-paiement-apercu"
                rows={apercu.dettes}
                getRowKey={(d) => d.facture_id}
                columns={[
                  { key: 'fournisseur', label: 'Fournisseur',
                    cell: (d) => d.fournisseur_nom || `Tiers #${d.fournisseur_id}` },
                  { key: 'reference', label: 'Pièce', cell: (d) => d.reference || '—' },
                  { key: 'echeance', label: 'Échéance',
                    sortValue: (d) => d.date_echeance || '',
                    cell: (d) => formatDate(d.date_echeance) },
                  { key: 'montant', label: 'Montant', align: 'right', numeric: true,
                    sortValue: (d) => Number(d.montant) || 0,
                    cell: (d) => formatMAD(d.montant) },
                ]}
              />
            )}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button onClick={creer} disabled={busy || !apercu || rien || bloque}>
            Créer la campagne (brouillon)
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
