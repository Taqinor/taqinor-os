import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

/* ============================================================================
   CAL159 — L'ÉCRAN POMPAGE NE CALCULE RIEN, IL REND CE QUE LE SERVEUR SERT.
   ----------------------------------------------------------------------------
   La charge utile vient du contrat COMMITTÉ `calepinage_pompage.json`
   (PACT10) — le MÊME fichier que la vue CAL159 (moitié serveur) affirme.
   Aucun objet n'est écrit à la main ici : un mock maison serait une seconde
   source de vérité, exactement l'incident du 03/08/2026.

   CE QUE CE TEST TIENT :
     * la courbe et le point de fonctionnement sont ceux du serveur — l'écran
       n'interpole rien (aucun point n'est calculé côté navigateur) ;
     * un champ fautif porte SON message SOUS LUI, et le bandeau le NOMME
       (règle fondateur « jamais un refus générique ») ;
     * un volume non calculable rend « non calculé — pompe sans courbe »,
       jamais un 0 ;
     * la saisie n'est jamais snappée : `noValidate` + `step="any"`.
   ========================================================================== */

const RESULTAT = exempleContrat('calepinage', 'calepinage_pompage')
const RESULTAT_VIDE = exempleContrat('calepinage', 'calepinage_pompage',
  'exemple_vide')

const pompage = vi.fn()
vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { pompage: (...a) => pompage(...a) } },
}))

const { default: PompagePanel } = await import('./PompagePanel')

const rendre = () => render(
  <MemoryRouter><PompagePanel calepinageId={1} /></MemoryRouter>,
)

const calculer = () => fireEvent.submit(screen.getByTestId('cal-pompage-form'))

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

describe('CAL159 — la saisie du puits, du besoin et du réservoir', () => {
  it('monte les groupes de champs (puits, niveau d’eau, besoin, réservoir), tous libres de saisie', () => {
    rendre()
    for (const groupe of ['puits', 'niveau_eau', 'besoin', 'reservoir', 'champ_solaire']) {
      expect(screen.getByTestId(`cal-pompage-groupe-${groupe}`)).toBeInTheDocument()
    }
    // Règle fondateur : l'écran ne refuse ni n'arrondit jamais une frappe.
    expect(screen.getByTestId('cal-pompage-form')).toHaveAttribute('noValidate')
    const champ = screen.getByLabelText(/Débit souhaité/)
    expect(champ).toHaveAttribute('step', 'any')
  })

  it('envoie au serveur EXACTEMENT ce qui a été tapé, sans conversion', () => {
    pompage.mockResolvedValue({ data: RESULTAT })
    rendre()
    fireEvent.change(screen.getByLabelText(/Débit souhaité/), { target: { value: '8.25' } })
    fireEvent.change(screen.getByLabelText(/Niveau statique/), { target: { value: '40' } })
    calculer()
    expect(pompage).toHaveBeenCalledWith(1, expect.objectContaining({
      debit_souhaite_m3h: '8.25', niveau_statique_m: '40',
    }))
  })
})

describe('CAL159 — le rendu d’un dimensionnement SERVI', () => {
  it('affiche HMT, pompe, variateur et autonomie tels que servis', async () => {
    pompage.mockResolvedValue({ data: RESULTAT })
    rendre()
    calculer()

    expect(await screen.findByTestId('cal-pompage-hmt'))
      .toHaveTextContent(String(RESULTAT.hmt.hmt_m))
    expect(screen.getByTestId('cal-pompage-hmt'))
      .toHaveTextContent(RESULTAT.hmt.source)
    expect(screen.getByTestId('cal-pompage-pompe'))
      .toHaveTextContent(RESULTAT.pompe.nom)
    expect(screen.getByTestId('cal-pompage-variateur'))
      .toHaveTextContent(RESULTAT.variateur.nom)
    expect(screen.getByTestId('cal-pompage-autonomie'))
      .toHaveTextContent(String(RESULTAT.besoin.autonomie_jours))
    expect(screen.getByTestId('cal-pompage-irradiation'))
      .toHaveTextContent(RESULTAT.volumes.source_irradiation)
  })

  it('trace la courbe SERVIE et le point de fonctionnement SERVI', async () => {
    pompage.mockResolvedValue({ data: RESULTAT })
    rendre()
    calculer()

    const svg = await screen.findByTestId('cal-pompage-courbe')
    const polyline = svg.querySelector('polyline')
    // Autant de points tracés que le serveur en a publié — ni plus (pas
    // d'interpolation), ni moins.
    expect(polyline.getAttribute('points').trim().split(/\s+/))
      .toHaveLength(RESULTAT.pompe.courbe.debits_m3h.length)
    expect(screen.getByTestId('cal-pompage-point')).toBeInTheDocument()
  })

  it('rend les DOUZE volumes mensuels, plat et PVGIS', async () => {
    pompage.mockResolvedValue({ data: RESULTAT })
    rendre()
    calculer()

    const table = await screen.findByTestId('cal-pompage-volumes')
    expect(table).toBeInTheDocument()
    for (let i = 0; i < 12; i += 1) {
      const ligne = screen.getByTestId(`cal-pompage-mois-${i}`)
      expect(ligne).toHaveTextContent(String(RESULTAT.volumes.m3_mois_plat[i]))
      expect(ligne).toHaveTextContent(String(RESULTAT.volumes.m3_mois_pvgis[i]))
    }
  })
})

