// ALEA71 (D-ACAL-97, contrôle C4-E7) — la carte « Conception » de la fiche du
// lead : ce que le moteur UNIQUE a rangé pour ce lead (taille, production,
// économies, retour sur investissement avec la source du prix, suppositions
// avec leur champ, « Recalcul en cours », phrase du dernier recalcul).
//
// Aucun calcul ici : des lectures de `GET ventes/conception/<lead>/` (contrat
// `apps/ventes/contract_samples/conception_lead.json`). La carte n'écrit rien.
// Un lead tout neuf n'a pas encore de conception (404 = la réponse NORMALE du serveur) :
// la carte le dit calmement ; la lecture est partagée avec l'onglet Devis (useConceptionLead). La PREMIÈRE conception d'un
// lead se calcule en arrière-plan : après une action (ou à l'ouverture d'un lead créé à l'instant) un 404 est « en cours de
// calcul », relu de façon BORNÉE par le store partagé (une minuterie par lead).
import { useEffect, useState } from 'react'
import { Button } from '../../../ui'
import useConceptionLead, { relireConceptionLead } from './useConceptionLead'
import { formatKwc, formatMAD, formatNumber } from '../../../lib/format'

const OPTIONS = [['sans', 'Sans batterie'], ['avec', 'Avec batterie']]
/** Les valeurs servies d'une option qui portent un produit désigné à la main (`source: 'impose'`). */
const DESIGNES = ['onduleur_produit', 'module_produit']

/** Une valeur servie `{valeur, unite, source}` → sa valeur, ou `null`. */
const lire = (table, cle) => table?.[cle]?.valeur ?? null

function Ligne({ libelle, children, testId }) {
  return (
    <div className="flex justify-between gap-2" data-testid={testId}>
      <dt className="text-muted-foreground">{libelle}</dt>
      <dd className="m-0 text-right text-foreground">{children}</dd>
    </div>
  )
}

function Colonne({ option, titre, table, payback, retenue = false }) {
  const panneaux = lire(table, 'nb_panneaux')
  const kwc = lire(table, 'puissance_kwc')
  const production = lire(table, 'production_annuelle')
  const economies = lire(table, 'economies_annuelles')
  const m3 = lire(table, 'm3_jour')
  const retour = lire(table, 'payback')
  return (
    <div className="min-w-0 flex-1" data-testid={`carte-conception-option-${option}`}>
      {titre && (
        <div className="mb-1 text-xs font-semibold text-foreground">
          {titre}
          {retenue && (
            <span className="ml-2 rounded border border-border px-1 text-xs font-normal text-muted-foreground"
              data-testid={`carte-conception-retenue-${option}`}>retenue</span>
          )}
          {/* D-ACAL-109 — laquelle des options porte le matériel désigné à la main (source servie « impose ») ;
              la phrase servie qui le dit est dans les suppositions. */}
          {DESIGNES.some((cle) => table?.[cle]?.source === 'impose') && (
            <span className="ml-2 rounded border border-border px-1 text-xs font-normal text-muted-foreground"
              data-testid={`carte-conception-designe-${option}`}>matériel désigné</span>
          )}
        </div>
      )}
      <dl className="m-0 flex flex-col gap-1">
        {panneaux != null && (
          <Ligne libelle="Taille">
            {panneaux} panneaux{kwc != null ? ` · ${formatKwc(kwc)}` : ''}
          </Ligne>
        )}
        {production != null && (
          <Ligne libelle="Production">{formatNumber(production, { decimals: 0 })} kWh/an</Ligne>
        )}
        {m3 != null && <Ligne libelle="Eau pompée">{formatNumber(m3, { maxDecimals: 1 })} m³/jour</Ligne>}
        {/* R5F-N1 — en C&I, le retour lit l'économie du DEVIS (ses kWh, sa base) : quand elle diffère de
            celle de la conception, chacune est nommée pour ce qu'elle est (aucun chiffre changé). */}
        {economies != null && (
          <Ligne libelle={payback?.devis_ref && table?.payback?.economie_annuelle != null
            && Math.round(table.payback.economie_annuelle) !== Math.round(economies)
            ? 'Économies (conception du lead)' : 'Économies'}>
            {formatMAD(economies, { decimals: 0 })}/an
          </Ligne>
        )}
        {table?.payback !== undefined && (
          <Ligne libelle="Retour">
            {retour != null
              ? <>
                {`${formatNumber(retour, { maxDecimals: 1 })} ans`}
                {payback?.devis_ref && (
                  <span className="block text-xs text-muted-foreground">
                    d'après le devis {payback.devis_ref}
                  </span>
                )}
                {/* T4-X9-016 — le montant et l'économie de CETTE option, servis avec le retour ;
                    T4-X6-006 — sur SA base (« HT » quand la TVA du client est récupérable). */}
                {table.payback.investissement != null && table.payback.economie_annuelle != null && (
                  <span className="block text-xs text-muted-foreground" data-testid={`carte-conception-calcul-${option}`}>
                    {formatMAD(table.payback.investissement, { decimals: 0 })} {table.payback.base || 'TTC'} pour{' '}
                    {formatMAD(table.payback.economie_annuelle, { decimals: 0 })}/an — {table.payback.calcul}
                  </span>
                )}
              </>
              : <span className="text-xs text-muted-foreground">{payback?.motif || '—'}</span>}
          </Ligne>
        )}
      </dl>
    </div>
  )
}

