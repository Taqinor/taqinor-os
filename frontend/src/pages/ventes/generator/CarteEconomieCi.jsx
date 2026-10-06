// CIQ223 — LA CARTE « ÉCONOMIES » C&I, servie par le serveur (`economie_ci`,
// contrat `economie_ci.json`) : base HT/TTC (les DEUX côte à côte quand la TVA
// récupérable est inconnue), économie de l'année 1 par poste, facture
// avant/après, cumuls aux jalons, TRI avec son horizon, retour, VAN seulement
// si le client a déclaré son taux, coût du kWh solaire face au tarif évité,
// revente MT (ou mention BT), O&M, omissions avec leur motif.
// AUCUN calcul ici : chaque chiffre est celui du serveur ; seuls des formats
// d'affichage. Les saisies (TVA récupérable, taux d'actualisation + source)
// sont tapées telles quelles (`step="any"`, jamais corrigées).
import { Input, Label } from '../../../ui'
import { formatNumber } from '../../../lib/format'

const SELECT = 'form-control form-control-sm'
const mad = (v) => (v === null || v === undefined ? '—' : `${formatNumber(v, { decimals: 0 })} MAD`)
const nb = (v, d) => (v === null || v === undefined ? '—' : formatNumber(v, d === undefined ? {} : { decimals: d }))

const LIBELLES_OM = {
  souscrit: 'O&M souscrit',
  propose: 'O&M proposé',
  absent: 'sans O&M',
  tarif_a_renseigner: 'O&M : tarif à renseigner',
}

function Saisies({ eco, setEcoChamp }) {
  const e = eco || {}
  const taux = e.taux_actualisation_client || {}
  return (
    <div className="grid gap-3 sm:grid-cols-3" data-testid="eco-ci-saisies">
      <div className="grid gap-1.5">
        <Label htmlFor="gen-eco-tva">TVA récupérable par le client</Label>
        <select id="gen-eco-tva" className={SELECT} value={e.tva_recuperable?.valeur || ''}
                onChange={(ev) => setEcoChamp('tva_recuperable', ev.target.value
                  ? { valeur: ev.target.value, provenance: 'declare_client', saisi_le: e.tva_recuperable?.saisi_le || '' }
                  : null)}>
          <option value="">—</option>
          <option value="oui">Oui</option>
          <option value="non">Non</option>
          <option value="inconnu">Inconnu</option>
        </select>
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="gen-eco-taux">Taux d'actualisation déclaré par le client (%)</Label>
        <Input id="gen-eco-taux" type="number" min="0" step="any" value={taux.valeur_pct ?? ''}
               onChange={(ev) => setEcoChamp('taux_actualisation_client', { ...taux, valeur_pct: ev.target.value })} />
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="gen-eco-taux-source">Source du taux</Label>
        <Input id="gen-eco-taux-source" placeholder="ex: déclaré par le DAF" value={taux.source ?? ''}
               onChange={(ev) => setEcoChamp('taux_actualisation_client', { ...taux, source: ev.target.value })} />
      </div>
    </div>
  )
}

