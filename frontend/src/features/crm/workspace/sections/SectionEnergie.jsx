import { FormField, Input } from '../../../../ui'
import { getField } from '../draftCore'
import { jumpToField } from '../jumpToField'

const RACCORDEMENTS = { monophase: 'Monophasé', triphase: 'Triphasé', inconnu: 'Je ne sais pas' }

// L-FRONT lot 4 (contrat L-BACK, 24/08) — créneaux horaires par équipement.
// source-choix: crm.Lead.equip_chauffe_eau_creneau
const CRENEAU_CHAUFFE_EAU = { matin: 'Matin', soir: 'Soir', nuit: 'Nuit', journee: 'Journée' }
// source-choix: crm.Lead.equip_ve_creneau
const CRENEAU_VE = { nuit: 'Nuit', jour: 'Jour', soir: 'Soir' }
// L-FRONT lot 5 (contrat L-BACK2, 24/08) — mêmes 4 créneaux pour clim/piscine.
// source-choix: crm.Lead.equip_clim_creneau / crm.Lead.equip_piscine_creneau
const CRENEAU_JOUR = { matin: 'Matin', apres_midi: 'Après-midi', soir: 'Soir', journee: 'Toute la journée' }

// L4 (extension fondateur) — présence en journée, script d'appel. Mêmes
// clés que crm.Lead.OccupationJour et courbes_journalieres._occupation.
const OCCUPATION_JOUR = {
  present: 'Présent en journée',
  absent: 'Absent en journée',
  partiel: 'Présence partielle (télétravail/mi-temps)',
}

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

// L4 (21/08/2026) — tri-état Oui/Non/Inconnu : un booléen `null=True` sur le
// lead veut dire « question pas encore posée », JAMAIS « Non ». Une case à
// cocher classique (comme `ete_differente`/`regularisation_8221`, toutes deux
// `default=False`) collapse null à false — ce composant garde les trois états
// distincts, `''`/`null` affiché comme « — » (pas encore demandé).
function triStateValue(v) {
  if (v === true) return 'oui'
  if (v === false) return 'non'
  return ''
}
function onTriStateChange(setField, key) {
  return (e) => {
    const val = e.target.value
    setField(key, val === 'oui' ? true : val === 'non' ? false : null)
  }
}
function TriStateSelect({ id, value, onChange }) {
  return (
    <select id={id} className="form-select" value={triStateValue(value)} onChange={onChange}>
      <option value="">— (pas encore demandé)</option>
      <option value="oui">Oui</option>
      <option value="non">Non</option>
    </select>
  )
}

// L4 (+ extension fondateur) — « Questionnaire d'appel » : TOUTES les
// questions à poser au téléphone pour composer le profil de consommation
// (apps/ventes/courbes_journalieres.py `_occupation`/`_equipements`). Le
// label EST le script d'appel — la question exacte à poser, mot pour mot.
// Occupation + équipements sont des champs à part entière ici ; les
// questions déjà portées par d'AUTRES champs du lead (raccordement mono/tri,
// factures kWh saisonnières) ne sont PAS dupliquées — un lien d'ancrage les
// pointe vers leur bloc existant (zéro second état pour la même donnée). Les
// champs de grandeur (kW/pièces/km) n'ont AUCUNE valeur préremplie : pas de
// source fiable pour un défaut chiffré (règle « zéro chiffre inventé ») — le
// commercial saisit la valeur réelle, ou laisse vide.
const AUTRES_QUESTIONS_APPEL = [
  { label: 'Raccordement : monophasé ou triphasé ?', section: 'energie', field: 'lf-raccordement' },
  { label: 'Facture mensuelle (MAD/kWh)', section: 'energie', field: 'lf-facture-hiver' },
  { label: "L'été est différent de l'hiver ?", section: 'energie', field: 'lf-facture-hiver' },
]

