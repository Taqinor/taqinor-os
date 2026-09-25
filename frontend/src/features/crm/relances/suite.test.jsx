// CAD17 — la suite annoncée d'une réponse vient du SERVEUR (`etape.suites`,
// dérivée du moteur), jamais d'une phrase écrite par cadence à l'écran.
//
// Les touches de départ sont celles du contrat COMMITTÉ `relance_etape_v2.json`
// (PACT10) : la première est un appel de prise de contact (ordre 2), la
// seconde un WhatsApp du suivi de proposition portant un devis. Le test back
// jumeau (`apps/crm/tests_cad17_parite_promesse_effet.py`) AFFIRME ce même
// exemple et rejoue chaque réponse de chaque cadence pour vérifier l'effet de
// chaque code annoncé.
import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import PHRASES from './suite_phrases.json'
import {
  CLE_SANS_ISSUE, cleSuite, codesConnus, codesSuite, phraseEffet, suiteAnnoncee,
} from './suite'
import RelanceEtapeRow from './RelanceEtapeRow'

const [ETAPE_APPEL, ETAPE_APRES_DEVIS] = exempleContrat('crm', 'relance_etape_v2').results

afterEach(() => { cleanup() })

function noop() {}

function ouvrirFait(etape) {
  render(
    <RelanceEtapeRow etape={etape} onFait={noop} onSauter={noop} onReporter={noop}
      onOuvrirMessage={noop} />,
  )
  fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
}

describe('CAD17 suite.js — traduire les codes du serveur, rien de plus', () => {
  it('chaque code annoncé par le contrat committé a SA phrase (aucun code muet)', () => {
    const connus = new Set(codesConnus())
    for (const etape of [ETAPE_APPEL, ETAPE_APRES_DEVIS]) {
      for (const codes of Object.values(etape.suites)) {
        for (const code of codes) expect(connus.has(code), code).toBe(true)
      }
    }
  })

  // VISCAD6-B (fondateur 24/09/2026) — « un débrief de visite sans réponse ne
  // parque plus le lead au Froid » : le SERVEUR ne sert plus le code
  // `visite_froid_si_seule` (retiré de `CODES`, `apps/crm/suite_touche.py`),
  // remplacé par les codes EXISTANTS `etape_dernier_appel` /
  // `suite_si_plus_rien_ouvert` — déjà traduits ci-dessus, aucune phrase à
  // ajouter. L'écran ne porte plus la sienne. Cette moitié ÉCRAN ne peut pas
  // lire le contrat serveur mis à jour (la lane serveur tourne en parallèle,
  // hors périmètre de ce worktree) : le test reste donc VERT que le contrat
  // committé serve encore l'ancien code (transition) ou non — jamais une
  // liste de codes recopiée en dur pour comparaison stricte.
  it('`visite_froid_si_seule` a disparu de l’écran (le serveur ne l’émet plus)', () => {
    const connus = new Set(codesConnus())
    expect(connus.has('visite_froid_si_seule')).toBe(false)
    expect(phraseEffet('visite_froid_si_seule')).toBe('')
    // Les remplaçants annoncés par la décision fondateur sont des codes
    // EXISTANTS : rien à ajouter côté écran.
    expect(connus.has('etape_dernier_appel')).toBe(true)
    expect(connus.has('suite_si_plus_rien_ouvert')).toBe(true)
  })

  it('un code que l’écran ne connaît plus n’invente aucune phrase (dégradation silencieuse, jamais un mensonge)', () => {
    const etape = { ...ETAPE_APPEL, suites: { non_joint: ['visite_froid_si_seule'] } }
    expect(suiteAnnoncee(etape, { outcome: 'non_joint' })).toBe('')
  })

  it('chaque phrase est non vide, unique, et ne contient aucun chiffre (zéro chiffre inventé)', () => {
    const phrases = Object.values(PHRASES.effets)
    expect(phrases.length).toBeGreaterThan(0)
    expect(new Set(phrases).size).toBe(phrases.length)
    for (const phrase of phrases) {
      expect(phrase.trim().length).toBeGreaterThan(0)
      expect(phrase).not.toMatch(/\d/)
    }
  })

  it('la clé de suite : la réponse du client, sinon l’issue, « aucune issue » = sans_issue', () => {
    expect(cleSuite({ reponse: 'plus_tard', outcome: 'rappel' })).toBe('plus_tard')
    expect(cleSuite({ outcome: 'non_joint', note: 'Répondeur' })).toBe('non_joint')
    expect(cleSuite({ outcome: '' })).toBe(CLE_SANS_ISSUE)
    // L'issue historique `interesse` a exactement l'effet moteur de `joint`
    // (le journal d'appel de la fiche la propose encore).
    expect(cleSuite({ outcome: 'interesse' })).toBe('joint')
    expect(cleSuite(null)).toBeNull()
  })

  it('la phrase = les phrases des codes, dans l’ordre du serveur, puis la précision d’écran', () => {
    const reponse = { outcome: 'refuse', precision: 'Geste d’écran.' }
    expect(suiteAnnoncee(ETAPE_APPEL, reponse)).toBe(
      [...ETAPE_APPEL.suites.refuse.map(phraseEffet), 'Geste d’écran.'].join(' '))
  })

  it('sans `suites` (touche traitée, ancienne réponse) : AUCUNE phrase inventée', () => {
    const etape = { ...ETAPE_APPEL, suites: {} }
    expect(codesSuite(etape, { outcome: 'joint' })).toEqual([])
    expect(suiteAnnoncee(etape, { outcome: 'joint' })).toBe('')
    expect(suiteAnnoncee({ ...ETAPE_APPEL, suites: undefined }, { outcome: 'joint' })).toBe('')
  })
})

