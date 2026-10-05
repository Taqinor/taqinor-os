import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { initState, dirtyKeys } from '../draftCore'
import fieldLabels from '../fieldLabels'
import { documentContrat } from '../../../../test/fixtures/contractSamples'
import SectionDivers from './SectionDivers'

/* AGR524 — fiche lead : l'état du dossier de subvention (FDA), contre le
   contrat partagé `lead_dossier_subvention.json` (check_api_shapes) : le mock
   est IMPORTÉ de l'échantillon, jamais inventé. */
vi.mock('../../../../components/CustomFieldsInput', () => ({ default: () => null }))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const contrat = documentContrat('crm', 'lead_dossier_subvention')
const base = { setField: vi.fn(), errors: {} }

const monter = (lead, props = {}) => render(
  <SectionDivers state={initState({ lead, mode: 'edit' })} {...base} {...props} />,
)

describe('AGR524 — Dossier de subvention sur la fiche lead', () => {
  it('lead agricole : les deux champs sont là, la liste = libellés du contrat', () => {
    monter({ id: 1512, type_installation: 'agricole', ...contrat.exemple_vide })
    const select = document.getElementById('lf-dossier-subvention')
    expect(select).toBeInTheDocument()
    expect(document.getElementById('lf-dossier-subvention-le')).toBeInTheDocument()
    const options = Array.from(select.options).filter((o) => o.value)
    expect(Object.fromEntries(options.map((o) => [o.value, o.textContent])))
      .toEqual(contrat.notes.libelles)
    // Entrées fieldLabels réelles (jamais `pending`).
    for (const cle of ['dossier_subvention', 'dossier_subvention_le']) {
      expect(fieldLabels[cle].pending).toBeUndefined()
      expect(document.getElementById(fieldLabels[cle].inputId)).toBeInTheDocument()
    }
  })

  it('une mention « interne, jamais montré au client » est visible', () => {
    monter({ id: 1512, type_installation: 'agricole', ...contrat.exemple_vide })
    expect(screen.getByTestId('dossier-subvention-interne').textContent)
      .toMatch(/interne.*jamais montrée au client/)
  })

  it('lead résidentiel sans valeur : champs absents', () => {
    monter({ id: 1388, type_installation: 'residentiel', ...contrat.exemple_vide })
    expect(document.getElementById('lf-dossier-subvention')).toBeNull()
    expect(document.getElementById('lf-dossier-subvention-le')).toBeNull()
  })

  it('lead non agricole avec une valeur existante : champs affichés', () => {
    monter({ id: 1388, type_installation: 'residentiel', ...contrat.exemple })
    expect(document.getElementById('lf-dossier-subvention').value).toBe('depose')
    expect(document.getElementById('lf-dossier-subvention-le').value).toBe('2026-10-20')
  })

  it('choisir « Déposé » sans date : le message serveur s’affiche SOUS la date', () => {
    const setField = vi.fn()
    const message = contrat.exemple_400.dossier_subvention_le[0]
    const lead = { id: 1512, type_installation: 'agricole', ...contrat.exemple_vide }
    const { rerender } = render(
      <SectionDivers state={initState({ lead, mode: 'edit' })} {...base} setField={setField} />,
    )
    fireEvent.change(document.getElementById('lf-dossier-subvention'), { target: { value: 'depose' } })
    expect(setField).toHaveBeenCalledWith('dossier_subvention', 'depose')
    // Le serveur refuse (400) : l'erreur est posée sur le champ fautif.
    rerender(
      <SectionDivers
        state={initState({ lead, mode: 'edit' })} {...base} setField={setField}
        errors={{ dossier_subvention_le: message }}
      />,
    )
    const date = document.getElementById('lf-dossier-subvention-le')
    expect(date).toHaveAttribute('aria-invalid', 'true')
    const alerte = document.getElementById('lf-dossier-subvention-le-error')
    expect(alerte).toHaveTextContent(message)
    // Le message est dans le MÊME bloc que le champ date (sous lui), pas ailleurs.
    expect(alerte.parentElement.contains(date)).toBe(true)
    // Et rien n'est reproché au champ « Dossier de subvention » lui-même.
    expect(document.getElementById('lf-dossier-subvention-error')).toBeNull()
  })

  it('enregistrer → rouvrir → enregistrer sans toucher : aucun écart avec le serveur', () => {
    const lead = { id: 1512, type_installation: 'agricole', ...contrat.exemple }
    const state = initState({ lead, mode: 'edit' })
    render(<SectionDivers state={state} {...base} />)
    const relu = {
      dossier_subvention: document.getElementById('lf-dossier-subvention').value,
      dossier_subvention_le: document.getElementById('lf-dossier-subvention-le').value,
    }
    expect(relu).toEqual(contrat.corps)
    expect(dirtyKeys({ ...state, draft: relu })).toEqual([])
    // L'état vide se relit vide (null ≡ '') : toujours aucune différence.
    cleanup()
    const vide = initState({ lead: { id: 1512, type_installation: 'agricole', ...contrat.exemple_vide }, mode: 'edit' })
    render(<SectionDivers state={vide} {...base} />)
    const releVide = {
      dossier_subvention: document.getElementById('lf-dossier-subvention').value,
      dossier_subvention_le: document.getElementById('lf-dossier-subvention-le').value,
    }
    expect(dirtyKeys({ ...vide, draft: releVide })).toEqual([])
  })
})
