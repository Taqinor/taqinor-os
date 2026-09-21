import { useCallback, useEffect, useRef, useState } from 'react'
import { Maximize2, Minimize2, Redo2, Save, SlidersHorizontal, Undo2 } from 'lucide-react'
import PageHeader from '../../../components/layout/PageHeader'
import {
  Button,
  Card,
  IconButton,
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SimpleTooltip,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  TooltipProvider,
} from '../../../ui'
import { useIsMobile } from '../../../ui/ResponsiveDialog'

/* ============================================================================
   AOF73 — `StudioShell` : la coquille d'ATELIER plein écran, réutilisable.
   ----------------------------------------------------------------------------
   `ListShell` est une coquille de LISTE et `RecordShell` une coquille de FICHE :
   un atelier géométrique (canvas élastique + rail d'outils + inspecteur) n'entre
   dans ni l'une ni l'autre. Cette coquille est la troisième — et la DERNIÈRE :
   l'éditeur de toiture (AOF84+), l'atelier de calepinage (AOF92+) et, plus tard,
   l'atelier villas la consomment tels quels, avec des *slots* différents.

   **Ce n'est PAS un second design system.** Zéro couleur locale, zéro primitif
   neuf : tout est composé de `PageHeader`, `Card`, `Tabs`, `Sheet`, `Tooltip`,
   `Button`/`IconButton` déjà thémés clair/sombre. La coquille n'apporte QUE la
   mise en page (5 zones), la responsivité, le plein écran et le clavier.

   Les 5 zones :
     1. barre d'actions HAUTE  — titre + annuler/rétablir + enregistrer + plein
                                 écran ; `verdict` est un SLOT (la barre de
                                 verdict permanente appartient à AOF93, elle
                                 porte elle-même `data-ao-verdict`).
     2. rail d'OUTILS gauche   — vertical, icône + raccourci clavier, infobulle.
                                 SEUL hook DOM posé ici : `data-ao-outil`
                                 (contrat AOF8, `E2E_HOOKS.md`).
     3. CANVAS central         — élastique (`flex-1`, `min-h-0`), pur conteneur :
                                 `data-ao-canvas` est posé par la SURFACE
                                 elle-même (`CanvasSvg`, AOF74) — « un seul
                                 repère par écran » exige que la coquille ne le
                                 pose pas en double.
     4. INSPECTEUR droit       — repliable ; sous 1024 px il devient un `Sheet`
                                 (même contenu, aucune duplication d'arbre).
     5. barre d'ÉTAT basse     — slot (`BarreEtat`, AOF74).

   Clavier : `F6` / `Maj+F6` fait tourner le focus entre les 3 zones
   principales (rail → canvas → inspecteur), convention des ateliers ; les
   raccourcis d'outils à une touche sont ignorés dès que la frappe vient d'un
   champ de saisie (sinon taper « r » dans le tableau de géométrie changerait
   d'outil).
   ========================================================================== */

// Une frappe venue d'un champ de saisie n'est JAMAIS un raccourci d'atelier.
function estSaisie(cible) {
  if (!cible) return false
  const tag = cible.tagName
  return (
    tag === 'INPUT'
    || tag === 'TEXTAREA'
    || tag === 'SELECT'
    || cible.isContentEditable === true
  )
}

// Plein écran natif, entièrement optionnel : jsdom (et un navigateur qui refuse
// la permission) n'expose pas l'API — la coquille reste parfaitement utilisable
// sans, elle masque simplement le bouton.
function pleinEcranDisponible() {
  return (
    typeof document !== 'undefined'
    && typeof document.documentElement?.requestFullscreen === 'function'
  )
}

