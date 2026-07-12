import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import { Plus, Trash2, Send, Check, X } from 'lucide-react'
import installationsApi from '../../api/installationsApi'
import stockApi from '../../api/stockApi'
import ProduitPicker from '../../components/ProduitPicker'
import { formatMAD, formatDate } from '../../lib/format'
import { toastSuccess, toastError } from '../../lib/toast'
import {
  Button, IconButton, StatusPill, DataTable,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Input, Textarea,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'

// FG310 — statuts de la demande d'achat. Les codes ne figurent pas dans le
// STATUS_TONES générique de StatusPill (propres à ce cycle), donc on passe une
// `tone` explicite pour une couleur porteuse de sens.
const STATUT_LABEL = {
  brouillon: 'Brouillon', soumise: 'Soumise', approuvee: 'Approuvée',
  refusee: 'Refusée', commandee: 'Commandée',
}
const STATUT_TONE = {
  brouillon: 'neutral', soumise: 'info', approuvee: 'success',
  refusee: 'danger', commandee: 'primary',
}
const PRIORITE_LABEL = {
  basse: 'Basse', normale: 'Normale', haute: 'Haute', urgente: 'Urgente',
}
const PRIORITES = ['basse', 'normale', 'haute', 'urgente']

// Traducteur d'erreur DRF → message français (mêmes formes que le reste de
// l'app : {detail} | {champ: [...]}).
function frError(err, fallback) {
  const d = err?.response?.data
  if (typeof d === 'string') return d
  if (d?.detail) return d.detail
  if (d && typeof d === 'object') {
    const first = Object.values(d)[0]
    if (Array.isArray(first) && first.length) return String(first[0])
    if (typeof first === 'string') return first
  }
  return fallback
}

let _keySeq = 0
const newLigne = () => ({
  _key: `l${++_keySeq}`, produit: null, designation: '', quantite: '', prix_estime: '',
})

const emptyForm = () => ({
  objet: '', chantier: '', priorite: 'normale', date_besoin: '', note: '',
  lignes: [newLigne()],
})

export default function DemandesAchatList() {
  const isManager = useIsAdminOrResponsable()
  // VX227 — pré-remplissage depuis une intervention : un tap dans la
  // préparation ouvre la DA avec le chantier (et l'intervention) déjà
  // renseignés dans l'objet, pour ne pas ressaisir le contexte terrain.
  const [searchParams, setSearchParams] = useSearchParams()

  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [produits, setProduits] = useState([])
  const [chantiers, setChantiers] = useState([])

  // Dialogue de création (form) et de détail (une demande existante).
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')

  const [detail, setDetail] = useState(null) // demande sélectionnée
  const [acting, setActing] = useState(false)
  const [refusing, setRefusing] = useState(false)
  const [motifRefus, setMotifRefus] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const res = await installationsApi.getDemandesAchat()
      setItems(res.data?.results ?? res.data ?? [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // Chargement initial + listes de référence du formulaire (produits pour le
    // picker, chantiers pour le rattachement). L'état n'est posé que dans les
    // callbacks asynchrones (pas de setState synchrone dans le corps d'effet).
    let alive = true
    installationsApi.getDemandesAchat().then(
      (res) => { if (alive) { setItems(res.data?.results ?? res.data ?? []); setLoading(false) } },
      () => { if (alive) setLoading(false) },
    )
    stockApi.getProduits().then(
      (r) => { if (alive) setProduits(r.data?.results ?? r.data ?? []) },
      () => {},
    )
    installationsApi.getInstallations().then(
      (r) => { if (alive) setChantiers(r.data?.results ?? r.data ?? []) },
      () => {},
    )
    return () => { alive = false }
  }, [])

  // VX227 — un lien « Autre besoin non prévu → Nouvelle demande d'achat »
  // depuis la préparation d'une intervention navigue vers
  // `/chantiers/demandes-achat?chantier={id}&intervention={id}` ; on ouvre
  // alors le formulaire de création avec le chantier pré-sélectionné et un
  // objet pré-rempli rappelant l'intervention d'origine. Consommé UNE fois,
  // puis les params sont retirés de l'URL pour ne pas re-déclencher au retour.
  useEffect(() => {
    const chantierParam = searchParams.get('chantier')
    if (!chantierParam) return
    const interventionParam = searchParams.get('intervention')
    // eslint-disable-next-line react-hooks/set-state-in-effect -- pre-remplissage depuis l'URL au montage
    setForm({
      ...emptyForm(),
      chantier: chantierParam,
      objet: interventionParam
        ? `Besoin non prévu — intervention #${interventionParam}`
        : '',
    })
    setFormError('')
    setCreating(true)
    // Nettoie l'URL pour que le formulaire ne se rouvre pas sur un simple
    // remontage (retour arrière, refresh) — le pré-remplissage est ponctuel.
    setSearchParams({}, { replace: true })
  }, [searchParams, setSearchParams])

  const openCreate = () => {
    setForm(emptyForm())
    setFormError('')
    setCreating(true)
  }

  const setLigne = (key, patch) =>
    setForm((f) => ({
      ...f,
      lignes: f.lignes.map((l) => (l._key === key ? { ...l, ...patch } : l)),
    }))
  const addLigne = () => setForm((f) => ({ ...f, lignes: [...f.lignes, newLigne()] }))
  const removeLigne = (key) =>
    setForm((f) => ({
      ...f,
      lignes: f.lignes.length > 1 ? f.lignes.filter((l) => l._key !== key) : f.lignes,
    }))

  // Sélection d'un produit catalogue. La désignation reste libre : on ne la
  // pré-remplit depuis le catalogue que si l'utilisateur ne l'a pas déjà saisie
  // (jamais l'écraser).
  const pickProduit = (key, produitId) => {
    const p = produits.find((x) => String(x.id) === String(produitId))
    setForm((f) => ({
      ...f,
      lignes: f.lignes.map((l) => {
        if (l._key !== key) return l
        const patch = { produit: produitId || null }
        if (p && !(l.designation || '').trim()) patch.designation = p.nom
        return { ...l, ...patch }
      }),
    }))
  }

  const submitCreate = async (thenSoumettre) => {
    setFormError('')
    if (!form.objet.trim()) {
      setFormError("L'objet est obligatoire.")
      return
    }
    // On ne conserve que les lignes réellement renseignées (produit OU
    // désignation) — la garde serveur les rejette sinon.
    const lignes = form.lignes.filter(
      (l) => l.produit || (l.designation || '').trim(),
    )
    setSaving(true)
    try {
      const res = await installationsApi.createDemandeAchat({
        objet: form.objet.trim(),
        chantier: form.chantier || null,
        priorite: form.priorite,
        date_besoin: form.date_besoin || null,
        note: form.note || null,
      })
      const id = res.data.id
      for (const l of lignes) {
        await installationsApi.createDemandeAchatLigne({
          demande: id,
          produit: l.produit || null,
          designation: (l.designation || '').trim() || null,
          quantite: l.quantite || 0,
          prix_estime: l.prix_estime || 0,
        })
      }
      if (thenSoumettre) {
        await installationsApi.soumettreDemandeAchat(id)
      }
      toastSuccess(thenSoumettre ? 'Demande créée et soumise.' : 'Demande enregistrée.')
      setCreating(false)
      await load()
    } catch (err) {
      setFormError(frError(err, "Impossible d'enregistrer la demande."))
    } finally {
      setSaving(false)
    }
  }

  const runAction = async (fn, okMsg) => {
    setActing(true)
    try {
      const res = await fn()
      setDetail(res.data)
      toastSuccess(okMsg)
      await load()
    } catch (err) {
      toastError(frError(err, "L'action a échoué."))
    } finally {
      setActing(false)
    }
  }

  const soumettre = () =>
    runAction(() => installationsApi.soumettreDemandeAchat(detail.id), 'Demande soumise.')
  const approuver = () =>
    runAction(() => installationsApi.approuverDemandeAchat(detail.id), 'Demande approuvée.')
  const confirmRefus = () =>
    runAction(
      () => installationsApi.refuserDemandeAchat(detail.id, motifRefus.trim()),
      'Demande refusée.',
    ).then(() => { setRefusing(false); setMotifRefus('') })

  const columns = useMemo(() => [
    { id: 'reference', header: 'Référence', accessor: (d) => d.reference, width: 140, searchable: true },
    { id: 'objet', header: 'Objet', accessor: (d) => d.objet, minWidth: 220, searchable: true },
    {
      id: 'chantier', header: 'Chantier',
      accessor: (d) => chantiers.find((c) => c.id === d.chantier)?.nom || '—',
      minWidth: 160,
    },
    {
      id: 'statut', header: 'Statut', accessor: (d) => d.statut, width: 130,
      cell: (v) => <StatusPill status={v} tone={STATUT_TONE[v]} label={STATUT_LABEL[v] || v} />,
    },
    {
      id: 'priorite', header: 'Priorité', accessor: (d) => d.priorite, width: 110,
      cell: (v) => PRIORITE_LABEL[v] || v,
    },
    {
      id: 'montant_estime', header: 'Montant estimé', accessor: (d) => d.montant_estime,
      align: 'right', width: 150,
      cell: (v) => formatMAD(v),
    },
    {
      id: 'date_besoin', header: 'Besoin le', accessor: (d) => d.date_besoin, width: 120,
      cell: (v) => (v ? formatDate(v) : '—'),
    },
  ], [chantiers])

  return (
    <div className="ui-root space-y-4 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Demandes d'achat</h1>
          <p className="text-sm text-muted-foreground">
            Réquisitions de matériel chantier soumises à approbation.
          </p>
        </div>
        <Button onClick={openCreate}>
          <Plus /> Nouvelle demande
        </Button>
      </div>

      <DataTable
        data={items}
        columns={columns}
        loading={loading}
        getRowId={(d) => d.id}
        searchPlaceholder="Rechercher (référence, objet)…"
        globalColumns={['reference', 'objet']}
        onRowClick={(d) => { setDetail(d); setRefusing(false); setMotifRefus('') }}
        emptyTitle="Aucune demande d'achat"
        emptyDescription="Créez une réquisition avec « Nouvelle demande »."
        emptyAction={<Button size="sm" onClick={openCreate}><Plus className="size-4" /> Nouvelle demande</Button>}
        aria-label="Demandes d'achat"
      />

      {/* ── Dialogue de création ── */}
      <Dialog open={creating} onOpenChange={(o) => { if (!o) setCreating(false) }}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Nouvelle demande d'achat</DialogTitle>
            <DialogDescription>
              Décrivez le besoin et les articles ; la demande part en approbation à la soumission.
            </DialogDescription>
          </DialogHeader>

          <div className="max-h-[60vh] space-y-4 overflow-y-auto pr-1">
            <div className="space-y-1.5">
              <label className="text-sm font-medium" htmlFor="da-objet">Objet</label>
              <Input
                id="da-objet" value={form.objet}
                onChange={(e) => setForm((f) => ({ ...f, objet: e.target.value }))}
                placeholder="Ex. Matériel de fixation pour le chantier Villa Anfa"
              />
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Chantier</label>
                <Select
                  value={form.chantier ? String(form.chantier) : ''}
                  onValueChange={(v) => setForm((f) => ({ ...f, chantier: v }))}
                >
                  <SelectTrigger><SelectValue placeholder="Aucun" /></SelectTrigger>
                  <SelectContent>
                    {chantiers.map((c) => (
                      <SelectItem key={c.id} value={String(c.id)}>
                        {c.nom || c.reference || `Chantier ${c.id}`}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Priorité</label>
                <Select
                  value={form.priorite}
                  onValueChange={(v) => setForm((f) => ({ ...f, priorite: v }))}
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {PRIORITES.map((p) => (
                      <SelectItem key={p} value={p}>{PRIORITE_LABEL[p]}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium" htmlFor="da-besoin">Besoin le</label>
                <Input
                  id="da-besoin" type="date" value={form.date_besoin}
                  onChange={(e) => setForm((f) => ({ ...f, date_besoin: e.target.value }))}
                />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium">Articles</label>
                <IconButton type="button" label="Ajouter une ligne" onClick={addLigne}>
                  <Plus />
                </IconButton>
              </div>
              <div className="space-y-2">
                {form.lignes.map((l) => (
                  <div key={l._key} className="grid grid-cols-12 items-start gap-2">
                    <div className="col-span-12 sm:col-span-5">
                      <ProduitPicker
                        produits={produits}
                        value={l.produit}
                        onChange={(v) => pickProduit(l._key, v)}
                      />
                    </div>
                    <div className="col-span-6 sm:col-span-3">
                      <Input
                        aria-label="Désignation"
                        placeholder="Désignation libre"
                        value={l.designation}
                        onChange={(e) => setLigne(l._key, { designation: e.target.value })}
                      />
                    </div>
                    <div className="col-span-3 sm:col-span-1">
                      <Input
                        aria-label="Quantité" type="number" step="any" min="0"
                        placeholder="Qté" value={l.quantite}
                        onChange={(e) => setLigne(l._key, { quantite: e.target.value })}
                      />
                    </div>
                    <div className="col-span-3 sm:col-span-2">
                      <Input
                        aria-label="Prix estimé" type="number" step="any" min="0"
                        placeholder="Prix est." value={l.prix_estime}
                        onChange={(e) => setLigne(l._key, { prix_estime: e.target.value })}
                      />
                    </div>
                    <div className="col-span-12 flex justify-end sm:col-span-1">
                      <IconButton
                        type="button" label="Supprimer la ligne"
                        onClick={() => removeLigne(l._key)}
                      >
                        <Trash2 />
                      </IconButton>
                    </div>
                  </div>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">
                Un article = un produit du catalogue OU une désignation libre. Le prix estimé est
                indicatif (interne).
              </p>
            </div>

            <div className="space-y-1.5">
              <label className="text-sm font-medium" htmlFor="da-note">Note</label>
              <Textarea
                id="da-note" rows={2} value={form.note}
                onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))}
                placeholder="Précisions éventuelles…"
              />
            </div>

            {formError && (
              <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                {formError}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreating(false)} disabled={saving}>
              Annuler
            </Button>
            <Button variant="outline" onClick={() => submitCreate(false)} loading={saving}>
              Enregistrer en brouillon
            </Button>
            <Button onClick={() => submitCreate(true)} loading={saving}>
              <Send /> Créer et soumettre
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialogue de détail + cycle de vie ── */}
      <Dialog open={!!detail} onOpenChange={(o) => { if (!o) { setDetail(null); setRefusing(false) } }}>
        <DialogContent className="max-w-2xl">
          {detail && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  {detail.reference}
                  <StatusPill
                    status={detail.statut} tone={STATUT_TONE[detail.statut]}
                    label={STATUT_LABEL[detail.statut] || detail.statut}
                  />
                </DialogTitle>
                <DialogDescription>{detail.objet}</DialogDescription>
              </DialogHeader>

              <div className="max-h-[55vh] space-y-3 overflow-y-auto pr-1 text-sm">
                <div className="grid grid-cols-2 gap-2 text-muted-foreground">
                  <div>Priorité : <span className="text-foreground">{PRIORITE_LABEL[detail.priorite] || detail.priorite}</span></div>
                  <div>Besoin le : <span className="text-foreground">{detail.date_besoin ? formatDate(detail.date_besoin) : '—'}</span></div>
                  <div>Chantier : <span className="text-foreground">{chantiers.find((c) => c.id === detail.chantier)?.nom || '—'}</span></div>
                  <div>Montant estimé : <span className="text-foreground">{formatMAD(detail.montant_estime)}</span></div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-muted-foreground">
                        <th className="py-1.5 pr-2 font-medium">Article</th>
                        <th className="py-1.5 pr-2 text-right font-medium">Qté</th>
                        <th className="py-1.5 pr-2 text-right font-medium">Prix est.</th>
                        <th className="py-1.5 text-right font-medium">Total est.</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(detail.lignes || []).map((l) => (
                        <tr key={l.id} className="border-b border-border/60">
                          <td className="py-1.5 pr-2">{l.designation || l.produit_nom || '—'}</td>
                          <td className="py-1.5 pr-2 text-right tabular-nums">{l.quantite}</td>
                          <td className="py-1.5 pr-2 text-right tabular-nums">{formatMAD(l.prix_estime)}</td>
                          <td className="py-1.5 text-right tabular-nums">{formatMAD(l.total_estime)}</td>
                        </tr>
                      ))}
                      {(!detail.lignes || detail.lignes.length === 0) && (
                        <tr><td colSpan={4} className="py-2 text-muted-foreground">Aucun article.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>

                {detail.note && (
                  <div className="rounded-lg bg-muted/40 p-2 text-muted-foreground">{detail.note}</div>
                )}
                {detail.statut === 'refusee' && detail.motif_refus && (
                  <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-2 text-destructive">
                    Motif du refus : {detail.motif_refus}
                  </div>
                )}

                {refusing && (
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium" htmlFor="da-motif">Motif du refus (optionnel)</label>
                    <Textarea
                      id="da-motif" rows={2} value={motifRefus}
                      onChange={(e) => setMotifRefus(e.target.value)}
                      placeholder="Ex. hors budget, fournisseur à revoir…"
                    />
                  </div>
                )}
              </div>

              <DialogFooter>
                {detail.statut === 'brouillon' && (
                  <Button onClick={soumettre} loading={acting}>
                    <Send /> Soumettre pour approbation
                  </Button>
                )}
                {detail.statut === 'soumise' && isManager && !refusing && (
                  <>
                    <Button variant="outline" onClick={() => setRefusing(true)} disabled={acting}>
                      <X /> Refuser
                    </Button>
                    <Button onClick={approuver} loading={acting}>
                      <Check /> Approuver
                    </Button>
                  </>
                )}
                {detail.statut === 'soumise' && isManager && refusing && (
                  <>
                    <Button variant="ghost" onClick={() => { setRefusing(false); setMotifRefus('') }} disabled={acting}>
                      Annuler
                    </Button>
                    <Button variant="outline" onClick={confirmRefus} loading={acting}>
                      Confirmer le refus
                    </Button>
                  </>
                )}
                {!(detail.statut === 'brouillon' || (detail.statut === 'soumise' && isManager)) && (
                  <Button variant="ghost" onClick={() => setDetail(null)}>Fermer</Button>
                )}
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