describe('CAL159 — ce que le serveur ne sert PAS n’est jamais inventé', () => {
  it('sans pompe retenue : « non calculé — pompe sans courbe », jamais 0', async () => {
    pompage.mockResolvedValue({ data: RESULTAT_VIDE })
    rendre()
    calculer()

    expect(RESULTAT_VIDE.volumes).toBeNull()
    const absent = await screen.findByTestId('cal-pompage-volumes-absents')
    expect(absent).toHaveTextContent('non calculé — pompe sans courbe')
    expect(screen.queryByTestId('cal-pompage-volumes')).toBeNull()
    expect(screen.queryByTestId('cal-pompage-courbe')).toBeNull()
    // La pompe et le variateur valent `null` au contrat : « — », pas « 0 ».
    expect(screen.getByTestId('cal-pompage-pompe')).toHaveTextContent('—')
    expect(screen.getByTestId('cal-pompage-variateur')).toHaveTextContent('—')
  })

  it('chaque champ fautif porte SON message, et le bandeau le nomme', async () => {
    pompage.mockResolvedValue({ data: RESULTAT_VIDE })
    rendre()
    calculer()

    for (const [cle, message] of Object.entries(RESULTAT_VIDE.erreurs)) {
      const sousChamp = await screen.findByTestId(`cal-pompage-erreur-${cle}`)
      expect(sousChamp).toHaveTextContent(message.slice(0, 30))
      // Le message est posé DANS le champ, pas ailleurs sur l'écran.
      expect(screen.getByTestId(`cal-pompage-champ-${cle}`)).toContainElement(sousChamp)
      expect(document.getElementById(`cal-pompage-${cle}`))
        .toHaveAttribute('aria-invalid', 'true')
    }
    // Le bandeau NOMME les champs et y emmène — jamais « Non enregistré ».
    const bandeau = screen.getByTestId('cal-pompage-bandeau')
    expect(bandeau).toHaveTextContent('Débit souhaité')
    expect(bandeau.querySelector('a[href="#cal-pompage-debit_souhaite_m3h"]'))
      .toBeTruthy()
  })

  it('les avertissements du serveur sont répétés tels quels', async () => {
    pompage.mockResolvedValue({ data: RESULTAT_VIDE })
    rendre()
    calculer()
    expect(await screen.findByTestId('cal-pompage-avertissements'))
      .toHaveTextContent('pompe sans courbe')
  })

  it('refus du serveur : son message, sous une alerte', async () => {
    pompage.mockRejectedValue({ response: { data: { detail: 'Calepinage introuvable.' } } })
    rendre()
    calculer()
    expect(await screen.findByTestId('cal-pompage-refus'))
      .toHaveTextContent('Calepinage introuvable.')
  })
})

describe('CAL159 — l’écran est ATTEIGNABLE', () => {
  it('le module déclare la route `/calepinage/:id/pompage` avec ses rôles', async () => {
    const { default: config } = await import('../module.config.jsx')
    const route = config.routes.find((r) => r.path === '/calepinage/:id/pompage')
    expect(route, 'route de pompage absente du module').toBeTruthy()
    expect(Array.isArray(route.roles) && route.roles.length > 0).toBe(true)
  })
})

