import { FormField, Input } from '../../../../ui'
import { getField } from '../draftCore'
import { jumpToField } from '../jumpToField'
import fieldLabels from '../fieldLabels'
import { COMMERCIAL_CATEGORY_QUESTIONS } from '../../../ventes/solar'
import SelectEnum from './SelectEnum'

/* CIQ418 — « Professionnel » : la fiche d'un lead COMMERCIAL ou INDUSTRIEL.
   Contrat partagé `lead_pro.json` (CIQ1, check_api_shapes) : chaque colonne
   pro a un champ ATTEIGNABLE (fieldLabels → jumpToField), avec un libellé
   court et la question de l'appel EN AIDE, mot pour mot.

   Cinq blocs dans l'ORDRE DE L'APPEL (D-CIQ-7), puis deux blocs de
   questionnaire. Une colonne déjà saisie dans une autre section (raison
   sociale, raccordement, toiture, surface, financement, facture, kWh) n'est
   JAMAIS dupliquée : un lien la pointe dans sa section (zéro second état pour
   la même donnée, une seule ancre DOM par champ). Toutes les saisies
   numériques sont `step="any"` — jamais un arrondi (12,5 kVA part tel quel).
   Les provenances servies (`entrees_ci`, CIQ405) sont en LECTURE SEULE. */

// source-choix: crm.Lead.tension_raccordement
const TENSION = { bt: 'Basse tension (BT)', mt: 'Moyenne tension (MT)', ne_sait_pas: 'Ne sait pas' }
// source-choix: crm.Lead.tension_source
const TENSION_SOURCE = {
  declare: 'Déclarée', site_web: 'Saisie sur le site', site_defaut_visible: 'Défaut visible du site',
  facture: 'Lue sur la facture', mesure_visite: 'Mesurée en visite',
}
// source-choix: crm.Lead.contrat_electricite
const CONTRAT_ELECTRICITE = {
  bt_domestique: 'BT domestique', bt_patente: 'BT patenté', bt_force_motrice: 'BT force motrice',
  mt_general: 'MT (Tarif Général)', ne_sait_pas: 'Ne sait pas',
}
// source-choix: crm.Lead.option_tarifaire_bt
const OPTION_TARIFAIRE_BT = { normale: 'Option normale (tranches)', bi_horaire: 'Option bi-horaire (HP / HN)' }
// source-choix: crm.Lead.puissance_souscrite_source
const PUISSANCE_SOURCE = {
  declare: 'Déclarée', facture: 'Lue sur la facture', contrat: 'Lue sur le contrat',
  site_web: 'Saisie sur le site', mesure_visite: 'Mesurée en visite',
}
// source-choix: crm.Lead.categorie_commerciale
const CATEGORIE = {
  hotel: 'Hôtel / riad', restaurant: 'Restaurant / café', commerce: 'Commerce / supermarché',
  bureau: 'Bureaux', sante: 'Santé (clinique, cabinet)', ecole: 'École',
  hammam: 'Hammam / spa / salle de sport', boulangerie: 'Boulangerie',
  froid: 'Froid / entrepôt frigorifique', autre: 'Autre',
}
// source-choix: crm.Lead.regime_equipes
const REGIME_EQUIPES = {
  '1x8': 'Une équipe (1×8)', '2x8': 'Deux équipes (2×8)', '3x8': 'Trois équipes (3×8)',
  continu: 'En continu', ne_sait_pas: 'Ne sait pas',
}
// source-choix: crm.Lead.type_surface
const TYPE_SURFACE = { toiture: 'Toiture', ombriere: 'Ombrière de parking', terrain: 'Terrain' }
// source-choix: crm.Lead.surface_source
const SURFACE_SOURCE = {
  declare: 'Déclarée', site_web: 'Saisie sur le site', calepinage: 'Calepinage',
  mesure_visite: 'Mesurée en visite',
}
// source-choix: crm.Lead.cos_phi_source
const COS_PHI_SOURCE = { facture: 'Lu sur la facture', site_web: 'Saisi sur le site', mesure_visite: 'Mesuré en visite' }
// source-choix: crm.Lead.tva_recuperable
const TVA_RECUPERABLE = { oui: 'Oui', non: 'Non', ne_sait_pas: 'Ne sait pas' }
// source-choix: crm.Lead.export_ue_declare
const OUI_NON = { oui: 'Oui', non: 'Non' }