function Jalons({ jalons, jalonsTtc }) {
  if (!Array.isArray(jalons) || !jalons.length) return null
  const ttc = Array.isArray(jalonsTtc) ? jalonsTtc : null
  return (
    <table className="w-full text-xs" data-testid="eco-ci-jalons">
      <thead>
        <tr><th className="text-left">Cumul à</th><th>{ttc ? 'HT' : 'Économie cumulée'}</th>{ttc && <th>TTC</th>}</tr>
      </thead>
      <tbody>
        {jalons.map((j, i) => (
          <tr key={j.annee}>
            <td>{j.annee} ans</td><td>{mad(j.cumul_mad)}</td>
            {ttc && <td>{mad(ttc[i]?.cumul_mad)}</td>}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function CarteEconomieCi({ apercu, eco, setEcoChamp, children }) {
  const { donnees: d, chargement, erreur } = apercu || {}
  return (
    <div className="mt-4 grid gap-3 rounded-lg border border-border p-3" data-testid="eco-ci">
      <p className="font-display text-sm font-semibold">Économies (moteur serveur)</p>
      {setEcoChamp && <Saisies eco={eco} setEcoChamp={setEcoChamp} />}
      {erreur && <p className="text-xs text-warning" data-testid="eco-ci-erreur">{erreur}</p>}
      {chargement && !d && <p className="text-xs text-muted-foreground">Calcul des économies…</p>}
      {d && d.statut === 'omis' && (
        <ul className="text-xs text-warning" data-testid="eco-ci-omis">
          {(d.motifs_omission || []).map((m) => <li key={m}>{m}</li>)}
        </ul>
      )}
      {d && d.statut !== 'omis' && (
        <div className="grid gap-2 text-xs" data-testid="eco-ci-resultat">
          {d.motif_base && <p data-testid="eco-ci-base">{d.motif_base}</p>}
          {d.economie_annee1 && (
            <table className="w-full" data-testid="eco-ci-postes">
              <thead>
                <tr>
                  <th className="text-left">Poste</th><th>kWh évités</th><th>Tarif</th>
                  <th>{d.base === 'deux' ? 'Économie HT' : 'Économie année 1'}</th>
                  {d.base === 'deux' && <th>Économie TTC</th>}
                </tr>
              </thead>
              <tbody>
                {(d.economie_annee1.par_poste || []).map((p) => (
                  <tr key={p.poste}>
                    <td>{p.poste}</td><td>{nb(p.kwh_evites)}</td><td>{nb(p.tarif_kwh, 4)}</td>
                    <td>{mad(p.mad)}</td>
                    {d.base === 'deux' && <td>{mad(p.mad_ttc)}</td>}
                  </tr>
                ))}
                <tr>
                  <td>Total</td><td /><td />
                  <td><strong>{mad(d.economie_annee1.total_mad)}</strong></td>
                  {d.base === 'deux' && <td><strong>{mad(d.economie_annee1.total_mad_ttc)}</strong></td>}
                </tr>
              </tbody>
            </table>
          )}
          {(d.facture_avant || d.facture_apres) && (
            <div data-testid="eco-ci-factures">
              {[['Facture avant', d.facture_avant], ['Facture après', d.facture_apres]].map(([lib, f]) => f && (
                <p key={lib}>
                  {lib} : {(f.energie_par_poste || []).map((x) => `${x.poste} ${mad(x.mad_ht ?? x.mad_ttc)}`).join(' · ')}
                  {' · '}prime fixe {mad(f.prime_fixe_mad)}
                </p>
              ))}
            </div>
          )}
          <Jalons jalons={d.jalons} jalonsTtc={d.base === 'deux' ? d.jalons_ttc : null} />
          {d.indicateurs && (
            <p data-testid="eco-ci-indicateurs">
              TRI : <strong>{nb(d.indicateurs.tri_pct, 1)} %</strong> sur {d.indicateurs.tri_horizon_ans} ans
              {' · '}retour : {nb(d.indicateurs.retour_ans)} ans
              {' · '}{d.indicateurs.van_mad != null
                ? <>VAN : {mad(d.indicateurs.van_mad)}</>
                : <span data-testid="eco-ci-van-motif">VAN non calculée : {d.indicateurs.van_motif}</span>}
              {' · '}kWh solaire {nb(d.indicateurs.lcoe_mad_kwh, 3)} MAD face au tarif évité
              {' '}{nb(d.indicateurs.tarif_kwh_evite_moyen, 3)} MAD
            </p>
          )}
          {d.revente && (
            <div data-testid="eco-ci-revente">
              {d.revente.statut === 'calculee' && <p>Revente MT : {mad(d.revente.valeur_mad_an)} / an</p>}
              {(d.revente.mentions || []).map((m) => <p key={m} className="text-muted-foreground">{m}</p>)}
            </div>
          )}
          {d.om && <p data-testid="eco-ci-om">{LIBELLES_OM[d.om.statut] || d.om.statut}
            {d.om.montant_mad_an != null ? ` — ${mad(d.om.montant_mad_an)} / an` : ''}</p>}
          {Array.isArray(d.omissions) && d.omissions.length > 0 && (
            <ul className="text-muted-foreground" data-testid="eco-ci-omissions">
              {d.omissions.map((o) => <li key={o.cle}>{o.cle} : {o.motif}</li>)}
            </ul>
          )}
        </div>
      )}
      {children}
    </div>
  )
}
