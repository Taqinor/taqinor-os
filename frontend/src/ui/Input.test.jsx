import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Input } from './Input'
import { Textarea } from './Textarea'

/* VX174 — politique de saisie iOS sur les primitives : `sanitize` force
   autoCapitalize/autoCorrect/spellCheck/autoComplete(/inputMode) au lieu du
   défaut navigateur — pour les références/ICE/IF/SKU/emails que le clavier
   iPhone auto-capitalisait/corrigeait silencieusement. */
describe('VX174 — Input/Textarea sanitize', () => {
  it('sanitize="code" pose les 4 attributs off (+ inputMode text)', () => {
    render(<Input sanitize="code" aria-label="Référence" />)
    const el = screen.getByLabelText('Référence')
    expect(el).toHaveAttribute('autocapitalize', 'off')
    expect(el).toHaveAttribute('autocorrect', 'off')
    expect(el).toHaveAttribute('spellcheck', 'false')
    expect(el).toHaveAttribute('autocomplete', 'off')
    expect(el).toHaveAttribute('inputmode', 'text')
  })

  it('sanitize="email" pose autoComplete=email + inputMode=email', () => {
    render(<Input sanitize="email" aria-label="Email" />)
    const el = screen.getByLabelText('Email')
    expect(el).toHaveAttribute('autocapitalize', 'off')
    expect(el).toHaveAttribute('autocomplete', 'email')
    expect(el).toHaveAttribute('inputmode', 'email')
  })

  it('sanitize="name" capitalise les mots mais coupe la correction', () => {
    render(<Input sanitize="name" aria-label="Nom" />)
    const el = screen.getByLabelText('Nom')
    expect(el).toHaveAttribute('autocapitalize', 'words')
    expect(el).toHaveAttribute('autocorrect', 'off')
  })

  it('sans sanitize, aucun attribut forcé (comportement navigateur par défaut inchangé)', () => {
    render(<Input aria-label="Libre" />)
    const el = screen.getByLabelText('Libre')
    expect(el).not.toHaveAttribute('autocapitalize')
    expect(el).not.toHaveAttribute('autocomplete')
  })

  it('un prop explicite reste prioritaire sur le préréglage sanitize', () => {
    render(<Input sanitize="code" autoComplete="one-time-code" aria-label="OTP" />)
    const el = screen.getByLabelText('OTP')
    expect(el).toHaveAttribute('autocomplete', 'one-time-code')
  })

  it('Textarea partage le même préréglage sanitize', () => {
    render(<Textarea sanitize="code" aria-label="Note code" />)
    const el = screen.getByLabelText('Note code')
    expect(el).toHaveAttribute('autocapitalize', 'off')
    expect(el).toHaveAttribute('spellcheck', 'false')
  })
})
