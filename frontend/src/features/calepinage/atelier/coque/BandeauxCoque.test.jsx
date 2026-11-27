/* Nouveau fichier car : BandeauxCoque.jsx n'avait aucun module de test voisin (ACAL1980).
   Le script du constructeur ne tourne pas sous vitest : le noeud qu'il écrit (`#rp9-pan-module-erreur`, marqué
   `data-ton="a-regler"` par zones.ts::direRefusModule) est posé à la main, comme il l'écrit ; la bande est jugée sur
   ce qu'elle LIT et CLIQUE. */
import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, act, fireEvent } from '@testing-library/react'
import { BandeauAlertes } from './BandeauxCoque'

const MOTIF = 'Zone 1 : le module « Module 715 W » ne figure plus dans le catalogue de la société — rechargez le catalogue, ou choisissez un module de la liste.'

function monter(etape = 'electrique') {
  const surEtape = vi.fn()
  const r = render(
    <div className="cal-coque" data-etape={etape}>
      <BandeauAlertes />
      <button type="button" data-testid="cal-etape-panneaux" onClick={surEtape}>Panneaux</button>
      <p id="rp9-pan-module-erreur" role="alert" hidden />
    </div>)
  const noeud = r.container.querySelector('#rp9-pan-module-erreur')
  const ecrire = (motif, ton = 'a-regler') => act(async () => {
    noeud.textContent = motif
    noeud.hidden = !motif
    if (motif && ton) { noeud.dataset.ton = ton; noeud.dataset.code = 'module-absent' } else { delete noeud.dataset.ton; delete noeud.dataset.code }
    await Promise.resolve()
  })
  return { ...r, ecrire, surEtape }
}

afterEach(cleanup)

describe('BandeauAlertes — « module absent du catalogue » au ton « À régler » (ACAL1980)', () => {
  it('étape Électrique : le motif posé par le script s’affiche dans la bande, avec « À régler » et le lien de réparation', async () => {
    const t = monter('electrique')
    expect(screen.queryByTestId('cal-a-regler-module')).toBeNull()
    await t.ecrire(MOTIF)
    const ligne = screen.getByTestId('cal-a-regler-module')
    expect(ligne.textContent).toContain('À régler')
    expect(ligne.textContent).toContain(MOTIF)
    fireEvent.click(screen.getByRole('button', { name: /choisir un module/i }))
    expect(t.surEtape).toHaveBeenCalledTimes(1) // mène à l'étape Panneaux, où se choisit le module
  })

  it('le motif disparaît quand le script le retire (le module est revenu au catalogue)', async () => {
    const t = monter('electrique')
    await t.ecrire(MOTIF)
    expect(screen.getByTestId('cal-a-regler-module')).toBeTruthy()
    await t.ecrire('')
    expect(screen.queryByTestId('cal-a-regler-module')).toBeNull()
  })

  it('un refus sans le marqueur « À régler » (refus d’un geste) n’est pas répété dans la bande', async () => {
    const t = monter('electrique')
    await t.ecrire('Zone 1 : ce module est grisé.', null)
    expect(screen.queryByTestId('cal-a-regler-module')).toBeNull()
  })

  it('étape Panneaux : le sélecteur porte déjà le motif, la bande ne le répète pas', async () => {
    const t = monter('panneaux')
    await t.ecrire(MOTIF)
    expect(screen.queryByTestId('cal-a-regler-module')).toBeNull()
  })
})
