import {
  describe, it, expect, beforeEach, vi,
} from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ModeExpert from './ModeExpert'

/* AOF101 (1/2) — le « Done = » exige : mode expert désactivé par défaut ET
   mémorisé PAR UTILISATEUR ; seuils affichés à côté des valeurs (délégué à
   `RobustesseBadges`, testé dans son propre fichier) ; les états sous/au-dessus
   du seuil sont couverts par `RobustesseBadges.test.jsx`. */

beforeEach(() => {
  window.localStorage.clear()
})

describe('ModeExpert — désactivé par défaut', () => {
  it('masque les réglages fins tant que le mode expert n’est pas activé', () => {
    render(<ModeExpert valeurs={{}} onChange={() => {}} />)
    expect(screen.getByRole('switch', { name: /mode expert/i })).not.toBeChecked()
    expect(screen.queryByLabelText('Pas de recherche (m)')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Mode de pose')).not.toBeInTheDocument()
  })

  it('révèle pas de recherche, seuils, phase et mode de pose à l’activation', async () => {
    const user = userEvent.setup()
    render(<ModeExpert valeurs={{}} onChange={() => {}} />)
    await user.click(screen.getByRole('switch', { name: /mode expert/i }))
    expect(screen.getByLabelText('Pas de recherche (m)')).toBeInTheDocument()
    expect(screen.getByLabelText('Phase (m)')).toBeInTheDocument()
    expect(screen.getByLabelText('Seuil marge tronçon (cm)')).toBeInTheDocument()
    expect(screen.getByLabelText('Seuil marge bande (cm)')).toBeInTheDocument()
    expect(screen.getByRole('radiogroup', { name: 'Mode de pose' })).toBeInTheDocument()
  })
})

describe('ModeExpert — mémorisation PAR UTILISATEUR', () => {
  it('un utilisateur qui active le mode expert le retrouve activé au remontage', async () => {
    const user = userEvent.setup()
    const { unmount } = render(<ModeExpert valeurs={{}} onChange={() => {}} utilisateurId="u1" />)
    await user.click(screen.getByRole('switch', { name: /mode expert/i }))
    expect(screen.getByRole('switch', { name: /mode expert/i })).toBeChecked()
    unmount()

    render(<ModeExpert valeurs={{}} onChange={() => {}} utilisateurId="u1" />)
    expect(screen.getByRole('switch', { name: /mode expert/i })).toBeChecked()
  })

  it('un AUTRE utilisateur ne hérite pas de l’activation', async () => {
    const user = userEvent.setup()
    render(<ModeExpert valeurs={{}} onChange={() => {}} utilisateurId="u1" />)
    await user.click(screen.getByRole('switch', { name: /mode expert/i }))

    render(<ModeExpert valeurs={{}} onChange={() => {}} utilisateurId="u2" />)
    expect(screen.getAllByRole('switch', { name: /mode expert/i })[1]).not.toBeChecked()
  })
})

describe('ModeExpert — réglages fins', () => {
  it('le champ Phase est désactivé en mode « rangées explicites » et activé en « rangées uniformes »', async () => {
    const user = userEvent.setup()
    const { rerender } = render(
      <ModeExpert valeurs={{ mode_pose: 'rangees_explicites_dp' }} onChange={() => {}} />,
    )
    await user.click(screen.getByRole('switch', { name: /mode expert/i }))
    expect(screen.getByLabelText('Phase (m)')).toBeDisabled()

    rerender(<ModeExpert valeurs={{ mode_pose: 'rangees_uniformes_phase' }} onChange={() => {}} />)
    expect(screen.getByLabelText('Phase (m)')).toBeEnabled()
  })

  it('change de mode de pose via le Segmented et remonte la valeur brute', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<ModeExpert valeurs={{ mode_pose: 'rangees_explicites_dp' }} onChange={onChange} />)
    await user.click(screen.getByRole('switch', { name: /mode expert/i }))
    await user.click(screen.getByRole('radio', { name: 'Rangées uniformes (phase)' }))
    expect(onChange).toHaveBeenCalledWith({ mode_pose: 'rangees_uniformes_phase' })
  })

  it('convertit le seuil saisi en CENTIMÈTRES vers des mètres pour le moteur', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<ModeExpert valeurs={{}} onChange={onChange} />)
    await user.click(screen.getByRole('switch', { name: /mode expert/i }))
    const champ = screen.getByLabelText('Seuil marge tronçon (cm)')
    await user.clear(champ)
    await user.type(champ, '3')
    expect(onChange).toHaveBeenCalledWith({ marge_troncon_min_m: 0.03 })
  })

  // PV51 — le seul consommateur serveur (`apps/ao/calepinage_io.
  // parametres_vers_document`) lit `phase_forcee_m` : `phase_m` voyageait
  // jusqu'au corps de `/ao/calepinage/calculer/` et le serveur l'ignorait en
  // silence.
  it('la Phase se PRÉREMPLIT depuis `phase_forcee_m` et remonte cette MÊME clé', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<ModeExpert
      valeurs={{ mode_pose: 'rangees_uniformes_phase', phase_forcee_m: 1.2 }}
      onChange={onChange}
    />)
    await user.click(screen.getByRole('switch', { name: /mode expert/i }))
    const champ = screen.getByLabelText('Phase (m)')
    expect(champ).toHaveValue(1.2)

    await user.clear(champ)
    await user.type(champ, '2.5')
    expect(onChange).toHaveBeenCalledWith({ phase_forcee_m: 2.5 })
    expect(onChange).not.toHaveBeenCalledWith(expect.objectContaining({ phase_m: expect.anything() }))
  })

  // PV51 — `rangee_forcee` a été RETIRÉ : aucun consommateur serveur
  // (`calepinage_io.parametres_vers_document` ne lit jamais cette clé).
  it('ne rend plus de champ « Forçage de rangée » (dead field retiré)', async () => {
    const user = userEvent.setup()
    render(<ModeExpert valeurs={{}} onChange={() => {}} />)
    await user.click(screen.getByRole('switch', { name: /mode expert/i }))
    expect(screen.queryByLabelText(/forçage de rangée/i)).not.toBeInTheDocument()
  })
})
