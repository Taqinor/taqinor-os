import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import PrintPageWrapper from './PrintPageWrapper'

/* PUB47 — enveloppe d'impression réutilisable (cockpit) : bouton Imprimer +
   contenu enfant intact, sans dépendre du composant enveloppé. */

describe('PrintPageWrapper (PUB47)', () => {
  it('rend les enfants + un bouton Imprimer qui appelle window.print()', () => {
    const printSpy = vi.spyOn(window, 'print').mockImplementation(() => {})
    render(
      <PrintPageWrapper>
        <div data-testid="child">Contenu enveloppé</div>
      </PrintPageWrapper>,
    )
    expect(screen.getByTestId('child')).toHaveTextContent('Contenu enveloppé')
    screen.getByTestId('ae-print-wrapper-btn').click()
    expect(printSpy).toHaveBeenCalled()
    printSpy.mockRestore()
  })

  it('le bouton porte la classe no-print (masqué par print.css)', () => {
    render(<PrintPageWrapper><div>x</div></PrintPageWrapper>)
    expect(screen.getByTestId('ae-print-wrapper-bar')).toHaveClass('no-print')
  })
})
