// QJR100 — LES PRIMITIVES DE PRÉSENTATION DU GÉNÉRATEUR.
// ---------------------------------------------------------------------------
// `CarteMetrique` est LE SEUL DÉBALLEUR D'UNE VALEUR SIGNÉE (QJR86) de l'écran
// générateur : elle rend la puce « estimation d'exemple » d'une valeur
// `apercu` et le MOTIF FR verbatim d'une valeur `absent(...)`, à la place du
// nombre. C'est ce qui fait de la règle « aucun nombre nu ne se rend » une
// propriété du composant de rendu, et non un `if` que chaque appelant doit
// penser à écrire (QJR35 : la puce était posée à la main sur 4 des 15 cartes).
//
// Elle remplace le `MetricCard` local de `DevisGenerator.jsx` (ex-`:311`) et
// garde EXACTEMENT sa signature (`label`/`value`/`unit`/`recommended`/`accent`/
// `badge`) pour que les quinze appels existants soient inchangés — la voie
// signée (`valeur`) est la nouvelle, et les deux ne se mélangent jamais sur un
// même appel.
//
// `GenCardHeader` est l'autre primitive de l'écran (l'en-tête de carte du
// design system) : elle vit ici avec `CarteMetrique` pour que les morceaux
// extraits (LigneTable, RailArgent, les quatre panneaux de marché) la
// partagent au lieu d'en recopier le balisage — aucun double chemin.
import { unwrap } from '../../../features/ventes/quote/valeur'

/** En-tête de carte du générateur (style design system, repose sur Card). */
export function GenCardHeader({ icon: Icon, title, children }) {
  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-3 sm:px-5">
      {Icon && <Icon className="size-4 text-primary" aria-hidden="true" />}
      <span className="font-display text-base font-semibold tracking-tight">{title}</span>
      {children && <div className="ml-auto flex items-center gap-2">{children}</div>}
    </div>
  )
}

/**
 * Carte de métrique du générateur.
 *
 * DEUX voies, jamais mélangées :
 *   · `valeur` — une VALEUR SIGNÉE (`moteur`/`saisie`/`apercu`/`absent`). Elle
 *     est déballée ICI : une valeur d'aperçu sort avec sa puce, un `absent`
 *     sort avec son motif FR VERBATIM À LA PLACE du chiffre (jamais un 0
 *     déguisé, jamais un tiret muet) ;
 *   · `value` (+ `badge`) — la voie historique, littérale, des quinze appels
 *     existants : rendue à l'octet comme avant.
 *
 * `formatValeur` sert à mettre en forme le nombre déballé (le composant ne
 * décide jamais d'un format monétaire ou d'une unité à la place de l'appelant).
 */
export default function CarteMetrique({
  label, value, unit, recommended, accent, badge,
  valeur = null, formatValeur = (v) => v,
}) {
  let contenu = value
  let puce = badge
  let motif = null
  if (valeur != null) {
    const u = unwrap(valeur)
    if (u.source === null) {
      // Rien à montrer : le motif REMPLACE le chiffre, il ne l'accompagne pas.
      motif = u.motif
      contenu = null
      puce = null
    } else {
      contenu = formatValeur(u.valeur)
      puce = u.puce
    }
  }
  return (
    <div className={`gen-metric${accent ? ' gen-metric-accent' : ''}${recommended ? ' gen-metric-rec' : ''}`}>
      <div className="gen-metric-label">
        {label}
        {recommended && <span className="gen-rec-badge">★ Recommandé</span>}
      </div>
      {motif ? (
        <div className="gen-metric-motif text-xs text-muted-foreground"
             data-testid="gen-metric-motif">
          {motif}
        </div>
      ) : (
        <div className="gen-metric-value">
          {contenu}
          {/* QJR35 — la carte lit une économie/payback dérivé LOCALEMENT
              (miroir `roi`, jamais serveur) sans facture réelle saisie ni
              étude horaire serveur : puce visible À CÔTÉ de la valeur, la
              carte reste rendue (le vendeur s'en sert comme repère). */}
          {puce && (
            <span className="ml-1.5 align-middle rounded px-1.5 py-0.5 text-xs font-semibold uppercase tracking-wide bg-warning/10 text-warning"
                  data-testid="gen-metric-badge-exemple">
              {puce}
            </span>
          )}
        </div>
      )}
      <div className="gen-metric-unit">{unit}</div>
    </div>
  )
}