describe('ACAL807 — le niveau d’eau, le réservoir jour par jour, les alertes sous leur champ', () => {
  it('le groupe « Le niveau d’eau » porte ses cinq champs et les 12 pastilles de mois', () => {
    pompage.mockResolvedValue({ data: RESULTAT })
    rendre()
    const groupe = screen.getByTestId('cal-pompage-groupe-niveau_eau')
    for (const cle of ['niveau_statique_ete_m', 'niveau_statique_hiver_m', 'profondeur_calage_m',
      'diametre_tubage_mm', 'debit_exploitation_m3h']) {
      expect(groupe).toContainElement(screen.getByTestId(`cal-pompage-champ-${cle}`))
    }
    for (let m = 1; m <= 12; m += 1) {
      expect(groupe).toContainElement(screen.getByTestId(`cal-pompage-mois-bas-${m}`))
    }
    fireEvent.click(screen.getByTestId('cal-pompage-mois-bas-7'))
    fireEvent.click(screen.getByTestId('cal-pompage-mois-bas-8'))
    expect(screen.getByTestId('cal-pompage-mois-bas-7')).toHaveAttribute('aria-pressed', 'true')
    calculer()
    expect(pompage.mock.calls[0][1]).toEqual({ mois_niveau_bas: [7, 8] })
  })

  it('la carte « Réservoir jour par jour » se lit sur l’exemple du contrat', async () => {
    pompage.mockResolvedValue({ data: RESULTAT })
    rendre()
    calculer()
    const bilan = RESULTAT.bilan_reservoir
    const carte = await screen.findByTestId('cal-pompage-bilan')
    expect(carte).toHaveTextContent(`Jours où l'eau manque : ${bilan.jours_manque} sur 365`)
    expect(carte).toHaveTextContent(
      `Jours où le réservoir est plein (la pompe s'arrête) : ${bilan.jours_plein}`)
    expect(carte).toHaveTextContent(`Besoin couvert : ${bilan.besoin_couvert_pct} %`)
    expect(carte).toHaveTextContent(bilan.mention)
    expect(carte.querySelectorAll('[data-mois-manque]')).toHaveLength(12)
    expect(screen.queryByTestId('cal-pompage-bilan-motif')).toBeNull()
  })

  it('chaque alerte apparaît SOUS son champ : une phrase simple puis le texte du serveur', async () => {
    pompage.mockResolvedValue({ data: RESULTAT })
    rendre()
    calculer()
    const alerte = await screen.findByTestId('cal-pompage-alerte-immersion_minimale')
    expect(screen.getByTestId('cal-pompage-champ-profondeur_calage_m')).toContainElement(alerte)
    expect(alerte).toHaveTextContent('La pompe risque de tourner à sec')
    expect(alerte).toHaveTextContent(RESULTAT.alertes[0].message)
    const forage = screen.getByTestId('cal-pompage-alerte-plafond_forage')
    expect(screen.getByTestId('cal-pompage-champ-debit_exploitation_m3h')).toContainElement(forage)
    expect(forage).toHaveTextContent('Le forage ne donne pas assez d\'eau pour ce besoin')
  })

  it('sans réservoir, la carte dit pourquoi elle est absente', async () => {
    pompage.mockResolvedValue({ data: RESULTAT_VIDE })
    rendre()
    calculer()
    expect(await screen.findByTestId('cal-pompage-bilan-motif')).toHaveTextContent(
      `Bilan du réservoir non calculé : ${RESULTAT_VIDE.bilan_reservoir.motif}`)
    expect(screen.queryByTestId('cal-pompage-bilan')).toBeNull()
  })
})