describe('CAD17 RelanceEtapeRow — le panneau « Fait » affiche la suite DU SERVEUR', () => {
  it('« Client joint » sur l’appel d’ouverture : la phrase des codes servis, mot pour mot', () => {
    ouvrirFait(ETAPE_APPEL)
    fireEvent.click(screen.getByRole('button', { name: 'Client joint' }))
    expect(screen.getByTestId('suite-reponse')).toHaveTextContent(
      ETAPE_APPEL.suites.joint.map(phraseEffet).join(' '))
  })

  it('la même réponse change de phrase quand le SERVEUR annonce une autre suite (rang, libellé)', () => {
    // Même cadence, même réponse — mais la touche est la dernière : le
    // serveur annonce le parking Froid, l'écran le dit (plus de promesse
    // « la cadence continue » écrite par cadence).
    const derniere = {
      ...ETAPE_APPEL, ordre: 11,
      suites: { ...ETAPE_APPEL.suites, non_joint: ['derniere_froid_reveils'] },
    }
    ouvrirFait(derniere)
    fireEvent.click(screen.getByRole('button', { name: 'Pas de réponse' }))
    expect(screen.getByTestId('suite-reponse'))
      .toHaveTextContent(phraseEffet('derniere_froid_reveils'))
    expect(screen.getByTestId('suite-reponse'))
      .not.toHaveTextContent(phraseEffet('touche_suivante'))
  })

  it('Répondeur / Occupé annoncent la suite de « non_joint » (même issue serveur)', () => {
    ouvrirFait(ETAPE_APPEL)
    fireEvent.click(screen.getByRole('button', { name: 'Répondeur' }))
    expect(screen.getByTestId('suite-reponse')).toHaveTextContent(
      ETAPE_APPEL.suites.non_joint.map(phraseEffet).join(' '))
  })

  it('une réponse du client (CAD-A) lit SA clé : « Plus tard » annonce la veille', () => {
    ouvrirFait(ETAPE_APRES_DEVIS)
    fireEvent.click(screen.getByRole('button', { name: 'Plus tard — pas maintenant' }))
    expect(screen.getByTestId('suite-reponse'))
      .toHaveTextContent(phraseEffet('veille_meme_touche'))
  })

  it('une touche sans `suites` n’annonce rien plutôt qu’une suite fausse', () => {
    ouvrirFait({ ...ETAPE_APPEL, suites: {} })
    fireEvent.click(screen.getByRole('button', { name: 'Pas de réponse' }))
    expect(screen.getByTestId('suite-reponse')).toHaveTextContent(/^$/)
  })
})
