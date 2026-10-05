import { useEffect, useState } from 'react'
import { FormField, Input } from '../../../../ui'
import crmApi from '../../../../api/crmApi'
import { getField } from '../draftCore'
import TraceToitClient from './TraceToitClient'
// STKCAT10 — LE MÊME sélecteur de structures que le générateur de devis
// (décision fondateur 16/09/2026) : la fiche lead épingle un PRODUIT du
// catalogue (`structure_produit`, STKCAT9) — une pergola, un carport, un bac
// lesté — au lieu du seul couple acier/aluminium. Le composant rend le champ
// acier/aluminium d'hier en REPLI quand la société n'a aucune catégorie typée
// « structure » : cette section ne perd jamais son contrôle.
import StructureSelector from '../../../stock/StructureSelector'
import { enumOptions } from './enumOptions'

const TYPES_TOITURE = {
  terrasse_beton: 'Terrasse béton', tole_metal: 'Tôle/Métal', tuiles: 'Tuiles',
  bac_acier: 'Bac acier', fibrociment: 'Fibrociment', autre: 'Autre',
}
const ORIENTATIONS = {
  sud: 'Sud', sud_est: 'Sud-Est', sud_ouest: 'Sud-Ouest',
  est: 'Est', ouest: 'Ouest', autre: 'Autre',
}
const OMBRAGES = { aucun: 'Aucun', partiel: 'Partiel', important: 'Important' }
const STRUCTURES = { acier: 'Acier', aluminium: 'Aluminium' }
const BATTERIES = { sans: 'Sans batterie', avec: 'Avec batterie', les_deux: 'Les deux options' }

const MOIS_FR = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']

// « 2026-07 » → « juillet 2026 » ; absent/illisible → '' (jamais approximé).
function moisFr(valeur) {
  const m = /^(\d{4})-(\d{2})/.exec(valeur ?? '')
  const mois = m ? MOIS_FR[Number(m[2]) - 1] : null
  return mois ? `${mois} ${m[1]}` : ''
}

