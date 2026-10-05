import { useState } from 'react'
import { FormField, Input } from '../../../../ui'
import { factureAuMois, getField } from '../draftCore'
import { jumpToField } from '../jumpToField'
import fieldLabels from '../fieldLabels'
// CAD157 — les mentions « ce que le chiffre ne compte pas » : UNE source de
// texte (le script d'appel guidé), partagée par la fiche et le panneau.
import { NON_COMPTE_PLAQUE, NON_COMPTE_TRANCHE_ONEE } from '../../relances/appelGuidance'
import { ChampSite } from './SectionDivers'
import { enumOptions } from './enumOptions'

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
              id="lf-regularisation-8221" data-field-anchor="lf-regularisation-8221"
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

// ── AGR415 — Sous-bloc Pompage (agricole) ─────────────────────────────────
// Nav-section dédiée, mais fichier ÉNERGIE (blueprint file map). Cinq blocs,
// dans l'ordre de l'APPEL : Énergie actuelle / Eau / Besoin / Pompe actuelle
// & site / Règles & aides. Chaque champ porte un libellé court (fieldLabels) et
// la QUESTION de l'appel en aide (= `help_text` serveur, contrat partagé
// `lead_pompage.json` — `SectionsRender.test.jsx` compare les deux). Aucun
// arrondi : `step="any"`, la saisie 12,5 reste 12,5.

// Vocabulaires — chacun DÉCLARE sa source serveur (garde
// scripts/check_choices_declares.py) ; libellés = ceux du modèle.
// source-choix: crm.Lead.source_eau
const SOURCE_EAU = { puits: 'Puits', forage: 'Forage', bassin: 'Bassin', riviere: 'Rivière' }
// source-choix: crm.Lead.niveau_statique_source
const NIVEAU_STATIQUE_SOURCE = {
  declare: 'Déclaré par le client', site_web: 'Saisi sur le site', mesure_visite: 'Mesuré en visite',
}
// source-choix: crm.Lead.debit_forage_source
const DEBIT_FORAGE_SOURCE = {
  essai: 'Essai de pompage', foreur: 'Donné par le foreur',
  client: 'Estimation du client', mesure_visite: 'Mesuré en visite',
}
// source-choix: crm.Lead.besoin_eau_source
const BESOIN_EAU_SOURCE = {
  client: 'Déclaré par le client', site_web: 'Saisi sur le site',
  pompe_actuelle: 'Calculé depuis la pompe actuelle',
}
// source-choix: crm.Lead.irrigation_methode
const IRRIGATION_METHODE = {
  goutte: 'Goutte-à-goutte', aspersion: 'Aspersion', gravitaire: 'Gravitaire (à la raie)',
}
// source-choix: crm.Lead.region_agricole
const REGION_AGRICOLE = {
  'souss-massa': 'Souss-Massa', doukkala: 'Doukkala', tadla: 'Tadla', saiss: 'Saïss',
  oriental: 'Oriental', 'draa-tafilalet': 'Drâa-Tafilalet', 'gharb-loukkos': 'Gharb-Loukkos',
  haouz: 'Haouz',
}
// source-choix: crm.Lead.pompe_actuelle_type
const POMPE_ACTUELLE_TYPE = { immergee: 'Immergée', surface: 'De surface', ne_sait_pas: 'Ne sait pas' }
// source-choix: crm.Lead.pompe_alim_actuelle
const POMPE_ALIM_ACTUELLE = {
  aucune: 'Aucune pompe', diesel: 'Diesel', butane: 'Butane', electrique: 'Électrique (réseau)',
}
// source-choix: crm.Lead.electricite_sur_place
const ELECTRICITE_SUR_PLACE = {
  aucune: 'Aucune', monophase: 'Monophasé', triphase: 'Triphasé', ne_sait_pas: 'Ne sait pas',
}
// source-choix: crm.Lead.autorisation_prelevement
const AUTORISATION_PRELEVEMENT = { oui: 'Oui', non: 'Non', en_cours: 'En cours', ne_sait_pas: 'Ne sait pas' }
// source-choix: crm.Lead.projet_pompage
const PROJET_POMPAGE = { existant: 'Remplacer une pompe existante', nouveau_forage: 'Nouveau forage' }
// source-choix: crm.Lead.pompe_hmt_source
const POMPE_HMT_SOURCE = { declaree: 'Déclarée', site_web: 'Saisie sur le site' }
// source-choix: crm.Lead.decideur
const DECIDEUR = {
  seul: 'Décide seul', conjoint_famille: 'Avec le conjoint / la famille',
  associe_direction: 'Avec un associé / la direction', proprietaire_tiers: 'Le propriétaire (un tiers) décide',
}

