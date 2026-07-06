// Onglet « Leads » de la page Paramètres (responsable/installateur par défaut,
// parrainage, étiquettes & motifs CRM, canaux/sources). Restylé sur le système
// de design (@/ui) ; champs, libellés et comportement identiques.
import { Plus, Trash2, Archive, ArchiveRestore, Lock } from 'lucide-react'
import {
  Card, CardContent, Input, Switch, Label, Badge, IconButton, Button, Spinner,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { SectionTitle, Field } from './peComponents'
import EquipesCommercialesSection from './EquipesCommercialesSection'
import MessageTemplatesCrmSection from './MessageTemplatesCrmSection'

// Sentinel pour l'option « aucun » : Radix Select n'autorise pas la valeur ''.
const NONE = '__none__'

// L777 — petit indicateur de chargement / liste vide réutilisable.
function ListState({ loading, empty, children }) {
  if (loading) return (
    <div className="flex items-center gap-2 py-2 text-xs text-muted-foreground">
      <Spinner className="size-3.5 text-primary" /> Chargement…
    </div>
  )
  if (empty) return (
    <p className="py-2 text-xs text-muted-foreground">Aucun élément.</p>
  )
  return children
}

export default function LeadsSection({
  form, set, setForm, assignables,
  tags, newTag, setNewTag, addTag, renameTag, delTag, archiveTag, setTagColor,
  motifs, newMotif, setNewMotif, addMotif, renameMotif, delMotif, archiveMotif,
  canaux, newCanal, setNewCanal, addCanal, renameCanal, delCanal, archiveCanal,
  refLoading = {},
}) {
  // Met à jour un champ FK du formulaire ('' = aucun) depuis le Select.
  const setFk = (name) => (val) =>
    setForm(f => ({ ...f, [name]: val === NONE ? '' : val }))

  return (
    <>
      {/* Leads — responsable par défaut */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Leads" icon={<><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></>}/>
          <p className="mb-3.5 text-[11.5px] text-muted-foreground">
            Responsable assigné automatiquement aux nouveaux leads (site web et
            création manuelle) quand aucun responsable n'est choisi.
          </p>
          <Field label="Responsable par défaut des nouveaux leads" htmlFor="pe-resp-leads">
            <Select value={form.responsable_defaut_leads ? String(form.responsable_defaut_leads) : NONE}
                    onValueChange={setFk('responsable_defaut_leads')}>
              <SelectTrigger id="pe-resp-leads"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>— Aucun (laisser non assigné) —</SelectItem>
                {assignables.map(u => (
                  <SelectItem key={u.id} value={String(u.id)}>
                    {u.username}{u.poste ? ` — ${u.poste}` : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <p className="mb-1 mt-3.5 text-[12.5px] text-muted-foreground">
            Installateur (technicien) assigné automatiquement aux nouveaux
            chantiers quand aucun n'est choisi. Laisser vide = le créateur
            du chantier (comportement actuel).
          </p>
          <Field label="Installateur par défaut des nouveaux chantiers" htmlFor="pe-default-installer">
            <Select value={form.default_installer ? String(form.default_installer) : NONE}
                    onValueChange={setFk('default_installer')}>
              <SelectTrigger id="pe-default-installer"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>— Aucun (créateur du chantier) —</SelectItem>
                {assignables.map(u => (
                  <SelectItem key={u.id} value={String(u.id)}>
                    {u.username}{u.poste ? ` — ${u.poste}` : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <p className="mb-2 mt-3.5 text-[12.5px] text-muted-foreground">
            Programme de parrainage : récompense par défaut pré-remplie sur
            chaque nouveau parrainage (écran CRM → Parrainage).
          </p>
          <label className="mb-2 flex items-center gap-2 text-sm text-foreground">
            <Switch name="referral_enabled"
                    checked={!!form.referral_enabled}
                    onCheckedChange={v => setForm(f => ({ ...f, referral_enabled: v }))} />
            Activer le programme de parrainage
          </label>
          <Field label="Récompense de parrainage par défaut (DH)" htmlFor="pe-referral-reward">
            <Input id="pe-referral-reward" type="number" step="any"
                   name="referral_reward" value={form.referral_reward}
                   onChange={set} />
          </Field>
          {/* WR12/FG28 — délai SLA de première prise de contact (heures). */}
          <p className="mb-1 mt-3.5 text-[12.5px] text-muted-foreground">
            Délai maximum avant la première prise de contact sur un nouveau
            lead. Au-delà, le lead est signalé « non contacté » (badge kanban +
            filtre SLA). 0 = SLA désactivé.
          </p>
          <Field label="Délai SLA de premier contact (heures)" htmlFor="pe-lead-sla-hours">
            <Input id="pe-lead-sla-hours" type="number" min="0" step="1"
                   name="lead_sla_hours" value={form.lead_sla_hours}
                   onChange={set} />
          </Field>
          {/* XSAL11 — round-robin équilibré, OFF par défaut (comportement
              actuel inchangé). ON : rotation entre commerciaux actifs en
              sautant qui dépasse le plafond de leads ouverts ci-dessous. */}
          <p className="mb-1 mt-3.5 text-[12.5px] text-muted-foreground">
            Répartit automatiquement les leads entrants (site + création
            manuelle sans responsable) entre les commerciaux, en sautant ceux
            qui ont déjà trop de leads ouverts. Repli sur le responsable par
            défaut si tous sont au plafond.
          </p>
          <label className="mb-2 flex items-center gap-2 text-sm text-foreground">
            <Switch name="round_robin_leads_actif"
                    checked={!!form.round_robin_leads_actif}
                    onCheckedChange={v => setForm(f => ({ ...f, round_robin_leads_actif: v }))} />
            Activer l'affectation round-robin équilibrée
          </label>
          <Field label="Plafond de leads ouverts par commercial" htmlFor="pe-round-robin-plafond">
            <Input id="pe-round-robin-plafond" type="number" min="1" step="1"
                   name="round_robin_plafond_leads_ouverts"
                   value={form.round_robin_plafond_leads_ouverts}
                   onChange={set} />
          </Field>
        </CardContent>
      </Card>

      {/* CRM — Étiquettes & motifs */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="CRM — Étiquettes & motifs" icon={<><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></>}/>
          <p className="mb-3.5 text-[11.5px] text-muted-foreground">
            Étiquettes et motifs de perte proposés sur les leads. Le texte
            libre reste possible ; les leads existants ne changent pas.
          </p>
          <Label className="mb-1 block">Étiquettes</Label>
          <ListState loading={refLoading.tags} empty={tags.length === 0}>
            {tags.map(t => (
              <div key={t.id}
                   className={['mb-1.5 flex items-center gap-1.5',
                     t.archived ? 'opacity-50' : ''].join(' ')}>
                {/* L781 — couleur de l'étiquette (color-picker persistant). */}
                <input type="color" aria-label={`Couleur de l'étiquette ${t.nom}`}
                       value={t.couleur || '#6b7280'}
                       onChange={e => setTagColor(t, e.target.value)}
                       className="size-8 shrink-0 cursor-pointer rounded-md border border-input bg-card p-[3px]" />
                {/* ERR102 — re-monte le champ si le serveur normalise le nom. */}
                <Input key={t.nom} className="flex-1" defaultValue={t.nom}
                       onBlur={e => renameTag(t, e.target.value)} />
                {/* L780 — compteur d'usage (suppression bloquée si > 0). */}
                {t.en_usage > 0 && <Badge tone="neutral">{t.en_usage} lead(s)</Badge>}
                {/* L778 — archiver/réactiver. */}
                <IconButton size="md" variant="outline"
                            label={t.archived ? "Réactiver l'étiquette" : "Archiver l'étiquette"}
                            onClick={() => archiveTag(t)}>
                  {t.archived
                    ? <ArchiveRestore className="size-4" aria-hidden="true" />
                    : <Archive className="size-4" aria-hidden="true" />}
                </IconButton>
                <IconButton size="md" variant="outline" label="Supprimer l'étiquette"
                            className="text-destructive hover:text-destructive disabled:text-muted-foreground"
                            disabled={t.en_usage > 0}
                            title={t.en_usage > 0
                              ? `${t.en_usage} lead(s) utilisent cette étiquette — archivez-la`
                              : 'Supprimer'}
                            onClick={() => delTag(t)}>
                  <Trash2 className="size-4" aria-hidden="true" />
                </IconButton>
              </div>
            ))}
          </ListState>
          <div className="mb-3.5 mt-1.5 flex gap-1.5">
            <Input className="flex-1" placeholder="Nouvelle étiquette" value={newTag}
                   onChange={e => setNewTag(e.target.value)}
                   onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addTag() } }} />
            <Button type="button" onClick={addTag}><Plus className="size-4" aria-hidden="true" /></Button>
          </div>
          <Label className="mb-1 block">Motifs de perte</Label>
          <ListState loading={refLoading.motifs} empty={motifs.length === 0}>
            {motifs.map(m => (
              <div key={m.id}
                   className={['mb-1.5 flex items-center gap-1.5',
                     m.archived ? 'opacity-50' : ''].join(' ')}>
                {/* ERR102 — re-monte le champ si le serveur normalise le nom. */}
                <Input key={m.nom} className="flex-1" defaultValue={m.nom}
                       onBlur={e => renameMotif(m, e.target.value)} />
                {/* L779 — compteur d'usage (suppression bloquée si > 0). */}
                {m.en_usage > 0 && <Badge tone="neutral">{m.en_usage} lead(s)</Badge>}
                {/* L778 — archiver/réactiver. */}
                <IconButton size="md" variant="outline"
                            label={m.archived ? 'Réactiver le motif' : 'Archiver le motif'}
                            onClick={() => archiveMotif(m)}>
                  {m.archived
                    ? <ArchiveRestore className="size-4" aria-hidden="true" />
                    : <Archive className="size-4" aria-hidden="true" />}
                </IconButton>
                <IconButton size="md" variant="outline" label="Supprimer le motif"
                            className="text-destructive hover:text-destructive disabled:text-muted-foreground"
                            disabled={m.en_usage > 0}
                            title={m.en_usage > 0
                              ? `${m.en_usage} lead(s) utilisent ce motif — archivez-le`
                              : 'Supprimer'}
                            onClick={() => delMotif(m)}>
                  <Trash2 className="size-4" aria-hidden="true" />
                </IconButton>
              </div>
            ))}
          </ListState>
          <div className="mt-1.5 flex gap-1.5">
            <Input className="flex-1" placeholder="Nouveau motif" value={newMotif}
                   onChange={e => setNewMotif(e.target.value)}
                   onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addMotif() } }} />
            <Button type="button" onClick={addMotif}><Plus className="size-4" aria-hidden="true" /></Button>
          </div>
        </CardContent>
      </Card>

      {/* CRM — Canaux / sources */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="CRM — Canaux / sources" icon={<><path d="M4 11a9 9 0 0 1 9 9"/><path d="M4 4a16 16 0 0 1 16 16"/><circle cx="5" cy="19" r="1"/></>}/>
          <p className="mb-3.5 text-[11.5px] text-muted-foreground">
            Sources d'où viennent les leads. « Site web » est protégé (utilisé
            par le formulaire du site) et ne peut être ni renommé ni supprimé.
            Un canal déjà utilisé par des leads ne peut pas être supprimé.
          </p>
          <ListState loading={refLoading.canaux} empty={canaux.length === 0}>
            {canaux.map(c => (
              <div key={c.id}
                   className={['mb-1.5 flex items-center gap-1.5',
                     c.archived ? 'opacity-50' : ''].join(' ')}>
                {/* L783 — un canal protégé est en lecture seule avec indice. */}
                <div className="relative flex-1">
                  {/* ERR102 — re-monte le champ si le serveur normalise le libellé. */}
                  <Input key={c.libelle} className="w-full" defaultValue={c.libelle}
                         readOnly={c.protege}
                         title={c.protege ? 'protégé (webhook site)' : undefined}
                         onBlur={c.protege ? undefined : e => renameCanal(c, e.target.value)} />
                </div>
                {/* L782 — compte de leads en_usage en badge. */}
                <Badge tone="neutral">{c.en_usage ?? 0} lead(s)</Badge>
                {c.protege
                  ? (
                    <Badge tone="info" title="protégé (webhook site)">
                      <Lock className="mr-0.5 size-3" aria-hidden="true" /> protégé
                    </Badge>
                  )
                  : (
                    <>
                      {/* L778 — archiver/réactiver. */}
                      <IconButton size="md" variant="outline"
                                  label={c.archived ? 'Réactiver le canal' : 'Archiver le canal'}
                                  onClick={() => archiveCanal(c)}>
                        {c.archived
                          ? <ArchiveRestore className="size-4" aria-hidden="true" />
                          : <Archive className="size-4" aria-hidden="true" />}
                      </IconButton>
                      <IconButton size="md" variant="outline" label="Supprimer le canal"
                                  className="text-destructive hover:text-destructive disabled:text-muted-foreground"
                                  disabled={c.en_usage > 0}
                                  title={c.en_usage > 0 ? `${c.en_usage} lead(s) utilisent ce canal — archivez-le` : 'Supprimer'}
                                  onClick={() => delCanal(c)}>
                        <Trash2 className="size-4" aria-hidden="true" />
                      </IconButton>
                    </>
                  )}
              </div>
            ))}
          </ListState>
          <div className="mt-1.5 flex gap-1.5">
            <Input className="flex-1" placeholder="Nouveau canal" value={newCanal}
                   onChange={e => setNewCanal(e.target.value)}
                   onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addCanal() } }} />
            <Button type="button" onClick={addCanal}><Plus className="size-4" aria-hidden="true" /></Button>
          </div>
        </CardContent>
      </Card>

      {/* ZSAL3 — Équipes commerciales (admin CRUD). */}
      <EquipesCommercialesSection assignables={assignables} />

      {/* FG36/XSAL17 — Modèles de messages CRM ({lien_rdv} entre autres). */}
      <MessageTemplatesCrmSection />
    </>
  )
}
