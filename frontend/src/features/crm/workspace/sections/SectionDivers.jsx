import { useState } from 'react'
import {
  Badge, Button, DefinitionList, FormField, Input,
} from '../../../../ui'
import { formatDate, formatDateTime } from '../../../../lib/format'
import {
  getField, WEB_ORIGIN_FIELDS, WEB_QUESTIONNAIRE_STRUCTURED_FIELDS, estValeurWebRenseignee,
  etatChampSite, champsSiteAPoser,
} from '../draftCore'
import CustomFieldsInput from '../../../../components/CustomFieldsInput'

/* CAD150/CAD159 — UN champ capté par le site, TOUJOURS éditable (décision
   fondateur du 21/09/2026), jamais écrasé sans geste explicite :
   · vide → le contrôle, directement saisissable (lead Meta, walk-in, appel) ;
   · rempli par le site → la valeur « à confirmer » + « Modifier » : aucun
     contrôle n'est rendu tant que la commerciale ne l'a pas demandé ;
   · dans tous les cas, la provenance servie par le serveur (« saisie sur le
     site le … ») reste lisible sous le champ — y compris après écrasement. */
export function ChampSite({
  state, champ, label, htmlFor: inputId, error, renderControl,
}) {
  const [edition, setEdition] = useState(false)
  const { provenance, aConfirmer } = etatChampSite(state, champ)
  const verrouille = aConfirmer && !edition
  const hint = provenance
    ? `Saisie sur le site le ${formatDate(provenance.le)} : ${provenance.valeur}`
      + (provenance.ecrasee ? ' — modifiée depuis sur la fiche.' : '')
    : undefined
  return (
    <FormField label={label} htmlFor={inputId} error={error} hint={hint}>
      {verrouille ? (
        <div className="flex flex-wrap items-center gap-1.5" data-testid={`champ-site-${champ}`}>
          <span id={inputId} className="text-sm">{provenance.valeur}</span>
          <Badge tone="warning">à confirmer</Badge>
          <Button
            type="button" size="sm" variant="outline"
            aria-label={`Modifier « ${label} »`}
            onClick={() => setEdition(true)}
          >
            Modifier
          </Button>
        </div>
      ) : renderControl()}
    </FormField>
  )
}

// CAD150 — vocabulaires des choix, alignés sur le serveur (garde
// `check_choices_declares.py`).
// source-choix: crm.Lead.ownership
const OWNERSHIP = { proprietaire: 'Propriétaire', locataire: 'Locataire', autre: 'Autre' }
// source-choix: crm.Lead.financing_intent
const FINANCING_INTENT = { cash: 'Comptant', credit: 'Crédit / financement', indecis: 'Pas encore décidé' }
// source-choix: crm.Lead.project_timeline
const PROJECT_TIMELINE = {
  immediat: 'Dès que possible', '3_mois': 'Moins de 3 mois', '6_mois': '3 à 6 mois',
  plus_tard: 'Plus tard / je me renseigne',
}
// source-choix: crm.Lead.facility_type
const FACILITY_TYPE = {
  bureau: 'Bureau', entrepot: 'Entrepôt', usine: 'Usine', commerce: 'Commerce',
  agricole: 'Agricole', autre: 'Autre',
}

const optionsDe = (labels) => [
  <option key="" value="">—</option>,
  ...Object.entries(labels).map(([k, l]) => <option key={k} value={k}>{l}</option>),
]

// CAD159 — libellés des champs de ce bloc (mêmes que leurs FormField).
const LIBELLES_QUALIFICATION = {
  ownership: "Statut d'occupation",
  financing_intent: 'Financement envisagé',
  project_timeline: 'Horizon du projet',
  facility_type: 'Type de site (pro)',
  roof_type: 'Type de toiture (site)',
  roof_age: 'Âge de la toiture (ans)',
}

/* CAD150 — la qualification captée par le site, ÉDITABLE sur la fiche (hors
   énergie : `distributeur` et `bill_kwh` vivent dans SectionEnergie).
   CAD159 — la liste « à demander » ne porte QUE les champs vides : une
   valeur déjà là (du site ou de la fiche) n'est jamais une question à
   reposer, elle se confirme. */
