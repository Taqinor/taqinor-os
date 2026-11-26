import { useState } from 'react'
import { Link } from 'react-router-dom'
import { lienManque } from './lienManque'
import { manqueClair } from './nomsPertes'
import { CeQuiEstSur } from './ResultatIncomplet'
import { BoutonCalculer } from './PanneauProduction'
import { premierOngletEtape } from '../atelier/parcoursGuide' // R5B-N5 — l'onglet qui ouvre une étape

/* L'ÉTAT « PAS ENCORE SIMULÉ » (jamais lancé, ou calcul périmé) — même langage visuel que le résultat
   incomplet (ResultatsIncomplet.dc.html) : à gauche la carte sombre et le bouton de calcul (LE bouton
   existant `BoutonCalculer`, même requête, même suivi, mêmes refus), à droite « Pour un résultat complet »
   (lignes de `parcours.manque`, déjà fusionnées par le serveur : `nombre` = lignes identiques), dessous
   « Ce qui est déjà sûr ». Titres en clair (`MANQUES_CLAIRS`) ; la phrase servie reste derrière le « ? ».
   Aucune figure n'est écrite ici. */

const RANG = { bloquant: 0, a_regler: 1, info: 2 }
/* Ces deux lignes disent « lancez/relancez le calcul » : la carte sombre, à côté, porte déjà CE bouton — la liste
   ne garde que ce que l'utilisateur doit RENSEIGNER. */
const DOUBLON_DU_BOUTON = ['production_non_simulee', 'simulation_perimee']

function Ligne({ rang, m, calepinageId }) {
  const [ouvert, setOuvert] = useState(false)
  const { titre, ligne, bouton, technique, etape } = manqueClair(m)
  // R5B-N5 — une ligne qui nomme son ÉTAPE (ombres) ouvre l'écran de cette étape (`state.etapeChoisie`, comme le clic sur
  // l'étape : jamais la feuille « Avancé »), sinon la cible servie, comme avant.
  const vers = etape ? lienManque(calepinageId, { onglet: premierOngletEtape(etape) }) : lienManque(calepinageId, m.cible)
  return (
    <li className="cal-resinc-ligne" data-testid="cal-avant-ligne" data-code={m.code}>
      <span className="cal-resinc-rang" aria-hidden="true">{rang}</span>
      <span className="cal-resinc-texte">
        <span className="cal-resinc-nom">
          {titre}
          {technique && (
            <button type="button" className="cal-resinc-aide" aria-expanded={ouvert} title={technique}
              aria-label={`Pourquoi : ${titre}`} data-testid="cal-avant-aide" onClick={() => setOuvert((o) => !o)}>?</button>
          )}
        </span>
        {ligne && <span className="cal-resinc-raison">{ligne}</span>}
        {technique && ouvert && <span className="cal-resinc-raison" data-testid="cal-avant-servi">{technique}</span>}
      </span>
      <Link to={vers} state={etape ? { etapeChoisie: true } : undefined} className="cal-resinc-bouton"
        data-testid="cal-avant-renseigner">
        {bouton}
      </Link>
    </li>
  )
}

export default function ResultatAvantSimulation({
  calepinageId, data, parcours = null, intervalleMs = 2000, onTermine,
}) {
  const perime = data?.simulation_perimee === true
  const manque = (parcours?.manque ?? [])
    .filter((m) => !DOUBLON_DU_BOUTON.includes(m?.code))
    .map((m, i) => ({ m, i }))
    .sort((a, b) => (RANG[a.m.gravite] ?? 2) - (RANG[b.m.gravite] ?? 2) || a.i - b.i)
  return (
    <div className="cal-resinc" data-testid="cal-avant-simulation" data-etat={perime ? 'perime' : 'jamais'}>
      <div className="cal-resinc-haut">
        <section className="cal-res-tuile cal-resinc-plafond">
          <h1 className="cal-res-titre cal-resavant-titre" title={perime ? data?.motif || undefined : undefined}
            data-testid="cal-avant-titre">
            {perime ? 'Calcul à refaire' : 'Production pas encore calculée'}
          </h1>
          <p className="cal-resinc-phrase" data-testid="cal-avant-phrase">
            {perime
              ? 'Le calepinage ou un réglage de votre société a changé depuis le dernier calcul : relancez-le pour retrouver la production.'
              : 'Le calcul estime ce que vos panneaux produiront chaque année, mois par mois, à partir de leur pose et du soleil du site.'}
          </p>
          <BoutonCalculer calepinageId={calepinageId} data={data} avertissements={[]} manque={[]}
            intervalleMs={intervalleMs} onTermine={onTermine} variante="carte" />
        </section>
        <section className="cal-res-carte" data-testid="cal-avant-liste">
          <h2 className="cal-res-titre">Pour un résultat complet</h2>
          {manque.length === 0
            ? <p className="cal-res-sourdine m-0">Rien d’autre à renseigner : vous pouvez lancer la simulation.</p>
            : (
              <ol className="cal-resinc-liste">
                {manque.map(({ m, i }, k) => (
                  <Ligne key={`${m.code}-${m.cible?.onglet}-${m.cible?.champ}-${i}`} rang={k + 1} m={m}
                    calepinageId={calepinageId} />
                ))}
              </ol>
            )}
        </section>
      </div>
      <CeQuiEstSur data={data} parcours={parcours} />
    </div>
  )
}