describe('ACAL811 — le verdict des modules en série contre la fenêtre du variateur', () => {
  const CHAINES = RESULTAT.chaines_variateur
  const avecChaines = (surcharge) => ({
    ...RESULTAT, chaines_variateur: { ...CHAINES, ...surcharge },
  })

  it('le groupe « Le champ solaire » propose série et parallèles, et les modules posés', async () => {
    pompage.mockResolvedValue({ data: RESULTAT })
    rendre()
    const groupe = screen.getByTestId('cal-pompage-groupe-champ_solaire')
    for (const cle of ['modules_en_serie', 'chaines_paralleles']) {
      expect(groupe).toContainElement(screen.getByTestId(`cal-pompage-champ-${cle}`))
    }
    calculer()
    await screen.findByTestId('cal-pompage-chaines')
    expect(groupe).toHaveTextContent(`Modules posés : ${CHAINES.modules_poses}`)
  })

  it('conforme : icône ET mot, Voc à froid, fenêtre et température du site', async () => {
    pompage.mockResolvedValue({ data: RESULTAT })
    rendre()
    calculer()
    const ligne = await screen.findByTestId('cal-pompage-chaines')
    expect(ligne).toHaveTextContent('✔ Conforme')
    expect(ligne).toHaveTextContent(`${CHAINES.serie} modules en série : Voc à froid ${CHAINES.voc_froid_v} V`)
    expect(ligne).toHaveTextContent(
      `le variateur accepte ${CHAINES.fenetre.longueur_min} à ${CHAINES.fenetre.longueur_max} modules`)
    expect(ligne).toHaveTextContent(CHAINES.temperatures.source)
  })

  it('21 modules : « Hors fenêtre » en rouge, en mots simples, avec la longueur maximale', async () => {
    pompage.mockResolvedValue({ data: avecChaines({
      verdict: 'hors_fenetre', serie: 21, voc_froid_v: 1097,
      motif: 'trop longue : Voc à froid 1 097 V au-dessus des 1 000 V du variateur' }) })
    rendre()
    calculer()
    const ligne = await screen.findByTestId('cal-pompage-chaines')
    expect(ligne).toHaveTextContent('✖ Hors fenêtre')
    expect(ligne).not.toHaveTextContent('Conforme')
    expect(ligne.className).toMatch(/red/)
    expect(ligne).toHaveTextContent('Trop de modules en série : la tension à froid dépasse ce que le variateur accepte')
    expect(ligne).toHaveTextContent(`21 modules en série`)
    expect(ligne).toHaveTextContent(`à ${CHAINES.fenetre.longueur_max} modules`)
  })

  it('non vérifiable : « À vérifier », jamais vert, et le champ à saisir est nommé sous lui', async () => {
    pompage.mockResolvedValue({ data: RESULTAT_VIDE })
    rendre()
    calculer()
    const ligne = await screen.findByTestId('cal-pompage-chaines')
    expect(ligne).toHaveTextContent('⚠ À vérifier')
    expect(ligne).not.toHaveTextContent('Conforme')
    const sousChamp = screen.getByTestId('cal-pompage-alerte-chaine_a_saisir')
    expect(screen.getByTestId('cal-pompage-champ-modules_en_serie')).toContainElement(sousChamp)
    expect(sousChamp).toHaveTextContent(RESULTAT_VIDE.chaines_variateur.motif)
  })
})

describe('ACAL815 — « Pompage direct » contre « Avec le réservoir »', () => {
  it('les deux cartes se lisent sur l’exemple du contrat : 6,0 m³/h contre 2,4 m³/h', async () => {
    pompage.mockResolvedValue({ data: RESULTAT })
    rendre()
    calculer()
    const bloc = await screen.findByTestId('cal-pompage-comparaison')
    const [direct, avec] = bloc.querySelectorAll('[data-option]')
    expect(direct).toHaveAttribute('data-option', 'direct')
    expect(direct).toHaveTextContent('Pompage direct')
    expect(direct).toHaveTextContent('Débit de conception : 6,0 m³/h')
    expect(direct).toHaveTextContent('Mois critique : Jan')
    expect(avec).toHaveAttribute('data-option', 'avec_reservoir')
    expect(avec).toHaveTextContent('Avec le réservoir')
    expect(avec).toHaveTextContent('Débit de conception : 2,4 m³/h')
    expect(avec).toHaveTextContent('Mois critique : Déc')
    expect(avec).toHaveTextContent('Jours où l\'eau manque : 0')
  })

  it('sans heures de demande, la carte « direct » dit quel champ remplir', async () => {
    const comparaison = { ...RESULTAT.comparaison_reservoir, direct: null,
      motif: 'fenêtre de demande non saisie' }
    pompage.mockResolvedValue({ data: { ...RESULTAT, comparaison_reservoir: comparaison } })
    rendre()
    calculer()
    const bloc = await screen.findByTestId('cal-pompage-comparaison')
    const direct = bloc.querySelector('[data-option="direct"]')
    expect(direct).toHaveTextContent('fenêtre de demande non saisie')
    expect(direct).toHaveTextContent('Heures par jour où l’on tire l’eau')
    expect(direct).not.toHaveTextContent('Débit de conception')
    expect(screen.getByLabelText(/Heures par jour où l’on tire l’eau/)).toHaveAttribute('step', 'any')
  })
})