function QualificationSite({ state, setField, errors }) {
  const v = (k) => getField(state, k) ?? ''
  const aDemander = champsSiteAPoser(state, Object.keys(LIBELLES_QUALIFICATION))
  const select = (champ, id, labels) => () => (
    <select
      id={id} className={errors[champ] ? 'form-select is-invalid' : 'form-select'}
      aria-invalid={errors[champ] ? true : undefined}
      value={v(champ)} onChange={(e) => setField(champ, e.target.value)}
    >
      {optionsDe(labels)}
    </select>
  )
  return (
    <div className="mt-3" data-testid="qualification-site">
      <p className="form-label">Qualification (site ou appel)</p>
      {aDemander.length > 0 && (
        <p className="text-xs text-muted-foreground" data-testid="qualification-a-demander">
          À demander à l’appel : {aDemander.map((champ) => LIBELLES_QUALIFICATION[champ]).join(', ')}.
        </p>
      )}
      <div className="form-row">
        <ChampSite
          state={state} champ="ownership" label="Statut d'occupation" htmlFor="lf-ownership"
          error={errors.ownership} renderControl={select('ownership', 'lf-ownership', OWNERSHIP)}
        />
        <ChampSite
          state={state} champ="financing_intent" label="Financement envisagé" htmlFor="lf-financing-intent"
          error={errors.financing_intent}
          renderControl={select('financing_intent', 'lf-financing-intent', FINANCING_INTENT)}
        />
        <ChampSite
          state={state} champ="project_timeline" label="Horizon du projet" htmlFor="lf-project-timeline"
          error={errors.project_timeline}
          renderControl={select('project_timeline', 'lf-project-timeline', PROJECT_TIMELINE)}
        />
      </div>
      <div className="form-row">
        <ChampSite
          state={state} champ="facility_type" label="Type de site (pro)" htmlFor="lf-facility-type"
          error={errors.facility_type}
          renderControl={select('facility_type', 'lf-facility-type', FACILITY_TYPE)}
        />
        <ChampSite
          state={state} champ="roof_type" label="Type de toiture (site)" htmlFor="lf-roof-type"
          error={errors.roof_type}
          renderControl={() => (
            <Input
              id="lf-roof-type" invalid={!!errors.roof_type} value={v('roof_type')}
              onChange={(e) => setField('roof_type', e.target.value)}
            />
          )}
        />
        <ChampSite
          state={state} champ="roof_age" label="Âge de la toiture (ans)" htmlFor="lf-roof-age"
          error={errors.roof_age}
          renderControl={() => (
            <Input
              id="lf-roof-age" type="number" step="any" invalid={!!errors.roof_age} value={v('roof_age')}
              onChange={(e) => setField('roof_age', e.target.value)}
            />
          )}
        />
      </div>
    </div>
  )
}

// Champs d'origine web (taqinor.ma) en LECTURE SEULE : capturés par le site,
// jamais édités ici. La section est masquée si tous sont vides (SectionsPane).
// WEB_ORIGIN_FIELDS vit dans draftCore.js (module logique pur) : exporter une
// constante depuis un fichier de composants casse react-refresh (lint CI).

const WEB_ORIGIN_LABELS = {
  bill_range_bucket: 'Tranche de facture (site)',
  roi_band: 'Estimation ROI (site)',
  utm_source: 'UTM source',
  utm_medium: 'UTM medium',
  utm_campaign: 'UTM campagne',
  fbclid: 'fbclid',
}

// LW11 — Origine web : DefinitionList en lecture seule (repliée par défaut,
// géré par SectionsPane). Remplace les <input readOnly disabled> bruts.
export function SectionOrigine({ state }) {
  const server = state.server || {}
  const items = WEB_ORIGIN_FIELDS
    .map((k) => {
      const raw = server[k]
      const val = raw === undefined || raw === null || raw === '' ? '' : String(raw)
      return val ? { term: WEB_ORIGIN_LABELS[k], description: val } : null
    })
    .filter(Boolean)
  if (!items.length) return null
  return <DefinitionList items={items} />
}

