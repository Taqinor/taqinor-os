import { Badge } from '../../../../ui'
import {
  formatDate, formatDateTime, formatNumber, formatPercent,
} from '../../../../lib/format'
import {
  AFaire, BoutonEcran, Ligne, Rangee, SuiteListe, Titre, Vide,
} from './partsTerrain'

/* Copilote vague 2 (CRT-A) — cartes du domaine « calepinage » : `fiche_calepinage`
   (résumé d'un calepinage ou « du lead »), `liste_calepinages` (la file à traiter),
   `contenance` (estimation du nombre de panneaux). Contrats : `calepinage_assistant_resume`,
   `…_du_lead`, `…_a_traiter`, `…_contenance`. Tout est LU du serveur, rien n'est recalculé.

   Aucun bouton « Rafraîchir » : les crochets de `useCarte.js` ne savent pas relancer une
   lecture d'action ; l'assistant relit en répondant de nouveau. */

const SIMULATION = Object.freeze({
  a_jour: 'à jour', perimee: 'périmée', jamais: 'jamais lancée',
})
const VERDICT = Object.freeze({
  conforme: 'conforme', bloquant: 'bloquant', a_verifier: 'à vérifier',
})
const POSTE = Object.freeze({
  temperature: 'Température', shading: 'Ombrage', soiling: 'Salissure',
})
const SOURCE = Object.freeze({ hypothese: 'hypothèse', mesure: 'mesuré' })
const SIGNAL = Object.freeze({
  visite_non_reprise: 'Visite non reprise',
  visite_changee: 'Visite modifiée',
  sans_pose: 'Aucune pose dessinée',
  simulation_jamais: 'Simulation jamais lancée',
  simulation_perimee: 'Simulation périmée',
  bloquant_electrique: 'Blocage électrique',
  devis_absent: 'Aucun devis lié',
  devis_desynchronise: 'Devis pas à jour',
  approbation_attendue: 'Approbation attendue',
  approbation_perimee: 'Approbation périmée',
  approbation_refusee: 'Approbation refusée',
})

const sansTiret = (cle) => String(cle ?? '').replace(/_/g, ' ')
const kwc = (v) => `${formatNumber(v, { decimals: 2 })} kWc`

function Production({ p }) {
  if (!p) return null
  return (
    <div className="mt-1">
      <Ligne etiquette="Production (P50)">
        {formatNumber(p.p50_kwh)} kWh/an
        {p.rendement_kwh_kwc != null ? ` · ${formatNumber(p.rendement_kwh_kwc, { decimals: 1 })} kWh/kWc` : ''}
      </Ligne>
      {p.p90_kwh != null && <Ligne etiquette="Production prudente (P90)">{formatNumber(p.p90_kwh)} kWh/an</Ligne>}
      {p.mention && (
        <p className="mt-1 break-words text-xs font-medium text-warning">{p.mention}</p>
      )}
      {p.portee === 'etude_technique_interne' && (
        <p className="mt-1 text-xs text-muted-foreground">
          Étude technique interne : ce n’est pas le chiffre montré au client (celui du devis).
        </p>
      )}
    </div>
  )
}

function Conception({ c }) {
  if (!c) return null
  const pans = c.pans ?? []
  return (
    <div className="mt-1">
      <Ligne etiquette="Conception">
        {formatNumber(c.modules)} panneaux · {kwc(c.kwc)}
        {c.variantes > 1 ? ` · ${c.variantes} variantes` : ''}
      </Ligne>
      {pans.length > 0 && (
        <ul className="mt-0.5 space-y-0.5 pl-3 text-xs text-muted-foreground">
          {pans.map((p) => (
            <li key={p.pan} className="break-words">
              {p.pan} : {formatNumber(p.modules)} panneaux · {kwc(p.kwc)} · azimut {formatNumber(p.azimut_deg)}°
              {' '}· inclinaison {formatNumber(p.inclinaison_deg)}°
              {p.ombrage_pct != null ? ` · ombrage ${formatPercent(p.ombrage_pct, { decimals: 1 })}` : ''}
            </li>
          ))}
          {c.pans_autres > 0 && <li>et {c.pans_autres} autre(s) pan(s)</li>}
        </ul>
      )}
    </div>
  )
}

