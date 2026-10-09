import { useState } from 'react'
import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

vi.mock('../../lib/monitoring', () => ({
  isMonitoringEnabled: () => false,
  initMonitoring: () => Promise.resolve(false),
  captureException: () => {},
  bindCompany: () => {},
}))

import SocieteSection from './SocieteSection'
import { diffProfilePayload } from './peConstants'
import { FORM_VIDE } from '../../test/societeSectionHarness'

/* APDF22 (D-APDF-1) — l'administrateur saisit capital social + forme juridique
   dans Paramètres › Société, enregistre, et les retrouve après rechargement.

   CONTRAT PARTAGÉ (PACT10) : le faux serveur en mémoire est initialisé depuis
   `apps/parametres/contract_samples/company_identite_legale.json` (APDF21), jamais
   depuis une forme inventée. Le PATCH doit n'envoyer QUE les clés du contrat.
   Test-du-test : retirer les champs du payload ⇒ la relecture du faux serveur
   garde l'ancienne valeur et le test échoue. */

const ici = dirname(fileURLToPath(import.meta.url))
const CONTRAT = JSON.parse(readFileSync(join(
  ici, '..', '..', '..', '..', 'backend', 'django_core', 'apps', 'parametres',
  'contract_samples', 'company_identite_legale.json'), 'utf8'))
const CLES = Object.keys(CONTRAT.exemple)

// Faux serveur en mémoire : démarre VIDE pour ces clés (profil neuf).
function creerServeur() {
  const profil = { ...FORM_VIDE }
  for (const cle of CLES) profil[cle] = ''
  return {
    profil,
    get: () => ({ ...profil }),
    patch: (diff) => { Object.assign(profil, diff) },
  }
}

// Hôte minimal qui reproduit le rôle du parent : état du formulaire, diff, PATCH.
function Hote({ serveur, patchs }) {
  const lu = serveur.get()
  const [base, setBase] = useState(lu)
  const [form, setForm] = useState(lu)
  const set = (e) => setForm((p) => ({ ...p, [e.target.name]: e.target.value }))
  const enregistrer = () => {
    const diff = diffProfilePayload(base, form)
    patchs.push(diff)
    serveur.patch(diff)
    setBase(form)
  }
  const store = configureStore({
    reducer: {
      parametres: (s = { error: null }) => s,
      auth: (s = { user: { company_est_demo: false } }) => s,
    },
  })
  return (
    <Provider store={store}>
      <SocieteSection
        accent="#1d4ed8" profile={null} form={form} set={set}
        uploading={false} dispatch={() => {}}
      />
      <button type="button" onClick={enregistrer}>Enregistrer</button>
    </Provider>
  )
}

describe('APDF22 — identité légale dans Paramètres › Société', () => {
  afterEach(cleanup)

  it('saisir, enregistrer (clés du contrat seulement), recharger : valeurs conservées', () => {
    const serveur = creerServeur()
    const patchs = []
    const { unmount } = render(<Hote serveur={serveur} patchs={patchs} />)

    fireEvent.change(screen.getByLabelText('Capital social'), {
      target: { name: 'capital_social', value: '100 000,00 MAD' } })
    fireEvent.change(screen.getByLabelText('Forme juridique'), {
      target: { name: 'forme_juridique', value: 'SARLAU' } })
    fireEvent.click(screen.getByText('Enregistrer'))

    expect(patchs).toHaveLength(1)
    expect(Object.keys(patchs[0]).sort()).toEqual([...CLES].sort())
    expect(serveur.profil.capital_social).toBe('100 000,00 MAD')
    expect(serveur.profil.forme_juridique).toBe('SARLAU')

    // Rechargement : nouvel hôte, relu depuis le faux serveur.
    unmount()
    render(<Hote serveur={serveur} patchs={[]} />)
    expect(screen.getByLabelText('Capital social')).toHaveValue('100 000,00 MAD')
    expect(screen.getByLabelText('Forme juridique')).toHaveValue('SARLAU')
  })

  it('le contrat liste exactement capital_social et forme_juridique', () => {
    expect([...CLES].sort()).toEqual(['capital_social', 'forme_juridique'])
  })
})
