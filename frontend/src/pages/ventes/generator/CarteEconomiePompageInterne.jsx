// AGR214 — volet INTERNE de la carte économie de pompage : « Interne —
// jamais sur un document client ». Replié par défaut. Il lit la clé
// `vue_interne` de la réponse servie (contrat `economie_pompage.json`) et
// porte les saisies INTERNES qui s'écrivent dans `saisies_economie_pompage`
// (`taux_actualisation`, `pret`) — aucun taux par défaut, aucun calcul ici.
import { useState } from 'react'
import { Input, Label } from '../../../ui'
import { formatNumber } from '../../../lib/format'

const MENTION_INTERNE = 'Interne — jamais sur un document client (jamais imprimé)'
const MOTIF_VAN_SANS_TAUX = "VAN non calculée : taux d'actualisation non saisi"
const MESSAGE_SOURCE_REQUISE = "Source obligatoire : un taux sans source n'est jamais utilisé."

const TERMES_FDA = [
  ['taux_x_base_mad', 'taux × base'],
  ['plafond_ha_x_surface_mad', 'plafond par ha × surface'],
  ['plafond_kwc_x_kwc_mad', 'plafond par kWc × kWc'],
  ['plafond_projet_mad', 'plafond par projet'],
]
const CONDITIONS_FDA = {
  energie_actuelle_butane: 'Énergie actuelle : butane',
  irrigation_localisee: 'Irrigation localisée',
  compteur_eau: "Compteur d'eau",
  un_seul_projet_par_exploitation: 'Un seul projet par exploitation',
}
const ETATS = { remplie: 'remplie', a_verifier: 'à vérifier', non_remplie: 'non remplie' }
const MOIS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.',
  'oct.', 'nov.', 'déc.']

const mad = (v) => (v === null || v === undefined ? 'non calculé' : `${formatNumber(v)} MAD`)

function Champ({ id, label, valeur, onChange, type = 'number', erreur }) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} type={type} {...(type === 'number' ? { step: 'any', min: '0' } : {})}
             value={valeur ?? ''} onChange={(e) => onChange(e.target.value)} />
      {erreur && <p className="text-xs text-destructive" role="alert" data-testid={`${id}-erreur`}>{erreur}</p>}
    </div>
  )
}

function motifOmission(vue, cle) {
  return ((vue?.omissions || []).find((o) => o.cle === cle) || {}).motif || null
}

