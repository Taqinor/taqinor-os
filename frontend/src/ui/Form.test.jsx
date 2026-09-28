import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Form, FormField, FormErrorSummary, useFormField } from './Form'

// Contrôle qui consomme controlProps (comme les primitifs G22/G23).
function FieldInput() {
  const field = useFormField()
  return <input data-testid="ctrl" {...field.controlProps} />
}

/* G127 — Champ de formulaire : indice + erreur ensemble, deux styles d'erreur,
   espace réservé pour la barre d'actions collante (mobile). */
describe('G127 — FormField : indice + erreur', () => {
  it('affiche l’indice ET l’erreur en même temps', () => {
    render(
      <FormField label="Email" hint="Nous ne le partageons jamais" error="Adresse invalide">
        <input />
      </FormField>,
    )
    expect(screen.getByText('Nous ne le partageons jamais')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Adresse invalide')
  })

  it('décrit le contrôle par l’indice ET l’erreur (aria-describedby)', () => {
    render(
      <FormField label="Email" htmlFor="email" hint="Indice" error="Erreur">
        <FieldInput />
      </FormField>,
    )
    const describedBy = screen.getByTestId('ctrl').getAttribute('aria-describedby')
    expect(describedBy).toContain('email-error')
    expect(describedBy).toContain('email-hint')
  })

  it('distingue deux styles d’erreur : « requis » vs « format »', () => {
    const { rerender } = render(
      <FormField label="Nom" error="Champ obligatoire" errorKind="required">
        <input />
      </FormField>,
    )
    expect(screen.getByRole('alert')).toHaveAttribute('data-error-kind', 'required')

    rerender(
      <FormField label="Nom" error="Mauvais format" errorKind="format">
        <input />
      </FormField>,
    )
    expect(screen.getByRole('alert')).toHaveAttribute('data-error-kind', 'format')
  })

  it('réserve l’espace bas sur mobile pour la barre d’actions collante', () => {
    const { container } = render(
      <Form>
        <FormField label="X"><input /></FormField>
      </Form>,
    )
    const form = container.querySelector('form')
    expect(form.className).toContain('pb-20')
    expect(form.className).toContain('sm:pb-0')
  })
})

/* ERR-QAH-PARAMETRES-OBJECT-OBJECT-ERREUR — un appelant qui construit sa
   liste `[{field, message}]` depuis une réponse DRF brute peut par erreur y
   glisser une entrée dont `message` est resté un OBJET (ex. l'enveloppe
   `error: {code:…}` d'un middleware d'erreurs) au lieu d'être réduit à une
   chaîne. `FormErrorSummary` est le point PARTAGÉ par tous les formulaires :
   il ne doit jamais rendre `[object Object]` — il ignore silencieusement une
   entrée dont le message n'est pas une chaîne exploitable. */
describe('FormErrorSummary — jamais [object Object]', () => {
  it('ignore une entrée dont le message est un objet, garde les entrées valides', () => {
    render(
      <FormErrorSummary
        errors={[
          { field: 'visible_a_partir_de', message: 'Ce champ est obligatoire.' },
          { field: 'error', message: { code: 'validation_error' } },
        ]}
      />,
    )
    expect(screen.getByText('Ce champ est obligatoire.')).toBeInTheDocument()
    expect(screen.queryByText(/\[object Object\]/)).not.toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(1)
  })

  it('ne rend rien quand toutes les entrées sont invalides', () => {
    const { container } = render(
      <FormErrorSummary errors={[{ field: 'error', message: { code: 'x' } }]} />,
    )
    expect(container).toBeEmptyDOMElement()
  })
})
