import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { ConfirmProvider } from '../../../providers/ConfirmProvider'
import { useConfirmationSortie } from '../../../ui/useDirtyGuard'

const { documentsApiMock } = vi.hoisted(() => ({
  documentsApiMock: {
    acte: vi.fn(),
    modifierActe: vi.fn(),
    enregistrerModeleActe: vi.fn(),
  },
}))
vi.mock('../../../api/documentsApi', () => ({ default: documentsApiMock }))

import ActeEditeur from './ActeEditeur'

const acte = () => structuredClone(exempleContrat('documents', 'acte_contractuel'))

// Comme dans l'application : la boîte de confirmation de sortie est montée à la racine.
function Racine({ children }) {
  useConfirmationSortie()
  return children
}

function monter(props = {}) {
  const onSaved = vi.fn()
  const onOpenChange = vi.fn()
  render(
    <ConfirmProvider>
      <Racine>
        <ActeEditeur open acteId={31} onOpenChange={onOpenChange} onSaved={onSaved} {...props} />
      </Racine>
    </ConfirmProvider>,
  )
  return { onSaved, onOpenChange }
}

// Deux boutons « Fermer » : la croix du dialogue et celui du pied.
const boutonsFermer = () => screen.getAllByRole('button', { name: 'Fermer' })
const croix = () => boutonsFermer().find((b) => !b.closest('.contrats-dialogue__pied'))
const fermerDuPied = () => boutonsFermer().find((b) => b.closest('.contrats-dialogue__pied'))

async function salir(user) {
  const zone = await within(await screen.findByRole('group', { name: 'Conditions particulières' }))
    .findByLabelText('Conditions particulières')
  await user.type(zone, ' x')
}

// Le détail servi en arabe : le MÊME exemple, dont `sections_modifiables` est dérivé
// de l'exemple (jamais d'une liste écrite à la main) en écartant les sections
// COMMUNES aux deux langues (dates, options, signataire — `corps_patch._note`).
const COMMUNES = ['lieu', 'date_document', 'societe', 'options', 'livraison', 'reception', 'sav', 'paiement']
function acteAr(base = acte()) {
  const ar = structuredClone(base)
  ar.langue = 'ar'
  ar.contenu.langue = 'ar'
  ar.sections_modifiables = base.sections_modifiables.filter((k) => !COMMUNES.includes(k))
  ar.sections_personnalisees = []
  return ar
}

const section = (nom) => screen.getByRole('group', { name: nom })

beforeEach(() => {
  vi.clearAllMocks()
  documentsApiMock.acte.mockResolvedValue({ data: acte() })
  documentsApiMock.modifierActe.mockResolvedValue({ data: acte() })
})
afterEach(() => cleanup())

