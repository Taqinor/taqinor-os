import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within, waitFor } from '@testing-library/react'
import { Dialog, DialogContent } from '../../../ui'
import userEvent from '@testing-library/user-event'
import { exempleContrat, documentContrat } from '../../../test/fixtures/contractSamples'

const { documentsApiMock, toastMock } = vi.hoisted(() => ({
  toastMock: { success: vi.fn(), error: vi.fn() },
  documentsApiMock: {
    acte: vi.fn(),
    modifierActe: vi.fn(),
    enregistrerModeleActe: vi.fn(),
  },
}))
vi.mock('../../../api/documentsApi', () => ({ default: documentsApiMock }))
vi.mock('../../../ui', async (importOriginal) => ({ ...(await importOriginal()), toast: toastMock }))

import ActeEditeur from './ActeEditeur'

const acte = () => structuredClone(exempleContrat('documents', 'acte_contractuel'))

function monter(props = {}) {
  const onSaved = vi.fn()
  const onOpenChange = vi.fn()
  render(<ActeEditeur open acteId={31} onOpenChange={onOpenChange} onSaved={onSaved} {...props} />)
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
    // F12 : jamais immédiat, une confirmation d'abord.
    expect(documentsApiMock.modifierActe).not.toHaveBeenCalled()
    await user.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Rétablir' }))
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
    // F16 : une date lisible, pas l'ISO brut.
    expect(delais.textContent).not.toMatch(/\d{4}-\d{2}-\d{2}/)
    expect(delais.querySelector('strong').textContent).toMatch(/\d/)
    const garanties = screen.getByRole('group', { name: 'Garanties' })
    expect(within(garanties).queryByLabelText('Durée en mois')).toBeNull()
    expect(within(garanties).queryByRole('button', { name: /Ajouter une garantie|Retirer/ })).toBeNull()
    expect(garanties.textContent).not.toMatch(/\d{4}-\d{2}-\d{2}/)
    expect(within(garanties).getByText(/Fin :/).textContent).toMatch(/2037/)
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

  // Défaut vécu le 25/11/2026 : 36 mois tapés sur le certificat de garantie revenaient
  // à 24 après « Enregistrer » (la clôture reprend la durée du contrat).
  const cloture = (origine) => ({
    ...structuredClone(exempleContrat('documents', 'acte_contractuel', 'exemple_cloture_garanties')),
    garanties_du_contrat: origine,
  })

  it('clôture, contrat encore brouillon : la durée se tape, part au serveur, et l’écran dit qu’elle vaut pour le contrat', async () => {
    const detail = cloture('brouillon')
    documentsApiMock.acte.mockResolvedValue({ data: detail })
    documentsApiMock.modifierActe.mockResolvedValue({ data: detail })
    const user = userEvent.setup()
    monter()
    const garanties = await screen.findByRole('group', { name: 'Garanties' })
    expect(garanties.textContent).toMatch(/vaut aussi pour le contrat/)
    const i = detail.contenu.garanties.findIndex((g) => g.cle === 'installation')
    const duree = within(garanties).getAllByLabelText('Durée en mois')[i]
    await user.clear(duree)
    await user.type(duree, '36')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    const envoye = documentsApiMock.modifierActe.mock.calls[0][1]
    expect(envoye.garanties[i]).toMatchObject({ cle: 'installation', duree_mois: 36 })
  })

  it.each([['emis', /contrat émis/], ['signe', /contrat signé/]])(
    'clôture, contrat %s : durée en lecture seule avec sa raison, ni ajout ni retrait ; les textes restent modifiables',
    async (origine, raison) => {
      documentsApiMock.acte.mockResolvedValue({ data: cloture(origine) })
      const user = userEvent.setup()
      monter()
      const garanties = await screen.findByRole('group', { name: 'Garanties' })
      expect(within(garanties).queryByLabelText('Durée en mois')).toBeNull()
      expect(within(garanties).queryByRole('button', { name: /Ajouter une garantie|Retirer/ })).toBeNull()
      expect(within(garanties).getAllByText(raison).length).toBeGreaterThan(0)
      await user.type(within(garanties).getByLabelText('Désignation (garantie 1)'), ' x')
      expect(screen.getByRole('button', { name: 'Enregistrer' })).toBeEnabled()
    },
  )

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

  it('« Enregistrer comme modèle » apparaît quand le serveur l’autorise (peut_enregistrer_modele) et l’appelle', async () => {
    const user = userEvent.setup()
    documentsApiMock.acte.mockResolvedValue({ data: { ...acte(), peut_enregistrer_modele: true } })
    monter()
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
    documentsApiMock.acte.mockResolvedValue({ data: { ...acte(), peut_enregistrer_modele: true } })
    monter()
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
    const { unmount } = render(<ActeEditeur open acteId={31} onOpenChange={vi.fn()} />)
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
    // Une réserve de propriété par chantier : celle du contrat. Sur un procès-verbal
    // le serveur l'ignore — la case se montre, dit où elle se règle, ne se coche pas.
    const reserve = within(pv).getByLabelText(/Réserve de propriété.*réglée sur le contrat/)
    expect(reserve).toBeDisabled()
    await user.type(within(pv).getByLabelText(/Pénalité de retard/), '2')
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

  // F9 — la forme du corps envoyé vient de l'exemple (`corps_patch`, sinon le
  // `contenu` servi), jamais d'une forme écrite dans le test.
  describe('forme du corps envoyé = forme de l’exemple', () => {
    const corpsPatch = documentContrat('documents', 'acte_contractuel').corps_patch.surcharges

    // Chaque clé envoyée existe dans la référence, avec la même nature (null permis).
    function memeForme(envoye, reference, chemin) {
      if (envoye === null || reference === null || reference === undefined) return
      if (Array.isArray(reference)) {
        expect(Array.isArray(envoye), `${chemin} : liste attendue`).toBe(true)
        for (const e of envoye) if (reference[0] !== undefined) memeForme(e, reference[0], `${chemin}[]`)
        return
      }
      if (typeof reference === 'object') {
        expect(typeof envoye, `${chemin} : objet attendu`).toBe('object')
        for (const [k, v] of Object.entries(envoye)) {
          expect(Object.keys(reference), `${chemin}.${k} absent de l'exemple`).toContain(k)
          memeForme(v, reference[k], `${chemin}.${k}`)
        }
        return
      }
      expect(typeof envoye, chemin).toBe(typeof reference)
    }

    async function modifierEtLire(user, ouvrir) {
      await ouvrir()
      await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
      return documentsApiMock.modifierActe.mock.calls.at(-1)[1]
    }

    it('conditions_particulieres : un texte', async () => {
      const user = userEvent.setup()
      monter()
      const envoye = await modifierEtLire(user, () => salir(user))
      memeForme(envoye.conditions_particulieres, corpsPatch.conditions_particulieres, 'conditions_particulieres')
    })

    it('articles : { cle, titre, paragraphes[] }', async () => {
      const user = userEvent.setup()
      monter()
      const envoye = await modifierEtLire(user, async () => {
        const zone = await within(await screen.findByRole('group', { name: 'Articles' }))
          .findByLabelText('Texte de l’article 1')
        await user.type(zone, ' Un mot de plus.')
      })
      memeForme(envoye.articles, corpsPatch.articles, 'articles')
      expect(Object.keys(envoye.articles[0]).sort()).toEqual(Object.keys(corpsPatch.articles[0]).sort())
    })

    it('echeancier_textes : { <tranche>: { exigibilite, note } }', async () => {
      const user = userEvent.setup()
      monter()
      const envoye = await modifierEtLire(user, async () => {
        const quand = await within(await screen.findByRole('group', { name: 'Échéancier : les mots' }))
          .findByLabelText('Quand — Acompte')
        await user.type(quand, ' x')
      })
      for (const tranche of Object.values(envoye.echeancier_textes)) {
        memeForme(tranche, corpsPatch.echeancier_textes.acompte, 'echeancier_textes.<tranche>')
        expect(Object.keys(tranche).sort()).toEqual(Object.keys(corpsPatch.echeancier_textes.acompte).sort())
      }
    })

    it('options : { reserve_propriete, penalite_retard_pct, … }', async () => {
      const user = userEvent.setup()
      monter()
      const envoye = await modifierEtLire(user, async () => {
        await user.click(within(await screen.findByRole('group', { name: 'Options' }))
          .getByLabelText(/Réserve de propriété/))
      })
      // Référence : le corps d'exemple, complété par le `contenu` servi (délai d'exécution).
      memeForme(envoye.options, { ...acte().contenu.options, ...corpsPatch.options }, 'options')
      expect(typeof envoye.options.reserve_propriete).toBe('boolean')
    })

    it('delais, paiement, garanties : mêmes clés et mêmes natures que le contenu servi', async () => {
      const user = userEvent.setup()
      monter()
      const envoye = await modifierEtLire(user, async () => {
        const g = await screen.findByRole('group', { name: 'Garanties' })
        await user.type(within(g).getByLabelText('Désignation (garantie 1)'), ' x')
        await user.type(within(screen.getByRole('group', { name: 'Délais' })).getByLabelText('Détail'), ' x')
        await user.type(within(screen.getByRole('group', { name: 'Paiement : les modalités' }))
          .getByLabelText('Modalités de paiement'), ' x')
      })
      const contenu = acte().contenu
      memeForme(envoye.delais, contenu.delais, 'delais')
      memeForme(envoye.paiement, contenu.paiement, 'paiement')
      memeForme(envoye.garanties, contenu.garanties, 'garanties')
    })
  })

  it('« Enregistrer comme modèle » suit uniquement peut_enregistrer_modele du serveur (absent s’il est faux)', async () => {
    documentsApiMock.acte.mockResolvedValue({ data: { ...acte(), peut_enregistrer_modele: false } })
    monter()
    await screen.findByRole('group', { name: 'Options' })
    expect(screen.queryByRole('button', { name: 'Enregistrer comme modèle de la société' })).toBeNull()
  })

  it('un champ non touché est renvoyé avec sa valeur, jamais null ni vide (réception, livraison)', async () => {
    const user = userEvent.setup()
    const pv = structuredClone(exempleContrat('documents', 'acte_contractuel', 'exemple_pv_reception'))
    documentsApiMock.acte.mockResolvedValue({ data: pv })
    monter()
    const rec = await screen.findByRole('group', { name: 'Réception' })
    await user.type(within(rec).getByLabelText('Délai pour lever les réserves'), ' ouvrés')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    const envoye = documentsApiMock.modifierActe.mock.calls.at(-1)[1]
    // Seule la section ouverte ET modifiée part ; ses autres champs gardent leur valeur.
    expect(Object.keys(envoye)).toEqual(['reception'])
    expect(envoye.reception).toEqual({
      ...pv.contenu.reception, delai_levee_reserves: `${pv.contenu.reception.delai_levee_reserves} ouvrés`,
    })
    expect(envoye.reception.date_mise_en_service).toBe('2026-12-21')
    cleanup()
    const liv = structuredClone(exempleContrat('documents', 'acte_contractuel', 'exemple_pv_livraison_reste_a_regler'))
    documentsApiMock.acte.mockResolvedValue({ data: liv })
    monter()
    const g = await screen.findByRole('group', { name: 'Livraison' })
    await user.type(within(g).getByLabelText('Suite prévue'), ' !')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    const l = documentsApiMock.modifierActe.mock.calls.at(-1)[1]
    expect(l.livraison).toEqual({ ...liv.contenu.livraison, suite: `${liv.contenu.livraison.suite} !` })
    expect(l.livraison.date).toBe(liv.contenu.livraison.date)
  })

  describe('lot F10 à F16', () => {
    // L'éditeur est monté DANS un tiroir hôte (un autre Dialog Radix) : un clic dans
    // la confirmation ne doit jamais fermer ni l'éditeur ni le tiroir.
    function monterDansUnTiroir() {
      const onTiroir = vi.fn()
      const onOpenChange = vi.fn()
      render(
        <Dialog open onOpenChange={onTiroir}>
          <DialogContent aria-label="Tiroir du chantier">
            <ActeEditeur open acteId={31} onOpenChange={onOpenChange} onSaved={vi.fn()} />
          </DialogContent>
        </Dialog>,
      )
      return { onTiroir, onOpenChange }
    }

    it('F10 — « Rester » ferme la confirmation et garde les modifications ; « Quitter » ne ferme que l’éditeur', async () => {
      const user = userEvent.setup()
      const { onTiroir, onOpenChange } = monterDansUnTiroir()
      await salir(user)
      await user.click(fermerDuPied())
      let boite = await screen.findByRole('alertdialog', { name: 'Quitter sans enregistrer ?' })
      await user.click(within(boite).getByRole('button', { name: 'Rester' }))
      await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
      expect(onOpenChange).not.toHaveBeenCalled()
      expect(onTiroir).not.toHaveBeenCalled()
      const zone = within(section('Conditions particulières')).getByLabelText('Conditions particulières')
      expect(zone.value).toMatch(/ x$/)
      await user.click(fermerDuPied())
      boite = await screen.findByRole('alertdialog', { name: 'Quitter sans enregistrer ?' })
      await user.click(within(boite).getByRole('button', { name: 'Quitter' }))
      expect(onOpenChange).toHaveBeenCalledTimes(1)
      expect(onOpenChange).toHaveBeenCalledWith(false)
      expect(onTiroir).not.toHaveBeenCalled()
    })

    it('F12 — « Rétablir cet article » n’envoie que cet article réduit à sa clé, les autres tels quels', async () => {
      const user = userEvent.setup()
      const perso = acte()
      perso.sections_personnalisees = ['articles']
      perso.articles_personnalises = [perso.contenu.articles[1].cle]
      documentsApiMock.acte.mockResolvedValue({ data: perso })
      monter()
      const groupe = await screen.findByRole('group', { name: 'Articles' })
      const boutons = within(groupe).getAllByRole('button', { name: /^Rétablir l’article/ })
      // Seul l'article listé par `articles_personnalises` est rétablissable, et il est marqué « Modifié ».
      expect(boutons).toHaveLength(1)
      expect(within(groupe).getAllByText('Modifié')).toHaveLength(1)
      expect(within(groupe).getByRole('button', { name: 'Tout rétablir' })).toBeInTheDocument()
      await user.click(boutons[0])
      expect(documentsApiMock.modifierActe).not.toHaveBeenCalled()
      await user.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Rétablir' }))
      const liste = documentsApiMock.modifierActe.mock.calls[0][1].articles
      expect(liste).toHaveLength(perso.contenu.articles.length)
      expect(liste[1]).toEqual({ cle: perso.contenu.articles[1].cle })
      expect(liste[0]).toEqual({
        cle: perso.contenu.articles[0].cle,
        titre: perso.contenu.articles[0].titre,
        paragraphes: perso.contenu.articles[0].paragraphes,
      })
    })

    it('F13 — le titre par défaut est l’indication du champ « Titre »', async () => {
      monter()
      const champ = within(await screen.findByRole('group', { name: 'Titre du document' })).getByLabelText('Titre')
      expect(champ).toHaveAttribute('placeholder', acte().titre)
    })

    it('F16 — les pourcentages de l’échéancier sont à la française', async () => {
      const a = acte()
      a.contenu.echeancier[0].pourcentage = '0.09'
      documentsApiMock.acte.mockResolvedValue({ data: a })
      monter()
      const s = await screen.findByRole('group', { name: 'Échéancier : les mots' })
      expect(within(s).getByText(/0,09 %/)).toBeInTheDocument()
      expect(s.textContent).not.toMatch(/0\.09/)
    })

    it('F16 — le toast « Enregistré » est court et placé en haut (jamais sur le bouton Enregistrer)', async () => {
      const user = userEvent.setup()
      monter()
      await salir(user)
      await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
      await waitFor(() => expect(toastMock.success).toHaveBeenCalled())
      expect(toastMock.success.mock.calls[0][0]).toBe('Enregistré.')
      expect(toastMock.success.mock.calls[0][1]).toMatchObject({ position: 'top-center' })
    })
  })
})
