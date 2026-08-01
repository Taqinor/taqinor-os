import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ModeChantier, {
  BarreGabarits, PaveNumeriqueCote, CapturePhotoRepere, CalepinageLectureSeule,
  TOUCH_TARGET_CLASS, RAISON_CALEPINAGE_LECTURE_CHANTIER,
} from './ModeChantier'
import { DEFAULT_GABARITS } from './ModeChantier.constantes'

/* AOF189 — Mode CHANTIER (tablette 768-1024). Trois garanties du Done= :
   1) relevé réalisable au doigt (les gabarits/pavé/photo répondent à un tap,
      sans survol requis) ;
   2) cibles tactiles ≥ 44 px (TOUCH_TARGET_CLASS sur chaque bouton exposé) ;
   3) le calepinage passe en LECTURE avec sa raison TOUJOURS affichée. */

describe('cibles tactiles (>= 44px)', () => {
  it('chaque gabarit expose la classe de cible tactile 44px', () => {
    render(<BarreGabarits onPoserGabarit={() => {}} />)
    for (const g of DEFAULT_GABARITS) {
      const btn = screen.getByRole('button', { name: g.label })
      for (const cls of TOUCH_TARGET_CLASS.split(' ')) {
        expect(btn.className).toContain(cls)
      }
    }
  })

  it('les touches du pavé numérique sont de grandes cibles', () => {
    render(<PaveNumeriqueCote valeur="" onChange={() => {}} onValider={() => {}} />)
    const touche = screen.getByRole('button', { name: '5' })
    for (const cls of TOUCH_TARGET_CLASS.split(' ')) {
      expect(touche.className).toContain(cls)
    }
  })
})

describe('BarreGabarits — pose au tap', () => {
  it('un tap sur un gabarit pose directement l\'obstacle typé (aucun formulaire)', () => {
    const onPoserGabarit = vi.fn()
    render(<BarreGabarits onPoserGabarit={onPoserGabarit} />)
    fireEvent.click(screen.getByRole('button', { name: 'Cheminée' }))
    expect(onPoserGabarit).toHaveBeenCalledWith('cheminee')
  })
})

describe('PaveNumeriqueCote', () => {
  it('compose une valeur au tap et valide', () => {
    let valeur = ''
    const onChange = vi.fn((v) => { valeur = v })
    const onValider = vi.fn()
    const { rerender } = render(
      <PaveNumeriqueCote valeur={valeur} onChange={onChange} onValider={onValider} />,
    )
    fireEvent.click(screen.getByRole('button', { name: '1' }))
    expect(onChange).toHaveBeenCalledWith('1')
    rerender(<PaveNumeriqueCote valeur="1" onChange={onChange} onValider={onValider} />)
    fireEvent.click(screen.getByRole('button', { name: '2' }))
    expect(onChange).toHaveBeenCalledWith('12')

    fireEvent.click(screen.getByRole('button', { name: 'Valider la cote' }))
    expect(onValider).toHaveBeenCalled()
  })

  it('la touche « Effacer » retire le dernier caractère', () => {
    const onChange = vi.fn()
    render(<PaveNumeriqueCote valeur="12" onChange={onChange} onValider={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: 'Effacer' }))
    expect(onChange).toHaveBeenCalledWith('1')
  })
})

describe('CapturePhotoRepere', () => {
  it('ouvre directement l\'appareil photo (capture=environment) et transmet le fichier', () => {
    const onPhoto = vi.fn()
    const { container } = render(<CapturePhotoRepere onPhoto={onPhoto} />)
    const input = container.querySelector('input[type="file"]')
    expect(input).toHaveAttribute('capture', 'environment')
    expect(input).toHaveAttribute('accept', 'image/*')

    const file = new File(['x'], 'photo.jpg', { type: 'image/jpeg' })
    fireEvent.change(input, { target: { files: [file] } })
    expect(onPhoto).toHaveBeenCalledWith(file)
  })
})

describe('CalepinageLectureSeule', () => {
  it('affiche TOUJOURS la raison à côté du panneau désactivé (jamais un contrôle mort silencieux)', () => {
    render(
      <CalepinageLectureSeule>
        <input aria-label="Largeur allée" defaultValue="0.6" />
      </CalepinageLectureSeule>,
    )
    expect(screen.getByText(RAISON_CALEPINAGE_LECTURE_CHANTIER)).toBeVisible()
    expect(screen.getByLabelText('Largeur allée')).toBeDisabled()
  })

  it('accepte une raison personnalisée', () => {
    render(<CalepinageLectureSeule raison="Motif custom">contenu</CalepinageLectureSeule>)
    expect(screen.getByText('Motif custom')).toBeVisible()
  })
})

describe('ModeChantier (composition)', () => {
  it('force le calepinage en lecture par défaut, avec la raison affichée', () => {
    render(
      <ModeChantier calepinage={<input aria-label="Pas de rangée" defaultValue="1.2" />}>
        <div data-ao-canvas>éditeur</div>
      </ModeChantier>,
    )
    expect(screen.getByText(RAISON_CALEPINAGE_LECTURE_CHANTIER)).toBeVisible()
    expect(screen.getByLabelText('Pas de rangée')).toBeDisabled()
  })

  it('laisse le calepinage éditable si explicitement demandé (calepinageEnLecture=false)', () => {
    render(
      <ModeChantier
        calepinage={<input aria-label="Pas de rangée" defaultValue="1.2" />}
        calepinageEnLecture={false}
      >
        <div data-ao-canvas>éditeur</div>
      </ModeChantier>,
    )
    expect(screen.queryByText(RAISON_CALEPINAGE_LECTURE_CHANTIER)).not.toBeInTheDocument()
    expect(screen.getByLabelText('Pas de rangée')).toBeEnabled()
  })

  it('rend l\'éditeur fourni par le parent sans le recréer', () => {
    render(
      <ModeChantier>
        <div data-ao-canvas data-testid="editeur-reel">éditeur réel</div>
      </ModeChantier>,
    )
    expect(screen.getByTestId('editeur-reel')).toBeVisible()
  })
})
