import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { emptyForm, formFromCampagne } from './CampagneForm'

const mocks = vi.hoisted(() => ({
  listesList: vi.fn(),
  apercuFusion: vi.fn(),
}))

vi.mock('../../api/marketingApi', () => ({
  default: {
    unwrapList: (res) => {
      const data = res?.data
      return Array.isArray(data) ? data : (data?.results || [])
    },
    listes: { list: mocks.listesList },
    campagnes: { apercuFusion: mocks.apercuFusion },
  },
}))

import CampagneForm from './CampagneForm'

beforeEach(() => {
  vi.clearAllMocks()
  mocks.listesList.mockResolvedValue({ data: [{ id: 1, nom: 'Liste A' }] })
})

describe('emptyForm / formFromCampagne', () => {
  it('emptyForm renvoie un formulaire vide, canal email par défaut', () => {
    expect(emptyForm()).toEqual({
      nom: '', canal: 'email', objet: '', corps: '', planifiee_le: '',
      listes: [], variantes_langue: {},
    })
  })

  it('formFromCampagne reprend les champs existants + normalise les listes', () => {
    const c = {
      nom: 'Promo été', canal: 'sms', objet: 'Objet', corps: 'Corps',
      planifiee_le: '2026-07-20T10:00:00Z',
      listes: [{ id: 3 }, 4], variantes_langue: { ar: { objet: 'أ' } },
    }
    const form = formFromCampagne(c)
    expect(form.nom).toBe('Promo été')
    expect(form.listes).toEqual([3, 4])
    expect(form.planifiee_le).toBe('2026-07-20T10:00')
    expect(form.variantes_langue.ar.objet).toBe('أ')
  })
})

describe('CampagneForm (smoke + interactions)', () => {
  it('champ requis + canal whatsapp sélectionnable, sauvegarde appelle onSave', async () => {
    const onSave = vi.fn().mockResolvedValue()
    render(<CampagneForm initial={emptyForm()} onSave={onSave} editing={false} />)
    fireEvent.change(screen.getByTestId('campagne-nom'), { target: { value: 'Ma campagne' } })
    const canal = screen.getByTestId('campagne-canal')
    expect(Array.from(canal.querySelectorAll('option')).map(o => o.value))
      .toContain('whatsapp')
    fireEvent.click(screen.getByTestId('campagne-save'))
    await waitFor(() => expect(onSave).toHaveBeenCalled())
    expect(onSave.mock.calls[0][0].nom).toBe('Ma campagne')
  })

  it('affiche les listes de diffusion et bascule leur sélection', async () => {
    render(<CampagneForm initial={emptyForm()} onSave={vi.fn()} editing={false} />)
    const checkbox = await screen.findByTestId('campagne-liste-1')
    expect(checkbox.checked).toBe(false)
    fireEvent.click(checkbox)
    expect(checkbox.checked).toBe(true)
  })

  it("aperçu fusionné n'apparaît qu'en édition (campagne existante)", async () => {
    render(<CampagneForm initial={emptyForm()} onSave={vi.fn()} editing={false} />)
    expect(screen.queryByTestId('campagne-apercu-btn')).toBeNull()
  })

  it('aperçu fusionné affiche le corps rendu sans rien sauvegarder', async () => {
    mocks.apercuFusion.mockResolvedValue({ data: { corps_fusionne: 'Bonjour Ahmed' } })
    const initial = { ...formFromCampagne({ nom: 'X' }), id: 7 }
    render(<CampagneForm initial={initial} onSave={vi.fn()} editing />)
    fireEvent.change(screen.getByTestId('campagne-apercu-lead-id'), { target: { value: '42' } })
    fireEvent.click(screen.getByTestId('campagne-apercu-btn'))
    await waitFor(() => expect(mocks.apercuFusion).toHaveBeenCalledWith(7, { lead_id: '42' }))
    expect(await screen.findByTestId('campagne-apercu-resultat')).toHaveTextContent('Bonjour Ahmed')
  })
})
