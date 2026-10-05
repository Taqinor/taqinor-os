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
import { CHAMP_ECART_RECETTE, erreurDuChamp } from './peConstants'
// VX233 — feed d'audit extrait, paramétrable par section (filtre dynamique ici).
import SettingsAuditFeed from './SettingsAuditFeed'
// WIR112 — équipes terrain canoniques (DC40), à côté des Types d'intervention.
import EquipeTerrainSection from './EquipeTerrainSection'
// WIR114 (ZFSM3) — modèles de fiche d'intervention (champs de compte-rendu).
import FicheInterventionModelesSection from './FicheInterventionModelesSection'

// WIR67 — modules « customfieldables » (miroir de
// `customfields.registry` : 8 clés natives + pilotes ARC31 contrat/vehicule
// + WIR67 kb_article). Remplace le sélecteur figé lead/client/produit : un
// champ personnalisé peut cibler n'importe quel module enregistré, et le
// widget s'affiche là où `<CustomFieldsInput>` est monté (lead/client/produit
// aujourd'hui, article KB via ArticleEditor).
const CUSTOMFIELD_MODULES = [
  { key: 'lead', label: 'Leads' },
  { key: 'client', label: 'Clients' },
  { key: 'produit', label: 'Produits' },
  { key: 'devis', label: 'Devis' },
  { key: 'installation', label: 'Chantiers' },
  { key: 'ticket', label: 'Tickets SAV' },
  { key: 'document', label: 'Documents GED' },
  { key: 'fournisseur', label: 'Fournisseurs' },
  { key: 'employe', label: 'Employés' },
  { key: 'contrat', label: 'Contrats' },
  { key: 'vehicule', label: 'Véhicules' },
  { key: 'kb_article', label: 'Articles KB' },
]

/* AGR607 (Groupe AGR, 02/10/2026) — écart de recette pompage toléré (%),
   réglage société SANS défaut (AGR606), à côté des seuils 82-21. Vide = aide
   « non saisi : l'écart sera affiché sans verdict » ; une valeur tapée part
   telle quelle (step="any", jamais arrondie) ; le refus 400 du serveur
   s'affiche SOUS le champ. */
export function EcartRecettePompageField({ form, set, erreur }) {
  const message = erreurDuChamp(erreur, CHAMP_ECART_RECETTE)
  const valeur = form?.[CHAMP_ECART_RECETTE] ?? ''
  const vide = String(valeur).trim() === ''
  return (
    <Field label="Écart de recette pompage toléré (%)" htmlFor="pe-ecart-recette">
      <Input id="pe-ecart-recette" type="number" step="any"
             name={CHAMP_ECART_RECETTE} value={valeur} onChange={set}
             invalid={Boolean(message)}
             aria-describedby={message ? 'pe-ecart-recette-erreur' : undefined} />
      {vide && (
        <p className="text-[11px] text-muted-foreground">
          Non saisi : l&apos;écart sera affiché sans verdict.
        </p>
      )}
      {message && (
        <p id="pe-ecart-recette-erreur" role="alert"
           className="text-[11.5px] font-medium text-destructive">
          {message}
        </p>
      )}
    </Field>
  )
}

/* CIQ639 (Groupe CIQ) — seuils 82-21 SOURCÉS (CIQ614) : la référence vient
   des textes (11 kW, 5 MW, servie par `seuils_sources` avec son article) ;
   la société ne saisit qu'une SURCHARGE, vide par défaut (fin du 1 000
   prérempli). Réglages C&I de CIQ622, tous SANS défaut : vide = « écart
   affiché sans verdict » / « non engagé ». Valeurs tapées envoyées telles
   quelles (step="any"), refus 400 du serveur sous le champ fautif. */