const MOIS_FR = [
  [1, 'janv.'], [2, 'févr.'], [3, 'mars'], [4, 'avr.'], [5, 'mai'], [6, 'juin'],
  [7, 'juil.'], [8, 'août'], [9, 'sept.'], [10, 'oct.'], [11, 'nov.'], [12, 'déc.'],
]

// La question orale sous chaque champ — copie du `help_text` serveur (colonnes
// de `lead_pompage.json`), gardée à l'identique par un test de contrat.
const QUESTIONS_POMPAGE = {
  source_eau: "« D'où vient l'eau : un puits, un forage, un bassin ou une rivière ? »",
  niveau_statique_m: "« À quelle profondeur se trouve l'eau quand la pompe est arrêtée ? »",
  niveau_statique_source: "« Ce niveau, vous l'avez mesuré, ou on vous l'a dit ? » (posé avec le niveau ; mesure_visite = relevé par notre technicien lors de la visite)",
  profondeur_forage_m: "« Quelle est la profondeur totale du forage ? »",
  debit_forage_m3h: "« Combien d'eau le forage peut-il donner par heure ? »",
  debit_forage_source: "« Ce débit vient d'un essai de pompage, du foreur, ou c'est votre estimation ? »",
  besoin_eau_m3j: "« De combien de mètres cubes d'eau avez-vous besoin par jour au plus fort de la saison ? »",
  besoin_eau_source: "« Ce volume, c'est votre chiffre, celui du site, ou on le calcule depuis votre pompe actuelle ? »",
  culture: "« Qu'est-ce que vous cultivez ? »",
  surface_irriguee_ha: "« Combien d'hectares irriguez-vous ? »",
  irrigation_methode: "« Vous irriguez au goutte-à-goutte, par aspersion ou à la raie (gravitaire) ? »",
  region_agricole: "« Dans quelle région se trouve l'exploitation ? »",
  pompe_actuelle_cv: "« Quelle est la puissance de votre pompe ACTUELLE, en chevaux ? »",
  pompe_actuelle_type: "« Votre pompe actuelle est-elle immergée dans le forage, ou en surface ? »",
  pompe_actuelle_debit_m3h: "« Combien d'eau votre pompe actuelle sort-elle par heure ? »",
  pompage_heures_jour: "« Combien d'heures par jour la pompe ACTUELLE tourne-t-elle ? »",
  pompe_alim_actuelle: "« Votre pompe actuelle marche à quoi — diesel, butane, électricité, ou vous n'en avez pas ? »",
  butane_bouteilles_jour: "« Combien de bouteilles de butane utilisez-vous par jour d'irrigation ? »",
  carburant_litres_mois: "« Combien de litres de carburant la pompe consomme-t-elle par mois ? »",
  carburant_prix_unitaire_mad: "« Combien payez-vous la bouteille (ou le litre) ? »",
  depense_carburant_mad_mois: "« Combien dépensez-vous en carburant par mois ? »",
  mois_irrigation: "« Quels mois de l'année irriguez-vous ? »",
  distance_forage_champ_m: "« Quelle distance entre le forage et l'endroit où on poserait les panneaux ? »",
  electricite_sur_place: "« Avez-vous l'électricité sur place : monophasé, triphasé, ou pas du tout ? »",
  autorisation_prelevement: "« Avez-vous une autorisation de prélèvement de l'agence de bassin (ABH) ? »",
  autorisation_numero: "« Quel est le numéro de cette autorisation ? »",
  autorisation_debit_l_s: "« Quel débit l'autorisation vous accorde-t-elle, en litres par seconde ? »",
  autorisation_volume_m3_an: "« Quel volume par an l'autorisation vous accorde-t-elle ? »",
  compteur_eau: "« Avez-vous un compteur d'eau sur le forage ? »",
  projet_pompage: "« C'est pour remplacer une pompe qui tourne déjà, ou pour un nouveau forage ? »",
  deja_beneficiaire_fda: "« Avez-vous déjà reçu une aide du Fonds de développement agricole (FDA) pour l'irrigation ou le pompage ? »",
  pompe_hmt_m: "« Savez-vous la hauteur totale à laquelle la pompe doit monter l'eau (HMT) ? »",
  pompe_hmt_source: "« Cette HMT, c'est vous qui la donnez, ou elle vient du site ? »",
  pompe_debit_m3h: "« Quel débit souhaitez-vous, en mètres cubes par heure ? »",
  decideur: "« Qui décide avec vous de ce projet ? »",
}

