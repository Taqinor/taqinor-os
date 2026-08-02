import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TiroirElectrique from './TiroirElectrique'

/* AOF99 — la chaîne modules → kWc → chaînes → onduleurs → conformité est
   recalculée PAR LE MOTEUR ; l'écran affiche, et NOMME la non-conformité. */

const CONFORME = {
  chaine: { libelle_taille: '20 chaînes de 16 modules', reste_texte: '6 modules en réserve d\'appoint' },
  onduleurs: { nombre_texte: '4 onduleurs', puissance_texte: '80 kW', plafond_texte: '100 kW par onduleur (CPS)' },
  ratio_dc_ac: { texte: '0,98', fourchette_texte: 'Fourchette CPS : 0,75 – 1,00' },
  conformite: { conforme: true, bloquant: false },
}

const NON_CONFORME = {
  ...CONFORME,
  ratio_dc_ac: { texte: '1,23', fourchette_texte: 'Fourchette CPS : 0,75 – 1,00' },
  conformite: {
    conforme: false,
    bloquant: true,
    alerte: '80 kW hors fourchette 0,75-1',
    repartition_proposee: { texte: '5 onduleurs de 60 kW', patch: { nb_onduleurs: 5, puissance_onduleur_kw: 60 } },
  },
}

describe('TiroirElectrique (AOF99)', () => {
  it('affiche la chaîne, le reste « en réserve d\'appoint », les onduleurs et le ratio', () => {
    render(<TiroirElectrique donnees={CONFORME} valeurs={{ taille_chaine: 16 }} />)
    expect(screen.getByText('20 chaînes de 16 modules')).toBeInTheDocument()
    expect(screen.getByText("6 modules en réserve d'appoint")).toBeInTheDocument()
    expect(screen.getByText('4 onduleurs')).toBeInTheDocument()
    expect(screen.getByText('0,98')).toBeInTheDocument()
    expect(screen.getByText('Fourchette CPS : 0,75 – 1,00')).toBeInTheDocument()
    expect(screen.getByText('100 kW par onduleur (CPS)')).toBeInTheDocument()
  })

  it('CAS CONFORME : pastille de conformité, aucune alerte, aucun blocage', () => {
    const onConformite = vi.fn()
    const { container } = render(
      <TiroirElectrique donnees={CONFORME} valeurs={{ taille_chaine: 16 }} onConformite={onConformite} />,
    )
    expect(container.querySelector('[data-conformite="conforme"]')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(onConformite).toHaveBeenCalledWith(CONFORME.conformite)
  })

  it('CAS NON CONFORME : alerte NOMMÉE (grandeur, valeur, règle) et publication bloquée', async () => {
    const onConformite = vi.fn()
    const { container } = render(
      <TiroirElectrique donnees={NON_CONFORME} valeurs={{ taille_chaine: 16 }} onConformite={onConformite} />,
    )
    const alerte = screen.getByRole('alert')
    expect(alerte).toHaveTextContent('80 kW hors fourchette 0,75-1')
    expect(container.querySelector('[data-bloquant="true"]')).toBeInTheDocument()
    expect(screen.getByText(/Publication bloquée/)).toBeInTheDocument()
    await waitFor(() => expect(onConformite).toHaveBeenCalledWith(NON_CONFORME.conformite))
  })

  it('propose la répartition CONFORME calculée par le moteur, applicable en un clic', async () => {
    const onChange = vi.fn()
    render(<TiroirElectrique donnees={NON_CONFORME} valeurs={{ taille_chaine: 16 }} onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: /5 onduleurs de 60 kW/ }))
    expect(onChange).toHaveBeenCalledWith({ nb_onduleurs: 5, puissance_onduleur_kw: 60 })
  })

  it('changer la taille de chaîne remonte le paramètre (le recalcul est serveur)', () => {
    const onChange = vi.fn()
    render(<TiroirElectrique donnees={CONFORME} valeurs={{ taille_chaine: 16 }} onChange={onChange} />)
    const champ = screen.getByLabelText('Modules par chaîne')
    expect(champ.closest('form')).toHaveAttribute('novalidate')
    fireEvent.change(champ, { target: { value: '18' } })
    expect(onChange).toHaveBeenLastCalledWith({ taille_chaine: 18 })
  })

  it('expose le hook de tiroir `data-ao-tiroir`', () => {
    const { container } = render(<TiroirElectrique donnees={CONFORME} valeurs={{}} />)
    expect(container.querySelector('[data-ao-tiroir="electrique"]')).toBeInTheDocument()
  })

  it('ne rend rien tant que le serveur ne décrit pas le tiroir', () => {
    const { container } = render(<TiroirElectrique donnees={null} />)
    expect(container.firstChild).toBeNull()
  })
})
