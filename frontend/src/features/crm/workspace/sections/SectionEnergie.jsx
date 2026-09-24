import { useState } from 'react'
import { FormField, Input } from '../../../../ui'
import { factureAuMois, getField } from '../draftCore'
import { jumpToField } from '../jumpToField'
// CAD157 — les mentions « ce que le chiffre ne compte pas » : UNE source de
// texte (le script d'appel guidé), partagée par la fiche et le panneau.
import { NON_COMPTE_PLAQUE, NON_COMPTE_TRANCHE_ONEE } from '../../relances/appelGuidance'
import { ChampSite } from './SectionDivers'

// CAD157 — une valeur de grandeur réellement saisie (0 compris : c'est une
// réponse, pas un silence ; `''`/null = rien de saisi).
const saisi = (valeur) => valeur !== '' && valeur !== null && valeur !== undefined

// CAD150 — distributeur d'électricité (capté par le site, désormais éditable).
// Sans lui la courbe de consommation disparaît de la proposition (règle M10).
// Les libellés historiques restent choisissables pour relire une fiche ancienne.
// source-choix: crm.Lead.distributeur
const DISTRIBUTEURS = {
  srm_tanger: 'SRM Tanger-Tétouan-Al Hoceïma',
  srm_oriental: 'SRM de l’Oriental',
  srm_fes: 'SRM Fès-Meknès',
  srm_rabat: 'SRM Rabat-Salé-Kénitra',
  srm_beni_mellal: 'SRM Béni Mellal-Khénifra',
  srm_casablanca: 'SRM Casablanca-Settat',
  srm_marrakech: 'SRM Marrakech-Safi',
  srm_draa: 'SRM Drâa-Tafilalet',
  srm_souss: 'SRM Souss-Massa',
  srm_guelmim: 'SRM Guelmim-Oued Noun',
  srm_laayoune: 'SRM Laâyoune-Sakia El Hamra',
  srm_dakhla: 'SRM Dakhla-Oued Ed-Dahab',
  onee: 'ONEE (historique)',
  lydec: 'Lydec (historique)',
  redal: 'Redal (historique)',
  amendis: 'Amendis (historique)',
  autre: 'Autre (historique)',
}

