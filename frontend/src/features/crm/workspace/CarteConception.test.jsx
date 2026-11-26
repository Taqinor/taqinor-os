// ALEA71 (D-ACAL-97, contrôle C4-E7) — la carte « Conception » de la fiche du
// lead LIT le moteur unique (`GET ventes/conception/<lead>/`) et n'en calcule
// rien. Les réponses mockées sont celles du contrat committé
// `conception_lead.json` (PACT10), jamais écrites à la main.
// Nouveau fichier car : composant neuf.
//
// Run : npx vitest run --pool=threads --maxWorkers=1 src/features/crm/workspace/CarteConception.test.jsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act, fireEvent } from '@testing-library/react'

import { exempleContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/ventesApi', () => ({
  default: { getConceptionLead: vi.fn() },
}))

import ventesApi from '../../../api/ventesApi'
import CarteConception from './CarteConception'
import { relireConceptionLead, ATTENTE_DELAI_MS, ATTENTE_MAX_RELECTURES } from './useConceptionLead'
import { useBrouillonsConception } from './useBrouillonsConception'

const CONCEPTION = exempleContrat('ventes', 'conception_lead')
const clone = (o) => JSON.parse(JSON.stringify(o))
const introuvable = () => Object.assign(new Error('404'), { response: { status: 404 } })
const rendre = (props = {}) => render(
  <CarteConception leadId={1} delaiRelectureMs={5} maxRelectures={3} {...props} />,
)
const texte = () => screen.getByTestId('carte-conception').textContent
const sansEspaces = (s) => s.replace(/\s/g, '')
const fr = (n) => sansEspaces(new Intl.NumberFormat('fr-FR').format(n))

beforeEach(() => {
  vi.clearAllMocks()
  ventesApi.getConceptionLead.mockResolvedValue({ data: CONCEPTION })
})

afterEach(() => { vi.useRealTimers() })

