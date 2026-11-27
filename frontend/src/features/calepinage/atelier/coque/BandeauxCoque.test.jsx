/* Nouveau fichier car : BandeauxCoque.jsx n'avait aucun module de test voisin (ACAL1980).
   Le script du constructeur ne tourne pas sous vitest : le noeud qu'il écrit (`#rp9-pan-module-erreur`, marqué
   `data-ton="a-regler"` par zones.ts::direRefusModule) est posé à la main, comme il l'écrit ; la bande est jugée sur
   ce qu'elle LIT et CLIQUE. */
import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, act, fireEvent } from '@testing-library/react'
import { BandeauAlertes } from './BandeauxCoque'
import { publierLecturePret } from '../../commun/lecturePretAEnvoyer'

const relances = []
const MOTIF = 'Zone 1 : le module « Module 715 W » ne figure plus dans le catalogue de la société — rechargez le catalogue, ou choisissez un module de la liste.'

function monter(etape = 'electrique', id = null) {
  const surEtape = vi.fn()
  const r = render(
    <div className="cal-coque" data-etape={etape}>
      <BandeauAlertes calepinageId={id} />
      <button type="button" data-testid="cal-reessayer-lecture" onClick={() => relances.push(1)} hidden />
      <button type="button" data-testid="cal-etape-panneaux" onClick={surEtape}>Panneaux</button>
      <p id="rp9-pan-module-erreur" role="alert" hidden />
    </div>)
  const noeud = r.container.querySelector('#rp9-pan-module-erreur')
  const ecrire = (motif, ton = 'a-regler', code = 'module-absent') => act(async () => {
    noeud.textContent = motif
    noeud.hidden = !motif
    if (motif && ton) { noeud.dataset.ton = ton; noeud.dataset.code = code } else { delete noeud.dataset.ton; delete noeud.dataset.code }
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
    expect(ligne.textContent).not.toContain('À régler') // aucune lecture servie ne le compte : une information, pas un « À régler »
    expect(ligne.textContent).toContain('Module retiré du catalogue — choisissez-en un')
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

  it('la lecture servie liste le point (materiel_designe à régler) : « À régler » reste', async () => {
    publierLecturePret('77', null, [{ code: 'materiel_designe', etat: 'a_regler' }])
    const t = monter('electrique', '77')
    await t.ecrire(MOTIF)
    await act(async () => { await Promise.resolve() })
    expect(screen.getByTestId('cal-a-regler-module').textContent).toContain('À régler')
    publierLecturePret('77', null, [])
  })

  it('catalogue illisible : ni « À régler » ni « Choisir un module » ; le geste est « Réessayer »', async () => {
    const t = monter('electrique')
    await t.ecrire('Zone 1 : le catalogue des modules n’a pas pu être lu.', 'info', 'catalogue-illisible')
    const ligne = screen.getByTestId('cal-catalogue-illisible')
    expect(ligne.textContent).not.toContain('À régler')
    expect(screen.queryByRole('button', { name: /choisir un module/i })).toBeNull()
    relances.length = 0
    fireEvent.click(screen.getByRole('button', { name: /réessayer/i }))
    expect(relances).toHaveLength(1)
    expect(t.surEtape).not.toHaveBeenCalled()
  })
})
