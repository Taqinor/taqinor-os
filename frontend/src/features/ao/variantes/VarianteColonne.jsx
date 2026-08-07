import { Image as ImageIcon, Lock, Copy, Pin, CheckCircle2, Info } from 'lucide-react'
import { Card, Button, Badge, Skeleton } from '../../../ui'
import { StatutVariante, StatutControle } from '../statusAo'
import { formatMAD, formatNumber } from '../../../lib/format'

/* ============================================================================
   AOF102 — UNE colonne du comparateur de variantes.
   ----------------------------------------------------------------------------
   Trois bandes, dans cet ordre, TOUJOURS :
     1. TECHNIQUE   — miniature du plan, compte, kWc, kits, allée, marges de
                      robustesse, verdict vs engagement.
     2. CONFORMITÉ AO — caution, délai d'exécution, clauses `ExigenceCPS`
                      bloquantes, marge d'engagement. **Cette bande est le
                      différenciateur revendiqué** (technique + commercial +
                      conformité dans UN écran) : elle se rend TOUJOURS, même
                      quand le serveur n'a rien évalué (statut « avertissement
                      — non évalué »), jamais un vide silencieux qui ferait
                      retomber l'écran au rang de comparateur technique.
     3. INTERNE     — prix/marge, visuellement séparée et étiquetée, rendue
                      UNIQUEMENT si `peutVoirEconomie`. Sans la permission
                      `ao_rentabilite_voir`, `variante.economie` a déjà été
                      RETIRÉ du payload en amont (`VariantesCompare`) : ce
                      composant n'a alors littéralement rien à cacher.

   AUCUN chiffre n'est calculé ici — chaque valeur est une LECTURE du résultat
   serveur (même discipline que `DashboardPage`, AOF172) ; au plus un formatage
   d'affichage. Le verdict n'est jamais rédigé côté front : son libellé vient
   du serveur.

   HOOKS DOM — contrat AOF8 (`features/ao/E2E_HOOKS.md`) : cette colonne porte
   `data-ao-variante` (son hook propriétaire) et `data-ao-etat` sur ses
   pastilles. Elle N'UTILISE PAS `data-ao-verdict` / `data-ao-compte` /
   `data-ao-controle`, dont les propriétaires déclarés sont la barre de verdict
   permanente (AOF93) et le panneau de contrôles avant dépôt (AOF176) : les
   réutiliser ici ferait matcher DEUX éléments à une spec qui vise ces
   panneaux-là. Une spec qui vise une colonne la cible par son
   `data-ao-variante` ou par le nom accessible de la section.

   ── ACTION « DÉTAILS » (PACT172, 07/08/2026) ──────────────────────────────
   Ouvre, via `onDetails` (fourni par `VariantesCompare`), le détail complet
   de la variante : diff de plan, décomposition (AOF104), sensibilités
   (AOF103) et historique de versions (AOF105) — même patron que
   `onDupliquer`/`onEpingler` : le bouton n'apparaît QUE si un gestionnaire est
   fourni, jamais un bouton qui ne peut rien honorer.
   ========================================================================== */

// Les 4 contrôles de la bande CONFORMITÉ AO, dans l'ordre normatif d'AOF102.
// `cle` = clé attendue dans `variante.conformite`.
// eslint-disable-next-line react-refresh/only-export-components -- constante co-localisée (testable), même motif que DevisTab.DEVIS_MINI_TRACK
export const CONTROLES_CONFORMITE = [
  { cle: 'caution', libelle: "Caution constituée et non expirée à l'ouverture" },
  { cle: 'delai_execution', libelle: "Délai d'exécution tenable" },
  { cle: 'clauses_cps', libelle: 'Clauses CPS bloquantes respectées' },
  { cle: 'marge_engagement', libelle: "Marge d'engagement" },
]

const NON_EVALUE = { statut: 'avertissement', detail: 'Non évalué par le serveur.' }

function Ligne({ libelle, children }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1 text-sm">
      <span className="text-muted-foreground">{libelle}</span>
      <span className="text-right font-medium tabular-nums">{children}</span>
    </div>
  )
}

function Miniature({ src, nom, indisponible }) {
  if (src) {
    return (
      <img
        src={src}
        alt={`Plan de la variante ${nom}`}
        className="h-32 w-full rounded-md border border-border bg-white object-contain"
      />
    )
  }
  return (
    <div
      className="flex h-32 w-full flex-col items-center justify-center gap-1 rounded-md border border-dashed border-border bg-muted/40 px-2 text-center"
      role="img"
      aria-label={`Miniature indisponible — ${indisponible}`}
    >
      <ImageIcon size={18} className="text-muted-foreground" aria-hidden="true" />
      <span className="text-[11px] leading-tight text-muted-foreground">{indisponible}</span>
    </div>
  )
}