describe('ALEA71 — carte « Conception » de la fiche du lead', () => {
  it('m1 — version périmée après la dernière relecture : « Le recalcul n’est pas terminé. » + « Relire » (une lecture de plus, bornée)', async () => {
    vi.useFakeTimers()
    ventesApi.getConceptionLead.mockResolvedValue({ data: { ...clone(CONCEPTION), perimee: true } })
    rendre({ delaiRelectureMs: 1000, maxRelectures: 2 })
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    expect(screen.getByTestId('carte-conception-recalcul')).toHaveTextContent('Recalcul en cours')
    await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
    expect(ventesApi.getConceptionLead).toHaveBeenCalledTimes(3) // 1 lecture + 2 relectures, puis plus rien
    expect(screen.queryByTestId('carte-conception-recalcul')).toBeNull()
    expect(screen.getByTestId('carte-conception-recalcul-long').textContent).toContain("Le recalcul n'est pas terminé.")
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Relire' })); await vi.advanceTimersByTimeAsync(5000) })
    expect(ventesApi.getConceptionLead).toHaveBeenCalledTimes(4) // une seule lecture de plus
    expect(screen.getByTestId('carte-conception-recalcul-long')).toBeTruthy()
    // la relecture donne une version à jour : la phrase disparaît
    ventesApi.getConceptionLead.mockResolvedValue({ data: CONCEPTION })
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Relire' })); await vi.advanceTimersByTimeAsync(10) })
    expect(screen.queryByTestId('carte-conception-recalcul-long')).toBeNull()
  })

  it('Q3 — deux options : la colonne de l’option retenue porte « retenue », l’autre non ; une seule option : aucune marque', async () => {
    const deux = clone(CONCEPTION)
    deux.option_retenue = 'avec'
    ventesApi.getConceptionLead.mockResolvedValue({ data: deux })
    const { unmount } = rendre()
    await screen.findByTestId('carte-conception')
    expect(screen.getByTestId('carte-conception-retenue-avec').textContent).toBe('retenue')
    expect(screen.queryByTestId('carte-conception-retenue-sans')).toBeNull()
    unmount()
    const industriel = exempleContrat('ventes', 'conception_lead', 'exemple_industriel')
    ventesApi.getConceptionLead.mockResolvedValue({ data: industriel })
    rendre()
    await screen.findByTestId('carte-conception')
    expect(screen.queryByTestId('carte-conception-retenue-sans')).toBeNull()
    expect(screen.queryByTestId('carte-conception-retenue-avec')).toBeNull()
  })

  it('lit les valeurs de la route : taille, production, économies, retour, source du prix', async () => {
    rendre()
    await screen.findByTestId('carte-conception')
    expect(ventesApi.getConceptionLead).toHaveBeenCalledWith(1)
    // Les deux options du contrat, chacune avec SES valeurs servies.
    for (const [option, v] of Object.entries(CONCEPTION.valeurs)) {
      const colonne = screen.getByTestId(`carte-conception-option-${option}`).textContent
      expect(colonne).toContain(`${v.nb_panneaux.valeur} panneaux`)
      expect(sansEspaces(colonne)).toContain(`${String(v.puissance_kwc.valeur).replace('.', ',')}kWc`)
      expect(sansEspaces(colonne)).toContain(fr(v.production_annuelle.valeur))
      expect(sansEspaces(colonne)).toContain(fr(v.economies_annuelles.valeur))
      expect(colonne).toContain(`${v.payback.valeur} ans`)
      // T4-X9-016 — le montant et l'économie de CETTE option, et la phrase du calcul.
      const calcul = screen.getByTestId(`carte-conception-calcul-${option}`).textContent
      expect(sansEspaces(calcul)).toContain(`${fr(v.payback.investissement)}MAD${v.payback.base}`)  // T4-X6-006 : la base dite
      expect(sansEspaces(calcul)).toContain(fr(v.payback.economie_annuelle))
      expect(calcul).toContain(v.payback.calcul)
    }
    expect(texte()).toContain(`d'après le devis ${CONCEPTION.payback_devis.devis_ref}`)
    expect(texte()).not.toContain('Économies (conception du lead)')
  })

  it('R5F-N1 — économie du devis ≠ économie de la conception : la ligne « Économies » dit qu’elle est celle de la conception', async () => {
    const ecart = clone(CONCEPTION)
    ecart.valeurs.sans.economies_annuelles.valeur = 35542
    ecart.valeurs.sans.payback.economie_annuelle = 17432
    ventesApi.getConceptionLead.mockResolvedValue({ data: ecart })
    rendre()
    await screen.findByTestId('carte-conception')
    const sans = screen.getByTestId('carte-conception-option-sans').textContent
    expect(sans).toContain('Économies (conception du lead)')
    expect(sansEspaces(sans)).toContain(fr(35542))
    expect(sansEspaces(screen.getByTestId('carte-conception-calcul-sans').textContent)).toContain(fr(17432))
    // L'autre colonne, sans écart, garde « Économies ».
    expect(screen.getByTestId('carte-conception-option-avec').textContent).not.toContain('(conception du lead)')
  })

  it('dit chaque supposition avec son champ, et l\'historique « Recalculé le … »', async () => {
    rendre()
    await screen.findByTestId('carte-conception')
    for (const s of CONCEPTION.suppositions) {
      expect(texte()).toContain(s.message)
      expect(screen.getByTestId(`carte-conception-supposition-${s.champ}`)).toBeTruthy()
    }
    expect(screen.getByTestId('carte-conception-historique').textContent)
      .toContain(CONCEPTION.declencheur.raison)
  })

  it('« Recalcul en cours » quand la version est périmée, avec les valeurs gardées', async () => {
    ventesApi.getConceptionLead.mockResolvedValue({ data: { ...clone(CONCEPTION), perimee: true } })
    rendre({ delaiRelectureMs: 600000 }) // la relecture suivante n'a pas encore eu lieu : le recalcul est en cours
    await screen.findByTestId('carte-conception')
    expect(texte()).toContain('Recalcul en cours')
    expect(texte()).toContain(`${CONCEPTION.valeurs.sans.nb_panneaux.valeur} panneaux`)
  })

  // R5A-N6 — un 404 est la réponse NORMALE « aucune conception calculée » : état calme, UNE lecture, aucune relecture
  // automatique (avant : 1 + 6 relectures de 404 par ouverture de fiche) ; une ACTION qui crée la conception la relit.
  it('R5A-N6 — lead sans conception rangée (404) : phrase calme, UNE seule lecture, aucune relecture automatique', async () => {
    ventesApi.getConceptionLead.mockRejectedValue(introuvable())
    rendre({ delaiRelectureMs: 5 })
    expect((await screen.findByTestId('carte-conception-sans-conception')).textContent)
      .toContain('Pas encore de conception')
    await new Promise((r) => setTimeout(r, 60))
    expect(ventesApi.getConceptionLead).toHaveBeenCalledTimes(1)
    expect(screen.queryByTestId('carte-conception-attente')).toBeNull()
  })

  it('R5A-N6 — une action qui crée la conception (fiche enregistrée, devis créé) la relit : la carte se remplit', async () => {
    ventesApi.getConceptionLead.mockRejectedValueOnce(introuvable()).mockResolvedValue({ data: CONCEPTION })
    rendre()
    await screen.findByTestId('carte-conception-sans-conception')
    await act(async () => { relireConceptionLead(1) })
    await screen.findByTestId('carte-conception-option-avec')
    expect(ventesApi.getConceptionLead).toHaveBeenCalledTimes(2)
    expect(screen.queryByTestId('carte-conception-sans-conception')).toBeNull()
  })

  // La PREMIÈRE conception d'un lead se calcule en ARRIÈRE-PLAN (regroupement ~5 s + calcul) : jusqu'à sa première version le
  // serveur répond 404. Pour un lead qui vient d'être créé (ou déjà « en cours de calcul »), ce 404 est « en cours de calcul »,
  // relu d'elle-même, borné ; un ACTION (fiche enregistrée) pendant l'attente la relance.
  const recent = () => new Date().toISOString()

  it('lead récent + action pendant l’attente : la conception apparaît SANS aucune autre action (relue d’elle-même)', async () => {
    vi.useFakeTimers()
    ventesApi.getConceptionLead
      .mockRejectedValueOnce(introuvable()) // ouverture : lead créé à l'instant
      .mockRejectedValueOnce(introuvable()) // l'enregistrement relit : la tâche de fond n'a pas démarré
      .mockRejectedValueOnce(introuvable())
      .mockResolvedValue({ data: CONCEPTION })
    render(<CarteConception leadId={1} creeLe={recent()} />)
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    expect(screen.getByTestId('carte-conception-attente').textContent).toContain('Conception en cours de calcul…')
    await act(async () => { relireConceptionLead(1); await vi.advanceTimersByTimeAsync(0) })
    expect(screen.getByTestId('carte-conception-attente')).toBeTruthy()
    await act(async () => { await vi.advanceTimersByTimeAsync(ATTENTE_DELAI_MS * 2 + 50) })
    expect(screen.getByTestId('carte-conception-option-avec')).toBeTruthy()
    expect(screen.queryByTestId('carte-conception-attente')).toBeNull()
    expect(ventesApi.getConceptionLead).toHaveBeenCalledTimes(4)
  })

  it('lead récent, 404 persistant : relue 6 × 4 s au plus (une minuterie pour deux cartes), puis l’état calme', async () => {
    vi.useFakeTimers()
    ventesApi.getConceptionLead.mockRejectedValue(introuvable())
    render(<><CarteConception leadId={1} creeLe={recent()} /><CarteConception leadId={1} creeLe={recent()} /></>)
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    expect(screen.getAllByTestId('carte-conception-attente').length).toBe(2)
    await act(async () => { await vi.advanceTimersByTimeAsync(ATTENTE_DELAI_MS * (ATTENTE_MAX_RELECTURES + 3)) })
    expect(ventesApi.getConceptionLead).toHaveBeenCalledTimes(1 + ATTENTE_MAX_RELECTURES) // ouverture + 6 relectures, une seule file
    expect(screen.getAllByTestId('carte-conception-sans-conception').length).toBe(2)
  })

  it('lead ANCIEN sans conception + enregistrement d’un champ sans rapport : UNE lecture de plus, jamais « en cours de calcul »', async () => {
    vi.useFakeTimers()
    ventesApi.getConceptionLead.mockRejectedValue(introuvable())
    render(<CarteConception leadId={1} creeLe="2026-01-01T10:00:00Z" />)
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    expect(screen.getByTestId('carte-conception-sans-conception')).toBeTruthy()
    await act(async () => { relireConceptionLead(1); await vi.advanceTimersByTimeAsync(0) })
    expect(screen.queryByTestId('carte-conception-attente')).toBeNull()
    expect(screen.getByTestId('carte-conception-sans-conception')).toBeTruthy()
    await act(async () => { await vi.advanceTimersByTimeAsync(ATTENTE_DELAI_MS * (ATTENTE_MAX_RELECTURES + 2)) })
    expect(ventesApi.getConceptionLead).toHaveBeenCalledTimes(2)
  })

  it('lead ancien : la saisie fait naître la conception — l’historique qui change la relit, elle apparaît sans rechargement', async () => {
    vi.useFakeTimers()
    ventesApi.getConceptionLead.mockRejectedValueOnce(introuvable()).mockRejectedValueOnce(introuvable())
      .mockResolvedValue({ data: CONCEPTION })
    render(<CarteConception leadId={1} creeLe="2026-01-01T10:00:00Z" />)
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    await act(async () => { relireConceptionLead(1); await vi.advanceTimersByTimeAsync(0) }) // enregistrement : 404 calme
    expect(screen.queryByTestId('carte-conception-attente')).toBeNull()
    // Le serveur a rangé la première version : la ligne « Conception recalculée » change l'historique -> relecture simple.
    await act(async () => { relireConceptionLead(1, { attendre: false }); await vi.advanceTimersByTimeAsync(0) })
    expect(screen.getByTestId('carte-conception-option-avec')).toBeTruthy()
    expect(ventesApi.getConceptionLead).toHaveBeenCalledTimes(3)
  })

  it('lead créé à l’instant, ouvert sans action : le 404 de la première lecture est « en cours de calcul », puis la conception apparaît', async () => {
    vi.useFakeTimers()
    ventesApi.getConceptionLead.mockRejectedValueOnce(introuvable()).mockResolvedValue({ data: CONCEPTION })
    render(<CarteConception leadId={1} creeLe={new Date().toISOString()} />)
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    expect(screen.getByTestId('carte-conception-attente')).toBeTruthy()
    await act(async () => { await vi.advanceTimersByTimeAsync(ATTENTE_DELAI_MS + 50) })
    expect(screen.getByTestId('carte-conception-option-avec')).toBeTruthy()
  })

  it('lead créé il y a longtemps : le 404 à l’ouverture reste calme (une seule lecture)', async () => {
    ventesApi.getConceptionLead.mockRejectedValue(introuvable())
    render(<CarteConception leadId={1} creeLe="2026-01-01T10:00:00Z" />)
    await screen.findByTestId('carte-conception-sans-conception')
    await new Promise((r) => setTimeout(r, 40))
    expect(ventesApi.getConceptionLead).toHaveBeenCalledTimes(1)
  })

  it('R5A-N6 — plusieurs consommateurs montés sur la même fiche (carte + avis brouillons) : UNE seule requête, un 404 sans erreur', async () => {
    ventesApi.getConceptionLead.mockRejectedValue(introuvable())
    const Brouillons = () => { useBrouillonsConception(1); return null }
    render(<><CarteConception leadId={1} /><Brouillons /><Brouillons /></>)
    await screen.findByTestId('carte-conception-sans-conception')
    await new Promise((r) => setTimeout(r, 30))
    expect(ventesApi.getConceptionLead).toHaveBeenCalledTimes(1)
    expect(screen.queryByTestId('carte-conception-indisponible')).toBeNull()
  })

  it('un refus nomme le champ à remplir, jamais des zéros', async () => {
    const refus = exempleContrat('ventes', 'conception_lead', 'exemple_refus')
    ventesApi.getConceptionLead.mockResolvedValue({ data: refus })
    rendre()
    const carte = await screen.findByTestId('carte-conception')
    expect(carte.textContent).toContain(refus.refus.message)
    expect(screen.getByTestId('carte-conception-refus').textContent).toContain(refus.refus.champ)
    expect(screen.queryByTestId('carte-conception-option-sans')).toBeNull()
    expect(carte.textContent).not.toMatch(/\b0 (panneaux|kWc|ans)/)
  })

  it('payback nul : la phrase du serveur, puis « d\'après le devis DEV-… » une fois un devis rangé', async () => {
    const sansDevis = clone(CONCEPTION)
    for (const o of Object.values(sansDevis.valeurs)) o.payback = { valeur: null, unite: 'ans', source: 'devis' }
    sansDevis.payback_devis = { devis_ref: null, motif: 'retour sur investissement : après un premier devis' }
    ventesApi.getConceptionLead.mockResolvedValue({ data: sansDevis })
    const { unmount } = rendre()
    await screen.findByTestId('carte-conception')
    expect(texte()).toContain('retour sur investissement : après un premier devis')
    expect(texte()).not.toContain("d'après le devis")
    unmount()
    ventesApi.getConceptionLead.mockResolvedValue({ data: CONCEPTION })
    rendre()
    await screen.findByTestId('carte-conception')
    expect(texte()).toContain(`d'après le devis ${CONCEPTION.payback_devis.devis_ref}`)
  })

  it('fiche technique incomplète : la phrase `non_calcule` est une supposition à corriger, pas une erreur', async () => {
    const phrase = 'Fiche technique de l’onduleur incomplète : renseigner la tension MPPT maximale.'
    const incomplet = clone(CONCEPTION)
    incomplet.valeurs.sans.verdicts.valeur.non_calcule = phrase
    ventesApi.getConceptionLead.mockResolvedValue({ data: incomplet })
    rendre()
    await screen.findByTestId('carte-conception')
    const ligne = screen.getByTestId('carte-conception-non-calcule')
    expect(ligne.textContent).toContain(phrase)
    expect(ligne.closest('[role="alert"]')).toBeNull()
  })

  it('lane E9 — fiche vide : UNE ligne par produit (« Fiche technique de « … » incomplète (N champs) »), champs sur demande', async () => {
    // La phrase TELLE QUE le moteur la sert (`electrical_service.motifs_fiche_incomplete` joints par « ; »).
    const motif = (champ, de) => `« ${champ} » non renseigné(e) sur la fiche technique ${de} — complétez la fiche `
      + 'technique du produit (Stock → Catalogue).'
    const champsPanneau = ['puissance crête (Wc)', 'tension circuit ouvert — Voc (V)', 'courant de court-circuit — Isc (A)']
    const phrase = [...champsPanneau.map((c) => motif(c, 'du panneau')), motif('tension MPPT maximale (V)', "de l'onduleur")]
      .join(' ; ')
    const incomplet = clone(CONCEPTION)
    incomplet.valeurs.sans.verdicts.valeur.non_calcule = phrase
    ventesApi.getConceptionLead.mockResolvedValue({ data: incomplet })
    rendre()
    await screen.findByTestId('carte-conception')
    const lignes = screen.getAllByTestId('carte-conception-non-calcule')
    const module = incomplet.valeurs.sans.module.valeur
    const onduleur = incomplet.valeurs.sans.onduleurs.valeur[0].designation
    expect(lignes.map((l) => l.querySelector('[data-zone="fiche-titre"]').textContent)).toEqual([
      `Fiche technique de « ${module} » incomplète (3 champs) : complétez-la dans Stock → Catalogue`,
      `Fiche technique de « ${onduleur} » incomplète (1 champ) : complétez-la dans Stock → Catalogue`,
    ])
    // Les champs sont DANS un dépli « Voir les champs », fermé par défaut.
    const depli = lignes[0].querySelector('details')
    expect(depli.open).toBe(false)
    expect(depli.querySelector('summary').textContent).toBe('Voir les champs')
    expect([...depli.querySelectorAll('li')].map((li) => li.textContent)).toEqual(champsPanneau)
    expect(texte()).not.toContain('non renseigné(e)')
  })

  it('une seule option servie : pas de seconde colonne vide', async () => {
    const industriel = exempleContrat('ventes', 'conception_lead', 'exemple_industriel')
    ventesApi.getConceptionLead.mockResolvedValue({ data: industriel })
    rendre()
    await screen.findByTestId('carte-conception')
    expect(screen.getByTestId('carte-conception-option-sans')).toBeTruthy()
    expect(screen.queryByTestId('carte-conception-option-avec')).toBeNull()
    expect(document.querySelectorAll('[data-testid^="carte-conception-option-"]').length).toBe(1)
  })

  it('D-ACAL-109 / 110 — l’option qui porte le matériel désigné le dit ; les phrases servies (deux arrondis) sont toutes affichées', async () => {
    const designee = clone(CONCEPTION)
    designee.valeurs.avec.onduleur_produit = { ...designee.valeurs.avec.onduleur_produit, source: 'impose' }
    const arrondi = (option) => ({ code: 'panneaux_au_module_designe', champ: 'module_produit', source: 'defaut',
      valeur: { option }, message: `phrase servie de l’arrondi ${option}` })
    designee.suppositions = [...designee.suppositions,
      { code: 'option_materiel_du_moteur', champ: 'onduleur_produit', valeur: 'sans', source: 'defaut',
        message: 'phrase servie laquelle est laquelle' }, arrondi('sans'), arrondi('avec')]
    ventesApi.getConceptionLead.mockResolvedValue({ data: designee })
    rendre()
    await screen.findByTestId('carte-conception')
    expect(screen.getByTestId('carte-conception-designe-avec')).toHaveTextContent('matériel désigné')
    expect(screen.queryByTestId('carte-conception-designe-sans')).toBeNull()
    for (const phrase of ['phrase servie laquelle est laquelle', 'phrase servie de l’arrondi sans',
      'phrase servie de l’arrondi avec']) expect(texte()).toContain(phrase)
    expect(screen.getAllByTestId('carte-conception-supposition-module_produit')).toHaveLength(2)
  })

  it('erreur autre que 404 : la carte le dit sans casser la fiche', async () => {
    ventesApi.getConceptionLead.mockRejectedValue(
      Object.assign(new Error('x'), { response: { status: 500 } }))
    rendre()
    expect((await screen.findByTestId('carte-conception-indisponible')).textContent)
      .toContain('indisponible')
  })
})