/* DÉCISION FONDATEUR 2026-08-18 — « toutes les questions et les détails
   doivent atteindre l'ERP » : le questionnaire web (JSON complet, clés
   variables selon le profil du prospect) et l'estimation montrée au visiteur
   arrivent déjà par le GET détail (LeadSerializer __all__) mais n'avaient
   AUCUNE place à l'écran. Section conditionnelle (SectionsPane), repliée par
   défaut, PURE AFFICHAGE — aucun TRACKED_KEYS, aucun draft : jamais éditée
   ici, même patron lecture seule que SectionOrigine ci-dessus.
   CAD150 — ce RÉCAPITULATIF reste en lecture seule ; les champs captés par
   le site (CHAMPS_SITE) se CORRIGENT, eux, dans « Qualification (site ou
   appel) » et dans le profil énergétique, avec leur provenance. */

// (a) Colonnes structurées (QK1/QW2/QW3) — libellés FR humains ; la VALEUR
// reste brute (choix serveur — apps/crm/models.py Lead.*.TextChoices) sauf
// les quelques types illisibles tels quels (booléen, horodatage, liste de
// clés) : ceux-ci sont mis en forme par `formatStructured` ci-dessous.
const STRUCTURED_LABELS = {
  distributeur: 'Distributeur',
  roof_age: 'Âge du toit',
  ownership: 'Propriétaire/locataire',
  project_timeline: 'Horizon du projet',
  financing_intent: 'Financement envisagé',
  futures_charges: 'Charges futures',
  facility_type: "Type d'établissement",
  site_count: 'Nombre de sites',
  visit_window_part: 'Créneau de visite souhaité',
  visit_window_week: 'Semaine de visite souhaitée',
  client_ref: 'Référence client (site)',
  phone_is_foreign: 'Téléphone étranger',
  page: "Page d'origine",
  whatsapp_opt_in: 'Consentement WhatsApp',
  consent_timestamp: 'Consentement (horodatage)',
  utm_content: 'UTM content',
  utm_term: 'UTM terme',
  roof_type: 'Type de toiture (site)',
  bill_kwh: 'Consommation (site, kWh)',
}

// futures_charges = liste de clés parmi ('clim', 've', 'pompe') — voir
// apps/crm/models.py Lead.FUTURES_CHARGES_KEYS.
const FUTURES_CHARGES_LABELS = { clim: 'Climatisation', ve: 'Véhicule électrique', pompe: 'Pompe' }

function formatStructured(key, value) {
  if (key === 'phone_is_foreign' || key === 'whatsapp_opt_in') return value ? 'Oui' : 'Non'
  if (key === 'consent_timestamp') return formatDateTime(value, { long: true })
  if (key === 'roof_age') return `${value} ans`
  if (key === 'bill_kwh') return `${value} kWh`
  if (key === 'futures_charges') {
    const arr = Array.isArray(value) ? value : []
    return arr.map((k) => FUTURES_CHARGES_LABELS[k] || k).join(', ')
  }
  return String(value)
}

// (b)/(c) — humanise une clé snake_case/camelCase GÉNÉRIQUE : ni les
// questions du questionnaire ni les chiffres montrés n'ont un vocabulaire
// fixe (ils varient selon le profil du prospect côté site) — un fallback
// générique, jamais une table à maintenir à la main pour chaque nouvelle clé.
function humaniser(cle) {
  const mots = String(cle)
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2') // camelCase → mots séparés
    .replace(/_/g, ' ')
    .toLowerCase()
    .trim()
  if (!mots) return String(cle)
  return mots.charAt(0).toUpperCase() + mots.slice(1)
}

// (c) web_estimate est un ENSEMBLE FERMÉ de clés (whitelist serveur
// _ESTIMATE_SHOWN_KEYS, apps/crm/webhooks.py) : on connaît donc l'unité de
// chacune — appliquée seulement ici (« unités seulement si la clé les rend
// évidentes »). Une clé future non listée retombe sur `humaniser()`, sans
// unité inventée.
const ESTIMATE_LABELS = {
  kwc: 'Puissance (kWc)',
  prodKwh: 'Production (kWh/an)',
  ecoMadMonthLow: 'Économie mensuelle min (MAD)',
  ecoMadMonthHigh: 'Économie mensuelle max (MAD)',
  ecoMadYearLow: 'Économie annuelle min (MAD)',
  ecoMadYearHigh: 'Économie annuelle max (MAD)',
  paybackLabel: 'Retour sur investissement',
  tauxAutoconso: "Taux d'autoconsommation (%)",
  tauxCouverture: 'Taux de couverture (%)',
  pompeCv: 'Puissance pompe (CV)',
  champKwc: 'Champ solaire (kWc)',
  m3Jour: 'Débit (m³/j)',
  nbPanneaux: 'Nombre de panneaux',
  // `bassinM3` est un VOLUME de stockage (m³), pas un débit journalier : le
  // tunnel pose `s.bassinM3 = ag.m3Jour` = le besoin d'UNE journée de pointe,
  // borne basse de la fourchette 1-3× montrée au visiteur (lead.ts:231, et la
  // proposition l'affiche « Bassin recommandé … m³ »). L'unité du libellé suit
  // donc la donnée réelle — jamais « m³/j », qui en ferait un débit.
  bassinM3: 'Bassin recommandé (m³)',
}