export default function CarteEconomiePompageInterne({ reponse, eco, majEco }) {
  const [ouvert, setOuvert] = useState(false)
  const interne = (eco && eco.interne) || {}
  const taux = interne.taux_actualisation || {}
  const pret = interne.pret || {}
  const vue = reponse?.vue_interne || null
  const poserTaux = (cle) => (v) => majEco?.('interne', {
    ...interne, taux_actualisation: { ...taux, [cle]: v } })
  const poserPret = (cle) => (v) => majEco?.('interne', {
    ...interne, pret: { ...pret, [cle]: v } })
  const tauxSaisi = taux.valeur !== undefined && taux.valeur !== null && String(taux.valeur).trim() !== ''
  const sourceManquante = tauxSaisi && !String(taux.source || '').trim()
  const fda = vue?.aide_fda_indicative || null
  const scenario = vue?.scenario_butane_non_subventionne || null
  const financement = reponse?.financement || null

  return (
    <div className="mt-2 rounded-md border border-dashed p-2" data-testid="volet-interne">
      <button type="button" className="text-xs font-semibold" aria-expanded={ouvert}
              onClick={() => setOuvert((o) => !o)}>
        {MENTION_INTERNE}
      </button>
      {ouvert && (
        <div className="mt-2 grid gap-3 text-xs" data-testid="volet-interne-contenu">
          <div className="grid gap-3 sm:grid-cols-2">
            <Champ id="gen-eco-taux-actualisation" label="Taux d'actualisation (%)"
                   valeur={taux.valeur} onChange={poserTaux('valeur')} />
            <Champ id="gen-eco-taux-source" label="Source du taux" type="text"
                   valeur={taux.source} onChange={poserTaux('source')}
                   erreur={sourceManquante ? MESSAGE_SOURCE_REQUISE : null} />
          </div>
          <p data-testid="van-interne">
            {vue && vue.van_mad !== null && vue.van_mad !== undefined
              ? `VAN : ${mad(vue.van_mad)} ; retour actualisé : ${vue.retour_actualise_ans ?? 'non calculé'} ans`
              : (tauxSaisi ? (motifOmission(vue, 'van_mad') || 'VAN non calculée') : MOTIF_VAN_SANS_TAUX)}
          </p>

          <div className="grid gap-3 sm:grid-cols-3" data-testid="bloc-pret">
            <Champ id="gen-pret-principal" label="Prêt : montant (MAD)"
                   valeur={pret.principal_mad} onChange={poserPret('principal_mad')} />
            <Champ id="gen-pret-taux" label="Prêt : taux annuel (%)"
                   valeur={pret.taux_annuel_pct} onChange={poserPret('taux_annuel_pct')} />
            <Champ id="gen-pret-duree" label="Prêt : durée (mois)"
                   valeur={pret.duree_mois} onChange={poserPret('duree_mois')} />
            <Champ id="gen-pret-type" label="Prêt : type" type="text"
                   valeur={pret.type_pret} onChange={poserPret('type_pret')} />
            <Champ id="gen-pret-differe" label="Prêt : différé (mois)"
                   valeur={pret.differe_mois} onChange={poserPret('differe_mois')} />
            <Champ id="gen-pret-source" label="Prêt : source (offre écrite)" type="text"
                   valeur={pret.source} onChange={poserPret('source')} />
          </div>
          {financement ? (
            <div data-testid="financement">
              <p>Mensualité : {mad(financement.mensualite_mad)}</p>
              <ul>
                {(financement.carburant_evite_par_mois || []).map((v, i) => (v ? (
                  <li key={MOIS[i]}>{MOIS[i]} : carburant évité {mad(v)} face à {mad(financement.mensualite_mad)}</li>
                ) : null))}
              </ul>
            </div>
          ) : (
            <p className="text-muted-foreground" data-testid="financement-omis">
              {((reponse?.omissions || []).find((o) => o.cle === 'financement') || {}).motif
                || 'aucun prêt saisi'}
            </p>
          )}

          <p data-testid="scenario-butane">
            Butane non subventionné : {scenario
              ? `${scenario.libelle || ''} ${mad(scenario.economie_nette_mad_an ?? scenario.valeur)}`.trim()
              : (motifOmission(vue, 'scenario_butane_non_subventionne') || 'non calculé')}
          </p>

          {fda ? (
            <div data-testid="aide-fda">
              <p>Aide FDA indicative : {mad(fda.montant_mad)}
                {fda.base === 'a_confirmer' ? ' — base « à confirmer DPA »' : ` — base ${fda.base}`}
                {fda.edition ? ` (${fda.edition})` : ''}</p>
              <ul>
                {TERMES_FDA.map(([cle, libelle]) => (
                  <li key={cle}>{libelle} : {mad(fda.termes?.[cle])}</li>
                ))}
              </ul>
              <ul>
                {(fda.conditions || []).map((c) => (
                  <li key={c.cle}>{CONDITIONS_FDA[c.cle] || c.cle} : {ETATS[c.etat] || c.etat}</li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-muted-foreground" data-testid="aide-fda-omise">
              Aide FDA : {motifOmission(vue, 'aide_fda_indicative') || 'non calculée'}
            </p>
          )}

          <p data-testid="rendement-implicite">
            Rendement global implicite : {vue && vue.rendement_global_implicite_pct !== null
              && vue.rendement_global_implicite_pct !== undefined
              ? `${formatNumber(vue.rendement_global_implicite_pct)} %`
              : (motifOmission(vue, 'rendement_global_implicite_pct') || 'non calculé')}
          </p>
        </div>
      )}
    </div>
  )
}
