// CIQ125 — LA CARTE RÉSULTAT DU MOTEUR C&I (commercial ET industriel).
// Affiche la réponse de `POST /ventes/etude-ci/preview/` (contrat
// `etude_ci_preview.json`). AUCUN chiffre n'est calculé ici : seuls des formats
// d'affichage (pourcentage d'un taux servi en fraction).
//
// ADEV101 — LA SYNTHÈSE D'ABORD : quatre chiffres en tête (taille retenue,
// économie estimée par an HT, autoconsommation, couverture — et le retour
// seulement quand le serveur le sert), la composition résumée (« prix à
// renseigner », `incomplet`) et les alertes (les internes marquées « vendeur
// seulement ») restent visibles ; le relevé d'ingénieur (raison d'arrêt, paliers,
// bilan par mois, profil type) est replié sous « Détails du calcul ». Aucune
// clé interne n'est affichée brute : un libellé français, sinon la ligne
// « Autres » du détail.
import { formatNumber } from '../../../lib/format'
import { alertesAffichables } from '../../../features/ventes/etudeCiPreview'
import {
  COMMERCIAL_CATEGORIES, COMMERCIAL_CATEGORY_QUESTIONS,
} from '../../../features/ventes/solar'

const RAISONS_ARRET = {
  horizon_marginal: "le palier suivant ne se rembourse plus dans l'horizon marginal",
  toit: 'surface de toit atteinte',
  puissance_souscrite: 'puissance souscrite atteinte',
  plafond_injection: "plafond d'injection atteint",
  onduleurs: "aucune combinaison d'onduleurs ne convient",
  prix_manquants: 'prix de vente manquants',
  taille_explicite: 'taille saisie par le vendeur',
  consommation_absente: 'consommation absente',
}

// Ce qui a refusé un palier (colonne « Retenu ») : la limite, en français.
const BORNES_PALIER = {
  horizon_marginal: 'trop long à rembourser',
  toit: 'toit plein',
  puissance_souscrite: 'puissance souscrite',
  plafond_injection: "plafond d'injection",
  onduleurs: 'onduleurs',
}

const LIBELLES_CATEGORIES = Object.fromEntries(COMMERCIAL_CATEGORIES.map((c) => [c.value, c.label]))
// Libellé de saisie d'une réponse de catégorie (« Nombre de chambres »…).
const LIBELLES_REPONSES = Object.fromEntries(
  Object.values(COMMERCIAL_CATEGORY_QUESTIONS).flat().map((q) => [q.key, q.label]))

const n = (v, decimals) => (v === null || v === undefined ? '—' : formatNumber(v, { decimals }))
const pct = (v) => (v === null || v === undefined ? '—' : `${formatNumber(v * 100, { decimals: 1 })} %`)
const mad = (v) => (v === null || v === undefined ? '—' : `${formatNumber(v, { decimals: 0 })} MAD`)

/** Un chiffre de la synthèse. */
function Chiffre({ id, libelle, valeur, complement = null }) {
  return (
    <div className="rounded-md bg-background/70 p-2" data-testid={id}>
      <p className="text-[11px] text-muted-foreground">{libelle}</p>
      <p className="font-display text-base font-semibold leading-tight">{valeur}</p>
      {complement && <p className="text-[11px] text-muted-foreground">{complement}</p>}
    </div>
  )
}