// Provenances servies (`entrees_pompage.entrees[].provenance`, AGR404) —
// affichées en LECTURE SEULE sous le champ, jamais éditées ici.
const PROVENANCES = {
  client: 'déclaré', site_web: 'site web', mesure_visite: 'mesuré en visite', derive: 'calculé',
}

function provenanceDe(state, cle) {
  const entrees = state?.server?.entrees_pompage?.entrees
  const e = Array.isArray(entrees) ? entrees.find((x) => x.colonne === cle) : null
  return e ? (PROVENANCES[e.provenance] ?? e.provenance) : null
}

// Un champ pompage = libellé court (fieldLabels) + question de l'appel (aide)
// + provenance (lecture seule) + erreur serveur SOUS le champ. Le `htmlFor` du
// FormField vient du `data-field-anchor` posé à l'appel (lu par la garde
// fieldLabels.test.jsx : chaque ancre a son entrée).
function ChampPompage({ 'data-field-anchor': id, cle, ctx, label, children }) {
  const { state, requis, errors } = ctx
  const etiquette = label ?? fieldLabels[cle]?.label ?? cle
  const prov = provenanceDe(state, cle)
  return (
    <FormField
      label={<>{etiquette}{requis.has(cle) && <span className="req-auto"> *</span>}</>}
      htmlFor={id} error={errors[cle]} hint={QUESTIONS_POMPAGE[cle]}
    >
      {children}
      {prov && <span className="gen-hint" data-provenance={cle}>Provenance : {prov}</span>}
    </FormField>
  )
}

function PompNombre({ 'data-field-anchor': id, cle, ctx, label, placeholder }) {
  const { state, setField, errors } = ctx
  return (
    <ChampPompage data-field-anchor={id} cle={cle} ctx={ctx} label={label}>
      <Input
        id={id} type="number" step="any" placeholder={placeholder} invalid={!!errors[cle]}
        value={getField(state, cle) ?? ''} onChange={(e) => setField(cle, e.target.value)}
      />
    </ChampPompage>
  )
}

function PompTexte({ 'data-field-anchor': id, cle, ctx, label }) {
  const { state, setField, errors } = ctx
  return (
    <ChampPompage data-field-anchor={id} cle={cle} ctx={ctx} label={label}>
      <Input
        id={id} type="text" invalid={!!errors[cle]}
        value={getField(state, cle) ?? ''} onChange={(e) => setField(cle, e.target.value)}
      />
    </ChampPompage>
  )
}

function PompChoix({ 'data-field-anchor': id, cle, ctx, label, choix }) {
  const { state, setField, errors } = ctx
  return (
    <ChampPompage data-field-anchor={id} cle={cle} ctx={ctx} label={label}>
      <select
        id={id} className={errors[cle] ? 'form-select is-invalid' : 'form-select'}
        aria-invalid={errors[cle] ? true : undefined}
        value={getField(state, cle) ?? ''} onChange={(e) => setField(cle, e.target.value)}
      >
        {enumOptions(choix)}
      </select>
    </ChampPompage>
  )
}

function PompOuiNon({ 'data-field-anchor': id, cle, ctx, label }) {
  const { state, setField, errors } = ctx
  return (
    <ChampPompage data-field-anchor={id} cle={cle} ctx={ctx} label={label}>
      <TriStateSelect
        id={id} invalid={!!errors[cle]} value={getField(state, cle)}
        onChange={onTriStateChange(setField, cle)}
      />
    </ChampPompage>
  )
}

// Mois d'irrigation : liste d'entiers 1-12 (jamais « tous les mois » par
// défaut — vide = question pas encore posée).
function PompMois({ 'data-field-anchor': id, cle, ctx }) {
  const { state, setField } = ctx
  const brut = getField(state, cle)
  const choisis = Array.isArray(brut) ? brut : []
  const basculer = (m) => {
    const suite = choisis.includes(m) ? choisis.filter((x) => x !== m) : [...choisis, m]
    setField(cle, suite.length ? [...suite].sort((a, b) => a - b) : null)
  }
  return (
    <ChampPompage data-field-anchor={id} cle={cle} ctx={ctx}>
      <div role="group" aria-label={fieldLabels[cle].label} className="form-row">
        {MOIS_FR.map(([m, nom], i) => (
          <label key={m} className="form-check-label">
            <input
              type="checkbox" id={i === 0 ? id : `${id}-${m}`}
              checked={choisis.includes(m)} onChange={() => basculer(m)}
            />
            {' '}{nom}
          </label>
        ))}
      </div>
    </ChampPompage>
  )
}