const JOURS = [[1, 'lun.'], [2, 'mar.'], [3, 'mer.'], [4, 'jeu.'], [5, 'ven.'], [6, 'sam.'], [7, 'dim.']]
const MOIS = [
  [1, 'janv.'], [2, 'févr.'], [3, 'mars'], [4, 'avr.'], [5, 'mai'], [6, 'juin'],
  [7, 'juil.'], [8, 'août'], [9, 'sept.'], [10, 'oct.'], [11, 'nov.'], [12, 'déc.'],
]

// La question orale sous chaque champ — celle du contrat `lead_pro.json`
// (colonnes_pro[].question), gardée à l'identique par SectionsRender.test.jsx.
const QUESTIONS_PRO = {
  tension_raccordement: "« Votre site est-il raccordé en basse tension, avec un compteur ordinaire, ou en moyenne tension, avec un poste de transformation ? Si vous ne savez pas, ce n'est pas grave. »",
  tension_source: "(posée avec la tension) « Vous le lisez sur votre facture, ou c'est de mémoire ? » — `site_defaut_visible` = valeur pré-cochée du site non modifiée par le client ; `mesure_visite` = relevé par notre technicien lors de la visite",
  contrat_electricite: "« Quel est votre contrat d'électricité : basse tension patenté, force motrice, domestique, ou moyenne tension ? Il est écrit sur votre facture. » — CIQ666 (décision fondateur 08/10/2026) : vocabulaire de `tarifs_ci.json` (`tarif_declare.contrat`) ; « ne sait pas » = aucun contrat transmis, jamais un contrat supposé",
  option_tarifaire_bt: "(posée avec le contrat, force motrice seulement) « Êtes-vous en option normale ou en option bi-horaire ? » — le bi-horaire n'est transmis au moteur que pour la force motrice",
  compteur_puissance_kva: '« Quelle est votre puissance souscrite, en kVA ? Elle est écrite sur votre facture ou votre contrat. »',
  puissance_souscrite_source: "(posée avec la puissance) « Vous l'avez trouvée sur la facture, sur le contrat, ou c'est une estimation ? »",
  categorie_commerciale: '« Quelle est votre activité : hôtel, restaurant ou café, commerce, bureaux, santé, école, hammam, boulangerie, froid, ou autre chose ? »',
  reponses_categorie: "Les questions propres à la catégorie (voir `reponses_categorie_par_categorie`), posées juste après l'activité.",
  secteur_industriel: '« Que fabriquez-vous ou que transformez-vous sur ce site ? »',
  export_ue_declare: "« Exportez-vous une partie de votre production vers l'Union européenne ? »",
  regime_equipes: '« Travaillez-vous en une équipe de jour, en deux équipes, en trois équipes, ou en continu ? »',
  jours_ouverture: '« Quels jours de la semaine êtes-vous ouverts ou en production ? »',
  heure_debut: '« À quelle heure commence votre journée de travail ? »',
  heure_fin: '« Et à quelle heure se termine-t-elle ? »',
  fermeture_mois: "« Fermez-vous certains mois de l'année, pour des congés ou une saison creuse ? Lesquels ? »",
  type_surface: '« Où pourrait-on poser les panneaux : sur la toiture, sur une ombrière de parking, ou sur un terrain ? »',
  surface_source: "(posée avec la surface) « C'est une mesure, ou une estimation ? »",
  groupe_electrogene: '« Avez-vous un groupe électrogène sur le site ? »',
  groupe_kva: '« Quelle est sa puissance, en kVA ? »',
  groupe_litres_mois: '« Combien de litres de gasoil consomme-t-il par mois ? »',
  groupe_depense_mad_mois: '« Combien dépensez-vous en gasoil pour le groupe chaque mois ? » (déclaré seulement, jamais un prix pré-rempli — Q17)',
  pv_existant_kwc: '« Avez-vous déjà des panneaux solaires installés ? De quelle puissance ? »',
  cos_phi: "« Votre facture indique-t-elle un cosinus phi ou une pénalité d'énergie réactive ? Quelle valeur ? » — jamais supposé (même règle que calepinage/services/etapes/ecretage.py)",
  cos_phi_source: '(posée avec le cos φ) « Vous le lisez sur la facture ? »',
  releve_conso: "« Pouvez-vous nous envoyer vos dernières factures d'électricité ? Jusqu'à douze mois nous aident à être précis. » — jamais exigées toutes les douze (W5-VB-07)",
  tva_recuperable: '« Votre entreprise récupère-t-elle la TVA sur ses achats ? » (D-CIQ-3)',
  ice: "« Pouvez-vous nous donner l'ICE de l'entreprise ? Il figurera sur le devis et la facture. » — demandé, jamais bloquant au devis (D-CIQ-11)",
  rc: '« Et son numéro de registre de commerce ? »',
  if_fiscal: "« Et l'identifiant fiscal ? »",
  adresse_siege: "« Quelle est l'adresse du siège, si elle diffère de celle du site ? »",
  fonction_contact: "« Quelle est votre fonction dans l'entreprise ? »",
  contact_secondaire_fonction: "« Qui d'autre décide avec vous ? Quelle est sa fonction ? » (CAD144 : sans automatisation)",
  contact_secondaire_email: '« Pouvons-nous lui envoyer le devis par e-mail ? À quelle adresse ? »',
  facture_tranche_declaree: '« Votre facture mensuelle se situe dans quelle tranche ? » — D-CIQ-19 : une tranche ouverte n\'est JAMAIS stockée comme un montant',
}

