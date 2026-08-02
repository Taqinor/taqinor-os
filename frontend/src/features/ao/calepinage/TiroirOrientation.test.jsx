import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TiroirOrientation from './TiroirOrientation'

/* AOF98 — une orientation inconstructible est REFUSÉE, jamais dessinée ;
   le motif affiché est celui du serveur (l'écran est la SECONDE ligne de
   défense, la première étant `ErreurOrientation` côté moteur, AOF45). */

const MOTIF_SERVEUR = 'Faîtage est-ouest : les modules regarderaient le NORD — orientation inconstructible.'

const DONNEES = {
  sens_rangees: [
    { code: 'nord_sud', libelle: 'Nord-Sud', disponible: true },
    { code: 'est_ouest', libelle: 'Est-Ouest', disponible: false, motif: MOTIF_SERVEUR },
  ],
  orientations_tables: [
    { code: 'dos_a_dos', libelle: 'Dos-à-dos', disponible: true },
    { code: 'simple_pente', libelle: 'Simple pente', disponible: true },
  ],
  segmentations: [
    { code: 'continue', libelle: 'Surface continue', disponible: true },
    { code: 'arc', libelle: 'Segments (arc)', disponible: true },
  ],
  formes_l: [
    { code: 'continue', libelle: 'L en surface continue', disponible: true },
    { code: 'decoupe', libelle: 'L découpé en deux ailes', disponible: true },
  ],
}

const VALEURS = {
  sens_rangees: 'nord_sud', orientation_table: 'dos_a_dos', segmentation: 'arc', forme_l: 'continue',
}

const monter = (onChange = vi.fn(), donnees = DONNEES) => ({
  onChange,
  ...render(<TiroirOrientation donnees={donnees} valeurs={VALEURS} onChange={onChange} />),
})

describe('TiroirOrientation (AOF98)', () => {
  it("désactive l'orientation incompatible au lieu de la dessiner", () => {
    monter()
    const refuse = screen.getByRole('radio', { name: /Est-Ouest/ })
    expect(refuse).toBeDisabled()
    expect(refuse).toHaveAttribute('title', MOTIF_SERVEUR)
  })

  it('reprend le MOTIF du serveur, sans en inventer un', () => {
    const { container } = monter()
    expect(screen.getByText(`Est-Ouest — ${MOTIF_SERVEUR}`)).toBeInTheDocument()
    expect(container.querySelector('[data-motif-refus="est_ouest"]')).toBeInTheDocument()
  })

  it("n'affiche AUCUN motif quand le serveur n'en fournit pas (pas de texte inventé)", () => {
    const sansMotif = {
      ...DONNEES,
      sens_rangees: [
        { code: 'nord_sud', libelle: 'Nord-Sud', disponible: true },
        { code: 'est_ouest', libelle: 'Est-Ouest', disponible: false },
      ],
    }
    const { container } = monter(vi.fn(), sansMotif)
    expect(container.querySelector('[data-motif-refus]')).toBeNull()
    expect(screen.getByRole('radio', { name: /Est-Ouest/ })).toBeDisabled()
  })

  it('cliquer une option refusée ne déclenche AUCUN recalcul', async () => {
    const { onChange } = monter()
    await userEvent.click(screen.getByRole('radio', { name: /Est-Ouest/ }))
    expect(onChange).not.toHaveBeenCalled()
  })

  it('choisir une orientation admise remonte le paramètre', async () => {
    const { onChange } = monter()
    await userEvent.click(screen.getByRole('radio', { name: 'Simple pente' }))
    expect(onChange).toHaveBeenCalledWith({ orientation_table: 'simple_pente' })
  })

  it('changer la segmentation (arc) déclenche un recalcul', async () => {
    const { onChange } = monter()
    await userEvent.click(screen.getByRole('radio', { name: 'Surface continue' }))
    expect(onChange).toHaveBeenCalledWith({ segmentation: 'continue' })
  })

  it('traite le L en surface continue comme une option explicite', async () => {
    const { onChange } = monter()
    await userEvent.click(screen.getByRole('radio', { name: 'L découpé en deux ailes' }))
    expect(onChange).toHaveBeenCalledWith({ forme_l: 'decoupe' })
  })

  it('marque le choix courant comme sélectionné', () => {
    monter()
    expect(screen.getByRole('radio', { name: 'Nord-Sud' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('radio', { name: 'Dos-à-dos' })).toHaveAttribute('aria-checked', 'true')
  })

  it('expose le hook de tiroir `data-ao-tiroir`', () => {
    const { container } = monter()
    expect(container.querySelector('[data-ao-tiroir="orientation"]')).toBeInTheDocument()
  })

  it('ne rend rien tant que le serveur ne décrit pas le tiroir', () => {
    const { container } = render(<TiroirOrientation donnees={null} />)
    expect(container.firstChild).toBeNull()
  })
})
