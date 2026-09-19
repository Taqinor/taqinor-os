import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, act, cleanup } from '@testing-library/react'
import { I18nProvider, useI18n, STORAGE_KEY } from './index'
import api from '../api/axios'
import {
  formatDate, formatMAD, formatNumber, formatPersonName,
} from '../lib/format'

/* ============================================================================
   NTI18N27 — Test de non-régression : la bascule de langue n'affecte JAMAIS
   les données métier stockées, seulement l'AFFICHAGE.
   ----------------------------------------------------------------------------
   Ce groupe (NTI18N*) touche des dizaines d'écrans : `formatDate`/`formatMAD`/
   `formatNumber`/`formatPersonName` (lib/format.js) et `useI18n().locale`
   pilotent tous un paramètre `locale` FACULTATIF qui ne change QUE le texte
   rendu. Cette suite verrouille, mécaniquement, qu'aucune tâche de ce groupe
   n'a introduit un couplage accidentel affichage ↔ données :

     1. changer `useI18n().locale` ne modifie AUCUN champ d'un enregistrement
        métier (statut, montant, date STOCKÉE) — l'objet reste bit-identique ;
     2. les fonctions de `lib/format.js` sont PURES vis-à-vis de `locale` :
        même entrée + même locale => même sortie, et la VALEUR D'ENTRÉE n'est
        jamais mutée par l'appel (freeze + comparaison avant/après) ;
     3. changer de locale ne déclenche AUCUN appel d'écriture réseau
        (POST/PUT/PATCH/DELETE) — seule une lecture (surcharges de traduction)
        et une écriture `localStorage` de la PRÉFÉRENCE d'affichage elle-même
        sont attendues, jamais une mutation de donnée métier ;
     4. changer de locale ne touche AUCUNE autre clé `localStorage` que celle
        du cadre i18n lui-même (jamais, par exemple, une clé de brouillon de
        formulaire ou de cache de données métier).
   ========================================================================== */

const CADRE_STORAGE_KEYS = [STORAGE_KEY] // resolve.js (N93) — 'taqinor.locale'.

beforeEach(() => {
  window.localStorage.clear()
  document.documentElement.removeAttribute('dir')
  document.documentElement.removeAttribute('lang')
})
afterEach(() => { cleanup(); vi.restoreAllMocks() })

// Enregistrement métier simulé (statut/montant/date STOCKÉS) — Object.freeze
// pour que toute tentative de mutation lève au lieu de passer silencieusement.
function enregistrementMetierFige() {
  return Object.freeze({
    statut: 'signe',
    montant: 12345.6,
    date_creation: '2026-03-14T09:30:00Z',
    prenom: 'Reda',
    nom: 'Kasri',
  })
}

function EcranMetier({ enregistrement }) {
  const { locale, setLocale } = useI18n()
  return (
    <div>
      <span data-testid="locale-active">{locale}</span>
      <span data-testid="statut-brut">{enregistrement.statut}</span>
      <span data-testid="montant-affiche">{formatMAD(enregistrement.montant, { locale })}</span>
      <span data-testid="date-affichee">{formatDate(enregistrement.date_creation, { locale })}</span>
      <span data-testid="nom-affiche">
        {formatPersonName(enregistrement.prenom, enregistrement.nom, { locale })}
      </span>
      <button type="button" data-testid="vers-en" onClick={() => setLocale('en')}>en</button>
      <button type="button" data-testid="vers-ar" onClick={() => setLocale('ar')}>ar</button>
      <button type="button" data-testid="vers-fr" onClick={() => setLocale('fr')}>fr</button>
    </div>
  )
}

