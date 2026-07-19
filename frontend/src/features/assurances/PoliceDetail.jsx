import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Plus } from 'lucide-react'
import assurancesApi from './assurancesApi'
import {
  Badge, Button, Label, Input,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../ui'
import { RecordShell } from '../../ui/module'
import { formatMAD, formatDate, formatDateTime } from '../../lib/format'
import { POLICE_STATUS, toneEcheance } from './status'

/* ============================================================================
   NTASS26 — Fiche police détail (onglets).
   ----------------------------------------------------------------------------
   RecordShell UX1 : onglets Garanties (NTASS4), Actifs couverts (NTASS7),
   Échéancier de primes (NTASS5, bouton « Proposer écriture » NTASS6),
   Historique (chatter NTASS3), Attestations (NTASS17). Lecture des montants
   client-safe (formatMAD — jamais de prix d'achat/marge).
   ========================================================================== */

function useLoader(fn, deps) {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)
  const reload = () => {
    setLoading(true)
    fn()
      .then((res) => setData(Array.isArray(res.data) ? res.data : (res.data?.results ?? [])))
      .catch(() => setData([]))
      .finally(() => setLoading(false))
  }
  // reload() sets the loading flag synchronously on mount/deps change — the
  // load-on-mount loading state, same pattern as the sibling assurances lists.
  // eslint-disable-next-line react-hooks/exhaustive-deps, react-hooks/set-state-in-effect
  useEffect(() => { reload() }, deps)
  return { data, loading, reload }
}

function Empty({ label }) {
  return <p className="py-6 text-center text-sm text-muted-foreground">{label}</p>
}

/* WIR56 — modales de création des onglets Garanties / Actifs / Attestations.
   Chaque champ de saisie envoie `police` + les champs métier ; la société est
   posée côté serveur (jamais dans le corps). */
const ITEM_FORMS = {
  garantie: {
    title: 'Nouvelle garantie',
    fields: [
      { name: 'libelle_garantie', label: 'Libellé de la garantie', required: true },
      { name: 'plafond_indemnisation', label: "Plafond d'indemnisation (MAD)", type: 'number' },
      { name: 'franchise_montant', label: 'Franchise (MAD)', type: 'number' },
    ],
    submit: (data) => assurancesApi.createGarantie(data),
  },
  actif: {
    title: 'Nouvel actif couvert',
    fields: [
      { name: 'type_actif', label: 'Type d\'actif', required: true },
      { name: 'actif_ref', label: 'Référence de l\'actif' },
      { name: 'actif_libelle', label: 'Libellé de l\'actif' },
    ],
    submit: (data) => assurancesApi.createActifCouvert(data),
  },
  attestation: {
    title: 'Nouvelle attestation',
    fields: [
      { name: 'emise_pour', label: 'Émise pour', required: true },
      { name: 'date_emission', label: "Date d'émission", type: 'date' },
      { name: 'date_validite', label: 'Date de validité', type: 'date' },
    ],
    submit: (data) => assurancesApi.createAttestation(data),
  },
}