/** Lane E9 — LE gabarit de `apps/ventes/electrical_service.py::motifs_fiche_incomplete` (un motif par champ, joints
    par « ; » dans `non_calcule`) : « « <champ> » non renseigné(e) sur la fiche technique du panneau|de l'onduleur — … ».
    Seule une phrase qui suit EXACTEMENT ce gabarit est regroupée ; toute autre est dite telle quelle (rien n'est perdu). */
const MOTIF_FICHE = /^« (.+) » non renseigné\(e\) sur la fiche technique (du panneau|de l'onduleur) — /

/** Les lignes `verdicts.non_calcule`, sans doublon : `{ cle, phrase }` (dite telle quelle) ou, pour une fiche technique
    incomplète, `{ cle, produit, champs }` — UNE ligne par produit (le module / l'onduleur que l'option sert). */
function phrasesNonCalcule(valeurs) {
  const lignes = new Map()
  for (const table of Object.values(valeurs || {})) {
    const phrase = table?.verdicts?.valeur?.non_calcule
    if (!phrase) continue
    const noms = { 'du panneau': table?.module?.valeur, "de l'onduleur": table?.onduleurs?.valeur?.[0]?.designation }
    for (const morceau of phrase.split(' ; ')) {
      const m = MOTIF_FICHE.exec(morceau)
      const produit = m ? (noms[m[2]] || (m[2] === 'du panneau' ? 'panneau' : 'onduleur')) : null
      if (!m) { lignes.set(morceau, { cle: morceau, phrase: morceau }); continue }
      const ligne = lignes.get(`fiche:${produit}`) ?? { cle: `fiche:${produit}`, produit, champs: [] }
      if (!ligne.champs.includes(m[1])) ligne.champs.push(m[1])
      lignes.set(ligne.cle, ligne)
    }
  }
  return [...lignes.values()]
}

/** Lane E9 — une fiche technique incomplète en UNE ligne ; ses champs sur demande. */
function LigneFiche({ ligne }) {
  if (ligne.phrase) return <li data-testid="carte-conception-non-calcule">{ligne.phrase}</li>
  const n = ligne.champs.length
  return (
    <li data-testid="carte-conception-non-calcule">
      <span data-zone="fiche-titre">
        {`Fiche technique de « ${ligne.produit} » incomplète (${n} champ${n > 1 ? 's' : ''}) : complétez-la dans Stock → Catalogue`}
      </span>
      <details>
        <summary className="min-h-11 cursor-pointer">Voir les champs</summary>
        <ul className="m-0 pl-4">{ligne.champs.map((c) => <li key={c}>{c}</li>)}</ul>
      </details>
    </li>
  )
}

export default function CarteConception({ leadId, creeLe = null, delaiRelectureMs = 4000, maxRelectures = 6 }) {
  // R5A-N6 — la conception est lue UNE fois par fiche (useConceptionLead, partagée avec l'onglet Devis) ; un 404 est l'état
  // calme « pas encore de conception », jamais rejoué. Seule une version PÉRIMÉE (réponse 200 « recalcul en cours ») est
  // relue, bornée ; « Relire » est une lecture de plus, jamais une chaîne.
  const lu = useConceptionLead(leadId, { creeLe })
  const conception = lu.donnees?.etat && lu.donnees.etat !== 'aucune' ? lu.donnees : null
  const perimee = Boolean(conception?.perimee)
  const [relectures, setRelectures] = useState(0)
  const [perimeeVue, setPerimeeVue] = useState(false)
  if (perimeeVue !== perimee) {
    setPerimeeVue(perimee)
    if (!perimee) setRelectures(0)
  }
  useEffect(() => {
    if (!leadId || !perimee || relectures >= maxRelectures) return undefined
    const minuterie = setTimeout(() => {
      setRelectures((n) => n + 1)
      relireConceptionLead(leadId)
    }, delaiRelectureMs)
    return () => clearTimeout(minuterie)
  }, [leadId, perimee, relectures, maxRelectures, delaiRelectureMs])

  const epuisee = perimee && relectures >= maxRelectures // m1 — plus de relecture automatique : la carte le dit
  let statut = 'charge'
  if (lu.statut === 'erreur') statut = 'erreur'
  else if (lu.statut === 'attente') statut = 'absente'
  else if (lu.statut !== 'charge') statut = conception ? 'ok' : 'vide'
  const etat = { epuisee }
  if (!leadId || statut === 'charge') return null
  const boite = 'mb-3 rounded-lg border border-border bg-card p-3 text-sm'
  const titre = <h3 className="mb-2 text-sm font-semibold text-foreground">Conception</h3>

  if (statut === 'absente') {
    return (
      <section className={boite} data-testid="carte-conception-attente">
        {titre}
        <p className="m-0 text-muted-foreground">Conception en cours de calcul…</p>
      </section>
    )
  }
  if (statut === 'vide') {
    return (
      <section className={boite} data-testid="carte-conception-sans-conception">
        {titre}
        <p className="m-0 text-muted-foreground">
          Pas encore de conception : elle apparaît dès que la fiche est assez remplie.
        </p>
      </section>
    )
  }
  if (statut === 'erreur') {
    return (
      <section className={boite} data-testid="carte-conception-indisponible">
        {titre}
        <p className="m-0 text-muted-foreground">Conception indisponible pour le moment.</p>
      </section>
    )
  }

  if (conception.etat === 'refus') {
    const refus = conception.refus || {}
    return (
      <section className={boite} data-testid="carte-conception">
        {titre}
        <p className="m-0 text-warning" data-testid="carte-conception-refus">
          {refus.message}{refus.champ ? ` (champ : ${refus.champ})` : ''}
        </p>
      </section>
    )
  }

  const valeurs = conception.valeurs || {}
  const colonnes = OPTIONS.filter(([cle]) => valeurs[cle])
  const deux = colonnes.length > 1
  const nonCalcules = phrasesNonCalcule(valeurs)
  const raison = conception.declencheur?.raison

  return (
    <section className={boite} data-testid="carte-conception">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="m-0 text-sm font-semibold text-foreground">Conception</h3>
        {conception.perimee && !etat.epuisee && (
          <span className="text-xs text-warning" role="status" data-testid="carte-conception-recalcul">
            Recalcul en cours
          </span>
        )}
        {conception.perimee && etat.epuisee && (
          <span className="flex items-center gap-2 text-xs text-warning" role="status" data-testid="carte-conception-recalcul-long">
            Le recalcul n'est pas terminé.
            <Button type="button" size="sm" variant="outline" onClick={() => relireConceptionLead(leadId)}>Relire</Button>
          </span>
        )}
      </div>
      <div className="flex flex-wrap gap-3">
        {colonnes.map(([cle, libelle]) => (
          <Colonne key={cle} option={cle} titre={deux ? libelle : ''} table={valeurs[cle]}
            payback={conception.payback_devis} retenue={deux && conception.option_retenue === cle} />
        ))}
      </div>
      {(conception.suppositions?.length > 0 || nonCalcules.length > 0) && (
        <div className="mt-2 border-t border-border pt-2">
          <div className="text-xs font-semibold text-foreground">Suppositions à vérifier</div>
          <ul className="m-0 mt-1 list-disc pl-4 text-xs text-muted-foreground">
            {(conception.suppositions || []).map((s, i) => (
              <li key={`${s.code}-${s.champ}-${i}`} data-testid={`carte-conception-supposition-${s.champ}`}>
                {s.message}
              </li>
            ))}
            {nonCalcules.map((ligne) => <LigneFiche key={ligne.cle} ligne={ligne} />)}
          </ul>
        </div>
      )}
      {raison && (
        <p className="m-0 mt-2 text-xs text-muted-foreground" data-testid="carte-conception-historique">
          {raison}
        </p>
      )}
    </section>
  )
}