export function SectionEquipements({ state, setField }) {
  const v = (k) => getField(state, k) ?? ''
  const piscine = getField(state, 'equip_piscine')
  const ve = getField(state, 'equip_voiture_electrique')
  const clim = getField(state, 'equip_clim')
  return (
    <>
      <div className="form-row">
        <FormField
          label="Y a-t-il quelqu'un à la maison en journée ?"
          htmlFor="lf-occupation-jour"
        >
          <select
            id="lf-occupation-jour" className="form-select"
            value={v('occupation_jour')}
            onChange={(e) => setField('occupation_jour', e.target.value)}
          >
            {enumOptions(OCCUPATION_JOUR)}
          </select>
        </FormField>
      </div>
      <div className="form-row">
        <FormField label="Avez-vous une piscine ?" htmlFor="lf-equip-piscine">
          <TriStateSelect
            id="lf-equip-piscine" value={piscine}
            onChange={onTriStateChange(setField, 'equip_piscine')}
          />
        </FormField>
        {piscine === true && (
          <FormField
            label="Puissance de la pompe de filtration (kW)"
            htmlFor="lf-equip-piscine-kw"
          >
            <Input
              id="lf-equip-piscine-kw" type="number" step="any"
              placeholder="plaque signalétique du moteur"
              value={v('equip_piscine_pompe_kw')}
              onChange={(e) => setField('equip_piscine_pompe_kw', e.target.value)}
            />
          </FormField>
        )}
      </div>
      {/* L-FRONT lot 4 (contrat L-BACK, 24/08) — grandeur complémentaire pour
          estimation_conso : la puissance de pompe reste `equip_piscine_pompe_kw`
          (question script d'appel ci-dessus, seule kW retenue par le moteur —
          aucune clé « kw estimation » séparée n'existe côté serveur). */}
      {piscine === true && (
        <div className="form-row">
          <FormField label="Heures de filtration par jour" htmlFor="lf-equip-piscine-heures">
            <Input
              id="lf-equip-piscine-heures" type="number" step="any" min="0" max="24" placeholder="ex: 6"
              value={v('equip_piscine_heures_jour')}
              onChange={(e) => setField('equip_piscine_heures_jour', e.target.value)}
            />
          </FormField>
          <FormField label="Quand la pompe tourne-t-elle le plus ?" htmlFor="lf-equip-piscine-creneau">
            <select
              id="lf-equip-piscine-creneau" className="form-select"
              value={v('equip_piscine_creneau')}
              onChange={(e) => setField('equip_piscine_creneau', e.target.value)}
            >
              {enumOptions(CRENEAU_JOUR)}
            </select>
          </FormField>
        </div>
      )}
      <div className="form-row">
        <FormField
          label="Avez-vous ou prévoyez-vous un véhicule électrique ?"
          htmlFor="lf-equip-ve"
        >
          <TriStateSelect
            id="lf-equip-ve" value={ve}
            onChange={onTriStateChange(setField, 'equip_voiture_electrique')}
          />
        </FormField>
        {ve === true && (
          <FormField
            label={<>Combien de km par semaine avec ce véhicule ?<span className="req-auto"> *</span></>}
            htmlFor="lf-equip-ve-km"
          >
            <Input
              id="lf-equip-ve-km" type="number" step="any" placeholder="ex: 150"
              value={v('equip_ve_km_semaine')}
              onChange={(e) => setField('equip_ve_km_semaine', e.target.value)}
            />
          </FormField>
        )}
      </div>
      {ve === true && (
        <div className="form-row">
          <FormField label="Puissance du chargeur/borne (kW)" htmlFor="lf-equip-ve-chargeur-kw">
            <Input
              id="lf-equip-ve-chargeur-kw" type="number" step="any" placeholder="ex: 7.4"
              value={v('equip_ve_chargeur_kw')}
              onChange={(e) => setField('equip_ve_chargeur_kw', e.target.value)}
            />
          </FormField>
          <FormField label="Quand rechargez-vous le plus souvent ?" htmlFor="lf-equip-ve-creneau">
            <select
              id="lf-equip-ve-creneau" className="form-select"
              value={v('equip_ve_creneau')}
              onChange={(e) => setField('equip_ve_creneau', e.target.value)}
            >
              {enumOptions(CRENEAU_VE)}
            </select>
          </FormField>
        </div>
      )}
      <div className="form-row">
        <FormField label="Avez-vous la climatisation ?" htmlFor="lf-equip-clim">
          <TriStateSelect
            id="lf-equip-clim" value={clim}
            onChange={onTriStateChange(setField, 'equip_clim')}
          />
        </FormField>
        {clim === true && (
          <FormField label="Combien de pièces/unités climatisées ?" htmlFor="lf-equip-clim-pieces">
            <Input
              id="lf-equip-clim-pieces" type="number" step="1" min="0" placeholder="ex: 2"
              value={v('equip_clim_pieces')}
              onChange={(e) => setField('equip_clim_pieces', e.target.value)}
            />
          </FormField>
        )}
      </div>
      {clim === true && (
        <div className="form-row">
          <FormField label="Puissance totale climatisation (kW)" htmlFor="lf-equip-clim-kw">
            <Input
              id="lf-equip-clim-kw" type="number" step="any" placeholder="ex: 2.8"
              value={v('equip_clim_kw')}
              onChange={(e) => setField('equip_clim_kw', e.target.value)}
            />
          </FormField>
          <FormField label="Quand la clim tourne-t-elle le plus ?" htmlFor="lf-equip-clim-creneau">
            <select
              id="lf-equip-clim-creneau" className="form-select"
              value={v('equip_clim_creneau')}
              onChange={(e) => setField('equip_clim_creneau', e.target.value)}
            >
              {enumOptions(CRENEAU_JOUR)}
            </select>
          </FormField>
        </div>
      )}
      <div className="form-row">
        <FormField label="Votre chauffe-eau est-il électrique ?" htmlFor="lf-equip-chauffe-eau">
          <TriStateSelect
            id="lf-equip-chauffe-eau" value={getField(state, 'equip_chauffe_eau_electrique')}
            onChange={onTriStateChange(setField, 'equip_chauffe_eau_electrique')}
          />
        </FormField>
      </div>
      {getField(state, 'equip_chauffe_eau_electrique') === true && (
        <div className="form-row">
          <FormField label="Puissance chauffe-eau (kW)" htmlFor="lf-equip-chauffe-eau-kw">
            <Input
              id="lf-equip-chauffe-eau-kw" type="number" step="any" placeholder="ex: 2.4"
              value={v('equip_chauffe_eau_kw')}
              onChange={(e) => setField('equip_chauffe_eau_kw', e.target.value)}
            />
          </FormField>
          <FormField label="Créneau de chauffe principal" htmlFor="lf-equip-chauffe-eau-creneau">
            <select
              id="lf-equip-chauffe-eau-creneau" className="form-select"
              value={v('equip_chauffe_eau_creneau')}
              onChange={(e) => setField('equip_chauffe_eau_creneau', e.target.value)}
            >
              {enumOptions(CRENEAU_CHAUFFE_EAU)}
            </select>
          </FormField>
        </div>
      )}
      <p className="gen-hint">
        <span className="req-auto">*</span> Km/semaine obligatoire pour chiffrer la recharge
        (aucun défaut : conversion ADEME 19,8 kWh/100 km). Sans grandeur réelle saisie, l&apos;
        équipement n&apos;ajuste pas la courbe de consommation.
      </p>
      {/* Autres questions du même appel, déjà portées par d'autres champs du
          lead — un lien saute au bloc existant plutôt que de le dupliquer
          (zéro second état pour la même donnée). */}
      <div className="lw-todo" role="group" aria-label="Autres questions du script d'appel">
        <span className="lw-todo-label">Aussi à demander (déjà ailleurs sur la fiche)</span>
        {AUTRES_QUESTIONS_APPEL.map((q) => (
          <button
            key={q.label}
            type="button"
            className="lw-todo-chip"
            onClick={() => jumpToField({ section: q.section, field: q.field })}
          >
            {q.label}
          </button>
        ))}
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