function AddItemDialog({ kind, policeId, onClose, onSaved }) {
  const cfg = ITEM_FORMS[kind]
  const [values, setValues] = useState({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const peut = cfg.fields.filter((f) => f.required).every((f) => String(values[f.name] ?? '').trim())

  const submit = async (e) => {
    e.preventDefault()
    if (!peut) return
    setSaving(true)
    setError(null)
    try {
      const payload = { police: Number(policeId) }
      cfg.fields.forEach((f) => {
        const v = values[f.name]
        if (v === undefined || v === '') return
        payload[f.name] = f.type === 'number' ? Number(v) : v
      })
      await cfg.submit(payload)
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setError(data?.detail || (typeof data === 'string' ? data : 'Enregistrement impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose?.() }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{cfg.title}</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-3" noValidate>
          {cfg.fields.map((f) => (
            <div key={f.name} className="flex flex-col gap-1.5">
              <Label htmlFor={`add-${f.name}`}>{f.label}</Label>
              <Input
                id={`add-${f.name}`}
                type={f.type === 'number' ? 'number' : f.type === 'date' ? 'date' : 'text'}
                step={f.type === 'number' ? 'any' : undefined}
                value={values[f.name] ?? ''}
                onChange={(e) => setValues((v) => ({ ...v, [f.name]: e.target.value }))}
              />
            </div>
          ))}
          {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={!peut || saving}>
              {saving ? 'Enregistrement…' : 'Ajouter'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function PoliceDetail() {
  const { id } = useParams()
  const [police, setPolice] = useState(null)
  const [error, setError] = useState(null)
  const [addDialog, setAddDialog] = useState(null)

  const loadPolice = () => {
    assurancesApi.getPolice(id)
      .then((res) => setPolice(res.data))
      .catch(() => setError('Police introuvable.'))
  }
  useEffect(() => { loadPolice() /* eslint-disable-line */ }, [id])

  const garanties = useLoader(() => assurancesApi.getGaranties(id), [id])
  const actifs = useLoader(() => assurancesApi.getActifsCouverts(id), [id])
  const echeances = useLoader(() => assurancesApi.getEcheancesPrime(id), [id])
  const historique = useLoader(() => assurancesApi.getPoliceHistorique(id), [id])
  const attestations = useLoader(() => assurancesApi.getAttestations(id), [id])

  const proposerEcriture = useCallback((echeanceId) => {
    assurancesApi.proposerEcriturePrime(echeanceId)
      .then(() => echeances.reload())
      .catch(() => { /* affiché via rechargement */ })
  }, [echeances])

  const tabs = useMemo(() => [
    {
      value: 'garanties',
      label: 'Garanties',
      count: garanties.data.length,
      content: (
        <div className="flex flex-col gap-2">
          <div className="flex justify-end">
            <Button size="sm" variant="outline" onClick={() => setAddDialog('garantie')}>
              <Plus className="size-3.5" /> Ajouter une garantie
            </Button>
          </div>
          {garanties.data.length === 0
            ? <Empty label="Aucune garantie enregistrée." />
            : (
              <ul className="divide-y">
                {garanties.data.map((g) => (
                  <li key={g.id} className="flex items-center justify-between py-2 text-sm">
                    <span className="font-medium">{g.libelle_garantie}</span>
                    <span className="text-muted-foreground">
                      Plafond {formatMAD(g.plafond_indemnisation)} · Franchise{' '}
                      {formatMAD(g.franchise_montant)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
        </div>
      ),
    },
    {
      value: 'actifs',
      label: 'Actifs couverts',
      count: actifs.data.length,
      content: (
        <div className="flex flex-col gap-2">
          <div className="flex justify-end">
            <Button size="sm" variant="outline" onClick={() => setAddDialog('actif')}>
              <Plus className="size-3.5" /> Ajouter un actif
            </Button>
          </div>
          {actifs.data.length === 0
            ? <Empty label="Aucun actif couvert." />
            : (
              <ul className="divide-y">
                {actifs.data.map((a) => (
                  <li key={a.id} className="flex items-center justify-between py-2 text-sm">
                    <span className="font-medium">{a.actif_libelle || '—'}</span>
                    <Badge tone="slate">{a.type_actif}</Badge>
                  </li>
                ))}
              </ul>
            )}
        </div>
      ),
    },
    {
      value: 'echeancier',
      label: 'Échéancier de primes',
      count: echeances.data.length,
      content: echeances.data.length === 0
        ? <Empty label="Aucune échéance de prime générée." />
        : (
          <ul className="divide-y">
            {echeances.data.map((e) => (
              <li key={e.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                <span>{formatDate(e.date_echeance_paiement)}</span>
                <span className="font-medium tabular-nums">{formatMAD(e.montant)}</span>
                <Badge tone={e.statut === 'payee' ? 'green' : 'amber'}>{e.statut}</Badge>
                {e.statut === 'a_payer' && (
                  <Button size="sm" variant="outline" onClick={() => proposerEcriture(e.id)}>
                    Proposer écriture
                  </Button>
                )}
              </li>
            ))}
          </ul>
        ),
    },
    {
      value: 'attestations',
      label: 'Attestations',
      count: attestations.data.length,
      content: (
        <div className="flex flex-col gap-2">
          <div className="flex justify-end">
            <Button size="sm" variant="outline" onClick={() => setAddDialog('attestation')}>
              <Plus className="size-3.5" /> Ajouter une attestation
            </Button>
          </div>
          {attestations.data.length === 0
            ? <Empty label="Aucune attestation." />
            : (
              <ul className="divide-y">
                {attestations.data.map((att) => (
                  <li key={att.id} className="flex items-center justify-between py-2 text-sm">
                    <span className="font-medium">{att.emise_pour || 'Attestation'}</span>
                    <Badge tone={toneEcheance(att.date_validite)}>
                      Valide jusqu'au {formatDate(att.date_validite)}
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
        </div>
      ),
    },
  ], [garanties.data, actifs.data, echeances.data, attestations.data, proposerEcriture])

  const activity = (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold">Historique</h3>
      {historique.data.length === 0
        ? <Empty label="Aucune activité." />
        : (
          <ul className="flex flex-col gap-2">
            {historique.data.map((h) => (
              <li key={h.id} className="rounded-md border p-2 text-xs">
                <div className="flex items-center justify-between text-muted-foreground">
                  <span>{h.kind}</span>
                  <span>{formatDateTime(h.created_at)}</span>
                </div>
                {h.field
                  ? <p>{h.field_label || h.field} : {h.old_value} → {h.new_value}</p>
                  : <p>{h.body}</p>}
              </li>
            ))}
          </ul>
        )}
    </div>
  )

  if (error) {
    return <p className="p-6 text-sm text-destructive">{error}</p>
  }

  const statut = police?.statut
  const statutInfo = statut ? POLICE_STATUS[statut] : null

  const reloadAfterAdd = (kind) => {
    if (kind === 'garantie') garanties.reload()
    else if (kind === 'actif') actifs.reload()
    else if (kind === 'attestation') attestations.reload()
  }

  return (
    <>
      <RecordShell
        title={police ? `${police.numero_police}` : 'Police'}
        subtitle={police
          ? `${police.type_police_display || police.type_police} · ${police.assureur_nom || ''}`
          : ''}
        backTo="/assurances"
        backLabel="Retour aux polices"
        status={statutInfo ? statutInfo.label : null}
        actions={police && (
          <Button variant="outline" onClick={() => assurancesApi.renouvelerPolice(id).then(loadPolice)}>
            Renouveler
          </Button>
        )}
        tabs={tabs}
        activity={activity}
      />
      {addDialog && (
        <AddItemDialog
          kind={addDialog}
          policeId={id}
          onClose={() => setAddDialog(null)}
          onSaved={() => { reloadAfterAdd(addDialog); setAddDialog(null) }}
        />
      )}
    </>
  )
}