// AGR517 — « Références de pompage proches » d'un lead AGRICOLE. Lecture
// seule : le serveur choisit, trie (distance croissante) et borne ; aucun
// chiffre n'est calculé ici. Liste vide = on le dit, on ne cite jamais un toit.
function ReferencesProches({ leadId }) {
  const [refs, setRefs] = useState(null)
  useEffect(() => {
    let vivant = true
    Promise.resolve()
      .then(() => crmApi.getLeadReferencesProches(leadId))
      .then((r) => { if (vivant) setRefs(r?.data?.references ?? []) })
      .catch(() => { if (vivant) setRefs([]) })
    return () => { vivant = false }
  }, [leadId])
  if (refs === null) return null
  return (
    <div data-testid="references-proches" className="mb-3">
      <p className="form-label">Références de pompage proches</p>
      {refs.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Aucune réalisation de pompage saisie : rien à montrer — ne citez
          jamais un toit à la place.
        </p>
      ) : (
        <ul className="space-y-1.5">
          {refs.map((r) => (
            <li key={r.id} data-testid="reference-proche" className="text-sm">
              <span className="font-medium">{r.titre}</span>
              {' — '}{r.ville}
              {r.distance_km != null ? ` (${r.distance_km} km)` : ''}
              {moisFr(r.mise_en_service) ? ` — mise en service ${moisFr(r.mise_en_service)}` : ''}
              {r.url_page && (
                <>
                  {' — '}
                  <a href={r.url_page} target="_blank" rel="noreferrer noopener"
                     className="underline">page publique</a>
                </>
              )}
              {r.lien_video && (
                <>
                  {' — '}
                  <a href={r.lien_video} target="_blank" rel="noreferrer noopener"
                     className="underline">vidéo</a>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// LW11 — Toiture & site : port 1:1 des champs (recon 01 §2).
// L-DESSIN (fondateur 25/08/2026) — en TÊTE de section, le tracé que le client
// a dessiné sur la carte du site public. `roof_point`/`roof_outline` sont des
// champs SERVEUR en lecture seule (jamais éditables ici) : on les lit donc sur
// `state.server` via getField, comme IdentityRail.
export default function SectionSite({ state, setField, errors = {} }) {
  const v = (k) => getField(state, k) ?? ''
  const leadId = state?.server?.id ?? null
  return (
    <>
      {getField(state, 'type_installation') === 'agricole' && leadId != null && (
        <ReferencesProches leadId={leadId} />
      )}
      {/* VT13 — `leadId` (id serveur du lead, jamais un brouillon) laisse le
          bloc demander au serveur la photo réelle du toit issue de la visite
          terrain validée ; absent (création), rien ne change. */}
      <TraceToitClient
        contour={getField(state, 'roof_outline')}
        epingle={getField(state, 'roof_point')}
        leadId={state?.server?.id ?? null}
      />
      <div className="form-row">
        <FormField label="Type de toiture" htmlFor="lf-type-toiture" error={errors.type_toiture}>
          <select
            id="lf-type-toiture" className={errors.type_toiture ? 'form-select is-invalid' : 'form-select'}
            aria-invalid={errors.type_toiture ? true : undefined}
            value={v('type_toiture')} onChange={(e) => setField('type_toiture', e.target.value)}
          >
            {enumOptions(TYPES_TOITURE)}
          </select>
        </FormField>
        <FormField label="Surface (m²)" htmlFor="lf-surface-toiture" error={errors.surface_toiture_m2}>
          <Input
            id="lf-surface-toiture" type="number" step="any" invalid={!!errors.surface_toiture_m2}
            value={v('surface_toiture_m2')} onChange={(e) => setField('surface_toiture_m2', e.target.value)}
          />
        </FormField>
        <FormField label="Taille souhaitée (kWc)" htmlFor="lf-taille-souhaitee" error={errors.taille_souhaitee_kwc}>
          <Input
            id="lf-taille-souhaitee" type="number" step="any" invalid={!!errors.taille_souhaitee_kwc}
            value={v('taille_souhaitee_kwc')} onChange={(e) => setField('taille_souhaitee_kwc', e.target.value)}
          />
        </FormField>
        <FormField label="Batterie" htmlFor="lf-batterie" error={errors.batterie_souhaitee}>
          <select
            id="lf-batterie" className={errors.batterie_souhaitee ? 'form-select is-invalid' : 'form-select'}
            aria-invalid={errors.batterie_souhaitee ? true : undefined}
            value={v('batterie_souhaitee')} onChange={(e) => setField('batterie_souhaitee', e.target.value)}
          >
            {enumOptions(BATTERIES)}
          </select>
        </FormField>
      </div>
      <div className="form-row">
        <FormField label="Orientation" htmlFor="lf-orientation" error={errors.orientation}>
          <select
            id="lf-orientation" className={errors.orientation ? 'form-select is-invalid' : 'form-select'}
            aria-invalid={errors.orientation ? true : undefined}
            value={v('orientation')} onChange={(e) => setField('orientation', e.target.value)}
          >
            {enumOptions(ORIENTATIONS)}
          </select>
        </FormField>
        <FormField label="Inclinaison / pente (°)" htmlFor="lf-inclinaison" error={errors.inclinaison_deg}>
          <Input
            id="lf-inclinaison" type="number" step="any" invalid={!!errors.inclinaison_deg}
            value={v('inclinaison_deg')} onChange={(e) => setField('inclinaison_deg', e.target.value)}
          />
        </FormField>
        <FormField label="Ombrage" htmlFor="lf-ombrage" error={errors.ombrage}>
          <select
            id="lf-ombrage" className={errors.ombrage ? 'form-select is-invalid' : 'form-select'}
            aria-invalid={errors.ombrage ? true : undefined}
            value={v('ombrage')} onChange={(e) => setField('ombrage', e.target.value)}
          >
            {enumOptions(OMBRAGES)}
          </select>
        </FormField>
        <div className="form-group fg-grow">
          <FormField label="Notes ombrage" htmlFor="lf-ombrage-notes" error={errors.ombrage_notes}>
            <Input
              id="lf-ombrage-notes" invalid={!!errors.ombrage_notes}
              value={v('ombrage_notes')} onChange={(e) => setField('ombrage_notes', e.target.value)}
            />
          </FormField>
        </div>
      </div>
      <div className="form-row">
        {/* STKCAT10 — le champ « Structure » est piloté par le CATALOGUE ;
            `fallback` = le champ acier/aluminium d'hier, au caractère près,
            rendu tel quel tant qu'aucune structure typée n'existe. Le
            sélecteur écrit `structure_produit` par le MÊME `setField` que les
            autres champs : le chemin d'enregistrement de la fiche est
            inchangé (la garde de société vit côté serveur, STKCAT9). */}
        <StructureSelector
          id="lf-structure-produit"
          label="Structure"
          value={v('structure_produit')}
          onChange={(val) => setField('structure_produit', val)}
          error={errors.structure_produit}
          fallback={(
            <FormField label="Structure" htmlFor="lf-structure" error={errors.structure_pref}>
              <select
                id="lf-structure" className={errors.structure_pref ? 'form-select is-invalid' : 'form-select'}
                aria-invalid={errors.structure_pref ? true : undefined}
                value={v('structure_pref')} onChange={(e) => setField('structure_pref', e.target.value)}
              >
                {enumOptions(STRUCTURES)}
              </select>
            </FormField>
          )}
        />
        <FormField label="Étages / hauteur" htmlFor="lf-nb-etages" error={errors.nb_etages}>
          <Input
            id="lf-nb-etages" type="number" step="any" invalid={!!errors.nb_etages}
            value={v('nb_etages')} onChange={(e) => setField('nb_etages', e.target.value)}
          />
        </FormField>
      </div>
    </>
  )
}