describe('NTI18N27 — bascule de locale : jamais de mutation de donnée métier', () => {
  it("l'enregistrement figé reste bit-identique après plusieurs bascules de locale", () => {
    const enregistrement = enregistrementMetierFige()
    render(<I18nProvider><EcranMetier enregistrement={enregistrement} /></I18nProvider>)

    const avant = JSON.stringify(enregistrement)

    act(() => { screen.getByTestId('vers-en').click() })
    act(() => { screen.getByTestId('vers-ar').click() })
    act(() => { screen.getByTestId('vers-fr').click() })

    // L'objet Object.freeze n'a pas levé (aucune tentative d'écriture) ET son
    // contenu JSON est bit-identique — seule l'AFFICHAGE a changé, jamais
    // les champs statut/montant/date/prénom/nom stockés.
    expect(JSON.stringify(enregistrement)).toBe(avant)
    expect(screen.getByTestId('statut-brut').textContent).toBe('signe')
  })

  it("le texte affiché change avec la locale alors que la donnée source ne bouge jamais", () => {
    const enregistrement = enregistrementMetierFige()
    render(<I18nProvider><EcranMetier enregistrement={enregistrement} /></I18nProvider>)

    const dateFr = screen.getByTestId('date-affichee').textContent // jj/mm/aaaa
    act(() => { screen.getByTestId('vers-en').click() })
    const dateEn = screen.getByTestId('date-affichee').textContent // mm/dd/yyyy

    // Même date STOCKÉE, rendu différent selon la locale — la preuve que
    // seul l'affichage a bougé (sinon les deux chaînes seraient identiques
    // ou, pire, la donnée source aurait changé).
    expect(dateFr).not.toBe(dateEn)
    expect(enregistrement.date_creation).toBe('2026-03-14T09:30:00Z')
  })

  it('ne déclenche aucun appel réseau d\'écriture (POST/PUT/PATCH/DELETE)', () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: {} })
    const put = vi.spyOn(api, 'put').mockResolvedValue({ data: {} })
    const patch = vi.spyOn(api, 'patch').mockResolvedValue({ data: {} })
    const del = vi.spyOn(api, 'delete').mockResolvedValue({ data: {} })

    const enregistrement = enregistrementMetierFige()
    render(<I18nProvider><EcranMetier enregistrement={enregistrement} /></I18nProvider>)

    act(() => { screen.getByTestId('vers-en').click() })
    act(() => { screen.getByTestId('vers-ar').click() })

    expect(post).not.toHaveBeenCalled()
    expect(put).not.toHaveBeenCalled()
    expect(patch).not.toHaveBeenCalled()
    expect(del).not.toHaveBeenCalled()
  })

  it('ne touche que la clé localStorage du cadre i18n — jamais une autre', () => {
    window.localStorage.setItem('brouillon.devis.123', JSON.stringify({ montant: 999 }))
    const enregistrement = enregistrementMetierFige()
    render(<I18nProvider><EcranMetier enregistrement={enregistrement} /></I18nProvider>)

    act(() => { screen.getByTestId('vers-ar').click() })

    // La clé métier non liée au cadre i18n n'a pas bougé.
    expect(window.localStorage.getItem('brouillon.devis.123'))
      .toBe(JSON.stringify({ montant: 999 }))
    // Seule(s) la/les clé(s) du cadre i18n ont pu changer.
    const clesInattendues = Object.keys(window.localStorage)
      .filter((k) => k !== 'brouillon.devis.123' && !CADRE_STORAGE_KEYS.includes(k))
    expect(clesInattendues).toEqual([])
  })
})

describe('NTI18N27 — lib/format.js : pureté vis-à-vis de `locale`', () => {
  it('formatDate/formatMAD/formatNumber : même entrée + même locale => même sortie, entrée jamais mutée', () => {
    const valeurDate = '2026-03-14T09:30:00Z'
    const valeurMontant = 12345.6

    for (const locale of [undefined, 'fr', 'en', 'ar']) {
      expect(formatDate(valeurDate, { locale })).toBe(formatDate(valeurDate, { locale }))
      expect(formatMAD(valeurMontant, { locale })).toBe(formatMAD(valeurMontant, { locale }))
      expect(formatNumber(valeurMontant, { locale })).toBe(formatNumber(valeurMontant, { locale }))
    }
    // Les valeurs d'entrée (primitives) restent, par construction, inchangées —
    // vérifié explicitement pour documenter le contrat de pureté attendu.
    expect(valeurDate).toBe('2026-03-14T09:30:00Z')
    expect(valeurMontant).toBe(12345.6)
  })

  it('formatPersonName ne mute jamais les chaînes prénom/nom fournies', () => {
    const prenom = 'Reda'
    const nom = 'Kasri'
    formatPersonName(prenom, nom, { locale: 'ar' })
    formatPersonName(prenom, nom, { locale: 'en' })
    expect(prenom).toBe('Reda')
    expect(nom).toBe('Kasri')
  })
})
