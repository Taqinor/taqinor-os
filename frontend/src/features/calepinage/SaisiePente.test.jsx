import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   ACAL208 — L'ONGLET PENTE PROPOSE LES MESURES DE LA VISITE, JAMAIS D'OFFICE.
   ----------------------------------------------------------------------------
   Une visite validée et reprise porte `pente_deg` et `orientation`
   (`calepinage_releve_visite.json`, échantillon committé lu par
   `exempleContrat`). L'onglet les AFFICHE, avec un bouton « Utiliser » qui remplit la saisie du
   pan choisi ; l'écriture passe par la primitive de section (`layout/section/`) et dit la
   provenance : `pitchSource.provenance = 'visite'`, `facingAzimuthSource = 'visite'`.
   Règle D7 : aucune conversion automatique — sans clic, rien n'est posé ni écrit.
   ========================================================================== */

const layout = vi.fn()
const releveVisite = vi.fn()
const enregistrerSectionLayout = vi.fn()
vi.mock('../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      layout: (...a) => layout(...a),
      releveVisite: (...a) => releveVisite(...a),
      enregistrerSectionLayout: (...a) => enregistrerSectionLayout(...a),
    },
  },
}))

const { default: SaisiePente } = await import('./SaisiePente')
const { penteDepuisPourcentage, penteDepuisCotes } = await import('./SaisiePente.helpers')
const { penteDepuisAide } = await import('@roofpro/penteAide')
const { mesuresDeVisite } = await import('./SaisiePente.helpers')

const VISITE = exempleContrat('calepinage', 'calepinage_releve_visite')
const mesure = (code) => VISITE.mesures.find((m) => m.code === code)

const PAN_A = { id: 'zA', label: 'Pan A', pitchDeg: 22 }
const PAN_B = { id: 'zB', label: 'Pan B', pitchDeg: 15 }

const rendre = () => render(
  <MemoryRouter><SaisiePente calepinageId={7} /></MemoryRouter>,
)

beforeEach(() => {
  vi.clearAllMocks()
  layout.mockResolvedValue({ data: {
    roof_layout: { zones: [PAN_A, PAN_B], activeAreaId: 'zB' },
    empreinte_document: 'jeton-1',
  } })
  releveVisite.mockResolvedValue({ data: VISITE })
  enregistrerSectionLayout.mockResolvedValue({ data: { empreinte_document: 'jeton-2' } })
})
afterEach(() => { cleanup() })