function itemsFromStructured(server) {
  return WEB_QUESTIONNAIRE_STRUCTURED_FIELDS
    .map((k) => (estValeurWebRenseignee(server[k])
      ? { term: STRUCTURED_LABELS[k] || humaniser(k), description: formatStructured(k, server[k]) }
      : null))
    .filter(Boolean)
}

// RÈGLE DURE : une clé vide/absente du JSON n'est JAMAIS rendue (jamais de
// « 0 » par défaut, jamais de placeholder) — filtrée avant le map.
// Les booléens du blob (weekend, piscine, has_generator… — acceptés tels quels
// par `_bool()` dans webhooks._extract_web_questionnaire) sont rendus « Oui »/
// « Non » comme la moitié STRUCTURÉE de la même section (formatStructured) :
// un CRM français n'affiche pas « Weekend : true » sous « Téléphone étranger :
// Non ».
function formatValeurWeb(v) {
  if (typeof v === 'boolean') return v ? 'Oui' : 'Non'
  return String(v)
}

function itemsFromObject(obj, labels) {
  return Object.entries(obj || {})
    .filter(([, v]) => estValeurWebRenseignee(v))
    .map(([k, v]) => ({ term: (labels && labels[k]) || humaniser(k), description: formatValeurWeb(v) }))
}

export function SectionWebQuestionnaire({ state }) {
  const server = state.server || {}
  const structures = itemsFromStructured(server)
  const questionnaire = itemsFromObject(server.web_questionnaire, null)
  const estimation = itemsFromObject(server.web_estimate, ESTIMATE_LABELS)

  if (!structures.length && !questionnaire.length && !estimation.length) return null

  return (
    <>
      {!!structures.length && <DefinitionList items={structures} />}
      {!!questionnaire.length && (
        <>
          <p className="form-label mt-3">Détails du questionnaire</p>
          <DefinitionList items={questionnaire} />
        </>
      )}
      {!!estimation.length && (
        <>
          <p className="form-label mt-3">Estimation montrée au visiteur</p>
          <DefinitionList items={estimation} />
        </>
      )}
    </>
  )
}

// LW11 — Compléments : Note générale + Champs personnalisés — ENFIN dans la nav
// (orphelins du scroll-spy avant, recon 01 §6.9).
// RÈGLE FONDATEUR 08/09/2026 — seul champ de cette section hors FormField (un
// <label htmlFor>/<textarea> bruts) : l'erreur serveur est donc affichée à la
// main, dans le MÊME langage visuel qu'un FormField (rouge, role="alert",
// juste sous le contrôle) plutôt que de restructurer le balisage existant.
export default function SectionDivers({ state, setField, errors = {} }) {
  const note = getField(state, 'note') ?? ''
  const customData = getField(state, 'custom_data') || {}
  return (
    <>
      <div className="form-group">
        <label className="form-label" htmlFor="lf-note">Note générale</label>
        <textarea
          id="lf-note"
          className={errors.note ? 'form-control is-invalid' : 'form-control'}
          aria-invalid={errors.note ? true : undefined}
          rows={2}
          value={note} onChange={(e) => setField('note', e.target.value)}
        />
        {errors.note && <p role="alert" className="text-xs text-destructive">{errors.note}</p>}
      </div>
      <CustomFieldsInput
        module="lead"
        value={customData}
        onChange={(obj) => setField('custom_data', obj)}
      />
      <QualificationSite state={state} setField={setField} errors={errors} />
    </>
  )
}