function BlocPompage({ titre, children }) {
  return (
    <div className="lw-bloc-pompage" role="group" aria-label={titre}>
      <h4 className="lw-bloc-titre">{titre}</h4>
      {children}
    </div>
  )
}

const nombreOuNull = (v) => {
  if (v === '' || v === null || v === undefined) return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

export function SectionPompage({ state, setField, errors = {} }) {
  // L'étoile « requis devis auto » : les SEULS groupes de la règle servie
  // (`devis_auto.requis`, AGR403) — jamais une liste recopiée ici.
  const requis = new Set((state?.server?.devis_auto?.requis ?? []).flat())
  const ctx = { state, setField, errors, requis }
  const debit = nombreOuNull(getField(state, 'pompe_debit_m3h'))
  const hmt = nombreOuNull(getField(state, 'pompe_hmt_m'))
  const debitEgalHmt = debit !== null && hmt !== null && debit === hmt
  const nouveauForage = getField(state, 'projet_pompage') === 'nouveau_forage'
  const prixDeclareLe = state?.server?.carburant_prix_declare_le
  return (
    <>
      <BlocPompage titre="Énergie actuelle">
        <div className="form-row">
          <PompChoix data-field-anchor="lf-pompe-alim-actuelle" cle="pompe_alim_actuelle" ctx={ctx} choix={POMPE_ALIM_ACTUELLE} />
          <PompNombre data-field-anchor="lf-butane-bouteilles-jour" cle="butane_bouteilles_jour" ctx={ctx} placeholder="ex: 4" />
          <PompNombre data-field-anchor="lf-carburant-litres-mois" cle="carburant_litres_mois" ctx={ctx} placeholder="ex: 120" />
        </div>
        <div className="form-row">
          <PompNombre data-field-anchor="lf-carburant-prix" cle="carburant_prix_unitaire_mad" ctx={ctx} placeholder="ex: 50" />
          <PompNombre data-field-anchor="lf-depense-carburant" cle="depense_carburant_mad_mois" ctx={ctx} placeholder="ex: 1500" />
        </div>
        {prixDeclareLe && (
          <p className="gen-hint" data-prix-declare-le>Prix déclaré le {prixDeclareLe} (posé par le serveur).</p>
        )}
      </BlocPompage>

      <BlocPompage titre="Eau">
        <div className="form-row">
          <PompChoix data-field-anchor="lf-source-eau" cle="source_eau" ctx={ctx} choix={SOURCE_EAU} />
          <PompNombre data-field-anchor="lf-niveau-statique" cle="niveau_statique_m" ctx={ctx} placeholder="ex: 32" />
          <PompChoix data-field-anchor="lf-niveau-statique-source" cle="niveau_statique_source" ctx={ctx} choix={NIVEAU_STATIQUE_SOURCE} />
        </div>
        <div className="form-row">
          <PompNombre data-field-anchor="lf-profondeur-forage" cle="profondeur_forage_m" ctx={ctx} placeholder="ex: 90" />
          <PompNombre data-field-anchor="lf-debit-forage" cle="debit_forage_m3h" ctx={ctx} placeholder="ex: 36" />
          <PompChoix data-field-anchor="lf-debit-forage-source" cle="debit_forage_source" ctx={ctx} choix={DEBIT_FORAGE_SOURCE} />
        </div>
      </BlocPompage>

      <BlocPompage titre="Besoin">
        <div className="form-row">
          <PompNombre data-field-anchor="lf-besoin-eau" cle="besoin_eau_m3j" ctx={ctx} placeholder="ex: 135" />
          <PompChoix data-field-anchor="lf-besoin-eau-source" cle="besoin_eau_source" ctx={ctx} choix={BESOIN_EAU_SOURCE} />
          <PompNombre data-field-anchor="lf-pompe-debit" cle="pompe_debit_m3h" ctx={ctx} placeholder="ex: 12" />
        </div>
        {debitEgalHmt && (
          <p className="gen-hint" role="status" data-avertissement="debit-egal-hmt">
            Valeurs identiques : vérifiez que le débit n&apos;a pas été recopié de la HMT.
          </p>
        )}
        <div className="form-row">
          <PompNombre data-field-anchor="lf-pompe-hmt" cle="pompe_hmt_m" ctx={ctx} placeholder="ex: 80" />
          <PompChoix data-field-anchor="lf-pompe-hmt-source" cle="pompe_hmt_source" ctx={ctx} choix={POMPE_HMT_SOURCE} />
        </div>
        <div className="form-row">
          <PompTexte data-field-anchor="lf-culture" cle="culture" ctx={ctx} />
          <PompNombre data-field-anchor="lf-surface-irriguee" cle="surface_irriguee_ha" ctx={ctx} placeholder="ex: 4" />
          <PompChoix data-field-anchor="lf-irrigation-methode" cle="irrigation_methode" ctx={ctx} choix={IRRIGATION_METHODE} />
          <PompChoix data-field-anchor="lf-region-agricole" cle="region_agricole" ctx={ctx} choix={REGION_AGRICOLE} />
        </div>
        <PompMois data-field-anchor="lf-mois-irrigation" cle="mois_irrigation" ctx={ctx} />
      </BlocPompage>

      <BlocPompage titre="Pompe actuelle & site">
        <div className="form-row">
          <PompNombre
            data-field-anchor="lf-pompe-actuelle-cv" cle="pompe_actuelle_cv" ctx={ctx} placeholder="ex: 7,5"
            label="Pompe actuelle (CV) — information, jamais la pompe du devis"
          />
          <PompChoix data-field-anchor="lf-pompe-actuelle-type" cle="pompe_actuelle_type" ctx={ctx} choix={POMPE_ACTUELLE_TYPE} />
          <PompNombre data-field-anchor="lf-pompe-actuelle-debit" cle="pompe_actuelle_debit_m3h" ctx={ctx} />
          <PompNombre data-field-anchor="lf-pompage-heures-jour" cle="pompage_heures_jour" ctx={ctx} placeholder="ex: 8" />
        </div>
        <div className="form-row">
          <PompNombre data-field-anchor="lf-distance-forage-champ" cle="distance_forage_champ_m" ctx={ctx} placeholder="ex: 25" />
          <PompChoix data-field-anchor="lf-electricite-sur-place" cle="electricite_sur_place" ctx={ctx} choix={ELECTRICITE_SUR_PLACE} />
          <PompChoix data-field-anchor="lf-projet-pompage" cle="projet_pompage" ctx={ctx} choix={PROJET_POMPAGE} />
        </div>
        {nouveauForage && (
          <p className="gen-hint" role="note" data-rappel="forage-a-creuser">
            Rappel interne : pour un forage à creuser, vérifier auprès de l&apos;ABH que la zone n&apos;est
            pas en périmètre d&apos;interdiction, et que le foreur a son permis (loi 36-15 consolidée du
            18/07/2024, art. 112 et 114).
          </p>
        )}
      </BlocPompage>

      <BlocPompage titre="Règles & aides">
        <div className="form-row">
          <PompChoix data-field-anchor="lf-autorisation-prelevement" cle="autorisation_prelevement" ctx={ctx} choix={AUTORISATION_PRELEVEMENT} />
          <PompTexte data-field-anchor="lf-autorisation-numero" cle="autorisation_numero" ctx={ctx} />
          <PompNombre data-field-anchor="lf-autorisation-debit" cle="autorisation_debit_l_s" ctx={ctx} />
          <PompNombre data-field-anchor="lf-autorisation-volume" cle="autorisation_volume_m3_an" ctx={ctx} />
        </div>
        <div className="form-row">
          <PompOuiNon data-field-anchor="lf-compteur-eau" cle="compteur_eau" ctx={ctx} />
          <PompOuiNon data-field-anchor="lf-deja-beneficiaire-fda" cle="deja_beneficiaire_fda" ctx={ctx} />
          <PompChoix data-field-anchor="lf-decideur" cle="decideur" ctx={ctx} choix={DECIDEUR} />
        </div>
      </BlocPompage>
      <p className="gen-hint">
        <span className="req-auto">*</span> Requis pour le devis automatique en mode agricole (règle
        servie : l&apos;un des champs de chaque groupe).
      </p>
    </>
  )
}