// CIQ131 — le profil de consommation type retenu par le moteur (catégorie en
// français, source, « estimation » quand aucun horaire n'est déclaré) et les
// réponses SANS effet sur le calcul (libellés de saisie, jamais les clés). Les
// clés sans libellé vont à `autres`.
function ArchetypeEtSansEffet({ profil, autres }) {
  if (!profil) return null
  const a = profil.archetype
  const sansEffet = (profil.reponses_non_consommees || []).map((cle) => {
    if (LIBELLES_REPONSES[cle]) return LIBELLES_REPONSES[cle]
    autres.add(cle)
    return null
  }).filter(Boolean)
  const nom = a ? LIBELLES_CATEGORIES[a.cle] || null : null
  if (a && !nom) autres.add(a.cle)
  return (
    <div className="grid gap-1">
      {nom && (
        <p data-testid="ci-archetype">
          Profil de consommation type : <strong>{nom}</strong>
          {a.source ? ` — source : ${a.source}` : ''}
          {profil.methode === 'archetype' ? ' (estimation : aucun horaire déclaré)' : ''}
        </p>
      )}
      {sansEffet.length > 0 && (
        <p data-testid="ci-sans-effet">
          Sans effet sur le calcul : {sansEffet.join(', ')}.
        </p>
      )}
    </div>
  )
}

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
  const eco = donnees.economie_ci || {}
  const alertes = alertesAffichables(donnees)
  // Les clés internes sans libellé français (affichées ensemble, repliées).
  const autres = new Set()
  let raisonArret = '—'
  if (RAISONS_ARRET[t.raison_arret]) raisonArret = RAISONS_ARRET[t.raison_arret]
  else if (t.raison_arret) {
    autres.add(t.raison_arret)
    raisonArret = 'autre limite'
  }
  const retenu = (pl) => {
    if (pl.admis) return 'oui'
    if (!pl.borne) return 'non'
    if (BORNES_PALIER[pl.borne]) return `non — ${BORNES_PALIER[pl.borne]}`
    autres.add(pl.borne)
    return 'non — autre limite'
  }
  // Appelé comme une fonction (pas un composant) : `autres` doit être complet avant le rendu.
  const profilType = ArchetypeEtSansEffet({ profil: donnees.profil_charge, autres })
  const economieAn = eco.statut !== 'omis' ? eco.economie_annee1?.total_mad : null
  const retour = eco.statut !== 'omis' ? eco.indicateurs?.retour_ans : null
  return (
    <div className="mt-4 rounded-lg border border-info/30 bg-info/5 p-3 sm:p-4 grid gap-3"
         data-testid="ci-resultat">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" data-testid="ci-synthese">
        <Chiffre id="ci-taille-retenue" libelle="Taille retenue"
                 valeur={t.retenue_kwc != null ? `${n(t.retenue_kwc, 2)} kWc` : 'aucune'}
                 complement={t.nb_panneaux != null ? `${n(t.nb_panneaux)} panneaux` : null} />
        <Chiffre id="ci-economie-an" libelle="Économie estimée / an (HT)" valeur={mad(economieAn)} />
        <Chiffre id="ci-autoconso" libelle="Autoconsommation" valeur={pct(b.taux_autoconso)} />
        <Chiffre id="ci-couverture" libelle="Couverture" valeur={pct(b.taux_couverture)} />
        {retour != null && (
          <Chiffre id="ci-retour" libelle="Retour sur investissement" valeur={`${n(retour, 1)} ans`} />
        )}
      </div>
      {donnees.sous_reserve_visite?.valeur && (
        <p className="text-xs text-warning">
          Estimation sous réserve de visite{donnees.sous_reserve_visite.motif ? ` — ${donnees.sous_reserve_visite.motif}` : ''}
        </p>
      )}

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

      <details className="text-xs" data-testid="ci-details-calcul">
        <summary className="cursor-pointer font-semibold">Détails du calcul</summary>
        <div className="mt-2 grid gap-3">
          <p data-testid="ci-raison-arret">Pourquoi cette taille : {raisonArret}</p>

          {Array.isArray(t.paliers) && t.paliers.length > 0 && (
            <table className="w-full" data-testid="ci-paliers">
              <thead>
                <tr>
                  <th className="text-left">kWc</th><th>Prix HT</th><th>Économie / an</th>
                  <th>Retour du palier (ans)</th><th>Retenu</th>
                </tr>
              </thead>
              <tbody>
                {t.paliers.map((pl) => (
                  <tr key={pl.kwc}>
                    <td>{n(pl.kwc, 2)}</td>
                    <td>{n(pl.cout_ht)}</td>
                    <td>{n(pl.economie_annuelle)}</td>
                    <td>{n(pl.ratio_marginal_annees, 2)}</td>
                    <td>{retenu(pl)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <div data-testid="ci-bilan">
            <p>Surplus non valorisé : <strong>{n(b.non_valorise_kwh)} kWh/an</strong></p>
            {Array.isArray(b.par_mois) && b.par_mois.length > 0 && (
              <table className="mt-1 w-full" data-testid="ci-bilan-mois">
                <thead>
                  <tr>
                    <th className="text-left">Mois</th><th>Production</th><th>Consommation</th>
                    <th>Autoconsommé</th><th>Surplus</th>
                  </tr>
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

          {profilType}
          {autres.size > 0 && (
            <p className="text-muted-foreground" data-testid="ci-autres">Autres : {[...autres].join(', ')}</p>
          )}
        </div>
      </details>
    </div>
  )
}