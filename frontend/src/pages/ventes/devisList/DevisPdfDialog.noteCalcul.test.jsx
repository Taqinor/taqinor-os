// AMOT68 (C-AMOT-058) — la note de calcul FDA (AGR319) se demande depuis le
// dialogue PDF d'un devis agricole : case « Joindre la note de calcul », et
// le corps envoyé à `generer-pdf` porte `include_note_calcul`. Test-du-test :
// retirer la clé de `optionsPdfDepuisModale` ⇒ le test du corps échoue.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import DevisPdfDialog from './DevisPdfDialog.jsx'
import { optionsPdfDepuisModale } from './useDevisPdf.js'

afterEach(cleanup)

const ETAT = {
  pdfMode: 'full', showMonthly: true, devisFinal: false, includeEtude: false,
  includeCalepinage: 'auto', includeNoteCalcul: true,
}

function dialogue(props) {
  return render(
    <DevisPdfDialog
      pdfTarget={{ id: 1, reference: 'DEV-AGR-1', mode_installation: 'agricole' }}
      batchPdf={false} selectedIds={[]}
      pdfMode="full" setPdfMode={vi.fn()} pdfModeAutoOnepage={false}
      targetIsAgricole showMonthly setShowMonthly={vi.fn()}
      targetHasEtude={false} targetIsCi={false} targetMode="agricole"
      includeEtude={false} setIncludeEtude={vi.fn()}
      includeCalepinage="auto" setIncludeCalepinage={vi.fn()}
      includeNoteCalcul={false} setIncludeNoteCalcul={vi.fn()}
      devisFinal={false} setDevisFinal={vi.fn()}
      paymentMode="standard" setPaymentMode={vi.fn()}
      customAcompte="" setCustomAcompte={vi.fn()}
      onClose={vi.fn()} onGenererLot={vi.fn()} onGenererUn={vi.fn()}
      {...props}
    />,
  )
}

describe('AMOT68 — note de calcul FDA demandable', () => {
  it('la case est offerte pour un devis agricole et pose l’état', () => {
    const setIncludeNoteCalcul = vi.fn()
    dialogue({ setIncludeNoteCalcul })
    const caseNote = screen.getByRole('checkbox', { name: /note de calcul/i })
    fireEvent.click(caseNote)
    expect(setIncludeNoteCalcul).toHaveBeenCalledWith(true)
  })

  it('aucune case hors agricole', () => {
    dialogue({ targetIsAgricole: false, targetMode: 'residentiel' })
    expect(screen.queryByRole('checkbox', { name: /note de calcul/i })).toBeNull()
  })

  it('le corps envoyé porte include_note_calcul pour un agricole', () => {
    const agricole = { mode_installation: 'agricole' }
    expect(optionsPdfDepuisModale(ETAT, agricole).include_note_calcul).toBe(true)
    expect(optionsPdfDepuisModale({ ...ETAT, includeNoteCalcul: false }, agricole)
      .include_note_calcul).toBe(false)
    expect(optionsPdfDepuisModale({ ...ETAT, pdfMode: 'onepage' }, agricole)
      .include_note_calcul).toBe(false)
  })

  it('hors agricole, le corps reste celui d’avant (aucune clé ajoutée)', () => {
    const corps = optionsPdfDepuisModale(ETAT, { mode_installation: 'residentiel' })
    expect(corps).not.toHaveProperty('include_note_calcul')
    expect(Object.keys(corps).sort()).toEqual(
      ['devis_final', 'include_calepinage', 'include_etude', 'pdf_mode', 'show_monthly'])
  })
})