const CHAMPS_SEUILS_8221 = [
  { champ: 'seuil_regime_declaration_kwc', cle: 'declaration',
    label: 'Surcharge du seuil « Déclaration » (kW)' },
  { champ: 'seuil_regime_anre_kwc', cle: 'autorisation',
    label: 'Surcharge du seuil « Autorisation » (kW)' },
]
const AIDE_SANS_VERDICT = "Vide : l'écart sera affiché sans verdict."
const AIDE_NON_ENGAGE = 'Vide : non engagé.'
const REGLAGES_CI_NOMBRES = [
  { champ: 'recette_ecart_pmax_pct', label: 'Écart de recette toléré sur la puissance crête (%)', aide: AIDE_SANS_VERDICT },
  { champ: 'recette_echantillon_iv_pct', label: 'Échantillon de courbes I-V à la recette (%)', aide: AIDE_SANS_VERDICT },
  { champ: 'recette_pr_seuil_interne', label: 'Seuil interne de performance ratio (%) — alerte interne', aide: AIDE_SANS_VERDICT },
  { champ: 'delai_intervention_suivi_heures', label: "Délai d'intervention du suivi (heures)", aide: AIDE_NON_ENGAGE },
  { champ: 'delai_reception_definitive_mois', label: 'Délai de réception définitive (mois)', aide: AIDE_NON_ENGAGE },
]
const REGLAGES_CI_BOOLEENS = [
  { champ: 'securite_obligatoire_avant_demarrage', label: 'Contrôle de sécurité obligatoire avant démarrage' },
  { champ: 'garantie_production_autorisee', label: 'Garantie de production autorisée' },
]
export const CHAMP_GARANTIE_VALIDATION = 'garantie_production_validation'
export const MESSAGE_GARANTIE_SANS_VALIDATION = (
  "La garantie de production ne peut être autorisée qu'avec sa validation "
  + 'écrite (assureur ou juriste : qui a validé et quand).')

const versTexte = (v) => (v === null || v === undefined ? '' : String(v))
const nombreOuNul = (v) => {
  if (v === null || v === undefined) return null
  const t = String(v).trim().replace(',', '.')
  return t === '' ? null : t
}

/** Profil serveur → état du formulaire (vide = '' / false ; aucun défaut). */
// eslint-disable-next-line react-refresh/only-export-components
export function formReglagesCi(profile = {}) {
  const p = profile || {}
  return {
    ...Object.fromEntries(CHAMPS_SEUILS_8221.map(({ champ }) => [champ, versTexte(p[champ])])),
    ...Object.fromEntries(REGLAGES_CI_NOMBRES.map(({ champ }) => [champ, versTexte(p[champ])])),
    ...Object.fromEntries(REGLAGES_CI_BOOLEENS.map(({ champ }) => [champ, !!p[champ]])),
    [CHAMP_GARANTIE_VALIDATION]: versTexte(p[CHAMP_GARANTIE_VALIDATION]),
  }
}

/** État du formulaire → PATCH : vide = null, tapé = tel quel. */
// eslint-disable-next-line react-refresh/only-export-components
export function payloadReglagesCi(form = {}) {
  const f = form || {}
  return {
    ...Object.fromEntries(CHAMPS_SEUILS_8221.map(({ champ }) => [champ, nombreOuNul(f[champ])])),
    ...Object.fromEntries(REGLAGES_CI_NOMBRES.map(({ champ }) => [champ, nombreOuNul(f[champ])])),
    ...Object.fromEntries(REGLAGES_CI_BOOLEENS.map(({ champ }) => [champ, !!f[champ]])),
    [CHAMP_GARANTIE_VALIDATION]: versTexte(f[CHAMP_GARANTIE_VALIDATION]).trim(),
  }
}

/** Erreur locale de la garantie (même règle que le serveur), ou ''. */
// eslint-disable-next-line react-refresh/only-export-components
export function erreurGarantieLocale(form = {}) {
  const f = form || {}
  return f.garantie_production_autorisee
    && versTexte(f[CHAMP_GARANTIE_VALIDATION]).trim() === ''
    ? MESSAGE_GARANTIE_SANS_VALIDATION : ''
}

function ErreurSous({ id, message }) {
  if (!message) return null
  return (
    <p id={id} role="alert" className="text-[11.5px] font-medium text-destructive">
      {message}
    </p>
  )
}

