// XMFG1-16 — Atelier (MRP-lite / kitting) : ordres d'assemblage (kits →
// composite) et démontage (unbuild). Liste filtrable + création + détail avec
// backflush de stock à la clôture, réservations/disponibilité par composant,
// gate qualité (checklist QC), gamme d'exécution, chatter et bon d'assemblage
// PDF (worksheet atelier). Aucun coût d'achat / marge n'est affiché ici.
import { useEffect, useMemo, useState } from 'react'
import { useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import {
  Plus, Play, CheckCircle2, XCircle, FileText, Printer, RefreshCw, Wrench,
} from 'lucide-react'
import installationsApi from '../../api/installationsApi'
import {
  Button, Badge, Segmented, Spinner, Skeleton, EmptyState, Input, Textarea,
  Checkbox,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  DataTable, StatusPill,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DialogFooter, Label, toast,
} from '../../ui'
import { formatDate } from '../../lib/format'
// VX132 — anti-scintillement propagé : Spinner + Skeleton s'affichaient
// SIMULTANÉMENT (voir InstallationsPage.jsx, déjà migrée).
import { useDelayedLoading } from '../../hooks/useDelayedLoading'

// Statuts de l'ordre d'assemblage (models_kitting OrdreAssemblage.Statut).
const STATUT_TONE = {
  planifie: 'info',
  en_cours: 'warning',
  termine: 'success',
  annule: 'neutral',
}
const STATUT_LABEL = {
  planifie: 'Planifié',
  en_cours: 'En cours',
  termine: 'Terminé',
  annule: 'Annulé',
}

// Disponibilité d'un composant (services.disponibilite_par_ligne).
const DISPO_TONE = {
  disponible: 'success',
  partiel: 'warning',
  manquant: 'danger',
}
const DISPO_LABEL = {
  disponible: 'Disponible',
  partiel: 'Partiel',
  manquant: 'Manquant',
}

// WIR248/XMFG11 — motifs de rebut (miroir EXACT de
// `stock.MouvementStock.MotifRebut`). Le motif est OBLIGATOIRE : un rebut sans
// raison n'est pas traçable.
const MOTIFS_REBUT = [
  { value: 'casse', label: 'Casse' },
  { value: 'defaut', label: 'Défaut' },
  { value: 'erreur', label: 'Erreur' },
  { value: 'obsolete', label: 'Obsolète' },
  { value: 'perime', label: 'Périmé' },
  { value: 'vol', label: 'Vol' },
  { value: 'autre', label: 'Autre' },
]
const MOTIF_LABEL = Object.fromEntries(MOTIFS_REBUT.map((m) => [m.value, m.label]))

function statutPill(statut) {
  return (
    <StatusPill
      tone={STATUT_TONE[statut] ?? 'neutral'}
      label={STATUT_LABEL[statut] ?? statut ?? '—'}
    />
  )
}

// ── Création d'un ordre d'assemblage ────────────────────────────────────────
function CreateAssemblageDialog({ kits, onClose, onCreated }) {
  const [form, setForm] = useState({ kit: '', quantite: '1', note: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const submit = () => {
    if (!form.kit) { setError('Sélectionnez un kit.'); return }
    setBusy(true)
    setError(null)
    installationsApi
      .createOrdreAssemblage({
        kit: form.kit,
        quantite: form.quantite,
        note: form.note || undefined,
      })
      .then((r) => {
        toast.success("Ordre d'assemblage créé.")
        onCreated(r.data)
      })
      .catch(() => setError("Création impossible. Vérifiez les champs."))
      .finally(() => setBusy(false))
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nouvel ordre d'assemblage</DialogTitle>
          <DialogDescription>
            La nomenclature du kit est copiée en lignes et les composants sont
            réservés dès la création.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asm-kit">Kit</Label>
            <Select value={form.kit} onValueChange={(v) => set('kit', v)}>
              <SelectTrigger id="asm-kit" aria-label="Kit à assembler">
                <SelectValue placeholder="Choisir un kit…" />
              </SelectTrigger>
              <SelectContent>
                {kits.map((k) => (
                  <SelectItem key={k.id} value={String(k.id)}>
                    {k.nom}{k.reference_interne ? ` (${k.reference_interne})` : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asm-qte">Quantité à assembler</Label>
            <Input
              id="asm-qte" type="number" min="1" step="any"
              value={form.quantite}
              onChange={(e) => set('quantite', e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asm-note">Note (facultatif)</Label>
            <Textarea
              id="asm-note" rows={2} value={form.note}
              onChange={(e) => set('note', e.target.value)}
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
            Annuler
          </Button>
          <Button type="button" onClick={submit} disabled={busy}>
            {busy ? <Spinner /> : <Plus />} Créer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── Création d'un ordre de démontage ────────────────────────────────────────
function CreateDemontageDialog({ kits, onClose, onCreated }) {
  const [form, setForm] = useState({ kit: '', quantite: '1', note: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const submit = () => {
    if (!form.kit) { setError('Sélectionnez un kit.'); return }
    setBusy(true)
    setError(null)
    installationsApi
      .createOrdreDemontage({
        kit: form.kit,
        quantite: form.quantite,
        note: form.note || undefined,
      })
      .then((r) => {
        toast.success('Ordre de démontage créé.')
        onCreated(r.data)
      })
      .catch(() => setError('Création impossible. Vérifiez les champs.'))
      .finally(() => setBusy(false))
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nouvel ordre de démontage</DialogTitle>
          <DialogDescription>
            Le composite sera sorti du stock et ses composants restockés selon
            les quantités récupérées.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="dsm-kit">Kit</Label>
            <Select value={form.kit} onValueChange={(v) => set('kit', v)}>
              <SelectTrigger id="dsm-kit" aria-label="Kit à démonter">
                <SelectValue placeholder="Choisir un kit…" />
              </SelectTrigger>
              <SelectContent>
                {kits.map((k) => (
                  <SelectItem key={k.id} value={String(k.id)}>
                    {k.nom}{k.reference_interne ? ` (${k.reference_interne})` : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="dsm-qte">Quantité à démonter</Label>
            <Input
              id="dsm-qte" type="number" min="1" step="any"
              value={form.quantite}
              onChange={(e) => set('quantite', e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="dsm-note">Note (facultatif)</Label>
            <Textarea
              id="dsm-note" rows={2} value={form.note}
              onChange={(e) => set('note', e.target.value)}
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
            Annuler
          </Button>
          <Button type="button" onClick={submit} disabled={busy}>
            {busy ? <Spinner /> : <Plus />} Créer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── Détail d'un ordre d'assemblage ──────────────────────────────────────────
function AssemblageDetail({ ordre, canWrite, onClose, onChanged }) {
  const [dispo, setDispo] = useState([])
  const [controles, setControles] = useState([])
  const [historique, setHistorique] = useState([])
  // WIR247 — gamme d'exécution (XMFG14) et lignes de composant (XMFG6) :
  // construites côté serveur, jamais appelées côté client.
  const [etapes, setEtapes] = useState([])
  const [lignes, setLignes] = useState([])
  // WIR247 — nomenclature indentée du kit (XMFG5). Chargée À LA DEMANDE : ce
  // n'est pas une donnée de la fiche, c'est une consultation.
  const [structure, setStructure] = useState(null)
  const [structureBusy, setStructureBusy] = useState(false)
  const [nouvelleLigne, setNouvelleLigne] = useState({ designation: '', quantite: '' })
  const [busy, setBusy] = useState(false)
  const [terminerOpen, setTerminerOpen] = useState(false)
  const [annulerOpen, setAnnulerOpen] = useState(false)
  // WIR248 — déclaration d'un rebut de production sur CET ordre.
  const [rebutOpen, setRebutOpen] = useState(false)
  const [note, setNote] = useState('')

  // Chargements read-only isolés dans une fonction pure (pas de setState
  // synchrone au montage) — appelée par l'effet et après chaque action.
  const load = () => {
    installationsApi.getDisponibiliteAssemblage(ordre.id)
      .then((r) => setDispo(Array.isArray(r.data) ? r.data : []))
      .catch(() => {})
    installationsApi.getControleQualiteAssemblage(ordre.id)
      .then((r) => setControles(Array.isArray(r.data) ? r.data : []))
      .catch(() => {})
    installationsApi.getHistoriqueAssemblage(ordre.id)
      .then((r) => setHistorique(Array.isArray(r.data) ? r.data : []))
      .catch(() => {})
    installationsApi.getEtapesAssemblage(ordre.id)
      .then((r) => setEtapes(Array.isArray(r.data) ? r.data : []))
      .catch(() => {})
    installationsApi.getLignesAssemblage(ordre.id)
      .then((r) => setLignes(r.data?.results ?? (Array.isArray(r.data) ? r.data : [])))
      .catch(() => {})
  }
  useEffect(() => { load() }, [ordre.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const qcBloque = controles.some(
    (c) => c.resultat == null || c.resultat === 'echec')

  const demarrer = () => {
    setBusy(true)
    installationsApi.demarrerAssemblage(ordre.id)
      .then((r) => { toast.success('Ordre démarré.'); onChanged(r.data) })
      .catch(() => toast.error('Démarrage impossible.'))
      .finally(() => setBusy(false))
  }

  const enregistrerNote = () => {
    const body = note.trim()
    if (!body) return
    setBusy(true)
    installationsApi.noterAssemblage(ordre.id, body)
      .then(() => { setNote(''); load() })
      .catch(() => toast.error('Note non enregistrée.'))
      .finally(() => setBusy(false))
  }

  const enregistrerQc = (itemModeleId, resultat) => {
    installationsApi
      .enregistrerControleQualiteAssemblage(ordre.id, itemModeleId, { resultat })
      .then(() => load())
      .catch(() => toast.error('Contrôle non enregistré.'))
  }

  // ── WIR247 — gamme d'exécution (XMFG14) ──────────────────────────────────
  const cocherEtape = (etape, fait, dureeReelle) => {
    setBusy(true)
    installationsApi
      .cocherEtapeAssemblage(ordre.id, etape.etape_modele, {
        fait,
        duree_reelle_min: dureeReelle === '' || dureeReelle == null
          ? null : dureeReelle,
      })
      .then((r) => setEtapes((prev) => prev.map(
        (e) => (e.etape_modele === etape.etape_modele ? r.data : e))))
      .catch(() => toast.error('Étape non enregistrée.'))
      .finally(() => setBusy(false))
  }

  // ── WIR247 — lignes de composant (XMFG6), éditables tant que PLANIFIÉ ────
  // Le serveur verrouille dès `en_cours` : l'écran fait DISPARAÎTRE l'édition
  // au même moment plutôt que d'offrir un bouton qui échouera.
  const lignesEditables = canWrite && ordre.statut === 'planifie'

  const modifierLigne = (ligne, quantite) => {
    setBusy(true)
    installationsApi.updateLigneAssemblage(ligne.id, { quantite })
      .then((r) => setLignes((prev) => prev.map(
        (l) => (l.id === ligne.id ? r.data : l))))
      .catch(() => toast.error('Ligne non modifiée.'))
      .finally(() => setBusy(false))
  }

  const supprimerLigne = (ligne) => {
    setBusy(true)
    installationsApi.deleteLigneAssemblage(ligne.id)
      .then(() => setLignes((prev) => prev.filter((l) => l.id !== ligne.id)))
      .catch(() => toast.error('Ligne non supprimée.'))
      .finally(() => setBusy(false))
  }

  const ajouterLigne = () => {
    const designation = nouvelleLigne.designation.trim()
    if (!designation) return
    setBusy(true)
    installationsApi.createLigneAssemblage({
      ordre: ordre.id,
      designation,
      quantite: nouvelleLigne.quantite === '' ? 1 : nouvelleLigne.quantite,
    })
      .then((r) => {
        setLignes((prev) => [...prev, r.data])
        setNouvelleLigne({ designation: '', quantite: '' })
      })
      .catch(() => toast.error('Ligne non ajoutée.'))
      .finally(() => setBusy(false))
  }

  // ── WIR247 — nomenclature indentée du kit (XMFG5) ────────────────────────
  // Consultation à la demande. Aucun coût ni marge n'est rendu ici : le
  // serveur en sert pour les rôles autorisés, l'atelier n'en affiche AUCUN.
  const ouvrirNomenclature = () => {
    if (structure) { setStructure(null); return }
    if (!ordre.kit) return
    setStructureBusy(true)
    installationsApi.getKitStructure(ordre.kit)
      .then((r) => setStructure(r.data ?? null))
      .catch(() => toast.error('Nomenclature indisponible.'))
      .finally(() => setStructureBusy(false))
  }

  // Les lignes PERSONNALISÉES (XMFG6) priment ; sinon la disponibilité
  // calculée, sinon les lignes portées par l'ordre.
  const dispoLignes = useMemo(
    () => (dispo.length ? dispo : (ordre.lignes ?? [])), [dispo, ordre.lignes])

  // WIR248 — produits rebutables : ceux DE CET ORDRE (jamais un catalogue
  // complet — un rebut d'atelier porte sur un composant de l'ordre).
  const produitsRebutables = useMemo(() => {
    const vus = new Map()
    for (const l of [...lignes, ...dispoLignes]) {
      const pid = l.produit ?? l.produit_id
      if (!pid || vus.has(pid)) continue
      vus.set(pid, { id: pid, nom: l.produit_nom ?? l.designation ?? `Produit ${pid}` })
    }
    return [...vus.values()]
  }, [lignes, dispoLignes])

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {ordre.reference} {statutPill(ordre.statut)}
          </DialogTitle>
          <DialogDescription>
            {ordre.kit_nom} · {ordre.quantite} unité(s)
            {ordre.date_prevue ? ` · prévu le ${formatDate(ordre.date_prevue)}` : ''}
          </DialogDescription>
        </DialogHeader>

        <div className="flex max-h-[60vh] flex-col gap-4 overflow-y-auto">
          {/* XMFG2 — disponibilité des composants (réservation-aware). */}
          <section>
            <h3 className="mb-1.5 text-sm font-semibold">Composants</h3>
            {dispoLignes.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucun composant.</p>
            ) : (
              <ul className="flex flex-col gap-1 text-sm">
                {dispoLignes.map((l, i) => (
                  <li key={l.id ?? i} className="flex items-center justify-between gap-2">
                    <span>{l.produit_nom ?? l.designation ?? '—'}</span>
                    <span className="flex items-center gap-2">
                      <span className="tabular-nums text-muted-foreground">
                        ×{l.quantite ?? l.quantite_requise ?? '—'}
                      </span>
                      {l.etat && (
                        <StatusPill
                          tone={DISPO_TONE[l.etat] ?? 'neutral'}
                          label={DISPO_LABEL[l.etat] ?? l.etat}
                        />
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* WIR247/XMFG6 — lignes de composant PERSONNALISABLES : éditables
              tant que l'ordre est PLANIFIÉ, verrouillées dès qu'il démarre
              (l'édition disparaît, elle n'échoue pas). */}
          {lignesEditables && (
            <section data-testid="atelier-lignes-editables">
              <h3 className="mb-1.5 text-sm font-semibold">Lignes de composant</h3>
              <ul className="flex flex-col gap-1.5 text-sm">
                {lignes.map((l) => (
                  <li key={l.id} className="flex items-center gap-2">
                    <span className="flex-1 truncate">
                      {l.produit_nom ?? l.designation ?? '—'}
                    </span>
                    <Input
                      className="w-24"
                      type="number"
                      step="any"
                      defaultValue={l.quantite ?? ''}
                      disabled={busy}
                      aria-label={`Quantité pour ${l.produit_nom ?? l.designation ?? l.id}`}
                      onBlur={(e) => {
                        if (String(e.target.value) !== String(l.quantite)) {
                          modifierLigne(l, e.target.value)
                        }
                      }}
                    />
                    <Button type="button" size="sm" variant="outline"
                            disabled={busy} onClick={() => supprimerLigne(l)}>
                      Retirer
                    </Button>
                  </li>
                ))}
              </ul>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <Input
                  className="min-w-[12rem] flex-1"
                  placeholder="Composant à ajouter"
                  value={nouvelleLigne.designation}
                  onChange={(e) => setNouvelleLigne(
                    (p) => ({ ...p, designation: e.target.value }))}
                  aria-label="Composant à ajouter"
                />
                <Input
                  className="w-24"
                  type="number"
                  step="any"
                  placeholder="Qté"
                  value={nouvelleLigne.quantite}
                  onChange={(e) => setNouvelleLigne(
                    (p) => ({ ...p, quantite: e.target.value }))}
                  aria-label="Quantité de la ligne à ajouter"
                />
                <Button type="button" size="sm" variant="outline"
                        disabled={busy || !nouvelleLigne.designation.trim()}
                        onClick={ajouterLigne}>
                  Ajouter la ligne
                </Button>
              </div>
            </section>
          )}

          {/* WIR247/XMFG14 — gamme d'exécution : étapes cochables + durée
              réelle. Le serveur instancie la gamme depuis le kit ; liste vide
              = kit sans gamme, la section ne s'affiche pas. */}
          {etapes.length > 0 && (
            <section data-testid="atelier-gamme">
              <h3 className="mb-1.5 text-sm font-semibold">Gamme d’exécution</h3>
              <ul className="flex flex-col gap-1.5 text-sm">
                {etapes.map((e) => (
                  <li key={e.etape_modele ?? e.id} className="flex flex-wrap items-center gap-2">
                    <Checkbox
                      checked={Boolean(e.fait)}
                      disabled={busy || !canWrite}
                      onCheckedChange={(v) => cocherEtape(e, Boolean(v), e.duree_reelle_min)}
                      aria-label={`Étape faite : ${e.libelle ?? e.etape_modele}`}
                    />
                    <span className="flex-1 truncate">{e.libelle ?? '—'}</span>
                    {e.duree_attendue_min != null && (
                      <span className="text-xs text-muted-foreground">
                        prévu {e.duree_attendue_min} min
                      </span>
                    )}
                    <Input
                      className="w-24"
                      type="number"
                      step="any"
                      defaultValue={e.duree_reelle_min ?? ''}
                      disabled={busy || !canWrite}
                      placeholder="Réel (min)"
                      aria-label={`Durée réelle de ${e.libelle ?? e.etape_modele}`}
                      onBlur={(ev) => {
                        if (String(ev.target.value) !== String(e.duree_reelle_min ?? '')) {
                          cocherEtape(e, Boolean(e.fait), ev.target.value)
                        }
                      }}
                    />
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* WIR247/XMFG5 — nomenclature indentée du kit, à la demande.
              AUCUN coût ni marge n'est affiché (atelier = quantités). */}
          {ordre.kit && (
            <section>
              <Button type="button" size="sm" variant="outline"
                      disabled={structureBusy} onClick={ouvrirNomenclature}>
                {structureBusy ? <Spinner /> : <FileText />} Nomenclature
              </Button>
              {structure && (
                <ul className="mt-2 flex flex-col gap-1 text-sm"
                    data-testid="atelier-nomenclature">
                  {(structure.composants ?? []).map((c, i) => (
                    <li key={c.produit_id ?? c.composant_kit_id ?? i}
                        style={{ paddingLeft: `${(c.niveau ?? 0) * 12}px` }}
                        className="flex items-center justify-between gap-2">
                      <span className="truncate">{c.designation ?? c.sku ?? '—'}</span>
                      <span className="tabular-nums text-muted-foreground">
                        ×{c.quantite ?? '—'}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {/* XMFG13 — gate qualité : checklist QC. */}
          {controles.length > 0 && (
            <section>
              <h3 className="mb-1.5 text-sm font-semibold">Contrôle qualité</h3>
              <ul className="flex flex-col gap-1.5 text-sm">
                {controles.map((c) => (
                  <li key={c.id ?? c.item_modele} className="flex items-center justify-between gap-2">
                    <span>{c.item_libelle}</span>
                    {ordre.statut === 'en_cours' && canWrite ? (
                      <span className="flex gap-1">
                        <Button
                          type="button" size="sm"
                          variant={c.resultat === 'conforme' ? 'default' : 'outline'}
                          onClick={() => enregistrerQc(c.item_modele, 'conforme')}
                        >
                          Conforme
                        </Button>
                        <Button
                          type="button" size="sm"
                          variant={c.resultat === 'echec' ? 'destructive' : 'outline'}
                          onClick={() => enregistrerQc(c.item_modele, 'echec')}
                        >
                          Échec
                        </Button>
                      </span>
                    ) : (
                      <StatusPill
                        tone={c.resultat === 'conforme' ? 'success'
                          : c.resultat === 'echec' ? 'danger' : 'neutral'}
                        label={c.resultat === 'conforme' ? 'Conforme'
                          : c.resultat === 'echec' ? 'Échec' : 'En attente'}
                      />
                    )}
                  </li>
                ))}
              </ul>
              {qcBloque && (
                <p className="mt-1 text-xs text-muted-foreground">
                  Checklist incomplète : la clôture sera bloquée sans forçage.
                </p>
              )}
            </section>
          )}

          {/* XMFG4 — chatter de l'ordre. */}
          <section>
            <h3 className="mb-1.5 text-sm font-semibold">Historique</h3>
            <ul className="flex flex-col gap-1 text-xs text-muted-foreground">
              {historique.length === 0 && <li>Aucune activité.</li>}
              {historique.map((a) => (
                <li key={a.id}>
                  <span className="font-medium text-foreground">{a.user_nom ?? 'Système'}</span>
                  {' — '}
                  {a.kind === 'note' ? a.body
                    : `${a.field_label ?? a.field ?? ''} : ${a.old_value ?? '—'} → ${a.new_value ?? '—'}`}
                  {a.created_at ? ` (${formatDate(a.created_at)})` : ''}
                </li>
              ))}
            </ul>
            {canWrite && (
              <div className="mt-2 flex gap-2">
                <Input
                  placeholder="Ajouter une note…"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  aria-label="Note de l'ordre"
                />
                <Button type="button" size="sm" variant="outline"
                        onClick={enregistrerNote} disabled={busy || !note.trim()}>
                  Noter
                </Button>
              </div>
            )}
          </section>
        </div>

        <DialogFooter className="flex-wrap gap-2">
          <a href={installationsApi.bonAssemblageUrl(ordre.id)}
             target="_blank" rel="noreferrer">
            <Button type="button" variant="outline" size="sm">
              <Printer /> Bon PDF
            </Button>
          </a>
          {canWrite && ordre.statut === 'planifie' && (
            <>
              <Button type="button" size="sm" onClick={demarrer} disabled={busy}>
                <Play /> Démarrer
              </Button>
              <Button type="button" size="sm" variant="destructive"
                      onClick={() => setAnnulerOpen(true)} disabled={busy}>
                <XCircle /> Annuler
              </Button>
            </>
          )}
          {canWrite && ordre.statut === 'en_cours' && (
            <Button type="button" size="sm"
                    onClick={() => setTerminerOpen(true)} disabled={busy}>
              <CheckCircle2 /> Clôturer
            </Button>
          )}
          {/* WIR248/XMFG11 — rebut de production (motif obligatoire). */}
          {canWrite && produitsRebutables.length > 0
            && ordre.statut !== 'annule' && (
            <Button type="button" size="sm" variant="outline"
                    onClick={() => setRebutOpen(true)} disabled={busy}>
              <XCircle /> Déclarer un rebut
            </Button>
          )}
          <Button type="button" variant="ghost" size="sm" onClick={onClose}>
            Fermer
          </Button>
        </DialogFooter>

        {terminerOpen && (
          <TerminerAssemblageDialog
            ordre={ordre}
            qcBloque={qcBloque}
            onClose={() => setTerminerOpen(false)}
            onDone={(data) => { setTerminerOpen(false); onChanged(data) }}
          />
        )}
        {annulerOpen && (
          <AnnulerAssemblageDialog
            ordre={ordre}
            onClose={() => setAnnulerOpen(false)}
            onDone={(data) => { setAnnulerOpen(false); onChanged(data) }}
          />
        )}
        {rebutOpen && (
          <DeclarerRebutDialog
            ordre={ordre}
            produits={produitsRebutables}
            onClose={() => setRebutOpen(false)}
            onDeclared={() => load()}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

// XMFG1 — clôture + backflush (quantité produite + forçage QC optionnel).
function TerminerAssemblageDialog({ ordre, qcBloque, onClose, onDone }) {
  const [qte, setQte] = useState(String(ordre.quantite ?? '1'))
  const [forcer, setForcer] = useState(false)
  const [motif, setMotif] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const submit = () => {
    setBusy(true)
    setError(null)
    const payload = { quantite_produite: qte }
    if (qcBloque && forcer) { payload.forcer = true; payload.motif_forcage = motif }
    installationsApi.terminerAssemblage(ordre.id, payload)
      .then((r) => { toast.success('Ordre clôturé, stock mouvementé.'); onDone(r.data) })
      .catch(() => setError('Clôture impossible. Vérifiez la checklist qualité.'))
      .finally(() => setBusy(false))
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Clôturer l'ordre</DialogTitle>
          <DialogDescription>
            Les composants seront consommés et le composite produit (backflush).
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="term-qte">Quantité produite</Label>
            <Input id="term-qte" type="number" min="1" step="any"
                   value={qte} onChange={(e) => setQte(e.target.value)} />
          </div>
          {qcBloque && (
            <div className="flex flex-col gap-1.5 rounded-lg border border-warning/40 p-2">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={forcer}
                       onChange={(e) => setForcer(e.target.checked)} />
                Forcer malgré une checklist qualité incomplète
              </label>
              {forcer && (
                <Textarea rows={2} placeholder="Motif de forçage (requis)…"
                          value={motif} onChange={(e) => setMotif(e.target.value)} />
              )}
            </div>
          )}
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
            Annuler
          </Button>
          <Button type="button" onClick={submit}
                  disabled={busy || (qcBloque && forcer && !motif.trim())}>
            {busy ? <Spinner /> : <CheckCircle2 />} Clôturer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// XMFG4 — annulation motivée.
function AnnulerAssemblageDialog({ ordre, onClose, onDone }) {
  const [motif, setMotif] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const submit = () => {
    if (!motif.trim()) { setError("Le motif d'annulation est requis."); return }
    setBusy(true)
    setError(null)
    installationsApi.annulerAssemblage(ordre.id, motif.trim())
      .then((r) => { toast.success('Ordre annulé.'); onDone(r.data) })
      .catch(() => setError('Annulation impossible (stock déjà mouvementé ?).'))
      .finally(() => setBusy(false))
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Annuler l'ordre</DialogTitle>
          <DialogDescription>
            L'annulation libère les réservations non consommées.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-2">
          <Label htmlFor="ann-motif">Motif</Label>
          <Textarea id="ann-motif" rows={2} value={motif}
                    onChange={(e) => setMotif(e.target.value)} />
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
            Retour
          </Button>
          <Button type="button" variant="destructive" onClick={submit} disabled={busy}>
            {busy ? <Spinner /> : <XCircle />} Confirmer l'annulation
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── WIR248/XMFG11 — déclaration d'un rebut de production ────────────────────
// Le MOTIF est obligatoire : sans lui rien n'est envoyé (le serveur le refuse
// aussi — la garde est des DEUX côtés). Quantités uniquement, aucun coût.
function DeclarerRebutDialog({ ordre, produits, onClose, onDeclared }) {
  const [produit, setProduit] = useState(
    produits.length === 1 ? String(produits[0].id) : '')
  const [quantite, setQuantite] = useState('')
  const [motif, setMotif] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const complet = Boolean(produit) && quantite !== '' && Boolean(motif)

  const submit = () => {
    if (!complet) {
      setError('Produit, quantité et motif sont obligatoires.')
      return
    }
    setBusy(true)
    setError(null)
    installationsApi.declarerRebutAssemblage(ordre.id, {
      produit: Number(produit), quantite, motif, note,
    })
      .then((r) => {
        toast.success('Rebut déclaré — stock mouvementé.')
        onDeclared?.(r.data)
        onClose()
      })
      .catch((err) => setError(
        err?.response?.data?.detail
        ?? err?.response?.data?.quantite
        ?? err?.response?.data?.produit
        ?? 'Rebut non enregistré.'))
      .finally(() => setBusy(false))
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Déclarer un rebut</DialogTitle>
          <DialogDescription>
            Sortie de stock typée REBUT rattachée à {ordre.reference}. Le motif
            est obligatoire — un rebut sans raison n’est pas traçable.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="reb-produit">Produit</Label>
            <select id="reb-produit" className="form-control" value={produit}
                    onChange={(e) => setProduit(e.target.value)}>
              <option value="">— Choisir un produit —</option>
              {produits.map((p) => (
                <option key={p.id} value={p.id}>{p.nom}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="reb-quantite">Quantité rebutée</Label>
            <Input id="reb-quantite" type="number" step="any" value={quantite}
                   onChange={(e) => setQuantite(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="reb-motif">Motif</Label>
            <select id="reb-motif" className="form-control" value={motif}
                    onChange={(e) => setMotif(e.target.value)}>
              <option value="">— Choisir un motif —</option>
              {MOTIFS_REBUT.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="reb-note">Note (facultatif)</Label>
            <Textarea id="reb-note" rows={2} value={note}
                      onChange={(e) => setNote(e.target.value)} />
          </div>
          {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
            Annuler
          </Button>
          <Button type="button" variant="destructive" onClick={submit}
                  disabled={busy || !complet}>
            {busy ? <Spinner /> : <XCircle />} Déclarer le rebut
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── WIR248/XMFG11 — mini-rapport rebuts agrégé, filtrable par période ───────
function RapportRebutsPanel() {
  const [debut, setDebut] = useState('')
  const [fin, setFin] = useState('')
  const [lignes, setLignes] = useState([])
  const [busy, setBusy] = useState(false)
  const [erreur, setErreur] = useState(null)

  const charger = (dateDebut, dateFin) => {
    setBusy(true)
    setErreur(null)
    const params = {}
    if (dateDebut) params.date_debut = dateDebut
    if (dateFin) params.date_fin = dateFin
    installationsApi.getRapportRebuts(params)
      .then((r) => setLignes(Array.isArray(r.data) ? r.data : []))
      .catch(() => setErreur('Rapport indisponible.'))
      .finally(() => setBusy(false))
  }

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { charger('', '') }, [])

  return (
    <div className="flex flex-col gap-3" data-testid="atelier-rapport-rebuts">
      <div className="flex flex-wrap items-end gap-2">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="reb-debut">Du</Label>
          <Input id="reb-debut" type="date" value={debut}
                 onChange={(e) => setDebut(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="reb-fin">Au</Label>
          <Input id="reb-fin" type="date" value={fin}
                 onChange={(e) => setFin(e.target.value)} />
        </div>
        <Button type="button" size="sm" variant="outline" disabled={busy}
                onClick={() => charger(debut, fin)}>
          {busy ? <Spinner /> : <RefreshCw />} Filtrer
        </Button>
      </div>

      {erreur && <p className="text-sm text-destructive" role="alert">{erreur}</p>}

      {!erreur && lignes.length === 0 ? (
        <EmptyState
          title="Aucun rebut sur la période"
          description="Les rebuts déclarés depuis un ordre apparaissent ici."
          icon={FileText}
          className="my-4"
        />
      ) : (
        <ul className="flex flex-col gap-1.5 text-sm">
          {lignes.map((l) => (
            <li key={l.produit_id} className="flex flex-wrap items-center gap-2">
              <span className="flex-1 truncate">{l.produit_nom ?? '—'}</span>
              <span className="tabular-nums font-medium">{l.quantite_totale}</span>
              <span className="text-xs text-muted-foreground">
                {Object.entries(l.motifs ?? {})
                  .map(([m, q]) => `${MOTIF_LABEL[m] ?? m} : ${q}`)
                  .join(' · ')}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ── Détail d'un ordre de démontage ──────────────────────────────────────────
function DemontageDetail({ ordre, canWrite, onClose, onChanged }) {
  const [busy, setBusy] = useState(false)
  // WIR247/XMFG12 — la quantité RÉCUPÉRÉE se saisit ligne à ligne AVANT la
  // clôture (c'est elle qui est restockée) : l'écran l'affichait en lecture
  // seule et `updateLigneDemontage` n'avait aucun appelant.
  const [lignes, setLignes] = useState(ordre.lignes ?? [])
  const [prevOrdre, setPrevOrdre] = useState(ordre)
  if (prevOrdre !== ordre) {
    setPrevOrdre(ordre)
    setLignes(ordre.lignes ?? [])
  }
  const lignesEditables = canWrite && ordre.statut === 'planifie'

  const modifierRecuperee = (ligne, valeur) => {
    setBusy(true)
    installationsApi.updateLigneDemontage(ligne.id, { quantite_recuperee: valeur })
      .then((r) => setLignes((prev) => prev.map(
        (l) => (l.id === ligne.id ? r.data : l))))
      .catch(() => toast.error('Quantité non enregistrée.'))
      .finally(() => setBusy(false))
  }

  const terminer = () => {
    setBusy(true)
    installationsApi.terminerDemontage(ordre.id)
      .then((r) => { toast.success('Démontage clôturé, stock mouvementé.'); onChanged(r.data) })
      .catch(() => toast.error('Clôture impossible.'))
      .finally(() => setBusy(false))
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {ordre.reference} {statutPill(ordre.statut)}
          </DialogTitle>
          <DialogDescription>
            {ordre.kit_nom} · {ordre.quantite} unité(s) à démonter
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-2">
          <h3 className="text-sm font-semibold">Composants récupérés</h3>
          {lignes.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucune ligne.</p>
          ) : (
            <ul className="flex flex-col gap-1.5 text-sm">
              {lignes.map((l) => (
                <li key={l.id} className="flex items-center justify-between gap-2">
                  <span className="flex-1 truncate">{l.produit_nom ?? l.designation ?? '—'}</span>
                  <span className="text-xs text-muted-foreground">
                    attendu {l.quantite_attendue ?? '—'}
                  </span>
                  {lignesEditables ? (
                    <Input
                      className="w-24"
                      type="number"
                      step="any"
                      defaultValue={l.quantite_recuperee ?? ''}
                      disabled={busy}
                      aria-label={`Quantité récupérée pour ${l.produit_nom ?? l.designation ?? l.id}`}
                      onBlur={(e) => {
                        if (String(e.target.value) !== String(l.quantite_recuperee ?? '')) {
                          modifierRecuperee(l, e.target.value)
                        }
                      }}
                    />
                  ) : (
                    <span className="tabular-nums text-muted-foreground">
                      {l.quantite_recuperee ?? l.quantite_attendue ?? '—'} récupéré(s)
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>

        <DialogFooter className="gap-2">
          {canWrite && ordre.statut === 'planifie' && (
            <Button type="button" size="sm" onClick={terminer} disabled={busy}>
              {busy ? <Spinner /> : <CheckCircle2 />} Clôturer le démontage
            </Button>
          )}
          <Button type="button" variant="ghost" size="sm" onClick={onClose}>
            Fermer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── Page ────────────────────────────────────────────────────────────────────
export default function AteliersPage() {
  const canWrite = useIsAdminOrResponsable()

  const [mode, setMode] = useState('assemblage')
  const [assemblages, setAssemblages] = useState([])
  const [demontages, setDemontages] = useState([])
  const [kits, setKits] = useState([])
  const [loading, setLoading] = useState(true)
  // VX132 — rien tant que l'attente reste imperceptible (< 300 ms), puis
  // spinner discret OU squelette, jamais les deux ensemble.
  const { showSpinner, showSkeleton } = useDelayedLoading(loading)
  const [error, setError] = useState(null)
  const [statutFilter, setStatutFilter] = useState('')
  const [selected, setSelected] = useState(null)
  const [creating, setCreating] = useState(false)

  const load = () => {
    Promise.all([
      installationsApi.getOrdresAssemblage(),
      installationsApi.getOrdresDemontage(),
      installationsApi.getKitsAssemblage({ active: 1 }),
    ])
      .then(([a, d, k]) => {
        const arr = (r) => (Array.isArray(r) ? r : r?.results ?? [])
        setAssemblages(arr(a.data))
        setDemontages(arr(d.data))
        setKits(arr(k.data))
        setLoading(false)
      })
      .catch(() => {
        setError("Impossible de charger l'atelier. Réessayez.")
        setLoading(false)
      })
  }
  const reload = () => { setLoading(true); setError(null); load() }
  useEffect(() => { load() }, [])

  const rows = useMemo(() => {
    const src = mode === 'assemblage' ? assemblages : demontages
    if (!statutFilter) return src
    return src.filter((o) => o.statut === statutFilter)
  }, [mode, assemblages, demontages, statutFilter])

  const columns = useMemo(() => [
    {
      id: 'reference', header: 'Référence', width: 160,
      accessor: (r) => r.reference ?? '',
      cell: (v, r) => <span className="font-semibold">{r.reference ?? '—'}</span>,
    },
    { id: 'kit_nom', header: 'Kit', width: 200, accessor: (r) => r.kit_nom ?? '' },
    {
      id: 'quantite', header: 'Qté', width: 80, align: 'right',
      accessor: (r) => Number(r.quantite) || 0,
    },
    {
      id: 'statut', header: 'Statut', width: 130, searchable: false,
      accessor: (r) => r.statut ?? '',
      cell: (v, r) => statutPill(r.statut),
    },
    {
      id: 'date_creation', header: 'Créé le', width: 120, align: 'right',
      accessor: (r) => r.date_creation ?? '',
      cell: (v) => (v ? formatDate(v) : '—'),
    },
  ], [])

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title flex items-center gap-2">
          <Wrench size={20} /> Atelier
          <Badge tone="primary">{rows.length}</Badge>
        </h1>
        <div className="page-subtitle">
          Ordres d'assemblage et de démontage (kitting magasin)
        </div>
        <div className="page-header-actions flex flex-wrap items-center gap-2">
          <Button type="button" size="sm" variant="outline" onClick={reload}>
            <RefreshCw /> Rafraîchir
          </Button>
          {canWrite && (
            <Button type="button" size="sm" onClick={() => setCreating(true)}>
              <Plus /> {mode === 'assemblage' ? 'Ordre d\'assemblage' : 'Ordre de démontage'}
            </Button>
          )}
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Segmented
          size="sm"
          value={mode}
          onChange={(v) => { setMode(v); setStatutFilter('') }}
          aria-label="Type d'ordre"
          options={[
            { value: 'assemblage', label: 'Assemblage' },
            { value: 'demontage', label: 'Démontage' },
            // WIR248/XMFG11 — mini-rapport des rebuts déclarés.
            { value: 'rebuts', label: 'Rebuts' },
          ]}
        />
        {mode !== 'rebuts' && (
        <Select value={statutFilter || '__all__'}
                onValueChange={(v) => setStatutFilter(v === '__all__' ? '' : v)}>
          <SelectTrigger className="w-auto min-w-[10rem]" aria-label="Filtrer par statut">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">Tous les statuts</SelectItem>
            {Object.entries(STATUT_LABEL)
              .filter(([k]) => mode === 'assemblage' || k === 'planifie' || k === 'termine')
              .map(([k, label]) => (
                <SelectItem key={k} value={k}>{label}</SelectItem>
              ))}
          </SelectContent>
        </Select>
        )}
      </div>

      {mode === 'rebuts' ? (
        <RapportRebutsPanel />
      ) : error ? (
        <EmptyState
          title="Erreur de chargement"
          description={error}
          action={<Button size="sm" onClick={reload}>Réessayer</Button>}
          className="my-6 border-destructive/40"
        />
      ) : loading ? (
        <div className="flex flex-col gap-2">
          {showSpinner && (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <Spinner /> Chargement…
            </p>
          )}
          {showSkeleton && Array.from({ length: 5 }).map((unused, i) => (
            <Skeleton key={i} className="h-10 w-full rounded-lg" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          title={mode === 'assemblage' ? "Aucun ordre d'assemblage" : 'Aucun ordre de démontage'}
          description={canWrite
            ? 'Créez un ordre pour lancer la production atelier.'
            : 'Aucun ordre ne correspond aux filtres.'}
          icon={FileText}
          className="my-6"
        />
      ) : (
        <DataTable
          data={rows}
          columns={columns}
          getRowId={(row) => row.id}
          onRowClick={(row) => setSelected({ mode, ordre: row })}
          pageSize={25}
          aria-label={mode === 'assemblage' ? "Ordres d'assemblage" : 'Ordres de démontage'}
        />
      )}

      {creating && mode === 'assemblage' && (
        <CreateAssemblageDialog
          kits={kits}
          onClose={() => setCreating(false)}
          onCreated={(data) => { setCreating(false); reload(); setSelected({ mode: 'assemblage', ordre: data }) }}
        />
      )}
      {creating && mode === 'demontage' && (
        <CreateDemontageDialog
          kits={kits}
          onClose={() => setCreating(false)}
          onCreated={(data) => { setCreating(false); reload(); setSelected({ mode: 'demontage', ordre: data }) }}
        />
      )}

      {selected?.mode === 'assemblage' && (
        <AssemblageDetail
          ordre={selected.ordre}
          canWrite={canWrite}
          onClose={() => setSelected(null)}
          onChanged={(data) => { reload(); setSelected(data ? { mode: 'assemblage', ordre: data } : null) }}
        />
      )}
      {selected?.mode === 'demontage' && (
        <DemontageDetail
          ordre={selected.ordre}
          canWrite={canWrite}
          onClose={() => setSelected(null)}
          onChanged={(data) => { reload(); setSelected(data ? { mode: 'demontage', ordre: data } : null) }}
        />
      )}
    </div>
  )
}