// Questions propres à la catégorie : les clés FERMÉES du contrat
// (`reponses_categorie_par_categorie.cles`) — libellés repris de
// COMMERCIAL_CATEGORY_QUESTIONS, plus les clés AJOUTÉES par CIQ1.
const QUESTIONS_AJOUTEES = {
  hotel: [
    { key: 'heures_piscine', label: 'Piscine — heures par jour', type: 'number' },
    { key: 'blanchisserie', label: 'Blanchisserie sur place', type: 'bool' },
    { key: 'reception_24h', label: 'Réception 24 h/24', type: 'bool' },
  ],
  restaurant: [{ key: 'ouvert_journee_ramadan', label: 'Ouvert en journée pendant le Ramadan', type: 'bool' }],
}
const questionsCategorie = (categorie) => [
  ...(COMMERCIAL_CATEGORY_QUESTIONS[categorie] ?? []),
  ...(QUESTIONS_AJOUTEES[categorie] ?? []),
]

// Provenance servie (`entrees_ci.entrees[].provenance.detail`), en clair.
const PROVENANCES = {
  declare: 'déclaré', client: 'déclaré', site_web: 'site web',
  site_defaut_visible: 'défaut visible du site', facture: 'facture', lu_sur_facture: 'facture',
  ocr_confirme: 'facture', mesure_visite: 'mesuré en visite', calepinage: 'calepinage',
}

function provenanceDe(state, cle) {
  const entrees = state?.server?.entrees_ci?.entrees
  const e = Array.isArray(entrees) ? entrees.find((x) => x.colonne === cle) : null
  if (!e || !e.provenance) return null
  const detail = e.provenance.detail ?? e.provenance.origine
  return PROVENANCES[detail] ?? detail
}

// Les colonnes déjà saisies dans une autre section : un lien, jamais un double.
const RENVOIS = {
  facture: [
    { cle: 'facture_hiver', texte: 'Facture mensuelle déclarée (MAD)' },
    { cle: 'conso_mensuelle_kwh', texte: 'Consommation mensuelle (kWh)' },
  ],
  raccordement: [{ cle: 'raccordement', texte: 'Phase : monophasé ou triphasé ?', segment: 'commercial' }],
  surface: [
    { cle: 'type_toiture', texte: 'Type de toiture' },
    { cle: 'surface_toiture_m2', texte: 'Surface disponible (m²)' },
  ],
  decideur: [
    { cle: 'contact_secondaire_nom', texte: 'Contact secondaire (nom)' },
    { cle: 'contact_secondaire_telephone', texte: 'Contact secondaire (téléphone)' },
  ],
  societe: [
    { cle: 'societe', texte: 'Raison sociale' },
    { cle: 'financing_intent', texte: 'Financement envisagé' },
  ],
}