export function SeuilsEtReglagesCiFields({ form, set, erreur, seuilsSources }) {
  const f = form || {}
  const garantieLocale = erreurGarantieLocale(f)
  const garantieMessage = erreurDuChamp(erreur, CHAMP_GARANTIE_VALIDATION) || garantieLocale
  return (
    <>
      {CHAMPS_SEUILS_8221.map(({ champ, cle, label }) => {
        const source = seuilsSources?.[cle]
        const message = erreurDuChamp(erreur, champ)
        const id = `pe-${champ}`
        return (
          <Field key={champ} label={label} htmlFor={id}>
            <Input id={id} type="number" step="any" name={champ}
                   value={versTexte(f[champ])} onChange={set}
                   invalid={Boolean(message)}
                   aria-describedby={message ? `${id}-erreur` : undefined} />
            <p className="text-[11px] text-muted-foreground">
              {source
                ? `Seuil des textes : ${source.valeur_kw} kW — ${source.source}. Vide = seuil des textes.`
                : 'Vide = seuil des textes.'}
            </p>
            <ErreurSous id={`${id}-erreur`} message={message} />
          </Field>
        )
      })}
      {REGLAGES_CI_NOMBRES.map(({ champ, label, aide }) => {
        const message = erreurDuChamp(erreur, champ)
        const id = `pe-${champ}`
        const vide = versTexte(f[champ]).trim() === ''
        return (
          <Field key={champ} label={label} htmlFor={id}>
            <Input id={id} type="number" step="any" name={champ}
                   value={versTexte(f[champ])} onChange={set}
                   invalid={Boolean(message)}
                   aria-describedby={message ? `${id}-erreur` : undefined} />
            {vide && !message && (
              <p className="text-[11px] text-muted-foreground">{aide}</p>
            )}
            <ErreurSous id={`${id}-erreur`} message={message} />
          </Field>
        )
      })}
      {REGLAGES_CI_BOOLEENS.map(({ champ, label }) => (
        <label key={champ} className="flex items-center gap-2 text-[12.5px]">
          <input type="checkbox" name={champ} checked={!!f[champ]} onChange={set} />
          {label}
        </label>
      ))}
      <Field label="Validation de la garantie de production (qui, quand)"
             htmlFor="pe-garantie-validation">
        <Input id="pe-garantie-validation" type="text"
               name={CHAMP_GARANTIE_VALIDATION}
               value={versTexte(f[CHAMP_GARANTIE_VALIDATION])} onChange={set}
               invalid={Boolean(garantieMessage)}
               aria-describedby={garantieMessage ? 'pe-garantie-validation-erreur' : undefined} />
        {!f.garantie_production_autorisee && (
          <p className="text-[11px] text-muted-foreground">
            Non autorisée : aucune garantie de production n&apos;est imprimée.
          </p>
        )}
        <ErreurSous id="pe-garantie-validation-erreur" message={garantieMessage} />
      </Field>
    </>
  )
}

export default function AvanceSection({
  form, set,
  profile = null,
  profileError = null,
  assignables = [],
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
            <SeuilsEtReglagesCiFields form={form} set={set} erreur={profileError}
                                      seuilsSources={profile?.seuils_sources} />
            <EcartRecettePompageField form={form} set={set} erreur={profileError} />
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground">
            Seuils loi 82-21 proposés à la création d'un chantier (régime
            suggéré, modifiable) : sous le 1er seuil = Déclaration, entre les
            deux = Accord de raccordement, au-dessus du 2nd = Autorisation.
            Ils viennent des textes ; une surcharge ne se saisit que par choix
            délibéré de la société.
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
            estimées ; le prix cible pré-remplit le générateur ; la limite de
            remise affiche un repère (sans bloquer la saisie).
            {' '}
            U3-900 (fondateur 29/08/2026) : le réglage « panneaux par tranche
            de 900 MAD » a été RETIRÉ — le dimensionnement (résidentiel) passe
            désormais entièrement par le moteur horaire serveur, qui chiffre
            une taille réelle à partir de la facture et du site plutôt que
            d'une règle forfaitaire par tranche.
            {' '}
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

      {/* WIR112 — Chantiers — Équipes terrain canoniques (DC40), à côté des types. */}
      <EquipeTerrainSection assignables={assignables} />

      {/* WIR114 — Modèles de fiche d'intervention (ZFSM3), à côté des types. */}
      <FicheInterventionModelesSection />

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
                  {/* WIR67 — tous les modules enregistrés (plus seulement
                      lead/client/produit). */}
                  {CUSTOMFIELD_MODULES.map(m => (
                    <SelectItem key={m.key} value={m.key}>{m.label}</SelectItem>
                  ))}
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
