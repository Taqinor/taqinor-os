// EZ9 — bascule « ☀ Plein soleil », posée sur les DEUX écrans terrain
// (« Ma journée » et « Interventions ») en plus de Mes préférences.
//
// Un seul état, une seule source : la préférence persistée (`prefs.js`) et
// l'attribut `[data-sunlight]` sur <html> — le mode n'est PAS un troisième
// thème, c'est le même patron que `[data-density]` (tokens.css).
import { useState } from 'react'
import { Sun } from 'lucide-react'
import { Button } from './Button'
import { getSunlightPref, setSunlightPref } from '../pages/preferences/prefs'

export function SunlightToggle({ className }) {
  const [on, setOn] = useState(getSunlightPref)
  const basculer = () => {
    const next = !on
    setOn(next)
    setSunlightPref(next)
  }
  return (
    <Button
      size="sm"
      variant={on ? 'default' : 'ghost'}
      className={className}
      onClick={basculer}
      aria-pressed={on}
      data-testid="sunlight-toggle"
      title={on
        ? 'Désactiver le mode « Plein soleil »'
        : 'Contraste maximal pour travailler en plein soleil'}
      aria-label={on ? 'Désactiver le mode Plein soleil' : 'Activer le mode Plein soleil'}
    >
      <Sun className="size-4" aria-hidden="true" />
      <span className="hidden sm:inline">Plein soleil</span>
    </Button>
  )
}

export default SunlightToggle