// OFFGRID (ajout produit onduleur hors réseau, backend crm.Lead.Raccordement.
// AUCUN = 'aucun') — site jamais raccordé au réseau ONEE : dérive le devis en
// composition hors réseau (voir DevisGenerator.jsx, contrôle « Raccordement »).
const RACCORDEMENTS = {
  monophase: 'Monophasé', triphase: 'Triphasé', inconnu: 'Je ne sais pas',
  aucun: 'Non raccordé (site isolé)',
}

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
export default function SectionEnergie({ state, setField, errors = {} }) {
  const v = (k) => getField(state, k) ?? ''
  const eteDifferente = !!getField(state, 'ete_differente')
  const regularisation = !!getField(state, 'regularisation_8221')
  // CAD158 — « elle couvre un mois ou deux mois ? » : sur deux mois, la
  // commerciale tape le montant de la FACTURE et c'est le montant MENSUEL
  // (÷ 2) qui part au serveur — et qui s'affiche, pour qu'elle voie ce qui
  // est enregistré. Rien n'est stocké sur la période (décision Q24).
  // Le choix vaut pour CE lead seulement : naviguer vers un autre lead le
  // remet à « 1 mois » (état keyé par `leadId`, sans effet de bord).
  const [saisiePeriode, setSaisiePeriode] = useState({ leadId: state.leadId, periodicite: 'mensuelle', montants: {} })
  const memeLead = saisiePeriode.leadId === state.leadId
  const periodicite = memeLead ? saisiePeriode.periodicite : 'mensuelle'
  const montantsFacture = memeLead ? saisiePeriode.montants : {}
  const setPeriodicite = (p) => setSaisiePeriode({ leadId: state.leadId, periodicite: p, montants: {} })
  const setMontantsFacture = (maj) => setSaisiePeriode((s) => ({
    leadId: state.leadId,
    periodicite: s.leadId === state.leadId ? s.periodicite : 'mensuelle',
    montants: maj(s.leadId === state.leadId ? s.montants : {}),
  }))
  const bimestrielle = periodicite === 'bimestrielle'
  const valeurFacture = (champ) => (bimestrielle ? (montantsFacture[champ] ?? '') : v(champ))
  const saisirFacture = (champ, brut) => {
    if (!bimestrielle) { setField(champ, brut); return }
    setMontantsFacture((m) => ({ ...m, [champ]: brut }))
    setField(champ, factureAuMois(brut, periodicite))
  }
  const indiceMensuel = (champ) => (bimestrielle && v(champ) !== ''
    ? `Enregistré au mois : ${v(champ)} MAD/mois`
    : undefined)
  return (
    <>
      <div className="form-row">
        <FormField
          label={bimestrielle
            ? `${eteDifferente ? 'Facture Hiver' : 'Facture'} — montant pour 2 mois (MAD)`
            : (eteDifferente ? 'Facture Hiver (MAD/mois)' : 'Facture mensuelle (MAD/mois)')}
          htmlFor="lf-facture-hiver"
          error={errors.facture_hiver}
          hint={indiceMensuel('facture_hiver')}
        >
          <Input
            id="lf-facture-hiver" type="number" step="any" placeholder="ex: 650" invalid={!!errors.facture_hiver}
            value={valeurFacture('facture_hiver')} onChange={(e) => saisirFacture('facture_hiver', e.target.value)}
          />
        </FormField>
        <FormField label="La facture couvre" htmlFor="lf-facture-periode" error={errors.facture_periodicite}>
          <select
            id="lf-facture-periode" className="form-select" value={periodicite}
            onChange={(e) => setPeriodicite(e.target.value)}
          >
            <option value="mensuelle">1 mois</option>
            <option value="bimestrielle">2 mois (montant ramené au mois)</option>
          </select>
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
          <FormField
            label={bimestrielle ? 'Facture Été — montant pour 2 mois (MAD)' : 'Facture Été (MAD/mois)'}
            htmlFor="lf-facture-ete" error={errors.facture_ete} hint={indiceMensuel('facture_ete')}
          >
            <Input
              id="lf-facture-ete" type="number" step="any" placeholder="ex: 420" invalid={!!errors.facture_ete}
              value={valeurFacture('facture_ete')} onChange={(e) => saisirFacture('facture_ete', e.target.value)}
            />
          </FormField>
        )}
      </div>
      <div className="form-row">
        <FormField label="Conso mensuelle (kWh)" htmlFor="lf-conso-mensuelle" error={errors.conso_mensuelle_kwh}>
          <Input
            id="lf-conso-mensuelle" type="number" step="any" invalid={!!errors.conso_mensuelle_kwh}
            value={v('conso_mensuelle_kwh')} onChange={(e) => setField('conso_mensuelle_kwh', e.target.value)}
          />
        </FormField>
        {/* CAD157 — texte libre qu'AUCUN calcul ne lit : la fiche le dit. */}
        <FormField
          label="Tarif / tranche ONEE" htmlFor="lf-tranche-onee" error={errors.tranche_onee}
          hint={NON_COMPTE_TRANCHE_ONEE}
        >
          <Input
            id="lf-tranche-onee" invalid={!!errors.tranche_onee}
            value={v('tranche_onee')} onChange={(e) => setField('tranche_onee', e.target.value)}
          />
        </FormField>
        <FormField label="Raccordement" htmlFor="lf-raccordement" error={errors.raccordement}>
          <select
            id="lf-raccordement"
            className={errors.raccordement ? 'form-select is-invalid' : 'form-select'}
            aria-invalid={errors.raccordement ? true : undefined}
            value={v('raccordement')} onChange={(e) => setField('raccordement', e.target.value)}
          >
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
      {/* CAD150 — captés par le site, TOUJOURS éditables : « à confirmer »
          tant qu'une valeur du site n'a pas été reprise explicitement. */}
      <div className="form-row">
        <ChampSite
          state={state} champ="distributeur" label="Distributeur d'électricité" htmlFor="lf-distributeur"
          error={errors.distributeur}
          renderControl={() => (
            <select
              id="lf-distributeur"
              className={errors.distributeur ? 'form-select is-invalid' : 'form-select'}
              aria-invalid={errors.distributeur ? true : undefined}
              value={v('distributeur')} onChange={(e) => setField('distributeur', e.target.value)}
            >
              {enumOptions(DISTRIBUTEURS)}
            </select>
          )}
        />
        <ChampSite
          state={state} champ="bill_kwh" label="Consommation déclarée sur le site (kWh)" htmlFor="lf-bill-kwh"
          error={errors.bill_kwh}
          renderControl={() => (
            <Input
              id="lf-bill-kwh" type="number" step="any" invalid={!!errors.bill_kwh}
              value={v('bill_kwh')} onChange={(e) => setField('bill_kwh', e.target.value)}
            />
          )}
        />
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
function TriStateSelect({ id, value, onChange, invalid = false }) {
  return (
    <select
      id={id}
      className={invalid ? 'form-select is-invalid' : 'form-select'}
      aria-invalid={invalid ? true : undefined}
      value={triStateValue(value)} onChange={onChange}
    >
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

// CAD157 — sous chaque champ de PUISSANCE d'un équipement déclaré : « pas
// compté tant que la puissance manque ». La condition suit la règle de
// composition du serveur (`apps/ventes/courbes_journalieres.py::_equipements`
// — piscine : puissance de pompe ; clim : puissance OU nombre de pièces ;
// chauffe-eau : puissance), sans rien calculer ici ; le panneau d'appel, lui,
// lit le drapeau SERVI (`panneau_appel.equipements[].compte_dans_etude`).
export function SectionEquipements({ state, setField, errors = {} }) {
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
          error={errors.occupation_jour}
        >
          <select
            id="lf-occupation-jour"
            className={errors.occupation_jour ? 'form-select is-invalid' : 'form-select'}
            aria-invalid={errors.occupation_jour ? true : undefined}
            value={v('occupation_jour')}
            onChange={(e) => setField('occupation_jour', e.target.value)}
          >
            {enumOptions(OCCUPATION_JOUR)}
          </select>
        </FormField>
      </div>
      <div className="form-row">
        <FormField label="Avez-vous une piscine ?" htmlFor="lf-equip-piscine" error={errors.equip_piscine}>
          <TriStateSelect
            id="lf-equip-piscine" value={piscine} invalid={!!errors.equip_piscine}
            onChange={onTriStateChange(setField, 'equip_piscine')}
          />
        </FormField>
        {piscine === true && (
          <FormField
            label="Puissance de la pompe de filtration (kW)"
            htmlFor="lf-equip-piscine-kw"
            error={errors.equip_piscine_pompe_kw}
            hint={saisi(v('equip_piscine_pompe_kw')) ? undefined : NON_COMPTE_PLAQUE}
          >
            <Input
              id="lf-equip-piscine-kw" type="number" step="any" invalid={!!errors.equip_piscine_pompe_kw}
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
          <FormField
            label="Heures de filtration par jour" htmlFor="lf-equip-piscine-heures"
            error={errors.equip_piscine_heures_jour}
          >
            <Input
              id="lf-equip-piscine-heures" type="number" step="any" min="0" max="24" placeholder="ex: 6"
              invalid={!!errors.equip_piscine_heures_jour}
              value={v('equip_piscine_heures_jour')}
              onChange={(e) => setField('equip_piscine_heures_jour', e.target.value)}
            />
          </FormField>
          <FormField
            label="Quand la pompe tourne-t-elle le plus ?" htmlFor="lf-equip-piscine-creneau"
            error={errors.equip_piscine_creneau}
          >
            <select
              id="lf-equip-piscine-creneau"
              className={errors.equip_piscine_creneau ? 'form-select is-invalid' : 'form-select'}
              aria-invalid={errors.equip_piscine_creneau ? true : undefined}
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
          error={errors.equip_voiture_electrique}
        >
          <TriStateSelect
            id="lf-equip-ve" value={ve} invalid={!!errors.equip_voiture_electrique}
            onChange={onTriStateChange(setField, 'equip_voiture_electrique')}
          />
        </FormField>
        {ve === true && (
          <FormField
            label={<>Combien de km par semaine avec ce véhicule ?<span className="req-auto"> *</span></>}
            htmlFor="lf-equip-ve-km"
            error={errors.equip_ve_km_semaine}
          >
            <Input
              id="lf-equip-ve-km" type="number" step="any" placeholder="ex: 150" invalid={!!errors.equip_ve_km_semaine}
              value={v('equip_ve_km_semaine')}
              onChange={(e) => setField('equip_ve_km_semaine', e.target.value)}
            />
          </FormField>
        )}
      </div>
      {ve === true && (
        <div className="form-row">
          <FormField
            label="Puissance du chargeur/borne (kW)" htmlFor="lf-equip-ve-chargeur-kw"
            error={errors.equip_ve_chargeur_kw}
          >
            <Input
              id="lf-equip-ve-chargeur-kw" type="number" step="any" placeholder="ex: 7.4"
              invalid={!!errors.equip_ve_chargeur_kw}
              value={v('equip_ve_chargeur_kw')}
              onChange={(e) => setField('equip_ve_chargeur_kw', e.target.value)}
            />
          </FormField>
          <FormField
            label="Quand rechargez-vous le plus souvent ?" htmlFor="lf-equip-ve-creneau"
            error={errors.equip_ve_creneau}
          >
            <select
              id="lf-equip-ve-creneau"
              className={errors.equip_ve_creneau ? 'form-select is-invalid' : 'form-select'}
              aria-invalid={errors.equip_ve_creneau ? true : undefined}
              value={v('equip_ve_creneau')}
              onChange={(e) => setField('equip_ve_creneau', e.target.value)}
            >
              {enumOptions(CRENEAU_VE)}
            </select>
          </FormField>
        </div>
      )}
      <div className="form-row">
        <FormField label="Avez-vous la climatisation ?" htmlFor="lf-equip-clim" error={errors.equip_clim}>
          <TriStateSelect
            id="lf-equip-clim" value={clim} invalid={!!errors.equip_clim}
            onChange={onTriStateChange(setField, 'equip_clim')}
          />
        </FormField>
        {clim === true && (
          <FormField
            label="Combien de pièces/unités climatisées ?" htmlFor="lf-equip-clim-pieces"
            error={errors.equip_clim_pieces}
          >
            <Input
              id="lf-equip-clim-pieces" type="number" step="1" min="0" placeholder="ex: 2"
              invalid={!!errors.equip_clim_pieces}
              value={v('equip_clim_pieces')}
              onChange={(e) => setField('equip_clim_pieces', e.target.value)}
            />
          </FormField>
        )}
      </div>
      {clim === true && (
        <div className="form-row">
          <FormField
            label="Puissance totale climatisation (kW)" htmlFor="lf-equip-clim-kw"
            error={errors.equip_clim_kw}
            hint={saisi(v('equip_clim_kw')) || saisi(v('equip_clim_pieces'))
              ? undefined : NON_COMPTE_PLAQUE}
          >
            <Input
              id="lf-equip-clim-kw" type="number" step="any" placeholder="ex: 2.8" invalid={!!errors.equip_clim_kw}
              value={v('equip_clim_kw')}
              onChange={(e) => setField('equip_clim_kw', e.target.value)}
            />
          </FormField>
          <FormField
            label="Quand la clim tourne-t-elle le plus ?" htmlFor="lf-equip-clim-creneau"
            error={errors.equip_clim_creneau}
          >
            <select
              id="lf-equip-clim-creneau"
              className={errors.equip_clim_creneau ? 'form-select is-invalid' : 'form-select'}
              aria-invalid={errors.equip_clim_creneau ? true : undefined}
              value={v('equip_clim_creneau')}
              onChange={(e) => setField('equip_clim_creneau', e.target.value)}
            >
              {enumOptions(CRENEAU_JOUR)}
            </select>
          </FormField>
        </div>
      )}
      <div className="form-row">
        <FormField
          label="Votre chauffe-eau est-il électrique ?" htmlFor="lf-equip-chauffe-eau"
          error={errors.equip_chauffe_eau_electrique}
        >
          <TriStateSelect
            id="lf-equip-chauffe-eau" value={getField(state, 'equip_chauffe_eau_electrique')}
            invalid={!!errors.equip_chauffe_eau_electrique}
            onChange={onTriStateChange(setField, 'equip_chauffe_eau_electrique')}
          />
        </FormField>
      </div>
      {getField(state, 'equip_chauffe_eau_electrique') === true && (
        <div className="form-row">
          <FormField
            label="Puissance chauffe-eau (kW)" htmlFor="lf-equip-chauffe-eau-kw"
            error={errors.equip_chauffe_eau_kw}
            hint={saisi(v('equip_chauffe_eau_kw')) ? undefined : NON_COMPTE_PLAQUE}
          >
            <Input
              id="lf-equip-chauffe-eau-kw" type="number" step="any" placeholder="ex: 2.4"
              invalid={!!errors.equip_chauffe_eau_kw}
              value={v('equip_chauffe_eau_kw')}
              onChange={(e) => setField('equip_chauffe_eau_kw', e.target.value)}
            />
          </FormField>
          <FormField
            label="Créneau de chauffe principal" htmlFor="lf-equip-chauffe-eau-creneau"
            error={errors.equip_chauffe_eau_creneau}
          >
            <select
              id="lf-equip-chauffe-eau-creneau"
              className={errors.equip_chauffe_eau_creneau ? 'form-select is-invalid' : 'form-select'}
              aria-invalid={errors.equip_chauffe_eau_creneau ? true : undefined}
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
export function SectionPompage({ state, setField, errors = {} }) {
  const v = (k) => getField(state, k) ?? ''
  return (
    <>
      <div className="form-row">
        <FormField
          label={<>Pompe (CV)<span className="req-auto"> *</span></>} htmlFor="lf-pompe-cv"
          error={errors.pompe_cv}
        >
          <Input
            id="lf-pompe-cv" type="number" step="any" placeholder="ex: 10" invalid={!!errors.pompe_cv}
            value={v('pompe_cv')} onChange={(e) => setField('pompe_cv', e.target.value)}
          />
        </FormField>
        <FormField
          label={<>HMT (m)<span className="req-auto"> *</span></>} htmlFor="lf-pompe-hmt"
          error={errors.pompe_hmt_m}
        >
          <Input
            id="lf-pompe-hmt" type="number" step="any" placeholder="ex: 80" invalid={!!errors.pompe_hmt_m}
            value={v('pompe_hmt_m')} onChange={(e) => setField('pompe_hmt_m', e.target.value)}
          />
        </FormField>
        <FormField
          label={<>Débit souhaité (m³/h)<span className="req-auto"> *</span></>} htmlFor="lf-pompe-debit"
          error={errors.pompe_debit_m3h}
        >
          <Input
            id="lf-pompe-debit" type="number" step="any" placeholder="ex: 12" invalid={!!errors.pompe_debit_m3h}
            value={v('pompe_debit_m3h')} onChange={(e) => setField('pompe_debit_m3h', e.target.value)}
          />
        </FormField>
      </div>
      <p className="gen-hint">
        <span className="req-auto">*</span> Requis pour le devis automatique en mode agricole.
      </p>
    </>
  )
}