export function VarianteColonne({
  variante,
  peutVoirEconomie = false,
  miniatureSrc = null,
  miniatureIndisponible = 'Aperçu du plan non généré',
  chargement = false,
  onDupliquer,
  onDefinirRetenue,
  onEpingler,
  onDetails,
}) {
  const t = variante.technique || {}
  const verdict = t.verdict || {}
  const conformite = variante.conformite || {}
  const economie = variante.economie
  const retenue = Boolean(variante.retenue)

  return (
    <Card
      data-ao-variante={variante.statut}
      aria-current={retenue ? 'true' : undefined}
      className={`flex min-w-[15rem] flex-col gap-3 p-4 ${retenue ? 'ring-2 ring-primary' : ''}`}
    >
      <section aria-label={`Variante ${variante.nom}`} className="flex flex-col gap-3">
        {/* ── En-tête : nom, état, marqueur RETENUE ───────────────────────── */}
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="truncate font-medium">{variante.nom}</h3>
            <StatutVariante status={variante.statut} data-ao-etat={variante.statut} className="mt-1" />
          </div>
          {retenue && (
            <Badge tone="success" className="shrink-0">
              <CheckCircle2 size={12} aria-hidden="true" /> Retenue
            </Badge>
          )}
        </div>

        {chargement ? <Skeleton className="h-32 w-full" /> : (
          <Miniature src={miniatureSrc} nom={variante.nom} indisponible={miniatureIndisponible} />
        )}

        {/* ── 1. TECHNIQUE ────────────────────────────────────────────────── */}
        <div className="border-t border-border pt-2">
          <Ligne libelle="Modules">{formatNumber(t.compte_modules, { decimals: 0 })}</Ligne>
          <Ligne libelle="Puissance">{`${formatNumber(t.puissance_kwc, { decimals: 2 })} kWc`}</Ligne>
          <Ligne libelle="Kits">
            {(t.kits || []).length
              ? (t.kits || []).map((k) => `${k.compte}× ${k.nom}`).join(' · ')
              : '—'}
          </Ligne>
          <Ligne libelle="Allée">{t.allee_m != null ? `${formatNumber(t.allee_m, { decimals: 2 })} m` : '—'}</Ligne>
          {(t.marges_robustesse || []).map((m) => (
            <Ligne key={m.libelle} libelle={m.libelle}>{m.valeur_affichee ?? '—'}</Ligne>
          ))}
        </div>

        {/* ── Verdict vs engagement — LIBELLÉ SERVEUR, jamais rédigé ici ──── */}
        <div className="rounded-md border border-border bg-muted/30 p-2">
          <div className="flex items-center justify-between gap-2">
            <StatutControle
              status={verdict.statut === 'confirme' ? 'ok' : verdict.statut === 'tendu' ? 'avertissement' : 'bloquant'}
              label={verdict.libelle_statut ?? '—'}
              data-ao-etat={verdict.statut}
            />
            <span className="text-xs text-muted-foreground">
              {verdict.engagement_modules != null
                ? `engagement ${formatNumber(verdict.engagement_modules, { decimals: 0 })}`
                : 'engagement non fixé'}
            </span>
          </div>
          {verdict.libelle && <p className="mt-1 text-xs text-muted-foreground">{verdict.libelle}</p>}
        </div>

        {/* ── 2. CONFORMITÉ AO — TOUJOURS rendue ──────────────────────────── */}
        <div className="border-t border-border pt-2">
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Conformité AO
          </p>
          <ul className="flex flex-col gap-1">
            {CONTROLES_CONFORMITE.map(({ cle, libelle }) => {
              const c = conformite[cle] || NON_EVALUE
              return (
                <li key={cle} className="flex items-start justify-between gap-2 text-sm">
                  <span className="text-muted-foreground">{libelle}</span>
                  <StatutControle status={c.statut} data-ao-etat={c.statut} title={c.detail} className="shrink-0" />
                </li>
              )
            })}
          </ul>
        </div>

        {/* ── 3. INTERNE — jamais rendue sans la permission ───────────────── */}
        {peutVoirEconomie && economie && (
          <div className="rounded-md border-2 border-dashed border-warning/60 bg-warning/5 p-2">
            <p className="mb-1 flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-warning">
              <Lock size={12} aria-hidden="true" /> Interne — non communicable
            </p>
            <Ligne libelle="Prix de vente HT">
              {economie.prix_vente_ht != null ? formatMAD(economie.prix_vente_ht) : '—'}
            </Ligne>
            <Ligne libelle="Marge">
              {economie.marge_mad != null ? formatMAD(economie.marge_mad) : '—'}
            </Ligne>
            <Ligne libelle="Taux de marge">
              {economie.marge_pct != null ? `${formatNumber(economie.marge_pct, { decimals: 1 })} %` : '—'}
            </Ligne>
          </div>
        )}

        {/* ── Actions ─────────────────────────────────────────────────────── */}
        {/* RÉPARATION 03/08/2026 — « Dupliquer » et « Épingler » ne sont plus
            rendus D'OFFICE : le serveur n'expose ni action de duplication ni
            champ `epinglee`, et un bouton qui ne peut rien honorer ment. Ils
            réapparaissent dès qu'un appelant fournit le gestionnaire — donc
            dès que l'endpoint existe. */}
        <div className="mt-auto flex flex-wrap gap-2 border-t border-border pt-2">
          {onDetails && (
            <Button size="sm" variant="outline" onClick={() => onDetails(variante)}>
              <Info size={14} aria-hidden="true" /> Détails
            </Button>
          )}
          {onDupliquer && (
            <Button size="sm" variant="outline" onClick={() => onDupliquer(variante)}>
              <Copy size={14} aria-hidden="true" /> Dupliquer
            </Button>
          )}
          <Button
            size="sm"
            variant={retenue ? 'secondary' : 'default'}
            disabled={retenue}
            onClick={() => onDefinirRetenue?.(variante)}
          >
            {retenue ? 'Variante retenue' : 'Définir comme retenue'}
          </Button>
          {onEpingler && (
            <Button
              size="sm"
              variant="ghost"
              aria-pressed={Boolean(variante.epinglee)}
              onClick={() => onEpingler(variante)}
            >
              <Pin size={14} aria-hidden="true" /> {variante.epinglee ? 'Épinglée' : 'Épingler'}
            </Button>
          )}
        </div>

        {retenue && (
          <p className="text-xs text-muted-foreground">
            Alimente le bordereau et les planches.
          </p>
        )}
      </section>
    </Card>
  )
}

export default VarianteColonne
