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
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  DataTable, StatusPill,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DialogFooter, Label, toast,
  // WIR247 — cases à cocher de la gamme d'exécution (XMFG14).
  Checkbox,
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
function AssemblageDetail({ ordre, kits = [], canWrite, onClose, onChanged }) {
  const [dispo, setDispo] = useState([])
  const [controles, setControles] = useState([])
  const [historique, setHistorique] = useState([])
  const [busy, setBusy] = useState(false)
  const [terminerOpen, setTerminerOpen] = useState(false)
  const [annulerOpen, setAnnulerOpen] = useState(false)
  // WIR248/XMFG11 — declaration d'un rebut de production sur cet ordre.
  const [rebutOpen, setRebutOpen] = useState(false)
  const [note, setNote] = useState('')
  // ── WIR247 — trois familles d'exports d'atelier n'avaient AUCUN appelant :
  //    la gamme d'exécution (XMFG14), les lignes de composant éditables
  //    (XMFG6) et la nomenclature du kit (XMFG5). Elles sont montées ici.
  const [etapes, setEtapes] = useState([])
  const [dureeSaisie, setDureeSaisie] = useState({}) // etape_modele → minutes
  const [lignes, setLignes] = useState([])
  const [nouvelleLigne, setNouvelleLigne] = useState({ designation: '', quantite: '' })
  const [nomenclatureOuverte, setNomenclatureOuverte] = useState(false)
  // WIR247/XMFG5 — la nomenclature de l'ordre est celle de SON kit
  // (`installations.Kit.composants`, déjà imbriqué en lecture par
  // KitSerializer et déjà chargé par la page). On ne passe PAS par
  // `getKitStructure` : cet endpoint adresse `stock.KitProduit`, un modèle
  // DISTINCT de `installations.Kit` — lui donner `ordre.kit` inventerait une
  // correspondance d'identifiants qui n'existe pas.
  const kitDeLOrdre = kits.find((k) => String(k.id) === String(ordre.kit)) ?? null
  const nomenclature = kitDeLOrdre?.composants ?? []

  // Les lignes de composant ne sont éditables que tant que l'ordre est
  // PLANIFIÉ (la vue serveur applique la même règle) : une fois démarré, la
  // composition est figée.
  const editableLignes = canWrite && ordre.statut === 'planifie'

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

  const cocherEtape = (etape, fait) => {
    setBusy(true)
    const duree = dureeSaisie[etape.etape_modele]
    installationsApi.cocherEtapeAssemblage(ordre.id, etape.etape_modele, {
      fait,
      // Une durée non saisie part en vide : le serveur la normalise en null,
      // on n'invente jamais un 0.
      duree_reelle_min: duree ?? '',
    })
      .then(() => load())
      .catch(() => toast.error('Étape non enregistrée.'))
      .finally(() => setBusy(false))
  }

  const ajouterLigne = () => {
    if (!nouvelleLigne.designation.trim()) return
    setBusy(true)
    installationsApi.createLigneAssemblage({
      ordre: ordre.id,
      designation: nouvelleLigne.designation.trim(),
      quantite: nouvelleLigne.quantite || '1',
    })
      .then(() => { setNouvelleLigne({ designation: '', quantite: '' }); load() })
      .catch(() => toast.error('Ligne non ajoutée.'))
      .finally(() => setBusy(false))
  }

  const modifierLigne = (ligne, quantite) => {
    installationsApi.updateLigneAssemblage(ligne.id, { quantite })
      .then(() => load())
      .catch(() => toast.error('Ligne non modifiée.'))
  }

  const supprimerLigne = (ligne) => {
    installationsApi.deleteLigneAssemblage(ligne.id)
      .then(() => load())
      .catch(() => toast.error('Ligne non supprimée.'))
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

  const dispoLignes = dispo.length ? dispo : (ordre.lignes ?? [])

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

          {/* WIR247/XMFG6 — lignes de composant PERSONNALISABLES, éditables
              tant que l'ordre est planifié (même règle que la vue serveur). */}
          {editableLignes && (
            <section>
              <h3 className="mb-1.5 text-sm font-semibold">Lignes de composant</h3>
              {lignes.length === 0 ? (
                <p className="text-sm text-muted-foreground">Aucune ligne personnalisée.</p>
              ) : (
                <ul className="flex flex-col gap-1 text-sm">
                  {lignes.map((l) => (
                    <li key={l.id} className="flex items-center justify-between gap-2">
                      <span>{l.produit_nom ?? l.designation ?? '—'}</span>
                      <span className="flex items-center gap-2">
                        <Input
                          className="h-8 w-24" type="number" step="any"
                          defaultValue={l.quantite}
                          aria-label={`Quantité de ${l.designation || l.produit_nom || 'la ligne'}`}
                          onBlur={(e) => modifierLigne(l, e.target.value)}
                        />
                        <Button type="button" size="sm" variant="ghost"
                                onClick={() => supprimerLigne(l)}>
                          Retirer
                        </Button>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              <div className="mt-2 flex flex-wrap gap-2">
                <Input
                  placeholder="Désignation du composant"
                  aria-label="Désignation du composant"
                  value={nouvelleLigne.designation}
                  onChange={(e) => setNouvelleLigne(s => ({ ...s, designation: e.target.value }))}
                />
                <Input
                  className="w-24" type="number" step="any" placeholder="Qté"
                  aria-label="Quantité du composant"
                  value={nouvelleLigne.quantite}
                  onChange={(e) => setNouvelleLigne(s => ({ ...s, quantite: e.target.value }))}
                />
                <Button type="button" size="sm" variant="outline"
                        onClick={ajouterLigne} disabled={busy || !nouvelleLigne.designation.trim()}>
                  Ajouter la ligne
                </Button>
              </div>
            </section>
          )}

          {/* WIR247/XMFG14 — gamme d'exécution : étapes cochables + durée réelle. */}
          {etapes.length > 0 && (
            <section>
              <h3 className="mb-1.5 text-sm font-semibold">Gamme d'exécution</h3>
              <ul className="flex flex-col gap-1.5 text-sm">
                {etapes.map((e) => (
                  <li key={e.id ?? e.etape_modele} className="flex flex-wrap items-center justify-between gap-2">
                    <span className="flex items-center gap-2">
                      <Checkbox
                        checked={!!e.fait}
                        disabled={!canWrite || busy}
                        onCheckedChange={(v) => cocherEtape(e, !!v)}
                        aria-label={`Étape faite : ${e.libelle ?? ''}`}
                      />
                      <span>
                        {e.libelle ?? '—'}
                        {e.duree_attendue_min != null && (
                          <span className="text-xs text-muted-foreground">
                            {' '}({e.duree_attendue_min} min attendues)
                          </span>
                        )}
                      </span>
                    </span>
                    <span className="flex items-center gap-2">
                      {canWrite && (
                        <Input
                          className="h-8 w-24" type="number" step="any"
                          placeholder="min réelles"
                          aria-label={`Durée réelle de ${e.libelle ?? "l'étape"}`}
                          defaultValue={e.duree_reelle_min ?? ''}
                          onChange={(ev) => setDureeSaisie(s => (
                            { ...s, [e.etape_modele]: ev.target.value }))}
                        />
                      )}
                      {e.fait && e.fait_par_nom && (
                        <span className="text-xs text-muted-foreground">
                          par {e.fait_par_nom}
                        </span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* WIR247/XMFG5 — nomenclature indentée du kit (lecture seule). */}
          {ordre.kit && (
            <section>
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-sm font-semibold">Nomenclature</h3>
                <Button type="button" size="sm" variant="ghost"
                        aria-expanded={nomenclatureOuverte}
                        onClick={() => setNomenclatureOuverte(o => !o)}>
                  {nomenclatureOuverte ? 'Masquer' : 'Nomenclature'}
                </Button>
              </div>
              {nomenclatureOuverte && (
                nomenclature.length > 0 ? (
                  <ul className="mt-1 flex flex-col gap-1 text-sm">
                    {nomenclature.map((c, i) => (
                      <li key={c.id ?? i} className="flex items-center justify-between gap-2">
                        <span>{c.produit_nom ?? c.designation ?? '—'}</span>
                        <span className="tabular-nums text-muted-foreground">
                          ×{c.quantite ?? '—'}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-1 text-sm text-muted-foreground">
                    Nomenclature indisponible pour ce kit.
                  </p>
                )
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
          {/* WIR248 — un rebut se déclare tant que l'ordre n'est pas clos. */}
          {canWrite && (ordre.statut === 'planifie' || ordre.statut === 'en_cours') && (
            <Button type="button" size="sm" variant="outline"
                    onClick={() => setRebutOpen(true)} disabled={busy}>
              Déclarer un rebut
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
        {rebutOpen && (
          <DeclarerRebutDialog
            ordre={ordre}
            lignes={lignes.length ? lignes : dispoLignes}
            onClose={() => setRebutOpen(false)}
            onDone={() => { setRebutOpen(false); load() }}
          />
        )}
        {annulerOpen && (
          <AnnulerAssemblageDialog
            ordre={ordre}
            onClose={() => setAnnulerOpen(false)}
            onDone={(data) => { setAnnulerOpen(false); onChanged(data) }}
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

// WIR248/XMFG11 — motifs de rebut. source-choix: stock.MouvementStock.MotifRebut
const MOTIFS_REBUT = [
  { value: 'casse', label: 'Casse' },
  { value: 'defaut', label: 'Défaut' },
  { value: 'erreur', label: 'Erreur' },
  { value: 'obsolete', label: 'Obsolète' },
  { value: 'perime', label: 'Périmé' },
  { value: 'vol', label: 'Vol' },
]

// WIR248/XMFG11 — déclaration d'un rebut de production sur un ordre. Le motif
// est OBLIGATOIRE (le service serveur refuse un motif hors liste) : l'écran le
// refuse d'abord pour éviter un aller-retour inutile.
function DeclarerRebutDialog({ ordre, lignes, onClose, onDone }) {
  const [form, setForm] = useState({ produit: '', quantite: '1', motif: '', note: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  // Les produits proposés sont ceux de l'ordre : on ne rebute pas au hasard
  // dans tout le catalogue depuis un ordre d'assemblage.
  const produits = (lignes ?? []).filter((l) => l.produit)

  const submit = () => {
    if (!form.produit) { setError('Sélectionnez le composant rebuté.'); return }
    if (!form.motif) { setError('Le motif du rebut est obligatoire.'); return }
    setBusy(true)
    setError(null)
    installationsApi.declarerRebutAssemblage(ordre.id, {
      produit: form.produit,
      quantite: form.quantite,
      motif: form.motif,
      note: form.note || '',
    })
      .then(() => { toast.success('Rebut déclaré.'); onDone() })
      .catch((err) => setError(
        err?.response?.data?.detail
        ?? err?.response?.data?.quantite
        ?? 'Déclaration impossible.'))
      .finally(() => setBusy(false))
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Déclarer un rebut</DialogTitle>
          <DialogDescription>
            Une sortie de stock typée « rebut », rattachée à l'ordre
            {' '}{ordre.reference}. Le motif est obligatoire.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="reb-produit">Composant</Label>
            <Select value={form.produit} onValueChange={(v) => set('produit', v)}>
              <SelectTrigger id="reb-produit" aria-label="Composant rebuté">
                <SelectValue placeholder="Choisir un composant…" />
              </SelectTrigger>
              <SelectContent>
                {produits.map((l) => (
                  <SelectItem key={l.id} value={String(l.produit)}>
                    {l.produit_nom ?? l.designation ?? `Produit ${l.produit}`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="reb-qte">Quantité rebutée</Label>
            <Input id="reb-qte" type="number" min="1" step="any"
                   value={form.quantite}
                   onChange={(e) => set('quantite', e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="reb-motif" required>Motif</Label>
            <Select value={form.motif} onValueChange={(v) => set('motif', v)}>
              <SelectTrigger id="reb-motif" aria-label="Motif du rebut">
                <SelectValue placeholder="Choisir un motif…" />
              </SelectTrigger>
              <SelectContent>
                {MOTIFS_REBUT.map((m) => (
                  <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="reb-note">Note (facultatif)</Label>
            <Textarea id="reb-note" rows={2} value={form.note}
                      onChange={(e) => set('note', e.target.value)} />
          </div>
          {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
            Annuler
          </Button>
          <Button type="button" variant="destructive" onClick={submit} disabled={busy}>
            {busy ? <Spinner /> : <XCircle />} Déclarer le rebut
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// WIR248/XMFG11 — mini-rapport des rebuts agrégé par produit, filtrable par
// période. Aucun coût d'achat n'est affiché (quantités seulement).
function RebutsPanel() {
  const [periode, setPeriode] = useState({ date_debut: '', date_fin: '' })
  const [lignes, setLignes] = useState([])
  const [busy, setBusy] = useState(false)

  const charger = () => {
    setBusy(true)
    installationsApi.getRapportRebuts({
      date_debut: periode.date_debut || undefined,
      date_fin: periode.date_fin || undefined,
    })
      .then((r) => setLignes(Array.isArray(r.data) ? r.data : []))
      .catch(() => setLignes([]))
      .finally(() => setBusy(false))
  }
  useEffect(() => { charger() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <section className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold">Rebuts</h3>
      <div className="flex flex-wrap items-end gap-2">
        <div className="flex flex-col gap-1">
          <Label htmlFor="reb-debut">Du</Label>
          <Input id="reb-debut" type="date" className="h-9"
                 value={periode.date_debut}
                 onChange={(e) => setPeriode(p => ({ ...p, date_debut: e.target.value }))} />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="reb-fin">Au</Label>
          <Input id="reb-fin" type="date" className="h-9"
                 value={periode.date_fin}
                 onChange={(e) => setPeriode(p => ({ ...p, date_fin: e.target.value }))} />
        </div>
        <Button type="button" size="sm" variant="outline" onClick={charger} disabled={busy}>
          {busy ? <Spinner /> : <RefreshCw />} Actualiser
        </Button>
      </div>
      {lignes.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Aucun rebut déclaré sur cette période.
        </p>
      ) : (
        <ul className="flex flex-col gap-1 text-sm">
          {lignes.map((l) => (
            <li key={l.produit_id} className="flex items-center justify-between gap-2">
              <span>{l.produit_nom}</span>
              <span className="flex items-center gap-2">
                <span className="tabular-nums">{l.quantite_totale}</span>
                <span className="text-xs text-muted-foreground">
                  {Object.entries(l.motifs ?? {})
                    .map(([m, q]) => `${MOTIFS_REBUT.find(x => x.value === m)?.label ?? m} : ${q}`)
                    .join(' · ')}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
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

// ── Détail d'un ordre de démontage ──────────────────────────────────────────
function DemontageDetail({ ordre, canWrite, onClose, onChanged }) {
  const [busy, setBusy] = useState(false)
  // WIR247/XMFG12 — la quantité RÉCUPÉRÉE était affichée en lecture seule
  // alors que `updateLigneDemontage` existait sans appelant : le magasinier ne
  // pouvait pas corriger ce qu'il avait réellement récupéré avant la clôture
  // (c'est pourtant elle qui pilote le restockage).
  const [lignes, setLignes] = useState(ordre.lignes ?? [])
  // L'édition n'est ouverte QUE tant que le démontage est planifié : après
  // clôture, le stock est mouvementé et les quantités sont figées.
  const editable = canWrite && ordre.statut === 'planifie'

  const modifierRecuperee = (ligne, quantite_recuperee) => {
    installationsApi.updateLigneDemontage(ligne.id, { quantite_recuperee })
      .then((r) => setLignes(ls => ls.map(l => (l.id === ligne.id ? r.data : l))))
      .catch(() => toast.error('Quantité non enregistrée.'))
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
            <ul className="flex flex-col gap-1 text-sm">
              {lignes.map((l) => (
                <li key={l.id} className="flex items-center justify-between gap-2">
                  <span>
                    {l.produit_nom ?? l.designation ?? '—'}
                    <span className="text-xs text-muted-foreground">
                      {' '}(attendu : {l.quantite_attendue ?? '—'})
                    </span>
                  </span>
                  {editable ? (
                    <Input
                      className="h-8 w-28" type="number" step="any"
                      defaultValue={l.quantite_recuperee ?? ''}
                      aria-label={`Quantité récupérée de ${l.produit_nom || l.designation || 'la ligne'}`}
                      onBlur={(e) => modifierRecuperee(l, e.target.value)}
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
          ]}
        />
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
      </div>

      {error ? (
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

      {/* WIR248/XMFG11 — rapport des rebuts d'atelier, filtrable par période.
          Rattaché au mode assemblage (c'est là que les rebuts se déclarent). */}
      {mode === 'assemblage' && <RebutsPanel />}

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
          kits={kits}
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