describe('ACAL208 — la mesure de la visite est proposée, posée au pan choisi sur clic', () => {
  it('propose la mesure de la visite et la pose au pan choisi sur clic', async () => {
    rendre()
    expect(await screen.findByTestId('cal-pente-visite-mesure'))
      .toHaveTextContent(`Mesure de la visite : ${mesure('pente_deg').valeur}°`)
    // L'orientation (choix « sud » du contrat) : azimut boussole et précision de secteur.
    expect(screen.getByTestId('cal-pente-visite-orientation-mesure'))
      .toHaveTextContent('Orientation de la visite : sud, 180° boussole, précision 22,5°')

    // Le pan choisi (défaut : le pan actif zB), puis « Utiliser ».
    await waitFor(() => expect(screen.getByTestId('cal-pente-pan')).toHaveValue('zB'))
    fireEvent.click(screen.getByTestId('cal-pente-visite-utiliser'))
    expect(screen.getByLabelText(/Pente \(°\)/)).toHaveValue(mesure('pente_deg').valeur)
    fireEvent.click(screen.getByTestId('cal-pente-visite-orientation-utiliser'))
    fireEvent.click(screen.getByTestId('cal-pente-enregistrer'))

    await waitFor(() => expect(enregistrerSectionLayout).toHaveBeenCalledTimes(1))
    expect(enregistrerSectionLayout).toHaveBeenCalledWith(7, {
      cle: 'zones',
      zone_id: 'zB',
      champs: {
        pitchDeg: mesure('pente_deg').valeur,
        pitchSource: { mode: 'degres', degres: mesure('pente_deg').valeur, provenance: 'visite' },
        facingAzimuthDeg: 180,
        facingAzimuthSource: 'visite',
        facingAzimuthPrecisionDeg: 22.5,
      },
      base_empreinte: 'jeton-1',
    })
  })

  it('n’applique rien sans clic', async () => {
    rendre()
    await screen.findByTestId('cal-pente-visite-mesure')
    // La saisie reste celle du pan (15°), pas la mesure de la visite ; rien n'est écrit.
    await waitFor(() => expect(screen.getByLabelText(/Pente \(°\)/)).toHaveValue(PAN_B.pitchDeg))
    expect(enregistrerSectionLayout).not.toHaveBeenCalled()
    fireEvent.click(screen.getByTestId('cal-pente-enregistrer'))
    await waitFor(() => expect(enregistrerSectionLayout).toHaveBeenCalledTimes(1))
    const { champs } = enregistrerSectionLayout.mock.calls[0][1]
    // Pas d'orientation de la visite, pas de provenance « visite » : l'utilisateur n'a rien retenu.
    expect(champs.facingAzimuthSource).toBeUndefined()
    expect(champs.pitchSource.provenance).toBeUndefined()
  })

  it('une saisie manuelle après « Utiliser » retire la provenance visite', async () => {
    rendre()
    await screen.findByTestId('cal-pente-visite-mesure')
    await waitFor(() => expect(screen.getByTestId('cal-pente-pan')).toHaveValue('zB'))
    fireEvent.click(screen.getByTestId('cal-pente-visite-utiliser'))
    fireEvent.change(screen.getByLabelText(/Pente \(°\)/), { target: { value: '31' } })
    fireEvent.click(screen.getByTestId('cal-pente-enregistrer'))
    await waitFor(() => expect(enregistrerSectionLayout).toHaveBeenCalledTimes(1))
    const { champs } = enregistrerSectionLayout.mock.calls[0][1]
    expect(champs.pitchDeg).toBe(31)
    expect(champs.pitchSource.provenance).toBeUndefined()
  })

  it('sans visite reprise, aucune proposition n’est affichée', async () => {
    releveVisite.mockResolvedValue({ data: exempleContrat(
      'calepinage', 'calepinage_releve_visite', 'exemple_vide') })
    rendre()
    await screen.findByTestId('cal-pente')
    await waitFor(() => expect(releveVisite).toHaveBeenCalled())
    expect(screen.queryByTestId('cal-pente-visite')).toBeNull()
    expect(screen.queryByTestId('cal-pente-visite-orientation')).toBeNull()
  })
})

describe('ACAL208 — la rose des vents de la visite', () => {
  it('sud-ouest = 225° boussole, précision de 22,5°', () => {
    const etat = { mesures: [
      { code: 'pente_deg', valeur: 28 }, { code: 'orientation', valeur: 'sud_ouest' }] }
    expect(mesuresDeVisite(etat)).toEqual({
      penteDeg: 28,
      orientation: { libelle: 'sud-ouest', azimutDeg: 225, precisionDeg: 22.5 },
    })
  })

  it('un choix hors rose (« autre ») ne fabrique aucun azimut', () => {
    expect(mesuresDeVisite({ mesures: [{ code: 'orientation', valeur: 'autre' }] }).orientation)
      .toBeNull()
  })
})

describe('Lot 2 critique #32 — lecture seule et verrou', () => {
  it('lecture seule : « Enregistrer la pente » désactivé, la raison dite', async () => {
    render(<MemoryRouter><SaisiePente calepinageId={7} lectureSeule /></MemoryRouter>)
    expect(await screen.findByTestId('cal-pente-lecture-seule')).toBeInTheDocument()
    expect(screen.getByTestId('cal-pente-enregistrer')).toBeDisabled()
    fireEvent.click(screen.getByTestId('cal-pente-enregistrer'))
    expect(enregistrerSectionLayout).not.toHaveBeenCalled()
  })

  it('verrou 409 : le motif serveur, jamais « a changé ailleurs »', async () => {
    enregistrerSectionLayout.mockRejectedValue({ response: { status: 409, data: {
      roof_layout: ['Devis accepté : révisez-le'] } } })
    rendre()
    await screen.findByTestId('cal-pente-visite-mesure')
    await waitFor(() => expect(screen.getByTestId('cal-pente-pan')).toHaveValue('zB'))
    fireEvent.click(screen.getByTestId('cal-pente-visite-utiliser'))
    fireEvent.click(screen.getByTestId('cal-pente-enregistrer'))
    await waitFor(() => expect(screen.getByTestId('cal-pente-message'))
      .toHaveTextContent('Devis accepté : révisez-le'))
    expect(screen.getByTestId('cal-pente-message')).not.toHaveTextContent('a changé ailleurs')
  })
})

