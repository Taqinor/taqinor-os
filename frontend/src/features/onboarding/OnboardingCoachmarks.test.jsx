import { describe, it, expect, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import OnboardingCoachmarks from './OnboardingCoachmarks'

/* VX247(a)/(b) — le tour de bienvenue (FG16) filtre désormais ses étapes par
   rôle (un compte Technicien ne doit jamais voir « Invitez votre équipe ») et
   se termine sur un rappel des raccourcis globaux (⌘K/Ctrl K, ?). */

function renderWith(role) {
  const store = configureStore({
    reducer: { auth: (s = { role }) => s },
  })
  return render(<Provider store={store}><OnboardingCoachmarks /></Provider>)
}

beforeEach(() => {
  try { window.localStorage.clear() } catch { /* noop */ }
})
afterEach(() => {
  cleanup()
  try { window.localStorage.clear() } catch { /* noop */ }
})

describe('VX247 — OnboardingCoachmarks : étapes filtrées par rôle', () => {
  it('le tour s’ouvre bien sur le message de bienvenue (commun à tous les rôles)', () => {
    renderWith('normal')
    expect(screen.getByText('Bienvenue sur TAQINOR OS')).toBeInTheDocument()
  })

  it('un rôle admin voit bien l’étape « Invitez votre équipe »', async () => {
    renderWith('admin')
    // Avance jusqu'à trouver l'étape équipe (admin-only) sans dépasser un
    // nombre de clics raisonnable — protège contre une boucle infinie si la
    // régression fait disparaître le bouton "Suivant".
    let found = false
    for (let i = 0; i < 8 && !found; i += 1) {
      if (screen.queryByText('Invitez votre équipe')) { found = true; break }
      const nextBtn = screen.queryByRole('button', { name: /Suivant/ })
      if (!nextBtn) break
      // `.click()` natif ne suffit pas ici : le clic est un événement discret
      // React 18 dont le flush n'est pas garanti synchrone hors `act()` —
      // `fireEvent.click` (qui enveloppe l'appel dans `act()`) fait avancer
      // l'étape de façon fiable avant l'assertion suivante.
      fireEvent.click(nextBtn)
    }
    expect(found).toBe(true)
  })

  it('un rôle "normal" ne rencontre jamais l’étape « Invitez votre équipe » en parcourant tout le tour', () => {
    renderWith('normal')
    for (let i = 0; i < 10; i += 1) {
      expect(screen.queryByText('Invitez votre équipe')).not.toBeInTheDocument()
      const nextBtn = screen.queryByRole('button', { name: /Suivant|Terminer/ })
      if (!nextBtn) break
      fireEvent.click(nextBtn)
    }
  })

  it('la dernière étape avant "Tout est prêt" mentionne les raccourcis (⌘K/Ctrl K et ?)', () => {
    renderWith('admin')
    for (let i = 0; i < 10; i += 1) {
      const body = screen.queryByText(/Ouvrir la recherche rapide/)
      if (body) {
        expect(screen.getByText(/\?/)).toBeInTheDocument()
        return
      }
      const nextBtn = screen.queryByRole('button', { name: /Suivant/ })
      if (!nextBtn) break
      fireEvent.click(nextBtn)
    }
    throw new Error('étape raccourcis jamais atteinte')
  })
})
