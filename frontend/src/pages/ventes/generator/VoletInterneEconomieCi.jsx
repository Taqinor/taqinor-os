// CIQ224 — VOLET INTERNE de l'économie C&I (« Vendeur seulement ») : l'offre
// ÉCRITE de financement (crédit ou location) et l'offre CSE concurrente, avec
// l'échéance face à l'économie mensuelle et la comparaison achat / CSE servies
// par le serveur (`economie_ci.financement`, `vue_interne.comparaison_cse`).
// Rien de ce volet n'atteint le client : il ne lit JAMAIS
// `economie_ci_publique` (seulement la réponse INTERNE de l'aperçu) et n'est
// monté que dans la carte « Économies » du générateur. Aucun taux par défaut,
// aucun nom de concurrent ; chaque nombre tel que tapé (`step="any"`).
import { Input, Label } from '../../../ui'
import { formatNumber } from '../../../lib/format'

const SELECT = 'form-control form-control-sm'
const mad = (v) => (v === null || v === undefined ? '—' : `${formatNumber(v, { decimals: 0 })} MAD`)

const CHAMPS_FINANCEMENT = [
  ['preteur', 'Prêteur / bailleur', 'text'],
  ['reference_offre', "Référence de l'offre", 'text'],
  ['date_offre', "Date de l'offre", 'date'],
  ['montant_finance_mad', 'Montant financé (MAD)', 'number'],
  ['apport_mad', 'Apport (MAD)', 'number'],
  ['duree_mois', 'Durée (mois)', 'number'],
  ['echeance_mad', 'Échéance (MAD)', 'number'],
  ['frais_mad', 'Frais (MAD)', 'number'],
  ['taux_annuel_pct', "Taux annuel (%) — seulement s'il est écrit", 'number'],
  ['valeur_residuelle_mad', 'Valeur résiduelle (MAD)', 'number'],
  ['source', 'Source (offre écrite)', 'text'],
]
const CHAMPS_CSE = [
  ['tarif_kwh_ht', 'Tarif CSE (MAD/kWh HT)', 'number'],
  ['duree_ans', 'Durée (ans)', 'number'],
  ['indexation_pct_an', "Indexation (%/an) — seulement si écrite", 'number'],
  ['source', 'Source (offre écrite)', 'text'],
]

function Champs({ prefixe, champs, valeur, poser, erreur, erreurChamp }) {
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {champs.map(([cle, libelle, type]) => (
        <div className="grid gap-1.5" key={cle}>
          <Label htmlFor={`gen-${prefixe}-${cle}`}>{libelle}</Label>
          <Input id={`gen-${prefixe}-${cle}`} type={type}
                 {...(type === 'number' ? { min: '0', step: 'any' } : {})}
                 value={valeur?.[cle] ?? ''} onChange={(e) => poser(cle, e.target.value)} />
          {erreurChamp === `${prefixe}.${cle}` && erreur && (
            <p className="text-xs text-destructive" data-testid={`erreur-${prefixe}.${cle}`}>{erreur}</p>
          )}
        </div>
      ))}
    </div>
  )
}

export default function VoletInterneEconomieCi({ apercu, eco, setEcoChamp }) {
  const { donnees: d, erreur, erreurChamp } = apercu || {}
  const offre = eco?.offre_financement || null
  const cse = eco?.offre_cse_concurrente || null
  const poserOffre = (cle, v) => setEcoChamp('offre_financement', { ...(offre || {}), [cle]: v })
  const poserCse = (cle, v) => setEcoChamp('offre_cse_concurrente', { ...(cse || {}), [cle]: v })
  const f = d?.financement
  const comp = d?.vue_interne?.comparaison_cse
  const sr500 = d?.vue_interne?.sr500
  return (
    <details className="rounded-md border border-warning/40 p-2 text-xs" data-testid="eco-ci-volet-interne">
      <summary className="cursor-pointer font-semibold">Vendeur seulement — financement et offre concurrente</summary>
      <div className="mt-2 grid gap-3">
        <fieldset className="grid gap-2">
          <legend className="font-semibold">Offre écrite de financement</legend>
          <div className="grid gap-1.5 sm:w-1/3">
            <Label htmlFor="gen-offre_financement-nature">Nature</Label>
            <select id="gen-offre_financement-nature" className={SELECT} value={offre?.nature || ''}
                    onChange={(e) => poserOffre('nature', e.target.value)}>
              <option value="">—</option>
              <option value="credit">Crédit</option>
              <option value="credit_bail">Location (crédit-bail)</option>
            </select>
            <select aria-label="Base de l'échéance" className={SELECT} value={offre?.base_echeance || ''}
                    onChange={(e) => poserOffre('base_echeance', e.target.value)}>
              <option value="">Base de l'échéance —</option>
              <option value="ht">HT</option>
              <option value="ttc">TTC</option>
            </select>
          </div>
          <Champs prefixe="offre_financement" champs={CHAMPS_FINANCEMENT} valeur={offre}
                  poser={poserOffre} erreur={erreur} erreurChamp={erreurChamp} />
          {f && (
            <p data-testid="eco-ci-financement">
              Échéance {mad(f.echeance_mad)} / mois face à une économie mensuelle moyenne de
              {' '}{mad(f.economie_mensuelle_moyenne_mad)} — écart {mad(f.ecart_mensuel_mad)}.
              {' '}Libellé client : « {f.libelle_client} ».
              {f.taux_annuel_pct != null ? ` Taux écrit : ${formatNumber(f.taux_annuel_pct)} %.` : ''}
            </p>
          )}
        </fieldset>
        <fieldset className="grid gap-2">
          <legend className="font-semibold">Offre CSE concurrente</legend>
          <Champs prefixe="offre_cse_concurrente" champs={CHAMPS_CSE} valeur={cse}
                  poser={poserCse} erreur={erreur} erreurChamp={erreurChamp} />
          {comp && (
            <p data-testid="eco-ci-comparaison-cse">
              {comp.statut === 'calculee'
                ? <>Cumul achat {mad(comp.cumul_achat_mad)} · cumul offre CSE {mad(comp.cumul_offre_mad)}
                  {comp.annee_croisement != null ? ` · croisement en année ${comp.annee_croisement}` : ' · aucun croisement'}</>
                : <>Comparaison omise : {comp.motif}</>}
            </p>
          )}
        </fieldset>
        {sr500 && (
          <p data-testid="eco-ci-sr500">SR500 : {sr500.statut} — {sr500.motif}</p>
        )}
      </div>
    </details>
  )
}
