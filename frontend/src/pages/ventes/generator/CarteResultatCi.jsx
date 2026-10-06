// CIQ125 — LA CARTE RÉSULTAT DU MOTEUR C&I (commercial ET industriel).
// Affiche la réponse de `POST /ventes/etude-ci/preview/` TELLE QUELLE
// (contrat `etude_ci_preview.json`) : taille retenue et raison d'arrêt, les
// paliers examinés (coût, économie, ratio marginal), autoconsommation,
// couverture et surplus non valorisé par mois, la composition résumée
// (« prix à renseigner », `incomplet`) et toutes les alertes — les internes
// marquées « vendeur seulement ». AUCUN chiffre n'est calculé ici : seuls des
// formats d'affichage (pourcentage d'un taux servi en fraction).
import { formatNumber } from '../../../lib/format'
import { alertesAffichables } from '../../../features/ventes/etudeCiPreview'

const RAISONS_ARRET = {
  horizon_marginal: 'le palier suivant ne se rembourse plus dans l\'horizon marginal',
  toit: 'surface de toit atteinte',
  puissance_souscrite: 'puissance souscrite atteinte',
  plafond_injection: 'plafond d\'injection atteint',
  onduleurs: 'aucune combinaison d\'onduleurs ne convient',
  prix_manquants: 'prix de vente manquants',
  taille_explicite: 'taille saisie par le vendeur',
  consommation_absente: 'consommation absente',
}

const n = (v, decimals) => (v === null || v === undefined ? '—' : formatNumber(v, { decimals }))
const pct = (v) => (v === null || v === undefined ? '—' : `${formatNumber(v * 100, { decimals: 1 })} %`)

export default function CarteResultatCi({ donnees, chargement, erreur }) {
  if (erreur) {
    return <p className="mt-3 text-xs text-warning" data-testid="ci-resultat-erreur">{erreur}</p>
  }
  if (chargement && !donnees) {
    return <p className="mt-3 text-xs text-muted-foreground" data-testid="ci-resultat-chargement">Calcul du moteur C&I…</p>
  }
  if (!donnees) return null
  const t = donnees.taille || {}
  const b = donnees.bilan || {}
  const c = donnees.composition || {}
  const alertes = alertesAffichables(donnees)
  return (
    <div className="mt-4 rounded-lg border border-info/30 bg-info/5 p-3 sm:p-4 grid gap-3"
         data-testid="ci-resultat">
      <div>
        <p className="font-display text-sm font-semibold" data-testid="ci-taille-retenue">
          Taille retenue : {t.retenue_kwc != null ? `${n(t.retenue_kwc, 2)} kWc` : 'aucune'}
          {t.nb_panneaux != null ? ` · ${n(t.nb_panneaux)} panneaux` : ''}
        </p>
        <p className="text-xs text-muted-foreground" data-testid="ci-raison-arret">
          Arrêt : {RAISONS_ARRET[t.raison_arret] || t.raison_arret || '—'}
        </p>
        {donnees.sous_reserve_visite?.valeur && (
          <p className="text-xs text-warning">
            Estimation sous réserve de visite{donnees.sous_reserve_visite.motif ? ` — ${donnees.sous_reserve_visite.motif}` : ''}
          </p>
        )}
      </div>

      {Array.isArray(t.paliers) && t.paliers.length > 0 && (
        <table className="w-full text-xs" data-testid="ci-paliers">
          <thead>
            <tr><th className="text-left">kWc</th><th>Prix HT</th><th>Économie / an</th><th>Ratio marginal (ans)</th><th>Admis</th></tr>
          </thead>
          <tbody>
            {t.paliers.map((pl) => (
              <tr key={pl.kwc}>
                <td>{n(pl.kwc, 2)}</td>
                <td>{n(pl.cout_ht)}</td>
                <td>{n(pl.economie_annuelle)}</td>
                <td>{n(pl.ratio_marginal_annees, 2)}</td>
                <td>{pl.admis ? 'oui' : `non${pl.borne ? ` (${pl.borne})` : ''}`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="text-xs" data-testid="ci-bilan">
        <p>
          Autoconsommation : <strong>{pct(b.taux_autoconso)}</strong>
          {' · '}Couverture : <strong>{pct(b.taux_couverture)}</strong>
          {' · '}Surplus non valorisé : <strong>{n(b.non_valorise_kwh)} kWh/an</strong>
        </p>
        {Array.isArray(b.par_mois) && b.par_mois.length > 0 && (
          <table className="mt-1 w-full" data-testid="ci-bilan-mois">
            <thead>
              <tr><th className="text-left">Mois</th><th>Production</th><th>Consommation</th><th>Autoconsommé</th><th>Surplus</th></tr>
            </thead>
            <tbody>
              {b.par_mois.map((m) => (
                <tr key={m.mois}>
                  <td>{m.mois}</td><td>{n(m.production_kwh)}</td><td>{n(m.consommation_kwh)}</td>
                  <td>{n(m.autoconso_kwh)}</td><td>{n(m.surplus_kwh)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {Array.isArray(c.lignes) && c.lignes.length > 0 && (
        <div className="text-xs" data-testid="ci-composition">
          <p className="font-semibold">
            Composition{c.incomplet ? ' — devis incomplet' : ''}
          </p>
          <ul className="list-disc pl-4">
            {c.lignes.map((l, i) => (
              <li key={i}>
                {n(l.quantite, 2)} {l.unite || ''} × {l.designation}
                {l.prix_connu === false ? ' — prix à renseigner' : ''}
                {l.a_confirmer_visite ? ' (à confirmer en visite)' : ''}
              </li>
            ))}
          </ul>
        </div>
      )}

      {alertes.length > 0 && (
        <ul className="text-xs grid gap-1" data-testid="ci-alertes">
          {alertes.map((a) => (
            <li key={a.cle}
                className={a.niveau === 'bloquant' ? 'text-destructive' : 'text-warning'}>
              {a.interne && <strong>Vendeur seulement — </strong>}
              {a.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
