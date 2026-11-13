// ZSAL5 — éditeur de modèles d'e-mail par clé (sujet + corps), parité
// WhatsApp (MessagesSection). Backend déjà en place : apps/parametres
// EmailTemplateViewSet (`effective` / `bulk`), consommé par
// apps.ventes.email_service à l'envoi réel — cet écran ne fait qu'éditer.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('../../api/ventesApi', () => ({
  default: {
    getEmailConfig: vi.fn(() => Promise.resolve({
      data: { configured: true, from_email: 'contact@taqinor.ma', inbound_configured: false },
    })),
  },
}))
vi.mock('../../api/parametresApi', () => ({
  default: {
    getEmailTemplates: vi.fn(),
    saveEmailTemplates: vi.fn(),
  },
}))

import parametresApi from '../../api/parametresApi'
import EmailSection from './EmailSection'

const TEMPLATE = {
  cle: 'envoi_devis', label: 'Envoi de devis',
  sujet: 'Votre devis {reference}', corps: 'Bonjour {nom}, voici votre devis.',
  sujet_defaut: 'Votre devis {reference}', corps_defaut: 'Bonjour {nom}, voici votre devis.',
  personnalise: false, placeholders: ['{nom}', '{reference}', '{lien}'],
  sujet_en: '', corps_en: '', sujet_ar: '', corps_ar: '',
}

beforeEach(() => {
  vi.clearAllMocks()
  parametresApi.getEmailTemplates.mockResolvedValue({ data: { results: [TEMPLATE] } })
})

describe('EmailSection — ZSAL5 modèles d\'e-mail', () => {
  it('affiche le modèle avec son sujet/corps et ses placeholders', async () => {
    render(<EmailSection />)
    expect(await screen.findByText('Envoi de devis')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Votre devis {reference}')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Bonjour {nom}, voici votre devis.')).toBeInTheDocument()
    expect(screen.getByText(/\{nom\} \{reference\} \{lien\}/)).toBeInTheDocument()
  })

  it('enregistre le modèle édité via saveEmailTemplates', async () => {
    parametresApi.saveEmailTemplates.mockResolvedValue({
      data: { results: [{ ...TEMPLATE, sujet: 'Nouveau sujet', personnalise: true }] },
    })
    render(<EmailSection />)
    const sujetInput = await screen.findByDisplayValue('Votre devis {reference}')
    fireEvent.change(sujetInput, { target: { value: 'Nouveau sujet' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(parametresApi.saveEmailTemplates).toHaveBeenCalledWith([
      expect.objectContaining(
        { cle: 'envoi_devis', sujet: 'Nouveau sujet', corps: 'Bonjour {nom}, voici votre devis.' }),
    ]))
    expect(await screen.findByText('Enregistré')).toBeInTheDocument()
    expect(await screen.findByText('Personnalisé')).toBeInTheDocument()
  })

  it('réinitialise au modèle par défaut', async () => {
    const personnalise = { ...TEMPLATE, sujet: 'Sujet modifié', personnalise: true }
    parametresApi.getEmailTemplates.mockResolvedValue({ data: { results: [personnalise] } })
    parametresApi.saveEmailTemplates.mockResolvedValue({ data: { results: [TEMPLATE] } })
    render(<EmailSection />)
    await screen.findByDisplayValue('Sujet modifié')
    fireEvent.click(screen.getByRole('button', { name: /Réinitialiser au modèle par défaut/ }))
    await waitFor(() => expect(parametresApi.saveEmailTemplates).toHaveBeenCalledWith([
      { cle: 'envoi_devis', sujet: TEMPLATE.sujet_defaut, corps: TEMPLATE.corps_defaut },
    ]))
  })

  it('ASOC99 — édite les traductions anglaise et arabe (arabe de droite à gauche)', async () => {
    parametresApi.saveEmailTemplates.mockResolvedValue({ data: { results: [TEMPLATE] } })
    render(<EmailSection />)
    await screen.findByText('Envoi de devis')
    expect(screen.getByText('Anglais')).toBeInTheDocument()
    expect(screen.getByText('Arabe')).toBeInTheDocument()
    const sujetAr = screen.getByLabelText('Sujet (arabe)')
    expect(sujetAr).toHaveAttribute('dir', 'rtl')
    fireEvent.change(sujetAr, { target: { value: 'عرض سعر' } })
    fireEvent.change(screen.getByLabelText('Corps (anglais)'), { target: { value: 'Hello' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(parametresApi.saveEmailTemplates).toHaveBeenCalledWith([
      expect.objectContaining({ cle: 'envoi_devis', sujet_ar: 'عرض سعر', corps_en: 'Hello' }),
    ]))
  })
})

describe('EmailSection — AMSG89 rappel de RDV sujet seul', () => {
  it('rappel_rdv : aucun champ Corps, phrase de renvoi affichée', async () => {
    const RAPPEL = {
      ...TEMPLATE, cle: 'rappel_rdv', label: 'Rappel de RDV (J-1)',
      sujet: 'Rappel de rendez-vous — demain', sujet_defaut: 'Rappel de rendez-vous — demain',
      corps: 'Bonjour {nom}', corps_defaut: 'Bonjour {nom}', corps_modifiable: false,
    }
    parametresApi.getEmailTemplates.mockResolvedValue({
      data: { results: [{ ...TEMPLATE, corps_modifiable: true }, RAPPEL] },
    })
    render(<EmailSection />)
    expect(await screen.findByText('Rappel de RDV (J-1)')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Rappel de rendez-vous — demain')).toBeInTheDocument()
    expect(document.getElementById('pe-email-corps-rappel_rdv')).toBeNull()
    expect(document.getElementById('pe-email-corps-en-rappel_rdv')).toBeNull()
    expect(document.getElementById('pe-email-corps-ar-rappel_rdv')).toBeNull()
    expect(document.getElementById('pe-email-sujet-en-rappel_rdv')).not.toBeNull()
    expect(screen.getByText(/seul le sujet se règle ici/)).toBeInTheDocument()
    // La carte « Envoi de devis » garde ses champs Corps.
    expect(document.getElementById('pe-email-corps-envoi_devis')).not.toBeNull()
    expect(document.getElementById('pe-email-corps-en-envoi_devis')).not.toBeNull()
  })
})
