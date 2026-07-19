// Onglet « Avancé » de la page Paramètres (hypothèses ROI, logique de devis,
// types d'intervention, checklist d'exécution, champs personnalisés). Restylé
// sur le système de design (@/ui) ; champs, libellés et comportement identiques.
import { useState } from 'react'
import {
  Plus, Trash2, Pencil, Check, X, ChevronUp, ChevronDown, BarChart3, Download,
} from 'lucide-react'
import { formatMAD } from '../../lib/format'
import {
  Card, CardContent, Input, Button, IconButton, Badge,
  Checkbox, Switch, EmptyState,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import reportingApi from '../../api/reportingApi'
import { downloadBlobInGesture } from '../../utils/downloadBlob'
import { SectionTitle, Field } from './peComponents'
// VX233 — feed d'audit extrait, paramétrable par section (filtre dynamique ici).
import SettingsAuditFeed from './SettingsAuditFeed'
// NTIDE7 — Campagnes innovation (boîte à idées), composant autonome (modèle
// backend séparé, apps/innovation) — même patron que SettingsAuditFeed.
import CampagnesInnovationSettings from '../../features/innovation/CampagnesInnovationSettings'

export default function AvanceSection({
  form, set,
  typesItv, newType, setNewType, addType, renameType, delType,
  checklistEtapes, newEtape, setNewEtape, addEtape, renameEtape, toggleEtapeActif, delEtape,
  toggleEtapeCapture, moveEtape,
  cfModule, setCfModule, cfDefs, newCf, setNewCf, addCf, delCf, loadCfDefs,
  cfEditId, cfEdit, setCfEdit, openCfEdit, cancelCfEdit, saveCfEdit,
  toggleCfActif, moveCf,
}) {
  // L787 — impact inline de l'économie : production annuelle d'1 kWc valorisée
  // au tarif ONEE × rendement, recalculée en direct à l'édition (repère
  // pédagogique ; autoconsommation/payback restent sur l'écran devis).
  const ecoParKwc = Math.round(
    (Number(form.productible_kwh_kwc) || 0)
    * (Number(form.rendement_global) || 0)
    * (Number(form.onee_tarif_kwh) || 0))
  const fmtMad = (n) => formatMAD(n, { decimals: 0, withSymbol: false })

  // WIR101 — répartition d'un champ personnalisé listable (group-by FG94) :
  // ouvre un panneau table + export xlsx sans quitter l'écran d'administration.
  const [cfDist, setCfDist] = useState(null)
  const [cfDistBusy, setCfDistBusy] = useState(false)
  const openCfDist = (d) => {
    setCfDist({ code: d.code, libelle: d.libelle, rows: null, total: 0, error: false })
    reportingApi.cfGroupBy(cfModule, d.code)
      .then(r => setCfDist({
        code: d.code, libelle: d.libelle,
        rows: r.data?.rows || [], total: r.data?.total || 0, error: false,
      }))
      .catch(() => setCfDist({
        code: d.code, libelle: d.libelle, rows: [], total: 0, error: true,
      }))
  }
  const closeCfDist = () => setCfDist(null)
  const exportCfDist = () => {
    if (!cfDist) return
    const pending = downloadBlobInGesture()
    setCfDistBusy(true)
    reportingApi.cfGroupByXlsx(cfModule, cfDist.code)
      .then(r => pending.deliver(r.data, `repartition-${cfDist.code}.xlsx`))
      .catch(() => {})
      .finally(() => setCfDistBusy(false))
  }

  return (
    <>
      {/* ROI — hypothèses (tarif ONEE, productible) */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Hypothèses ROI" icon={<><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></>}/>
          <p className="mb-3.5 text-[11.5px] text-muted-foreground">
            Constantes utilisées pour les estimations d'économies/rentabilité.
            Les valeurs par défaut reprennent l'historique du simulateur — rien
            ne change tant que vous ne les modifiez pas.
          </p>
          <div className="pe-grid-2">
            <Field label="Tarif ONEE moyen (MAD/kWh)" htmlFor="pe-onee">
              <Input id="pe-onee" type="number" step="any"
                     name="onee_tarif_kwh" value={form.onee_tarif_kwh} onChange={set} />
            </Field>
            <Field label="Productible (kWh/kWc/an)" htmlFor="pe-productible">
              <Input id="pe-productible" type="number" step="any"
                     name="productible_kwh_kwc" value={form.productible_kwh_kwc} onChange={set} />
            </Field>
            {/* L787 — impact recalculé en direct sous tarif ONEE / productible. */}
            <div className="sm:col-span-2 rounded-lg border border-primary/25 bg-primary/5 px-3 py-2 text-[12px] text-primary">
              ≈ <strong>{fmtMad(ecoParKwc)} MAD/an</strong> économisés pour
              {' '}<strong>1 kWc</strong> installé (production
              {' '}{fmtMad(Math.round((Number(form.productible_kwh_kwc) || 0) * (Number(form.rendement_global) || 0)))} kWh ×
              {' '}{Number(form.onee_tarif_kwh) || 0} MAD/kWh).
            </div>
            <Field label="Seuil d'approbation de remise (%)" htmlFor="pe-discount-thr">
              <Input id="pe-discount-thr" type="number" step="any"
                     name="discount_approval_threshold" placeholder="vide = désactivé"
                     value={form.discount_approval_threshold} onChange={set} />
            </Field>
            <Field label="Seuil régime « Déclaration » (kWc)" htmlFor="pe-seuil-decl">
              <Input id="pe-seuil-decl" type="number" step="any"
                     name="seuil_regime_declaration_kwc"
                     value={form.seuil_regime_declaration_kwc} onChange={set} />
            </Field>
            <Field label="Seuil régime « Autorisation ANRE » (kWc)" htmlFor="pe-seuil-anre">
              <Input id="pe-seuil-anre" type="number" step="any"
                     name="seuil_regime_anre_kwc"
                     value={form.seuil_regime_anre_kwc} onChange={set} />
            </Field>
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground">
            Seuils loi 82-21 proposés à la création d'un chantier (régime
            suggéré, modifiable) : sous le 1er seuil = Déclaration, entre les
            deux = Accord de raccordement, au-dessus du 2nd = Autorisation ANRE.
          </p>
          <p className="mt-2 text-[11px] text-muted-foreground">
            Au-delà de ce seuil de remise, un devis exige l'approbation d'un
            administrateur avant l'envoi. Vide = désactivé (défaut).
          </p>
        </CardContent>
      </Card>

      {/* FG22 — Politique de sécurité (mot de passe & verrouillage), par
          société. Tous les défauts sont inertes : rien ne change tant que
          vous ne durcissez pas la politique. */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Sécurité — mots de passe & verrouillage" icon={<><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></>}/>
          <p className="mb-3.5 text-[11.5px] text-muted-foreground">
            Règles appliquées aux mots de passe et aux connexions de votre
            société. Valeurs par défaut sans effet (longueur 8, complexité non
            exigée, verrouillage désactivé, expiration jamais) — la connexion
            reste identique tant que vous ne modifiez rien.
          </p>
          <div className="pe-grid-2">
            <Field label="Longueur minimale du mot de passe" htmlFor="pe-pw-min">
              <Input id="pe-pw-min" type="number" step="1" min="1"
                     name="password_min_length"
                     value={form.password_min_length} onChange={set} />
            </Field>
            <Field label="Verrouillage après N échecs (0 = désactivé)" htmlFor="pe-lockout-n">
              <Input id="pe-lockout-n" type="number" step="1" min="0"
                     name="lockout_max_attempts"
                     value={form.lockout_max_attempts} onChange={set} />
            </Field>
            <Field label="Durée du verrouillage (minutes)" htmlFor="pe-lockout-min">
              <Input id="pe-lockout-min" type="number" step="1" min="1"
                     name="lockout_duration_minutes"
                     value={form.lockout_duration_minutes} onChange={set} />
            </Field>
            <Field label="Expiration du mot de passe (jours, 0 = jamais)" htmlFor="pe-pw-expiry">
              <Input id="pe-pw-expiry" type="number" step="1" min="0"
                     name="password_expiry_days"
                     value={form.password_expiry_days} onChange={set} />
            </Field>
            {/* FG26 — rétention RGPD du journal d'audit (0 = illimité). */}
            <Field label="Rétention du journal d'audit (jours, 0 = illimité)" htmlFor="pe-audit-retention">
              <Input id="pe-audit-retention" type="number" step="1" min="0"
                     name="audit_retention_days"
                     value={form.audit_retention_days} onChange={set} />
            </Field>
            <label className="sm:col-span-2 flex items-center gap-2.5 text-sm text-foreground">
              <input type="checkbox" name="password_require_complexity"
                     checked={!!form.password_require_complexity} onChange={set} />
              Exiger un mélange majuscule / minuscule / chiffre / caractère spécial
            </label>
          </div>
        </CardContent>
      </Card>

      {/* Logique de devis (avancé) — paramètres implicites du simulateur (D5) */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Logique de devis (avancé)" icon={<><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/></>}/>
          <p className="mb-3.5 text-[11.5px] text-muted-foreground">
            Paramètres implicites du générateur de devis, rendus modifiables.
            Les valeurs par défaut reprennent EXACTEMENT les constantes du
            simulateur — le devis reste identique tant que vous ne les
            modifiez pas. Chaque changement est tracé (journal d'audit).
          </p>
          <div className="pe-grid-2">
            <Field label="Rendement global (0–1)" htmlFor="pe-rendement">
              <Input id="pe-rendement" type="number" step="any"
                     name="rendement_global" value={form.rendement_global} onChange={set} />
            </Field>
            <Field label="Panneaux par tranche de 900 MAD (auto-remplir)" htmlFor="pe-panneaux900">
              <Input id="pe-panneaux900" type="number" step="any"
                     name="panneaux_par_900mad" value={form.panneaux_par_900mad} onChange={set} />
            </Field>
            <Field label="Prix cible /kWc par défaut (MAD)" htmlFor="pe-prix-cible">
              <Input id="pe-prix-cible" type="number" step="any"
                     name="prix_cible_kwc_defaut" placeholder="vide = aucun"
                     value={form.prix_cible_kwc_defaut} onChange={set} />
            </Field>
            <Field label="Limite de remise conseillée (%)" htmlFor="pe-remise-max">
              <Input id="pe-remise-max" type="number" step="any"
                     name="remise_max_pct" placeholder="vide = aucune"
                     value={form.remise_max_pct} onChange={set} />
            </Field>
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground">
            Le rendement et le tarif ONEE (ci-dessus) pilotent les économies
            estimées ; le ratio de dimensionnement pilote la suggestion de
            panneaux du devis auto ; le prix cible pré-remplit le générateur ;
            la limite de remise affiche un repère (sans bloquer la saisie).
            Les tables tarifaires ONEE par tranche et les facteurs de
            production par région restent un raffinement futur (modèle de
            calcul à valider avec le founder).
          </p>
        </CardContent>
      </Card>

      {/* Chantiers — Types d'intervention */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Chantiers — Types d'intervention" icon={<><path d="M14.7 6.3a4 4 0 0 0-5.6 5.6l-6 6 2 2 6-6a4 4 0 0 0 5.6-5.6l-2.5 2.5-2-2 2.5-2.5z"/></>}/>
          <p className="mb-3.5 text-[11.5px] text-muted-foreground">
            Types d'intervention proposés sur les chantiers. Les types système
            sont protégés ; un type déjà utilisé ne peut pas être supprimé.
          </p>
          {typesItv.map(t => (
            <div key={t.id} className="mb-1.5 flex items-center gap-1.5">
              {/* ERR102 — re-monte le champ si le serveur normalise le libellé. */}
              <Input key={t.libelle} className="flex-1" defaultValue={t.libelle}
                     onBlur={e => renameType(t, e.target.value)} />
              {t.protege
                ? <Badge tone="info">système</Badge>
                : (
                  <IconButton size="md" variant="outline" label="Supprimer le type"
                              className="text-destructive hover:text-destructive disabled:text-muted-foreground"
                              disabled={t.en_usage > 0}
                              onClick={() => delType(t)}>
                    <Trash2 className="size-4" aria-hidden="true" />
                  </IconButton>
                )}
            </div>
          ))}
          <div className="flex gap-1.5">
            <Input className="flex-1" placeholder="Nouveau type" value={newType}
                   onChange={e => setNewType(e.target.value)}
                   onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addType() } }} />
            <Button type="button" onClick={addType}><Plus className="size-4" aria-hidden="true" /></Button>
          </div>
        </CardContent>
      </Card>

      {/* Chantiers — Checklist d'exécution */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Chantiers — Checklist d'exécution" icon={<><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></>}/>
          <p className="mb-3.5 text-[11.5px] text-muted-foreground">
            Étapes proposées sur la checklist des chantiers. Désactivez une
            étape pour la retirer des nouveaux chantiers sans toucher aux
            chantiers existants ; les étapes système sont protégées.
          </p>
          {checklistEtapes.map((et, idx) => (
            <div key={et.id} className="mb-1.5 flex flex-wrap items-center gap-1.5">
              {/* L784 — réordonner l'étape (haut/bas). */}
              <div className="flex flex-col">
                <IconButton size="sm" variant="ghost" label="Monter l'étape"
                            disabled={idx === 0} onClick={() => moveEtape(et, -1)}>
                  <ChevronUp className="size-3.5" aria-hidden="true" />
                </IconButton>
                <IconButton size="sm" variant="ghost" label="Descendre l'étape"
                            disabled={idx === checklistEtapes.length - 1}
                            onClick={() => moveEtape(et, 1)}>
                  <ChevronDown className="size-3.5" aria-hidden="true" />
                </IconButton>
              </div>
              {/* ERR102 — re-monte le champ si le serveur normalise le libellé. */}
              <Input key={et.libelle} className={['min-w-[120px] flex-[1_1_120px]', et.actif ? '' : 'opacity-50'].join(' ')} defaultValue={et.libelle}
                     onBlur={e => renameEtape(et, e.target.value)} />
              {/* L785 — capture_serie en toggle éditable (au lieu d'un simple badge). */}
              <Button type="button" size="sm"
                      variant={et.capture_serie ? 'default' : 'outline'}
                      title="Saisie de n° de série sur cette étape"
                      onClick={() => toggleEtapeCapture(et)}>
                Série
              </Button>
              <Button type="button" size="sm"
                      variant={et.actif ? 'success' : 'secondary'}
                      title={et.actif ? 'Désactiver' : 'Activer'}
                      onClick={() => toggleEtapeActif(et)}>
                {et.actif ? 'Actif' : 'Inactif'}
              </Button>
              {et.protege
                ? <Badge tone="info">système</Badge>
                : (
                  <IconButton size="md" variant="outline" label="Supprimer l'étape"
                              className="text-destructive hover:text-destructive"
                              onClick={() => delEtape(et)}>
                    <Trash2 className="size-4" aria-hidden="true" />
                  </IconButton>
                )}
            </div>
          ))}
          <div className="flex gap-1.5">
            <Input className="flex-1" placeholder="Nouvelle étape" value={newEtape}
                   onChange={e => setNewEtape(e.target.value)}
                   onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addEtape() } }} />
            <Button type="button" onClick={addEtape}><Plus className="size-4" aria-hidden="true" /></Button>
          </div>
        </CardContent>
      </Card>

      {/* NTIDE7 — Campagnes innovation (boîte à idées interne). */}
      <CampagnesInnovationSettings />

      {/* L765 — Journal des modifications (audit N55, lecture seule) */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Journal des modifications" icon={<><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></>}/>
          <p className="mb-3 text-[11.5px] text-muted-foreground">
            Derniers changements de paramètres : qui a modifié quoi et quand.
            Lecture seule.
          </p>
          {/* VX233 — feed extrait, filtre dynamique (≥ 6 sections réelles). */}
          <SettingsAuditFeed />
        </CardContent>
      </Card>

      {/* Champs personnalisés */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Champs personnalisés" icon={<><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 9h6v6H9z"/></>}/>
          <p className="mb-3.5 text-[11.5px] text-muted-foreground">
            Ajoutez vos propres champs aux fiches (leads, clients, produits).
            Ils apparaissent dans le formulaire ; rien n'est perdu si vous en
            retirez un.
          </p>
          <div className="mb-2 flex items-center gap-1.5">
            <div className="w-[140px]">
              <Select value={cfModule}
                      onValueChange={v => { setCfModule(v); loadCfDefs(v); closeCfDist() }}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="lead">Leads</SelectItem>
                  <SelectItem value="client">Clients</SelectItem>
                  <SelectItem value="produit">Produits</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {/* L817 — compte des champs définis pour le module courant. */}
            <span className="text-[11px] text-muted-foreground">
              {cfDefs.length} champ{cfDefs.length > 1 ? 's' : ''}
            </span>
          </div>
          {/* L817 — état vide explicite quand le module n'a aucun champ. */}
          {cfDefs.length === 0 ? (
            <div className="mb-2">
              <EmptyState
                title="Aucun champ pour ce module"
                description="Ajoutez un champ ci-dessous pour l'afficher sur les fiches." />
            </div>
          ) : cfDefs.map((d, idx) => (
            cfEditId === d.id ? (
              // L809 — éditeur inline (libellé/type/options/obligatoire/visible).
              <div key={d.id} className="mb-2 rounded-md border border-border p-2">
                <div className="flex flex-wrap items-center gap-1.5">
                  <Input className="min-w-[140px] flex-[1_1_140px]"
                         placeholder="Libellé du champ" value={cfEdit?.libelle ?? ''}
                         onChange={e => setCfEdit(c => ({ ...c, libelle: e.target.value }))} />
                  <div className="w-[120px]">
                    <Select value={cfEdit?.type}
                            onValueChange={v => setCfEdit(c => ({ ...c, type: v }))}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="text">Texte</SelectItem>
                        <SelectItem value="number">Nombre</SelectItem>
                        <SelectItem value="date">Date</SelectItem>
                        <SelectItem value="choice">Choix</SelectItem>
                        <SelectItem value="boolean">Oui/Non</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  {cfEdit?.type === 'choice' && (
                    <Input className="min-w-[160px] flex-[1_1_160px]"
                           placeholder="Options (a, b, c)" value={cfEdit?.options ?? ''}
                           onChange={e => setCfEdit(c => ({ ...c, options: e.target.value }))} />
                  )}
                  <IconButton size="md" variant="outline" label="Enregistrer"
                              onClick={() => saveCfEdit(d)}>
                    <Check className="size-4" aria-hidden="true" />
                  </IconButton>
                  <IconButton size="md" variant="outline" label="Annuler"
                              onClick={cancelCfEdit}>
                    <X className="size-4" aria-hidden="true" />
                  </IconButton>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-3 text-[11.5px] text-muted-foreground">
                  {/* Code non modifiable : protégé serveur dès qu'une donnée existe (L814). */}
                  <span>Code : <code>{d.code}</code></span>
                  <label className="flex items-center gap-1.5">
                    <Checkbox checked={!!cfEdit?.obligatoire}
                              onCheckedChange={v => setCfEdit(c => ({ ...c, obligatoire: !!v }))} />
                    Obligatoire
                  </label>
                  <label className="flex items-center gap-1.5">
                    <Checkbox checked={!!cfEdit?.visible_liste}
                              onCheckedChange={v => setCfEdit(c => ({ ...c, visible_liste: !!v }))} />
                    Visible en liste
                  </label>
                </div>
              </div>
            ) : (
              <div key={d.id}
                   className={`mb-1.5 flex items-center gap-1.5 ${d.actif ? '' : 'opacity-50'}`}>
                {/* L813 — réordonner (haut/bas). */}
                <div className="flex flex-col">
                  <IconButton size="sm" variant="ghost" label="Monter"
                              disabled={idx === 0} onClick={() => moveCf(d, -1)}>
                    <ChevronUp className="size-3.5" aria-hidden="true" />
                  </IconButton>
                  <IconButton size="sm" variant="ghost" label="Descendre"
                              disabled={idx === cfDefs.length - 1} onClick={() => moveCf(d, 1)}>
                    <ChevronDown className="size-3.5" aria-hidden="true" />
                  </IconButton>
                </div>
                <span className="flex-1 text-sm text-foreground">
                  {d.libelle}{d.obligatoire ? ' *' : ''}
                </span>
                {d.visible_liste && <Badge tone="outline">Liste</Badge>}
                <span className="text-[11px] text-muted-foreground">{d.type}</span>
                {/* L810 — toggle actif/inactif (soft-disable, custom_data conservé). */}
                <Switch checked={!!d.actif} onCheckedChange={() => toggleCfActif(d)}
                        aria-label={d.actif ? 'Désactiver le champ' : 'Réactiver le champ'} />
                {/* WIR101 — répartition (group-by) pour les champs listables. */}
                {d.visible_liste && (
                  <IconButton size="md" variant="outline" label="Voir la répartition"
                              onClick={() => openCfDist(d)}>
                    <BarChart3 className="size-4" aria-hidden="true" />
                  </IconButton>
                )}
                <IconButton size="md" variant="outline" label="Modifier le champ"
                            onClick={() => openCfEdit(d)}>
                  <Pencil className="size-4" aria-hidden="true" />
                </IconButton>
                <IconButton size="md" variant="outline" label="Supprimer le champ"
                            className="text-destructive hover:text-destructive"
                            onClick={() => delCf(d)}>
                  <Trash2 className="size-4" aria-hidden="true" />
                </IconButton>
              </div>
            )
          ))}
          <div className="flex flex-wrap items-center gap-1.5">
            <Input className="min-w-[140px] flex-[1_1_140px]" placeholder="Libellé du champ"
                   value={newCf.libelle} onChange={e => setNewCf(c => ({ ...c, libelle: e.target.value }))} />
            <div className="w-[120px]">
              <Select value={newCf.type}
                      onValueChange={v => setNewCf(c => ({ ...c, type: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="text">Texte</SelectItem>
                  <SelectItem value="number">Nombre</SelectItem>
                  <SelectItem value="date">Date</SelectItem>
                  <SelectItem value="choice">Choix</SelectItem>
                  <SelectItem value="boolean">Oui/Non</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {newCf.type === 'choice' && (
              <Input className="min-w-[160px] flex-[1_1_160px]" placeholder="Options (a, b, c)"
                     value={newCf.options} onChange={e => setNewCf(c => ({ ...c, options: e.target.value }))} />
            )}
            {/* L811 — obligatoire à la création ; L812 — visible en liste. */}
            <label className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
              <Checkbox checked={!!newCf.obligatoire}
                        onCheckedChange={v => setNewCf(c => ({ ...c, obligatoire: !!v }))} />
              Obligatoire
            </label>
            <label className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
              <Checkbox checked={!!newCf.visible_liste}
                        onCheckedChange={v => setNewCf(c => ({ ...c, visible_liste: !!v }))} />
              Visible en liste
            </label>
            <Button type="button" onClick={addCf}><Plus className="size-4" aria-hidden="true" /></Button>
          </div>

          {/* WIR101 — panneau de répartition d'un champ listable (group-by FG94). */}
          {cfDist && (
            <div className="mt-4 rounded-md border border-border p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className="text-sm font-medium text-foreground">
                  Répartition — {cfDist.libelle}
                </span>
                <div className="flex items-center gap-1.5">
                  <Button type="button" variant="outline" size="sm"
                          disabled={cfDistBusy || !cfDist.rows || cfDist.rows.length === 0}
                          onClick={exportCfDist}>
                    <Download className="size-3.5" aria-hidden="true" /> Excel
                  </Button>
                  <IconButton size="md" variant="ghost" label="Fermer" onClick={closeCfDist}>
                    <X className="size-4" aria-hidden="true" />
                  </IconButton>
                </div>
              </div>
              {cfDist.error ? (
                <p className="text-sm text-muted-foreground">Répartition indisponible.</p>
              ) : cfDist.rows === null ? (
                <p className="text-sm text-muted-foreground">Chargement…</p>
              ) : cfDist.rows.length === 0 ? (
                <p className="text-sm text-muted-foreground">Aucune valeur pour ce champ.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[11.5px] uppercase text-muted-foreground">
                      <th className="py-1">Valeur</th>
                      <th className="py-1 text-right">Nombre</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cfDist.rows.map((r) => (
                      <tr key={r.valeur} className="border-t border-border/60">
                        <td className="py-1.5">{r.valeur}</td>
                        <td className="py-1.5 text-right tabular-nums">{r.count}</td>
                      </tr>
                    ))}
                    <tr className="border-t border-border font-medium">
                      <td className="py-1.5">Total</td>
                      <td className="py-1.5 text-right tabular-nums">{cfDist.total}</td>
                    </tr>
                  </tbody>
                </table>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </>
  )
}