describe('ACAL821 — plusieurs pompes sur le même variateur', () => {
  const POMPES = RESULTAT.pompes_variateur
  const avecPompes = (surcharge) => ({ ...RESULTAT, pompes_variateur: { ...POMPES, ...surcharge } })

  it('saisie : ajouter, retirer, choisir le mode ; un kW vide n’est jamais envoyé', () => {
    pompage.mockResolvedValue({ data: RESULTAT })
    rendre()
    const ajouter = screen.getByRole('button', { name: 'Ajouter une pompe' })
    fireEvent.click(ajouter)
    fireEvent.click(ajouter)
    fireEvent.click(ajouter)
    fireEvent.change(screen.getByLabelText('Nom de la pompe 1'), { target: { value: 'Secteur A' } })
    fireEvent.change(screen.getByLabelText('kW de plaque de la pompe 1'), { target: { value: '1.1' } })
    fireEvent.change(screen.getByLabelText('kW de plaque de la pompe 2'), { target: { value: '1.1' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Retirer' })[2])
    expect(screen.queryByLabelText('kW de plaque de la pompe 3')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'À tour de rôle' }))
    calculer()
    expect(pompage.mock.calls[0][1]).toEqual({
      pompes_variateur: [{ nom: 'Secteur A', kw: '1.1' }, { kw: '1.1' }],
      mode_pompes: 'a_tour_de_role',
    })
  })

  it('conforme : « 4,4 kW demandés sur 5,5 kW : conforme »', async () => {
    pompage.mockResolvedValue({ data: RESULTAT })
    rendre()
    calculer()
    expect(await screen.findByTestId('cal-pompage-pompes'))
      .toHaveTextContent('4,4 kW demandés sur 5,5 kW : conforme')
  })

  it('dépasse : « 6,6 kW demandés sur 5,5 kW : le variateur est trop petit »', async () => {
    pompage.mockResolvedValue({ data: avecPompes({ verdict: 'depasse', kw_demande: 6.6, marge_kw: -1.1,
      motif: '6.6 kW de pompes au-dessus des 5.5 kW du variateur' }) })
    rendre()
    calculer()
    const ligne = await screen.findByTestId('cal-pompage-pompes')
    expect(ligne).toHaveTextContent('6,6 kW demandés sur 5,5 kW : le variateur est trop petit')
    expect(ligne).not.toHaveTextContent(': conforme')
  })

  it('non vérifiable : « À vérifier » ; sans liste, la ligne est absente', async () => {
    pompage.mockResolvedValue({ data: avecPompes({ verdict: 'non_verifiable', kw_demande: null,
      kw_variateur: null, marge_kw: null, motif: 'mode de marche non saisi (ensemble ou à tour de rôle)' }) })
    rendre()
    calculer()
    const ligne = await screen.findByTestId('cal-pompage-pompes')
    expect(ligne).toHaveTextContent('À vérifier : kW de plaque ou mode non saisi')
    expect(ligne).toHaveTextContent('mode de marche non saisi')
    cleanup()
    pompage.mockResolvedValue({ data: RESULTAT_VIDE })
    rendre()
    calculer()
    await screen.findByTestId('cal-pompage-hmt')
    expect(screen.queryByTestId('cal-pompage-pompes')).toBeNull()
  })
})

describe('ACAL820 — appoint réseau ou groupe sur le bus DC du variateur', () => {
  const APPOINT = RESULTAT.appoint_variateur
  const avecAppoint = (surcharge) => ({ ...RESULTAT, appoint_variateur: { ...APPOINT, ...surcharge } })

  it('le choix « Réseau » part dans le corps ; « Pas d’appoint » ne l’envoie pas', () => {
    pompage.mockResolvedValue({ data: RESULTAT })
    rendre()
    fireEvent.click(screen.getByRole('button', { name: 'Réseau' }))
    calculer()
    expect(pompage.mock.calls[0][1]).toEqual({ appoint: 'reseau' })
    fireEvent.click(screen.getByRole('button', { name: 'Pas d’appoint' }))
    calculer()
    expect(pompage.mock.calls[1][1]).toEqual({})
  })

  it('vmp_sous_bus (exemple du contrat) : le champ ne passe pas au-dessus du bus, en rouge', async () => {
    pompage.mockResolvedValue({ data: RESULTAT })
    rendre()
    calculer()
    const ligne = await screen.findByTestId('cal-pompage-appoint')
    expect(ligne).toHaveTextContent('Appoint : le variateur est alimenté par le réseau ou un groupe en plus des panneaux')
    expect(ligne).toHaveTextContent('Le champ ne passe pas au-dessus du bus : l’appoint fait tout le travail')
    expect(ligne).not.toHaveTextContent('Conforme')
    expect(ligne.className).toContain('text-red-300')
  })

  it('sans tension redressée publiée : la ligne nomme la fiche à compléter ; sans appoint : absente', async () => {
    pompage.mockResolvedValue({ data: avecAppoint({ verdict: 'non_verifiable', vmp_chaud_v: null,
      motif: 'tension redressée du bus DC non publiée (var_bus_dc_redresse_v)' }) })
    rendre()
    calculer()
    expect(await screen.findByTestId('cal-pompage-appoint'))
      .toHaveTextContent('À vérifier : tension redressée du bus non publiée sur la fiche du variateur')
    cleanup()
    pompage.mockResolvedValue({ data: RESULTAT_VIDE })
    rendre()
    calculer()
    await screen.findByTestId('cal-pompage-hmt')
    expect(screen.queryByTestId('cal-pompage-appoint')).toBeNull()
  })
})

describe('AGR125 — la HMT calculée comme au devis (pertes singulières, pression)', () => {
  it('les champs sont vides par défaut et en step="any"', () => {
    rendre()
    for (const re of [/Pertes singulières/, /Pression de service/]) {
      const champ = screen.getByLabelText(re)
      expect(champ).toHaveValue(null)
      expect(champ).toHaveAttribute('step', 'any')
    }
  })

  it('envoie pertes_singulieres_m et pression_service_bar tapés, tels quels', () => {
    pompage.mockResolvedValue({ data: RESULTAT })
    rendre()
    fireEvent.change(screen.getByLabelText(/Pertes singulières/), { target: { value: '1.35' } })
    fireEvent.change(screen.getByLabelText(/Pression de service/), { target: { value: '2.5' } })
    calculer()
    expect(pompage).toHaveBeenCalledWith(1, expect.objectContaining({
      pertes_singulieres_m: '1.35', pression_service_bar: '2.5',
    }))
  })

  it('n’envoie PAS un champ resté vide (aucun défaut inventé)', () => {
    pompage.mockResolvedValue({ data: RESULTAT })
    rendre()
    fireEvent.change(screen.getByLabelText(/Débit souhaité/), { target: { value: '8' } })
    calculer()
    const corps = pompage.mock.calls[0][1]
    expect(corps).toEqual({ debit_souhaite_m3h: '8' })
    expect(corps).not.toHaveProperty('pertes_singulieres_m')
    expect(corps).not.toHaveProperty('pression_service_bar')
  })

  it('affiche le message « manquant » du serveur sous le champ HMT et dans le bandeau', async () => {
    const manquant = 'Renseignez la HMT, ou toutes ses composantes pour qu’elle soit '
      + 'calculée comme au devis — manquant : pertes singulières, pression de service.'
    pompage.mockResolvedValue({ data: { ...RESULTAT_VIDE, erreurs: { hmt_saisie: manquant } } })
    rendre()
    calculer()
    expect(await screen.findByTestId('cal-pompage-erreur-hmt_saisie'))
      .toHaveTextContent('manquant : pertes singulières, pression de service')
    expect(screen.getByTestId('cal-pompage-bandeau')).toBeInTheDocument()
  })
})