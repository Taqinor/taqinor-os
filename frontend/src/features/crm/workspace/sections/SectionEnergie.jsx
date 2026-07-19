import { FormField, Input } from '../../../../ui'
import { getField } from '../draftCore'

const RACCORDEMENTS = { monophase: 'Monophasé', triphase: 'Triphasé', inconnu: 'Je ne sais pas' }

const enumOptions = (labels) => [
  <option key="" value="">—</option>,
  ...Object.entries(labels).map(([k, l]) => <option key={k} value={k}>{l}</option>),
]

// LW11 — Profil énergétique : facture hiver/été (la saisie facture inline
// devient le champ normal — l'autosauvegarde rend le raccourci redondant,
// blueprint D3), ete_differente, conso, tranche, raccordement, 82-21.
// Le placeholder « ex: 650 » sur #lf-facture-hiver est un contrat e2e.
export default function SectionEnergie({ state, setField }) {
  const v = (k) => getField(state, k) ?? ''
  const eteDifferente = !!getField(state, 'ete_differente')
  const regularisation = !!getField(state, 'regularisation_8221')
  return (
    <>
      <div className="form-row">
        <FormField
          label={eteDifferente ? 'Facture Hiver (MAD/mois)' : 'Facture mensuelle (MAD/mois)'}
          htmlFor="lf-facture-hiver"
        >
          <Input
            id="lf-facture-hiver" type="number" step="any" placeholder="ex: 650"
            value={v('facture_hiver')} onChange={(e) => setField('facture_hiver', e.target.value)}
          />
        </FormField>
        <div className="form-group" style={{ alignSelf: 'flex-end' }}>
          <label className="pdf-toggle">
            <input
              type="checkbox" checked={eteDifferente}
              onChange={(e) => setField('ete_differente', e.target.checked)}
            />
            <span>L&apos;été est différent de l&apos;hiver ?</span>
          </label>
        </div>
        {eteDifferente && (
          <FormField label="Facture Été (MAD/mois)" htmlFor="lf-facture-ete">
            <Input
              id="lf-facture-ete" type="number" step="any" placeholder="ex: 420"
              value={v('facture_ete')} onChange={(e) => setField('facture_ete', e.target.value)}
            />
          </FormField>
        )}
      </div>
      <div className="form-row">
        <FormField label="Conso mensuelle (kWh)" htmlFor="lf-conso-mensuelle">
          <Input id="lf-conso-mensuelle" type="number" step="any" value={v('conso_mensuelle_kwh')} onChange={(e) => setField('conso_mensuelle_kwh', e.target.value)} />
        </FormField>
        <FormField label="Tarif / tranche ONEE" htmlFor="lf-tranche-onee">
          <Input id="lf-tranche-onee" value={v('tranche_onee')} onChange={(e) => setField('tranche_onee', e.target.value)} />
        </FormField>
        <FormField label="Raccordement" htmlFor="lf-raccordement">
          <select id="lf-raccordement" className="form-select" value={v('raccordement')} onChange={(e) => setField('raccordement', e.target.value)}>
            {enumOptions(RACCORDEMENTS)}
          </select>
        </FormField>
        <div className="form-group" style={{ alignSelf: 'flex-end' }}>
          <label className="pdf-toggle">
            <input
              type="checkbox" checked={regularisation}
              onChange={(e) => setField('regularisation_8221', e.target.checked)}
            />
            <span>Installation existante à régulariser ? (82-21)</span>
          </label>
        </div>
      </div>
    </>
  )
}

// Sous-bloc Pompage (agricole) — nav-section dédiée, mais fichier ÉNERGIE
// (blueprint file map). Champs requis pour le devis automatique.
export function SectionPompage({ state, setField }) {
  const v = (k) => getField(state, k) ?? ''
  return (
    <>
      <div className="form-row">
        <FormField label={<>Pompe (CV)<span className="req-auto"> *</span></>} htmlFor="lf-pompe-cv">
          <Input id="lf-pompe-cv" type="number" step="any" placeholder="ex: 10" value={v('pompe_cv')} onChange={(e) => setField('pompe_cv', e.target.value)} />
        </FormField>
        <FormField label={<>HMT (m)<span className="req-auto"> *</span></>} htmlFor="lf-pompe-hmt">
          <Input id="lf-pompe-hmt" type="number" step="any" placeholder="ex: 80" value={v('pompe_hmt_m')} onChange={(e) => setField('pompe_hmt_m', e.target.value)} />
        </FormField>
        <FormField label={<>Débit souhaité (m³/h)<span className="req-auto"> *</span></>} htmlFor="lf-pompe-debit">
          <Input id="lf-pompe-debit" type="number" step="any" placeholder="ex: 12" value={v('pompe_debit_m3h')} onChange={(e) => setField('pompe_debit_m3h', e.target.value)} />
        </FormField>
      </div>
      <p className="gen-hint">
        <span className="req-auto">*</span> Requis pour le devis automatique en mode agricole.
      </p>
    </>
  )
}