function Pertes({ pertes }) {
  if (!pertes?.length) return null
  return (
    <Ligne etiquette="Pertes">
      {pertes.map((p) => (
        `${POSTE[p.poste] ?? sansTiret(p.poste)} ${formatPercent(p.pct, { decimals: 1 })} (${SOURCE[p.source] ?? sansTiret(p.source)})`
      )).join(' · ')}
    </Ligne>
  )
}

function Etats({ d }) {
  const sim = d.simulation
  const elec = d.electrique
  const devis = d.devis
  const visite = d.visite
  return (
    <>
      {sim && (
        <Ligne etiquette="Simulation">
          {SIMULATION[sim.etat] ?? sansTiret(sim.etat)}
          {sim.calcule_le ? ` · calculée le ${formatDateTime(sim.calcule_le)}` : ''}
          {sim.motif ? ` · ${sim.motif}` : ''}
        </Ligne>
      )}
      {elec && (
        <Ligne etiquette="Verdict électrique">
          {VERDICT[elec.verdict] ?? sansTiret(elec.verdict)}
        </Ligne>
      )}
      {elec?.bloquants?.length > 0 && (
        <ul className="mt-0.5 list-disc pl-5 text-xs text-destructive">
          {elec.bloquants.map((b) => <li key={b} className="break-words">{b}</li>)}
        </ul>
      )}
      {devis ? (
        <Ligne etiquette="Devis lié">
          {devis.reference} · {devis.statut}
          {devis.a_jour === false ? ' · pas à jour avec le calepinage' : ''}
          {devis.ecart_pct != null ? ` · écart ${formatPercent(devis.ecart_pct, { decimals: 1 })}` : ''}
        </Ligne>
      ) : <Ligne etiquette="Devis lié">aucun</Ligne>}
      {d.approbation?.exigee && (
        <Ligne etiquette="Approbation">exigée{d.approbation.etat ? ` · ${sansTiret(d.approbation.etat)}` : ''}</Ligne>
      )}
      {visite && (
        <Ligne etiquette="Visite">
          {visite.validee_le ? `validée le ${formatDate(visite.validee_le)}` : 'pas validée'}
          {visite.validee_le ? (visite.reprise ? ' · reprise dans le calepinage' : ' · pas encore reprise') : ''}
        </Ligne>
      )}
    </>
  )
}

function FicheDuCalepinage({ d }) {
  return (
    <div className="min-w-0">
      <Titre>
        {d.reference}
        {d.variante?.nom ? ` — variante « ${d.variante.nom} »` : ''}
      </Titre>
      <p className="-mt-1 mb-1 flex flex-wrap gap-1.5">
        <Badge tone="neutral">{d.statut}</Badge>
        {d.archive && <Badge tone="warning">Archivé</Badge>}
      </p>
      <Conception c={d.conception} />
      <Etats d={d} />
      <Production p={d.production} />
      <Pertes pertes={d.pertes} />
      {d.avertissements?.length > 0 && (
        <ul className="mt-1.5 list-disc pl-5 text-xs text-warning">
          {d.avertissements.map((a) => <li key={a} className="break-words">{a}</li>)}
        </ul>
      )}
    </div>
  )
}

/** `fiche_calepinage` : le résumé d'UN calepinage (id) ou celui « du lead » (peut n'en avoir aucun). */
export function CarteFicheCalepinage({ carte }) {
  const d = carte.donnees ?? {}
  const duLead = !Number.isInteger(d.calepinage)
  const fiche = duLead ? d.calepinage : d
  return (
    <div className="min-w-0">
      {fiche ? <FicheDuCalepinage d={fiche} /> : <Vide texte="Aucun calepinage ouvert pour ce lead." />}
      {duLead && d.visite && !fiche && (
        <p className="mt-1 text-xs text-muted-foreground">
          {d.visite.validee_le ? `Visite validée le ${formatDate(d.visite.validee_le)}.` : 'Visite pas encore validée.'}
        </p>
      )}
      <AFaire cle={d.a_faire} />
      <BoutonEcran chemin={d.lien} libelle={fiche ? 'Ouvrir le calepinage' : 'Ouvrir la fiche du lead'} />
    </div>
  )
}