export function StudioShell({
  titre,
  sousTitre,
  // Rail d'outils : [{ id, label, icon, raccourci?, disabled? }]
  outils = [],
  outilActif,
  onOutilChange,
  // Barre d'actions haute
  onAnnuler,
  onRetablir,
  peutAnnuler = false,
  peutRetablir = false,
  onEnregistrer,
  enregistrementEnCours = false,
  actions,
  verdict,
  // Inspecteur : [{ id, label, contenu }]
  onglets = [],
  ongletActif,
  onOngletChange,
  inspecteurTitre = 'Inspecteur',
  // Barre d'état basse
  etat,
  children,
  className = '',
}) {
  const racineRef = useRef(null)
  const railRef = useRef(null)
  const canvasRef = useRef(null)
  const inspecteurRef = useRef(null)

  const compact = useIsMobile('(max-width: 1023px)')
  const [inspecteurOuvert, setInspecteurOuvert] = useState(false)
  const [pleinEcran, setPleinEcran] = useState(false)

  // Onglet actif : contrôlé si `ongletActif` est fourni, sinon interne.
  const [ongletInterne, setOngletInterne] = useState(() => onglets[0]?.id)
  const ongletCourant = ongletActif ?? ongletInterne
  const changerOnglet = (id) => {
    setOngletInterne(id)
    onOngletChange?.(id)
  }

  // ── Plein écran ───────────────────────────────────────────────────────────
  const dispo = pleinEcranDisponible()
  useEffect(() => {
    if (typeof document === 'undefined') return undefined
    const onChange = () => setPleinEcran(Boolean(document.fullscreenElement))
    document.addEventListener('fullscreenchange', onChange)
    return () => document.removeEventListener('fullscreenchange', onChange)
  }, [])

  const basculerPleinEcran = useCallback(() => {
    if (typeof document === 'undefined') return
    if (document.fullscreenElement) {
      document.exitFullscreen?.()
    } else {
      racineRef.current?.requestFullscreen?.()
    }
  }, [])

  // ── Navigation clavier entre les 3 zones (F6 / Maj+F6) ────────────────────
  const zones = useCallback(
    () => [railRef, canvasRef, inspecteurRef].map((r) => r.current).filter(Boolean),
    [],
  )

  const tournerZone = useCallback(
    (sens) => {
      const liste = zones()
      if (liste.length === 0) return
      const actif = typeof document !== 'undefined' ? document.activeElement : null
      const index = liste.findIndex((z) => z === actif || z.contains?.(actif))
      const suivant = liste[((index < 0 ? 0 : index) + sens + liste.length) % liste.length]
      suivant?.focus?.()
    },
    [zones],
  )

  const onKeyDown = (e) => {
    if (e.key === 'F6') {
      e.preventDefault()
      tournerZone(e.shiftKey ? -1 : 1)
      return
    }
    if (estSaisie(e.target) || e.ctrlKey || e.metaKey || e.altKey) return
    const outil = outils.find(
      (o) => o.raccourci && !o.disabled && o.raccourci.toLowerCase() === e.key.toLowerCase(),
    )
    if (outil) {
      e.preventDefault()
      onOutilChange?.(outil.id)
    }
  }

  // ── Contenu de l'inspecteur : UN SEUL arbre, monté soit en colonne (bureau)
  //    soit dans un `Sheet` (compact). Pas de duplication de balisage. ───────
  const corpsInspecteur = onglets.length > 0
    ? (
      <Tabs value={ongletCourant} onValueChange={changerOnglet} className="flex min-h-0 flex-1 flex-col">
        <TabsList className="w-full justify-start overflow-x-auto">
          {onglets.map((o) => (
            <TabsTrigger key={o.id} value={o.id}>{o.label}</TabsTrigger>
          ))}
        </TabsList>
        {onglets.map((o) => (
          <TabsContent key={o.id} value={o.id} className="min-h-0 flex-1 overflow-y-auto">
            {o.contenu}
          </TabsContent>
        ))}
      </Tabs>
    )
    : null

  // `.pageheader` porte `margin-bottom: 1.5rem` en CSS NON layerisé (index.css) :
  // seule la forme `!important` de Tailwind v4 (`mb-0!`) la neutralise — un
  // `mb-0` ordinaire perdrait la cascade face à une règle non layerisée.
  const barreHaute = (
    <PageHeader
      className="mb-0! shrink-0"
      title={titre}
      subtitle={sousTitre}
      actions={(
        <div className="flex flex-wrap items-center gap-1.5">
          {actions}
          <SimpleTooltip label="Annuler (Ctrl+Z)">
            <IconButton
              label="Annuler"
              variant="outline"
              size="sm"
              disabled={!peutAnnuler}
              onClick={onAnnuler}
            >
              <Undo2 />
            </IconButton>
          </SimpleTooltip>
          <SimpleTooltip label="Rétablir (Ctrl+Maj+Z)">
            <IconButton
              label="Rétablir"
              variant="outline"
              size="sm"
              disabled={!peutRetablir}
              onClick={onRetablir}
            >
              <Redo2 />
            </IconButton>
          </SimpleTooltip>
          {dispo && (
            <IconButton
              label={pleinEcran ? 'Quitter le plein écran' : 'Plein écran'}
              variant="outline"
              size="sm"
              onClick={basculerPleinEcran}
            >
              {pleinEcran ? <Minimize2 /> : <Maximize2 />}
            </IconButton>
          )}
          {compact && corpsInspecteur && (
            <Button variant="outline" size="sm" onClick={() => setInspecteurOuvert(true)}>
              <SlidersHorizontal aria-hidden="true" />
              {inspecteurTitre}
            </Button>
          )}
          {onEnregistrer && (
            <Button size="sm" loading={enregistrementEnCours} onClick={onEnregistrer}>
              <Save aria-hidden="true" />
              Enregistrer
            </Button>
          )}
        </div>
      )}
      filters={verdict}
    />
  )

  return (
    <TooltipProvider>
      <div
        ref={racineRef}
        onKeyDown={onKeyDown}
        className={`flex h-full min-h-0 flex-col gap-2 bg-background ${className}`.trim()}
      >
        {barreHaute}

        <div className="flex min-h-0 flex-1 gap-2">
          {/* ── 2. Rail d'outils (vertical) ─────────────────────────────── */}
          {outils.length > 0 && (
            <Card
              ref={railRef}
              tabIndex={-1}
              role="toolbar"
              aria-orientation="vertical"
              aria-label="Outils de l'atelier"
              className="flex shrink-0 flex-col gap-1 overflow-y-auto p-1.5 focus-ring"
            >
              {outils.map((outil) => {
                const Icone = outil.icon
                const actif = outil.id === outilActif
                const libelle = outil.raccourci
                  ? `${outil.label} (${outil.raccourci.toUpperCase()})`
                  : outil.label
                return (
                  <SimpleTooltip key={outil.id} label={libelle}>
                    <IconButton
                      label={libelle}
                      data-ao-outil={outil.id}
                      aria-pressed={actif}
                      variant={actif ? 'secondary' : 'ghost'}
                      disabled={outil.disabled}
                      onClick={() => onOutilChange?.(outil.id)}
                    >
                      {Icone
                        ? <Icone aria-hidden="true" />
                        : <span aria-hidden="true">{(outil.label || '?')[0]}</span>}
                    </IconButton>
                  </SimpleTooltip>
                )
              })}
            </Card>
          )}

          {/* ── 3. Canvas élastique (la surface pose son propre
                 `data-ao-canvas` — AOF74) ───────────────────────────────── */}
          <section
            ref={canvasRef}
            tabIndex={-1}
            aria-label="Zone de dessin"
            className="relative flex min-h-0 min-w-0 flex-1 overflow-hidden rounded-xl border border-border bg-card focus-ring"
          >
            {children}
          </section>

          {/* ── 4. Inspecteur (colonne ≥1024 px) ─────────────────────────── */}
          {!compact && corpsInspecteur && (
            <Card
              ref={inspecteurRef}
              tabIndex={-1}
              role="region"
              aria-label={inspecteurTitre}
              className="flex w-[22rem] shrink-0 flex-col gap-2 overflow-hidden p-3 focus-ring"
            >
              {corpsInspecteur}
            </Card>
          )}
        </div>

        {/* ── 5. Barre d'état basse ──────────────────────────────────────── */}
        {etat && (
          <div
            role="status"
            aria-label="État de l'atelier"
            className="shrink-0 rounded-lg border border-border bg-muted px-3 py-1.5 text-xs text-muted-foreground"
          >
            {etat}
          </div>
        )}
      </div>

      {/* Inspecteur en `Sheet` sous 1024 px — MÊME contenu, jamais un second
          arbre de composants à maintenir. */}
      {compact && corpsInspecteur && (
        <Sheet open={inspecteurOuvert} onOpenChange={setInspecteurOuvert}>
          <SheetContent side="right" className="w-[min(22rem,calc(100%-2rem))]">
            <SheetHeader>
              <SheetTitle>{inspecteurTitre}</SheetTitle>
            </SheetHeader>
            <div ref={inspecteurRef} tabIndex={-1} className="flex min-h-0 flex-1 flex-col focus-ring">
              {corpsInspecteur}
            </div>
          </SheetContent>
        </Sheet>
      )}
    </TooltipProvider>
  )
}

export default StudioShell
