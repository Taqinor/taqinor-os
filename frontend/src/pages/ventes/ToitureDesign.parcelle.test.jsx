import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import process from 'node:process'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

/* ACAL233 — le bouton « Parcelle » n'existe que dans le DOM COMPLET de l'atelier ERP
   (BuilderDom.jsx) ; la page publique /devis/mon-toit (captureOnly) ne le porte jamais. */

vi.mock('../../hooks/useHasPermission', () => ({ useHasPermission: () => false }))

import '../../test/toitureDesignHarnessCalepinage'
import {
  rendreCalepinage, reinitialiserBoot,
} from '../../test/toitureDesignHarness'
import calepinageApi from '../../api/calepinageApi'

const CTX = exempleContrat('calepinage', 'calepinage_design_context')

beforeEach(() => {
  vi.clearAllMocks()
  reinitialiserBoot()
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ToitureDesign — bouton Parcelle (ACAL233)', () => {
  it('le bouton Parcelle existe dans l’atelier ERP (boot complet)', async () => {
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    rendreCalepinage(CTX.calepinage.id)
    expect(await screen.findByRole('button', { name: 'Parcelle' })).toBeTruthy()
    expect(document.getElementById('rp9-parcelle')).not.toBeNull()
    // Rien à effacer tant qu'aucune parcelle n'est posée.
    expect(document.getElementById('rp9-parcelle-clear').hidden).toBe(true)
  })

  it('la page publique (captureOnly) ne porte jamais ce bouton', () => {
    for (const page of ['devis/mon-toit.astro', 'en/devis/mon-toit.astro', 'ar/devis/mon-toit.astro']) {
      expect(readFileSync(join(process.cwd(), '..', 'apps', 'web', 'src', 'pages', page), 'utf8')).not.toContain('rp9-parcelle')
    }
  })
})