describe('ACAL416 — la carte et l’onglet Pente convertissent pareil', () => {
  it('pourcentage et cotes : mêmes degrés que SaisiePente.helpers', () => {
    expect(penteDepuisAide({ pourcentage: '50' }, 'pourcentage').degres).toBeCloseTo(penteDepuisPourcentage(50), 10)
    expect(penteDepuisAide({ porteeM: '5', hauteurFaitageM: '2' }, 'cotes').degres).toBeCloseTo(penteDepuisCotes(5, 2), 10)
  })

  it('portée nulle : l’un et l’autre refusent (jamais 0°)', () => {
    expect(penteDepuisCotes(0, 2)).toBeNull()
    expect(penteDepuisAide({ porteeM: '0', hauteurFaitageM: '2' }, 'cotes').erreur).toContain('portée')
  })
})

// Maquette Main (22/11) — « Modifier la pente » de l'étape Toit ouvre CE formulaire sur le pan ACTIF de
// l'atelier ; une pente enregistrée le dit à la carte, qui relit son document.
describe('étape Toit — ouvert depuis la carte « Pente et orientation »', () => {
  it('`zoneInitiale` choisit le pan ; `onEnregistre` suit l’écriture réussie', async () => {
    const onEnregistre = vi.fn()
    render(<MemoryRouter><SaisiePente calepinageId={7} zoneInitiale="zA" onEnregistre={onEnregistre} /></MemoryRouter>)
    await waitFor(() => expect(screen.getByTestId('cal-pente-pan')).toHaveValue('zA'))
    fireEvent.change(screen.getByLabelText(/Pente \(°\)/), { target: { value: '27' } })
    fireEvent.click(screen.getByTestId('cal-pente-enregistrer'))
    await waitFor(() => expect(onEnregistre).toHaveBeenCalledTimes(1))
    expect(enregistrerSectionLayout.mock.calls[0][1]).toMatchObject({ cle: 'zones', zone_id: 'zA', champs: { pitchDeg: 27 } })
    expect(screen.getByTestId('cal-pente-message')).toHaveTextContent('Pente enregistrée sur le pan « Pan A ».')
  })
})

// ACAL1341 — un pan « Toit plat » n'a pas de pente : ni « Enregistrer la pente » ni « Confirmer » n'y écrivent 22°.
describe('ACAL1341 — pan plat : aucune pente écrite', () => {
  const PLAT = { id: 'zP', label: 'Terrasse', roofType: 'flat', pitchDeg: 22 }

  it('l’onglet Pente ne s’offre pas pour un pan plat', async () => {
    layout.mockResolvedValue({ data: { roof_layout: { zones: [PLAT], activeAreaId: 'zP' }, empreinte_document: 'jeton-1' } })
    rendre()
    expect(await screen.findByTestId('cal-pente-plat')).toHaveTextContent('Toit plat')
    expect(screen.queryByTestId('cal-pente-enregistrer')).toBeNull()
    expect(enregistrerSectionLayout).not.toHaveBeenCalled()
  })

  it('« Confirmer » sur un pan plat : pitchDeg 0, jamais la pente de départ', async () => {
    const { enregistrerPentePan } = await import('./atelier/coque/etapes/EtapeToit.helpers')
    const doc = { empreinte: 'jeton-1', appliquerSection: vi.fn(), recharger: vi.fn() }
    const rendu = await enregistrerPentePan({ calepinageId: 7, doc, zone: PLAT, zones: [PLAT],
      champs: { pitchDeg: 22, pitchSource: { mode: 'degres', degres: 22 } } })
    expect(rendu.ok).toBe(true)
    expect(enregistrerSectionLayout.mock.calls[0][1].champs).toEqual({ pitchDeg: 0 })
    expect(doc.appliquerSection.mock.calls[0][1][0]).toMatchObject({ roofType: 'flat', pitchDeg: 0 })
  })
})