/** `liste_calepinages` : la file « à traiter », signaux et prochain geste par ligne. */
export function CarteListeCalepinages({ carte }) {
  const d = carte.donnees ?? {}
  const lignes = d.lignes ?? []
  if (!lignes.length) return <Vide texte="Aucun calepinage à traiter." />
  return (
    <div className="min-w-0">
      <Titre>Calepinages à traiter ({d.total ?? lignes.length})</Titre>
      <ul className="space-y-2">
        {lignes.map((l) => (
          <Rangee key={l.calepinage} titre={l.reference}
            detail={`modifié le ${formatDate(l.modifie_le)}`}>
            {l.signaux?.length > 0 && (
              <p className="mt-1 break-words text-xs">{l.signaux.map((s) => SIGNAL[s] ?? sansTiret(s)).join(' · ')}</p>
            )}
            <AFaire cle={l.a_faire} />
            <BoutonEcran chemin={l.lien} libelle="Ouvrir" />
          </Rangee>
        ))}
      </ul>
      <SuiteListe total={d.total} affiche={lignes.length} />
    </div>
  )
}

const ORIGINE = Object.freeze({
  visite: 'Mesuré à la visite',
  trace: 'Pans déjà tracés',
  dicte: 'Dimensions dictées',
})

/** `contenance` : une ESTIMATION du nombre de panneaux — jamais un chiffre de devis. */
export function CarteContenance({ carte }) {
  const d = carte.donnees ?? {}
  const t = d.total
  const zones = d.zones ?? []
  return (
    <div className="min-w-0">
      <p className="mb-1">
        <Badge tone="warning" className="max-w-full whitespace-normal break-words">
          Estimation — {ORIGINE[d.origine] ?? 'origine inconnue'}
        </Badge>
      </p>
      {d.libelle && <p className="break-words text-xs font-medium">{d.libelle}</p>}
      {t && (
        <p className="mt-1.5 break-words text-sm font-semibold">
          {t.modules_min === t.modules_max
            ? `${formatNumber(t.modules_min)} panneaux`
            : `${formatNumber(t.modules_min)} à ${formatNumber(t.modules_max)} panneaux`}
          {' '}({formatNumber(t.kwc_min, { decimals: 2 })} à {formatNumber(t.kwc_max, { decimals: 2 })} kWc)
        </p>
      )}
      <p className="text-xs text-muted-foreground">
        Estimation seulement : ce n’est pas un calepinage, ni un chiffre de devis.
      </p>
      {d.produit && (
        <Ligne etiquette="Panneau">{d.produit.nom} · {formatNumber(d.produit.wc)} Wc</Ligne>
      )}
      {zones.length > 0 && (
        <ul className="mt-1.5 space-y-1">
          {zones.map((z) => (
            <li key={z.zone} className="break-words text-xs">
              {z.zone} : {formatNumber(z.longueur_m, { decimals: 1 })} × {formatNumber(z.largeur_m, { decimals: 1 })} m
              {' '}→ {z.modules_min} à {z.modules_max} panneaux
            </li>
          ))}
        </ul>
      )}
      {d.suppositions?.length > 0 && (
        <ul className="mt-1.5 list-disc pl-5 text-xs text-muted-foreground">
          {d.suppositions.map((s) => <li key={s} className="break-words">{s}</li>)}
        </ul>
      )}
      {d.regles?.length > 0 && (
        <ul className="mt-1.5 list-disc pl-5 text-xs text-muted-foreground">
          {d.regles.map((r) => <li key={r} className="break-words">{r}</li>)}
        </ul>
      )}
      <AFaire cle={d.a_faire} />
      <BoutonEcran chemin={d.lien} libelle="Ouvrir" />
    </div>
  )
}

const CARTES_CALEPINAGE = Object.freeze({
  fiche_calepinage: CarteFicheCalepinage,
  liste_calepinages: CarteListeCalepinages,
  contenance: CarteContenance,
})
export default CARTES_CALEPINAGE
