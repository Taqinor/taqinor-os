import { useState } from 'react'
import { Camera, Check, Delete } from 'lucide-react'
import { Sheet, SheetContent } from '../../../ui/Sheet'
import { cn } from '../../../lib/cn'
import { DEFAULT_GABARITS } from './ModeChantier.constantes'

/* ============================================================================
   AOF189 — Mode CHANTIER (tablette 768-1024 px) : l'éditeur de toiture/relevé
   devient un outil de terrain, pensé pour être opéré au DOIGT sous le soleil,
   pas à la souris au bureau.
   ----------------------------------------------------------------------------
   Ce composant est un WRAPPER de mise en page/interaction : il reçoit
   l'éditeur réel (canvas + outils, `data-ao-canvas`/`data-ao-outil`, contrat
   AOF8) en `children` et l'entoure des affordances tactiles exigées par le
   Done= : grosses cibles ≥ 44 px, pavé numérique pour les cotes, gabarits
   d'obstacles fréquents au tap, capture photo → repère, et un inspecteur en
   `Sheet` (tiroir bas) plutôt qu'un panneau latéral étroit.

   Le calepinage y est TOUJOURS en lecture (`calepinageEnLecture`, vrai par
   défaut) : on ne règle pas la largeur d'une allée au soleil sur un toit — la
   raison est TOUJOURS affichée à côté du panneau désactivé, jamais un simple
   contrôle mort sans explication (même exigence produit que le mode MOBILE
   d'AOF190).
   ========================================================================== */

// Cible tactile minimale (44 px, recommandation WCAG 2.5.5 / iOS HIG) — Tailwind
// `11` = 2.75rem = 44px à la racine par défaut, donc `h-11 w-11` EST 44 px.
export const TOUCH_TARGET_CLASS = 'min-h-11 min-w-11'

export const RAISON_CALEPINAGE_LECTURE_CHANTIER =
  "Réglages de calepinage en lecture sur tablette chantier : les allées et l'implantation se règlent au bureau, jamais au soleil sur un toit."

function TouchButton({ className, children, ...props }) {
  return (
    <button
      type="button"
      className={cn(
        TOUCH_TARGET_CLASS,
        'flex items-center justify-center gap-2 rounded-lg border px-3 text-sm font-medium',
        'active:scale-95 transition-transform',
        className,
      )}
      {...props}
    >
      {children}
    </button>
  )
}

// Pavé numérique dédié à la saisie d'une cote — évite le clavier système
// (qui masque la moitié de l'écran tablette et n'a pas de touche "valider"
// dédiée à la mesure).
export function PaveNumeriqueCote({ valeur, onChange, onValider, unite = 'm' }) {
  const appuyer = (touche) => {
    if (touche === 'effacer') {
      onChange(valeur.slice(0, -1))
      return
    }
    if (touche === ',' && valeur.includes(',')) return
    onChange(`${valeur}${touche}`)
  }

  const touches = ['1', '2', '3', '4', '5', '6', '7', '8', '9', ',', '0', 'effacer']

  return (
    <div data-ao-tiroir="pave-numerique-cote" className="flex flex-col gap-2">
      <div className="rounded-md border px-3 py-2 text-right font-mono text-lg" aria-live="polite">
        {valeur || '0'} {unite}
      </div>
      <div className="grid grid-cols-3 gap-2">
        {touches.map((touche) => (
          <TouchButton key={touche} onClick={() => appuyer(touche)} aria-label={touche === 'effacer' ? 'Effacer' : touche}>
            {touche === 'effacer' ? <Delete size={18} aria-hidden="true" /> : touche}
          </TouchButton>
        ))}
      </div>
      <TouchButton
        className="w-full border-transparent bg-emerald-600 text-white"
        onClick={onValider}
      >
        <Check size={18} aria-hidden="true" />
        Valider la cote
      </TouchButton>
    </div>
  )
}