function Renvois({ liste, segment }) {
  const visibles = liste.filter((r) => !r.segment || r.segment === segment)
  if (!visibles.length) return null
  return (
    <p className="gen-hint" data-renvois>
      Saisi ailleurs :{' '}
      {visibles.map((r, i) => {
        const entree = fieldLabels[r.cle]
        return (
          <span key={r.cle}>
            {i > 0 && ' · '}
            <button
              type="button" className="link-button" data-renvoi={r.cle}
              onClick={() => jumpToField({ section: entree.section, field: entree.inputId })}
            >
              {r.texte}
            </button>
          </span>
        )
      })}
    </p>
  )
}

function Champ({ id, cle, ctx, children }) {
  const { state, requis, errors } = ctx
  const etiquette = fieldLabels[cle]?.label ?? cle
  const prov = provenanceDe(state, cle)
  return (
    <FormField
      label={<>{etiquette}{requis.has(cle) && <span className="req-auto"> *</span>}</>}
      htmlFor={id} error={errors[cle]} hint={QUESTIONS_PRO[cle]}
    >
      {children}
      {prov && <span className="gen-hint" data-provenance={cle}>Provenance : {prov}</span>}
    </FormField>
  )
}

function Nombre({ 'data-field-anchor': id, cle, ctx, placeholder }) {
  const { state, setField, errors } = ctx
  return (
    <Champ id={id} cle={cle} ctx={ctx}>
      <Input
        id={id} type="number" step="any" placeholder={placeholder} invalid={!!errors[cle]}
        value={getField(state, cle) ?? ''} onChange={(e) => setField(cle, e.target.value)}
      />
    </Champ>
  )
}

function Texte({ 'data-field-anchor': id, cle, ctx, type = 'text' }) {
  const { state, setField, errors } = ctx
  return (
    <Champ id={id} cle={cle} ctx={ctx}>
      <Input
        id={id} type={type} invalid={!!errors[cle]}
        value={getField(state, cle) ?? ''} onChange={(e) => setField(cle, e.target.value)}
      />
    </Champ>
  )
}

function Choix({ 'data-field-anchor': id, cle, ctx, choix }) {
  return (
    <Champ id={id} cle={cle} ctx={ctx}>
      <SelectEnum id={id} cle={cle} ctx={ctx} choix={choix} />
    </Champ>
  )
}

// Liste d'entiers (jours 1-7, mois 1-12) : cases à cocher, vide = pas encore
// demandé (jamais « tous » par défaut).
function Cases({ 'data-field-anchor': id, cle, ctx, valeurs }) {
  const { state, setField } = ctx
  const brut = getField(state, cle)
  const choisis = Array.isArray(brut) ? brut : []
  const basculer = (n) => {
    const suite = choisis.includes(n) ? choisis.filter((x) => x !== n) : [...choisis, n]
    setField(cle, suite.length ? [...suite].sort((a, b) => a - b) : null)
  }
  return (
    <Champ id={id} cle={cle} ctx={ctx}>
      <div role="group" aria-label={fieldLabels[cle].label} className="form-row">
        {valeurs.map(([n, nom], i) => (
          <label key={n} className="form-check-label">
            <input
              type="checkbox" id={i === 0 ? id : `${id}-${n}`}
              checked={choisis.includes(n)} onChange={() => basculer(n)}
            />
            {' '}{nom}
          </label>
        ))}
      </div>
    </Champ>
  )
}