describe('Éditeur d’un acte', () => {
  it('n’envoie que { surcharges: { <section> } } pour la section modifiée', async () => {
    const user = userEvent.setup()
    const { onSaved } = monter()
    const zone = await within(await screen.findByRole('group', { name: 'Conditions particulières' }))
      .findByLabelText('Conditions particulières')
    await user.clear(zone)
    await user.type(zone, 'Accès par le garage.')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(documentsApiMock.modifierActe).toHaveBeenCalledTimes(1)
    expect(documentsApiMock.modifierActe).toHaveBeenCalledWith(31, {
      conditions_particulieres: 'Accès par le garage.',
    }, 'fr')
    expect(onSaved).toHaveBeenCalled()
  })

  it('Rétablir envoie null pour la section personnalisée seulement', async () => {
    const user = userEvent.setup()
    monter()
    const s = await screen.findByRole('group', { name: 'Conditions particulières' })
    await user.click(within(s).getByRole('button', { name: /Rétablir le texte par défaut/ }))
    expect(documentsApiMock.modifierActe).toHaveBeenCalledWith(31, { conditions_particulieres: null }, 'fr')
    // Une section non personnalisée n’offre pas « Rétablir ».
    expect(within(section('Délais')).queryByRole('button', { name: /Rétablir/ })).toBeNull()
  })

  it('les montants de l’échéancier sont en lecture seule ; « quand » et « note » se modifient', async () => {
    const user = userEvent.setup()
    monter()
    const s = await screen.findByRole('group', { name: 'Échéancier : les mots' })
    expect(within(s).getByText(/changent sur la vente/)).toBeInTheDocument()
    expect(within(s).getByText(/30 % · 29\s550,00 DH/)).toBeInTheDocument()
    // Aucun champ ne porte ni le montant ni le pourcentage.
    for (const champ of within(s).getAllByRole('textbox')) {
      expect(champ.value).not.toMatch(/29550|29\s550|^30$/)
    }
    const quand = within(s).getByLabelText('Quand — Acompte')
    await user.clear(quand)
    await user.type(quand, 'Le jour de la livraison')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    const envoye = documentsApiMock.modifierActe.mock.calls[0][1]
    expect(Object.keys(envoye)).toEqual(['echeancier_textes'])
    expect(envoye.echeancier_textes.acompte).toEqual({ exigibilite: 'Le jour de la livraison', note: '' })
    for (const tranche of Object.values(envoye.echeancier_textes)) {
      expect(Object.keys(tranche).sort()).toEqual(['exigibilite', 'note'])
    }
  })

  it('une pénalité tapée n’est jamais arrondie ni refusée', async () => {
    const user = userEvent.setup()
    monter()
    const champ = await within(await screen.findByRole('group', { name: 'Options' }))
      .findByLabelText(/Pénalité de retard/)
    expect(champ).toHaveAttribute('step', 'any')
    await user.type(champ, '0.125')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(documentsApiMock.modifierActe.mock.calls[0][1].options.penalite_retard_pct).toBe(0.125)
  })

  it('le choix de l’arabe redemande l’acte en langue ar et enregistre avec langue ar', async () => {
    const ar = acteAr()
    ar.contenu.titre = 'عقد'
    documentsApiMock.acte.mockImplementation((id, langue) => Promise.resolve({
      data: langue === 'ar' ? ar : acte(),
    }))
    const user = userEvent.setup()
    monter()
    await screen.findByRole('group', { name: 'Conditions particulières' })
    await user.click(screen.getByRole('button', { name: 'العربية' }))
    expect(documentsApiMock.acte).toHaveBeenLastCalledWith(31, 'ar')
    const zone = await within(await screen.findByRole('group', { name: 'Titre du document' }))
      .findByLabelText('Titre')
    expect(zone).toHaveAttribute('dir', 'rtl')
    expect(zone).toHaveAttribute('lang', 'ar')
    // En arabe, seules les sections listées par CE détail (dérivé de l'exemple) sont montrées.
    expect(screen.queryByRole('group', { name: 'Options' })).toBeNull()
    expect(screen.getByRole('group', { name: 'Conditions particulières' })).toBeInTheDocument()
    await user.clear(zone)
    await user.type(zone, 'عقد جديد')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(documentsApiMock.modifierActe).toHaveBeenCalledWith(31, { titre: 'عقد جديد' }, 'ar')
  })

  it('F1 — en arabe : date limite, durées et fins de garantie en lecture seule, jamais envoyées', async () => {
    const ar = acteAr()
    ar.contenu.garanties = ar.contenu.garanties.map((g, i) => ({ ...g, fin: i === 0 ? '2037-01-23' : g.fin }))
    documentsApiMock.acte.mockImplementation((id, langue) => Promise.resolve({
      data: langue === 'ar' ? ar : acte(),
    }))
    const user = userEvent.setup()
    monter()
    await screen.findByRole('group', { name: 'Délais' })
    await user.click(screen.getByRole('button', { name: 'العربية' }))
    const delais = await screen.findByRole('group', { name: 'Délais' })
    expect(within(delais).queryByLabelText('Date limite')).toBeNull()
    expect(within(delais).getByText(ar.contenu.delais.date_limite)).toBeInTheDocument()
    const garanties = screen.getByRole('group', { name: 'Garanties' })
    expect(within(garanties).queryByLabelText('Durée en mois')).toBeNull()
    expect(within(garanties).queryByRole('button', { name: /Ajouter une garantie|Retirer/ })).toBeNull()
    expect(within(garanties).getByText(/2037-01-23/)).toBeInTheDocument()
    await user.type(within(delais).getByLabelText('Détail'), ' x')
    await user.type(within(garanties).getByLabelText('Désignation (garantie 1)'), ' x')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    const envoye = documentsApiMock.modifierActe.mock.calls[0][1]
    expect(Object.keys(envoye.delais)).toEqual(['detail'])
    for (const g of envoye.garanties) {
      expect(Object.keys(g).sort()).toEqual(['cle', 'designation', 'detail', 'garant'])
    }
    expect(documentsApiMock.modifierActe.mock.calls[0][2]).toBe('ar')
  })

  it('demande confirmation avant de changer de langue avec des modifications en cours', async () => {
    const user = userEvent.setup()
    monter()
    const zone = await within(await screen.findByRole('group', { name: 'Conditions particulières' }))
      .findByLabelText('Conditions particulières')
    await user.type(zone, ' x')
    await user.click(screen.getByRole('button', { name: 'العربية' }))
    expect(screen.getByText(/changer de langue les abandonne/)).toBeInTheDocument()
    expect(documentsApiMock.acte).toHaveBeenCalledTimes(1)
    await user.click(screen.getByRole('button', { name: 'Rester ici' }))
    expect(documentsApiMock.acte).toHaveBeenCalledTimes(1)
  })

  it('ne propose ni droit de rétractation ni section « conclusion »', async () => {
    monter()
    await screen.findByRole('group', { name: 'Options' })
    expect(screen.queryByRole('checkbox', { name: /rétractation/i })).toBeNull()
    expect(screen.queryByRole('group', { name: /conclusion/i })).toBeNull()
  })

  it('affiche le detail du serveur quand l’enregistrement est refusé (acte_fige)', async () => {
    documentsApiMock.modifierActe.mockRejectedValue({
      response: { data: exempleContrat('documents', 'acte_contractuel', 'exemple_409_acte_fige') },
    })
    const user = userEvent.setup()
    monter()
    const zone = await within(await screen.findByRole('group', { name: 'Conditions particulières' }))
      .findByLabelText('Conditions particulières')
    await user.type(zone, ' x')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(await screen.findByText('Cet acte est émis : rouvrez-le pour le modifier.')).toBeInTheDocument()
  })

  it('« Enregistrer comme modèle » n’apparaît que pour un rôle autorisé et appelle le serveur', async () => {
    const user = userEvent.setup()
    monter({ peutModele: true })
    documentsApiMock.enregistrerModeleActe.mockResolvedValue({ data: { detail: 'ok' } })
    await user.click(await screen.findByRole('button', { name: 'Enregistrer comme modèle de la société' }))
    expect(documentsApiMock.enregistrerModeleActe).toHaveBeenCalledWith(31)
  })

  it('F2 — fermer avec des modifications non enregistrées demande confirmation (bouton, Échap)', async () => {
    const user = userEvent.setup()
    const { onOpenChange } = monter()
    await salir(user)
    await user.click(fermerDuPied())
    const boite = await screen.findByRole('alertdialog')
    expect(within(boite).getByText('Quitter sans enregistrer ?')).toBeInTheDocument()
    expect(onOpenChange).not.toHaveBeenCalled()
    await user.click(within(boite).getByRole('button', { name: 'Rester' }))
    expect(onOpenChange).not.toHaveBeenCalled()
    // La croix et Échap passent par la même garde.
    await user.click(croix())
    await user.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Rester' }))
    expect(onOpenChange).not.toHaveBeenCalled()
    await user.keyboard('{Escape}')
    await user.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Quitter' }))
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('F2 — sans modification, la fermeture est immédiate', async () => {
    const user = userEvent.setup()
    const { onOpenChange } = monter()
    await screen.findByRole('group', { name: 'Conditions particulières' })
    await user.click(fermerDuPied())
    expect(onOpenChange).toHaveBeenCalledWith(false)
    expect(screen.queryByRole('alertdialog')).toBeNull()
  })

  it('F3 — « Enregistrer comme modèle » est désactivé tant que des modifications ne sont pas enregistrées', async () => {
    const user = userEvent.setup()
    monter({ peutModele: true })
    const modele = await screen.findByRole('button', { name: 'Enregistrer comme modèle de la société' })
    expect(modele).toBeEnabled()
    await salir(user)
    expect(modele).toBeDisabled()
  })

  it('F6 — si l’arabe ne se charge pas, le brouillon français ne reste pas sous l’étiquette arabe', async () => {
    documentsApiMock.acte.mockImplementation((id, langue) => (langue === 'ar'
      ? Promise.reject({ response: { data: { detail: 'Traduction indisponible.', code: 'x' } } })
      : Promise.resolve({ data: acte() })))
    const user = userEvent.setup()
    monter()
    await screen.findByRole('group', { name: 'Conditions particulières' })
    await user.click(screen.getByRole('button', { name: 'العربية' }))
    expect(await screen.findByText('Traduction indisponible.')).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Conditions particulières' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Enregistrer' })).toBeDisabled()
  })

  it('F4 — « Délai d’exécution » n’apparaît que sur le contrat, jamais sur un procès-verbal', async () => {
    const user = userEvent.setup()
    const { unmount } = render(
      <ConfirmProvider>
        <ActeEditeur open acteId={31} onOpenChange={vi.fn()} />
      </ConfirmProvider>,
    )
    const contrat = await screen.findByRole('group', { name: 'Options' })
    expect(within(contrat).getByLabelText(/Délai d’exécution/)).toBeInTheDocument()
    unmount()
    cleanup()
    documentsApiMock.acte.mockResolvedValue({
      data: structuredClone(exempleContrat('documents', 'acte_contractuel', 'exemple_pv_reception')),
    })
    monter()
    const pv = await screen.findByRole('group', { name: 'Options' })
    expect(within(pv).queryByLabelText(/Délai d’exécution/)).toBeNull()
    await user.click(within(pv).getByLabelText(/Réserve de propriété/))
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(Object.keys(documentsApiMock.modifierActe.mock.calls[0][1].options).sort())
      .toEqual(['penalite_retard_pct', 'reserve_propriete'])
  })

  it('F5 — les modalités de paiement et l’introduction des conseils se modifient', async () => {
    const user = userEvent.setup()
    monter()
    const paiement = await screen.findByRole('group', { name: 'Paiement : les modalités' })
    const zone = within(paiement).getByLabelText('Modalités de paiement')
    await user.clear(zone)
    await user.type(zone, 'Virement uniquement.')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(documentsApiMock.modifierActe).toHaveBeenLastCalledWith(31, {
      paiement: { modalites: 'Virement uniquement.' },
    }, 'fr')
    cleanup()
    documentsApiMock.acte.mockResolvedValue({
      data: structuredClone(exempleContrat('documents', 'acte_contractuel', 'exemple_cloture_garanties')),
    })
    monter()
    const intro = within(await screen.findByRole('group', { name: 'Conseils : introduction' }))
      .getByLabelText('Introduction des conseils')
    await user.type(intro, ' Merci.')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    const envoye = documentsApiMock.modifierActe.mock.calls.at(-1)[1]
    expect(Object.keys(envoye)).toEqual(['conseils_intro'])
    expect(envoye.conseils_intro).toMatch(/ Merci\.$/)
  })

  it('F7 — chaque case de constat est nommée par son texte, dans une cible de 44 px, et sa zone est étiquetée', async () => {
    const pv = structuredClone(exempleContrat('documents', 'acte_contractuel', 'exemple_pv_reception'))
    documentsApiMock.acte.mockResolvedValue({ data: pv })
    const user = userEvent.setup()
    monter()
    const groupe = await screen.findByRole('group', { name: 'Constats' })
    for (const [i, k] of pv.contenu.constats.entries()) {
      const nom = `Constat ${i + 1} coché : ${k.texte.replace(/\*\*/g, '')}`
      const case_ = within(groupe).getByRole('checkbox', { name: nom })
      expect(case_.closest('label')).toHaveClass('contrats-editeur__cible')
      expect(within(groupe).getByLabelText(`Texte du constat ${i + 1}`).tagName).toBe('TEXTAREA')
    }
    // Décocher la première case l'envoie bien (la case reste un vrai contrôle).
    await user.click(within(groupe).getAllByRole('checkbox')[0])
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(documentsApiMock.modifierActe.mock.calls[0][1].constats[0].cochee).toBe(false)
  })
})