// Barre de gabarits d'obstacles fréquents : un tap pose directement l'obstacle
// typé, sans passer par un formulaire.
export function BarreGabarits({ gabarits = DEFAULT_GABARITS, onPoserGabarit }) {
  return (
    <div data-ao-tiroir="gabarits-obstacles" className="flex flex-wrap gap-2" role="toolbar" aria-label="Gabarits d'obstacles fréquents">
      {gabarits.map((g) => (
        <TouchButton key={g.code} onClick={() => onPoserGabarit(g.code)}>
          {g.label}
        </TouchButton>
      ))}
    </div>
  )
}

// Capture photo → repère : ouvre directement l'appareil photo sur mobile/
// tablette (`capture="environment"`) et transmet le fichier au parent, qui le
// rattache au repère sélectionné.
export function CapturePhotoRepere({ onPhoto, disabled }) {
  return (
    <label className={cn(TOUCH_TARGET_CLASS, 'flex cursor-pointer items-center justify-center gap-2 rounded-lg border px-3 text-sm font-medium', disabled && 'pointer-events-none opacity-50')}>
      <Camera size={18} aria-hidden="true" />
      Photo → repère
      <input
        type="file"
        accept="image/*"
        capture="environment"
        className="sr-only"
        disabled={disabled}
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) onPhoto(file)
          e.target.value = ''
        }}
      />
    </label>
  )
}

// Panneau de réglages de calepinage, forcé en LECTURE sur tablette chantier —
// jamais un contrôle mort : la raison est toujours visible à côté.
export function CalepinageLectureSeule({ children, raison = RAISON_CALEPINAGE_LECTURE_CHANTIER }) {
  return (
    <div data-ao-tiroir="calepinage-lecture-chantier" aria-disabled="true">
      <p className="mb-2 text-sm text-muted-foreground">{raison}</p>
      <fieldset disabled className="pointer-events-none opacity-70">
        {children}
      </fieldset>
    </div>
  )
}

export default function ModeChantier({
  children,
  gabarits = DEFAULT_GABARITS,
  onPoserGabarit = () => {},
  onPhoto = () => {},
  inspecteur = null,
  inspecteurOuvert = false,
  onFermerInspecteur = () => {},
  calepinage = null,
  calepinageEnLecture = true,
  raisonLectureCalepinage = RAISON_CALEPINAGE_LECTURE_CHANTIER,
  coteValeur = '',
  onCoteChange = () => {},
  onCoteValider = () => {},
}) {
  const [paveOuvert, setPaveOuvert] = useState(false)

  return (
    <div data-ao-tiroir="mode-chantier" className="flex flex-col gap-3">
      <BarreGabarits gabarits={gabarits} onPoserGabarit={onPoserGabarit} />

      <div className="flex flex-wrap items-center gap-2">
        <CapturePhotoRepere onPhoto={onPhoto} />
        <TouchButton onClick={() => setPaveOuvert(true)}>Saisir une cote</TouchButton>
      </div>

      {/* L'éditeur réel (canvas `data-ao-canvas`, outils `data-ao-outil`) est
          fourni par le parent — ce wrapper ne le recrée jamais. */}
      <div className="min-h-0 flex-1">{children}</div>

      {calepinageEnLecture ? (
        <CalepinageLectureSeule raison={raisonLectureCalepinage}>{calepinage}</CalepinageLectureSeule>
      ) : (
        calepinage
      )}

      {/* Inspecteur en tiroir BAS (bottom sheet) : plus atteignable au pouce
          qu'un panneau latéral étroit sur une tablette tenue à deux mains. */}
      <Sheet open={inspecteurOuvert} onOpenChange={(open) => { if (!open) onFermerInspecteur() }}>
        <SheetContent side="bottom" data-ao-tiroir="inspecteur-chantier">
          {inspecteur}
        </SheetContent>
      </Sheet>

      <Sheet open={paveOuvert} onOpenChange={setPaveOuvert}>
        <SheetContent side="bottom">
          <PaveNumeriqueCote
            valeur={coteValeur}
            onChange={onCoteChange}
            onValider={() => { onCoteValider(); setPaveOuvert(false) }}
          />
        </SheetContent>
      </Sheet>
    </div>
  )
}