// Les réponses propres à l'activité (objet), une entrée par clé du contrat.
function ReponsesCategorie({ ctx }) {
  const { state, setField } = ctx
  const categorie = getField(state, 'categorie_commerciale')
  const brut = getField(state, 'reponses_categorie')
  const reponses = brut && typeof brut === 'object' ? brut : {}
  const questions = questionsCategorie(categorie)
  const poser = (cle, valeur) => {
    const suite = { ...reponses, [cle]: valeur }
    if (valeur === null || valeur === '') delete suite[cle]
    setField('reponses_categorie', Object.keys(suite).length ? suite : null)
  }
  return (
    <Champ id="lf-reponses-categorie" cle="reponses_categorie" ctx={ctx}>
      <div id="lf-reponses-categorie" data-field-anchor="lf-reponses-categorie" role="group" aria-label={fieldLabels.reponses_categorie.label} className="form-row">
        {!categorie && <span className="gen-hint">Choisissez d’abord l’activité.</span>}
        {questions.map((q) => {
          const idQ = `lf-reponses-categorie-${q.key}`
          const v = reponses[q.key]
          if (q.type === 'bool') {
            return (
              <label key={q.key} htmlFor={idQ} className="form-label">
                {q.label}{' '}
                <select
                  id={idQ} className="form-select"
                  value={v === true ? 'oui' : v === false ? 'non' : ''}
                  onChange={(e) => poser(q.key, e.target.value === 'oui' ? true : e.target.value === 'non' ? false : null)}
                >
                  <option value="">—</option>
                  <option value="oui">Oui</option>
                  <option value="non">Non</option>
                </select>
              </label>
            )
          }
          if (q.type === 'select') {
            return (
              <label key={q.key} htmlFor={idQ} className="form-label">
                {q.label}{' '}
                <select id={idQ} className="form-select" value={v ?? ''} onChange={(e) => poser(q.key, e.target.value || null)}>
                  <option value="">—</option>
                  {q.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </label>
            )
          }
          return (
            <label key={q.key} htmlFor={idQ} className="form-label">
              {q.label}{' '}
              <Input
                id={idQ} type="number" step="any" value={v ?? ''}
                onChange={(e) => poser(q.key, e.target.value === '' ? null : e.target.value)}
              />
            </label>
          )
        })}
      </div>
    </Champ>
  )
}

const REGISTRES_MT = [
  ['kwh_pointe', 'kWh pointe'], ['kwh_pleines', 'kWh pleines'], ['kwh_creuses', 'kWh creuses'],
  ['puissance_atteinte_kva', 'Puissance atteinte (kVA)'],
]

// Le relevé de 12 mois au plus : {mois: [{mois, kwh, registres MT…, cos_phi}],
// source}. Les registres MT ne s'affichent que pour un site en moyenne tension.
function ReleveConso({ ctx }) {
  const { state, setField } = ctx
  const brut = getField(state, 'releve_conso')
  const releve = brut && typeof brut === 'object' && Array.isArray(brut.mois) ? brut : null
  const lignes = releve ? releve.mois : []
  const mt = getField(state, 'tension_raccordement') === 'mt'
  const ecrire = (suite) => setField('releve_conso', suite.length
    ? { mois: suite, source: releve?.source ?? 'declare' } : null)
  const modifier = (i, cle, valeur) => ecrire(lignes.map((l, j) => (j === i
    ? { ...l, [cle]: valeur === '' ? null : valeur } : l)))
  const ajouter = () => ecrire([...lignes, { mois: '', kwh: null }])
  const retirer = (i) => ecrire(lignes.filter((_, j) => j !== i))
  return (
    <Champ id="lf-releve-conso" cle="releve_conso" ctx={ctx}>
      <div id="lf-releve-conso" data-field-anchor="lf-releve-conso" role="group" aria-label={fieldLabels.releve_conso.label}>
        {lignes.map((l, i) => (
          <div key={i} className="form-row" data-releve-ligne={i}>
            <label className="form-label" htmlFor={`lf-releve-conso-${i}-mois`}>
              Mois{' '}
              <Input id={`lf-releve-conso-${i}-mois`} type="month" value={l.mois ?? ''} onChange={(e) => modifier(i, 'mois', e.target.value)} />
            </label>
            <label className="form-label" htmlFor={`lf-releve-conso-${i}-kwh`}>
              kWh{' '}
              <Input id={`lf-releve-conso-${i}-kwh`} type="number" step="any" value={l.kwh ?? ''} onChange={(e) => modifier(i, 'kwh', e.target.value)} />
            </label>
            {mt && REGISTRES_MT.map(([cle, texte]) => (
              <label key={cle} className="form-label" htmlFor={`lf-releve-conso-${i}-${cle}`}>
                {texte}{' '}
                <Input
                  id={`lf-releve-conso-${i}-${cle}`} type="number" step="any" value={l[cle] ?? ''}
                  onChange={(e) => modifier(i, cle, e.target.value)}
                />
              </label>
            ))}
            <button type="button" className="link-button" onClick={() => retirer(i)}>Retirer ce mois</button>
          </div>
        ))}
        {lignes.length < 12 && (
          <button type="button" className="link-button" data-releve-ajouter onClick={ajouter}>
            Ajouter un mois
          </button>
        )}
      </div>
    </Champ>
  )
}

// La tranche déclarée (Meta / site) : LECTURE SEULE — une tranche ouverte
// n'est jamais un montant (D-CIQ-19).
function TrancheDeclaree({ ctx }) {
  const t = getField(ctx.state, 'facture_tranche_declaree')
  let texte = '—'
  if (t && typeof t === 'object') {
    texte = t.libelle || (t.max_mad != null ? `${t.min_mad} à ${t.max_mad} MAD` : `plus de ${t.min_mad} MAD`)
    if (t.source) texte += ` (${t.source})`
  }
  return (
    <Champ id="lf-facture-tranche" cle="facture_tranche_declaree" ctx={ctx}>
      <output id="lf-facture-tranche" data-field-anchor="lf-facture-tranche" className="text-sm">{texte}</output>
    </Champ>
  )
}

function Bloc({ titre, children }) {
  return (
    <div className="lw-bloc-pompage" role="group" aria-label={titre}>
      <h4 className="lw-bloc-titre">{titre}</h4>
      {children}
    </div>
  )
}

export default function SectionPro({ state, setField, errors = {} }) {
  // L'étoile « requis devis auto » : les SEULS groupes de la règle servie
  // (`devis_auto.requis`, CIQ404) — jamais une liste recopiée ici.
  const requis = new Set((state?.server?.devis_auto?.requis ?? []).flat())
  const ctx = { state, setField, errors, requis }
  const segment = getField(state, 'type_installation')
  const industriel = segment === 'industriel'
  const visite = state?.server?.devis_auto?.visite_avant_devis
  // CIQ428 — indicateur INTERNE (loi 47-09) : affiché SEULEMENT au seuil
  // atteint, en lecture seule ; aucune amende, aucune échéance.
  const audit = state?.server?.indicateurs_internes?.audit_47_09
  const auditAtteint = audit?.statut === 'seuil_atteint_electricite_seule'
  return (
    <>
      {auditAtteint && (
        <p className="gen-hint" role="note" data-audit-47-09>
          Audit énergétique obligatoire probable (loi 47-09) : {audit.motif}. Indicatif — sur
          déclaratif — à vérifier avec le client.
        </p>
      )}
      {visite?.requise && (
        <p className="gen-hint" role="note" data-visite-avant-devis>
          Visite avant devis : {(visite.motifs ?? []).join(' ; ') || 'requise'}.
        </p>
      )}

      <Bloc titre="Facture & conso">
        <Renvois liste={RENVOIS.facture} segment={segment} />
        <TrancheDeclaree ctx={ctx} />
        <ReleveConso ctx={ctx} />
      </Bloc>

      <Bloc titre="Raccordement">
        <div className="form-row">
          <Choix data-field-anchor="lf-tension-raccordement" cle="tension_raccordement" ctx={ctx} choix={TENSION} />
          <Choix data-field-anchor="lf-tension-source" cle="tension_source" ctx={ctx} choix={TENSION_SOURCE} />
        </div>
        {/* CIQ666 — le contrat déclaré : le devis automatique C&I en résout
            la grille ONEE (« ne sait pas » = aucun contrat transmis). */}
        <div className="form-row">
          <Choix data-field-anchor="lf-contrat-electricite" cle="contrat_electricite" ctx={ctx} choix={CONTRAT_ELECTRICITE} />
          <Choix data-field-anchor="lf-option-tarifaire-bt" cle="option_tarifaire_bt" ctx={ctx} choix={OPTION_TARIFAIRE_BT} />
        </div>
        <div className="form-row">
          <Nombre data-field-anchor="lf-compteur-puissance-kva" cle="compteur_puissance_kva" ctx={ctx} placeholder="ex: 60" />
          <Choix data-field-anchor="lf-puissance-souscrite-source" cle="puissance_souscrite_source" ctx={ctx} choix={PUISSANCE_SOURCE} />
        </div>
        <Renvois liste={RENVOIS.raccordement} segment={segment} />
      </Bloc>

      <Bloc titre="Activité & rythme">
        {industriel ? (
          <div className="form-row">
            <Texte data-field-anchor="lf-secteur-industriel" cle="secteur_industriel" ctx={ctx} />
            <Choix data-field-anchor="lf-export-ue" cle="export_ue_declare" ctx={ctx} choix={OUI_NON} />
          </div>
        ) : (
          <>
            <div className="form-row">
              <Choix data-field-anchor="lf-categorie-commerciale" cle="categorie_commerciale" ctx={ctx} choix={CATEGORIE} />
            </div>
            <ReponsesCategorie ctx={ctx} />
          </>
        )}
        <div className="form-row">
          <Choix data-field-anchor="lf-regime-equipes" cle="regime_equipes" ctx={ctx} choix={REGIME_EQUIPES} />
          <Nombre data-field-anchor="lf-heure-debut" cle="heure_debut" ctx={ctx} placeholder="ex: 8" />
          <Nombre data-field-anchor="lf-heure-fin" cle="heure_fin" ctx={ctx} placeholder="ex: 18" />
        </div>
        <Cases data-field-anchor="lf-jours-ouverture" cle="jours_ouverture" ctx={ctx} valeurs={JOURS} />
        <Cases data-field-anchor="lf-fermeture-mois" cle="fermeture_mois" ctx={ctx} valeurs={MOIS} />
      </Bloc>

      <Bloc titre="Surface">
        <div className="form-row">
          <Choix data-field-anchor="lf-type-surface" cle="type_surface" ctx={ctx} choix={TYPE_SURFACE} />
          <Choix data-field-anchor="lf-surface-source" cle="surface_source" ctx={ctx} choix={SURFACE_SOURCE} />
        </div>
        <Renvois liste={RENVOIS.surface} segment={segment} />
      </Bloc>

      <Bloc titre="Décideur">
        <div className="form-row">
          <Texte data-field-anchor="lf-fonction-contact" cle="fonction_contact" ctx={ctx} />
          <Texte data-field-anchor="lf-contact-secondaire-fonction" cle="contact_secondaire_fonction" ctx={ctx} />
          <Texte data-field-anchor="lf-contact-secondaire-email" cle="contact_secondaire_email" ctx={ctx} type="email" />
        </div>
        <Renvois liste={RENVOIS.decideur} segment={segment} />
      </Bloc>

      <Bloc titre="Site & énergie">
        <div className="form-row">
          <Choix data-field-anchor="lf-groupe-electrogene" cle="groupe_electrogene" ctx={ctx} choix={OUI_NON} />
          <Nombre data-field-anchor="lf-pv-existant" cle="pv_existant_kwc" ctx={ctx} />
        </div>
        <div className="form-row">
          <Nombre data-field-anchor="lf-groupe-kva" cle="groupe_kva" ctx={ctx} />
          <Nombre data-field-anchor="lf-groupe-litres-mois" cle="groupe_litres_mois" ctx={ctx} />
          <Nombre data-field-anchor="lf-groupe-depense" cle="groupe_depense_mad_mois" ctx={ctx} />
        </div>
        {industriel && (
          <div className="form-row">
            <Nombre data-field-anchor="lf-cos-phi" cle="cos_phi" ctx={ctx} placeholder="ex: 0,85" />
            <Choix data-field-anchor="lf-cos-phi-source" cle="cos_phi_source" ctx={ctx} choix={COS_PHI_SOURCE} />
          </div>
        )}
      </Bloc>

      <Bloc titre="Société">
        <div className="form-row">
          <Texte data-field-anchor="lf-ice" cle="ice" ctx={ctx} />
          <Texte data-field-anchor="lf-rc" cle="rc" ctx={ctx} />
          <Texte data-field-anchor="lf-if-fiscal" cle="if_fiscal" ctx={ctx} />
        </div>
        <div className="form-row">
          <Texte data-field-anchor="lf-adresse-siege" cle="adresse_siege" ctx={ctx} />
          <Choix data-field-anchor="lf-tva-recuperable" cle="tva_recuperable" ctx={ctx} choix={TVA_RECUPERABLE} />
        </div>
        <Renvois liste={RENVOIS.societe} segment={segment} />
      </Bloc>
      <p className="gen-hint">
        <span className="req-auto">*</span> Requis pour le devis automatique (règle servie : l&apos;un des
        champs de chaque groupe).
      </p>
    </>
  )
}
