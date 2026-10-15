import { expect } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import RelanceEtapeRow from '../features/crm/relances/RelanceEtapeRow'

/* Parcours « Visite acceptée » PARTAGÉ des suites RelanceEtapeRow (ENF19), sans
   aucun `vi.mock` : chaque suite garde ses propres neutralisations d'API.
   « Fait » → « Visite acceptée » → « Confirmer » : la modale s'ouvre AVANT tout
   envoi ; « Date pas encore fixée » envoie l'issue serveur exacte. */
const noop = () => {}

/** « Fait » → « Visite acceptée » → « Confirmer » : la fenêtre de planification
 *  s'affiche AVANT tout envoi (l'appelant vérifie qu'aucune API n'a été appelée). */
export async function ouvrirPlanificationVisite() {
  fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Visite acceptée' }))
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
  expect(await screen.findByText('Planifier la visite technique')).toBeInTheDocument()
}

export async function parcoursVisiteAcceptee(etape, onFait) {
  render(
    <RelanceEtapeRow
      etape={etape} onFait={onFait} onSauter={noop} onReporter={noop} onOuvrirMessage={noop}
    />,
  )
  await ouvrirPlanificationVisite()
  expect(onFait).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Date pas encore fixée' }))
  await waitFor(() => expect(onFait).toHaveBeenCalledWith(
    etape.id, { outcome: 'visite_acceptee' }))
}
