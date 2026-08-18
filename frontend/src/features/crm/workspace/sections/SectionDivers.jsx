import { DefinitionList } from '../../../../ui'
import { formatDateTime } from '../../../../lib/format'
import {
  getField, WEB_ORIGIN_FIELDS, WEB_QUESTIONNAIRE_STRUCTURED_FIELDS, estValeurWebRenseignee,
} from '../draftCore'
import CustomFieldsInput from '../../../../components/CustomFieldsInput'

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
   ici, même patron lecture seule que SectionOrigine ci-dessus. */

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
function itemsFromObject(obj, labels) {
  return Object.entries(obj || {})
    .filter(([, v]) => estValeurWebRenseignee(v))
    .map(([k, v]) => ({ term: (labels && labels[k]) || humaniser(k), description: String(v) }))
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
export default function SectionDivers({ state, setField }) {
  const note = getField(state, 'note') ?? ''
  const customData = getField(state, 'custom_data') || {}
  return (
    <>
      <div className="form-group">
        <label className="form-label" htmlFor="lf-note">Note générale</label>
        <textarea
          id="lf-note" className="form-control" rows={2}
          value={note} onChange={(e) => setField('note', e.target.value)}
        />
      </div>
      <CustomFieldsInput
        module="lead"
        value={customData}
        onChange={(obj) => setField('custom_data', obj)}
      />
    </>
  )
}
