/* VT13 (fondateur 10/09/2026) — LA PHOTO RÉELLE DU TOIT DANS L'ERP.
   ---------------------------------------------------------------------------
   Ce que ce fichier garde :

   * la FORME du serveur est celle du contrat VT12
     (`apps/crm/contract_samples/lead_photo_toit.json`) : `{visite_id, url,
     texture_calage}`, ses trois clés à null quand il n'y a rien à montrer.
     Les mocks ci-dessous la reproduisent EXACTEMENT (garde
     `scripts/check_api_shapes.py` : un mock qui diverge du serveur est un
     écran mort en production) ;
   * l'overlay APPARAÎT quand une texture calée existe, et RIEN ne s'affiche
     quand la réponse est nulle — jamais un cadre vide ni une image posée à
     l'estime (règle « zéro chiffre/objet inventé ») ;
   * la bascule « Photo réelle » masque bien la photo.

   Le canvas est rendu tel quel : jsdom ne fournit pas de contexte 2D, le
   composant le sait (`if (!ctx) return`) et n'échoue jamais dessus — c'est le
   drapage lui-même (`roofTextureWarp.js`) qui est testé côté maths, en VT10. */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('../../../api/crmApi', () => ({
  default: { getLeadPhotoToit: vi.fn() },
}))

import crmApi from '../../../api/crmApi'
import PhotoToitOverlay from './PhotoToitOverlay'
import { normaliserTextureToit, quadPhotoToit } from './photoToit'
import { dessinerContour } from './traceToit'
import TraceToitClient from './sections/TraceToitClient'

afterEach(() => { cleanup(); vi.clearAllMocks() })

// Carré ≈ 20 m de côté à Casablanca — même ordre d'axes que Lead.roof_outline.
const CONTOUR = [
  [33.589, -7.603],
  [33.589, -7.602784],
  [33.58918, -7.602784],
  [33.58918, -7.603],
]

// LA FORME DU SERVEUR, telle quelle (contrat VT12).
const REPONSE_AVEC_PHOTO = {
  visite_id: 7,
  url: '/api/django/crm/visites/7/photo-toit/',
  texture_calage: {
    coins: [
      [33.589, -7.603],
      [33.589, -7.602784],
      [33.58918, -7.602784],
      [33.58918, -7.603],
    ],
  },
}

const REPONSE_VIDE = { visite_id: null, url: null, texture_calage: null }

describe('normaliserTextureToit — la forme du contrat VT12', () => {
  it('accepte la réponse complète et en tire url + 4 coins', () => {
    const texture = normaliserTextureToit(REPONSE_AVEC_PHOTO)
    expect(texture).toBeTruthy()
    expect(texture.visiteId).toBe(7)
    expect(texture.url).toBe('/api/django/crm/visites/7/photo-toit/')
    expect(texture.coins).toHaveLength(4)
  })

  it('rend null sur la réponse à trois clés nulles (absence, pas erreur)', () => {
    expect(normaliserTextureToit(REPONSE_VIDE)).toBeNull()
  })

  it('refuse un calage qui n’a pas exactement 4 coins plausibles', () => {
    expect(normaliserTextureToit({
      ...REPONSE_AVEC_PHOTO, texture_calage: { coins: [[33.5, -7.6]] },
    })).toBeNull()
    expect(normaliserTextureToit({
      ...REPONSE_AVEC_PHOTO,
      texture_calage: { coins: [[999, -7.6], [33.5, -7.6], [33.5, -7.5], [33.6, -7.5]] },
    })).toBeNull()
    // Une url absente ne drape rien non plus.
    expect(normaliserTextureToit({ ...REPONSE_AVEC_PHOTO, url: null })).toBeNull()
  })
})

describe('quadPhotoToit — le quadrilatère de drapage', () => {
  it('projette les 4 coins dans le repère du contour (donc SOUS le tracé)', () => {
    const dessin = dessinerContour(CONTOUR)
    const cadre = quadPhotoToit(dessin, REPONSE_AVEC_PHOTO.texture_calage.coins)
    expect(cadre).toBeTruthy()
    expect(cadre.quad).toHaveLength(4)
    // Les coins du calage sont ceux du contour : le quad doit couvrir la même
    // emprise que le dessin (à l'unité de viewBox près).
    const xs = cadre.quad.map((p) => p[0])
    const ys = cadre.quad.map((p) => p[1])
    expect(Math.min(...xs)).toBeCloseTo(0, 1)
    expect(Math.max(...xs)).toBeCloseTo(dessin.largeur, 0)
    expect(Math.min(...ys)).toBeCloseTo(0, 1)
    expect(Math.max(...ys)).toBeCloseTo(dessin.hauteur, 0)
  })

  it('sait bâtir son propre cadre quand le lead n’a aucun contour tracé', () => {
    const cadre = quadPhotoToit(null, REPONSE_AVEC_PHOTO.texture_calage.coins)
    expect(cadre).toBeTruthy()
    expect(cadre.quad).toHaveLength(4)
    expect(cadre.largeur).toBeGreaterThan(0)
  })

  it('rend null sans coins exploitables', () => {
    expect(quadPhotoToit(dessinerContour(CONTOUR), null)).toBeNull()
    expect(quadPhotoToit(dessinerContour(CONTOUR), [[1, 2], [3, 4]])).toBeNull()
  })
})

describe('PhotoToitOverlay', () => {
  const dessin = () => dessinerContour(CONTOUR)

  it('affiche le calque quand une texture calée existe', () => {
    render(<PhotoToitOverlay dessin={dessin()} texture={normaliserTextureToit(REPONSE_AVEC_PHOTO)} />)
    const canvas = screen.getByTestId('photo-toit-overlay')
    expect(canvas.tagName.toLowerCase()).toBe('canvas')
    expect(canvas.getAttribute('data-visite-id')).toBe('7')
  })

  it('n’affiche RIEN sans texture (aucun cadre vide)', () => {
    render(<PhotoToitOverlay dessin={dessin()} texture={null} />)
    expect(screen.queryByTestId('photo-toit-overlay')).toBeNull()
  })

  it('n’affiche rien quand la bascule le masque', () => {
    render(
      <PhotoToitOverlay
        dessin={dessin()}
        texture={normaliserTextureToit(REPONSE_AVEC_PHOTO)}
        visible={false}
      />,
    )
    expect(screen.queryByTestId('photo-toit-overlay')).toBeNull()
  })
})

describe('TraceToitClient — la carte de la fiche lead lit la porte VT12', () => {
  it('drape la photo réelle sous le tracé, et la bascule la masque', async () => {
    crmApi.getLeadPhotoToit.mockResolvedValue({ data: REPONSE_AVEC_PHOTO })
    const user = userEvent.setup()
    render(<TraceToitClient contour={CONTOUR} epingle={null} leadId={118} />)

    await waitFor(() => expect(screen.getByTestId('photo-toit-overlay')).toBeTruthy())
    expect(crmApi.getLeadPhotoToit).toHaveBeenCalledWith(118)
    // Le contour du client reste dessiné PAR-DESSUS la photo.
    expect(document.querySelector('.lw-trace-toit-forme polygon')).toBeTruthy()

    await user.click(screen.getByTestId('lw-photo-toit-bascule'))
    expect(screen.queryByTestId('photo-toit-overlay')).toBeNull()
  })

  it('n’affiche ni photo ni bascule quand le serveur répond des clés nulles', async () => {
    crmApi.getLeadPhotoToit.mockResolvedValue({ data: REPONSE_VIDE })
    render(<TraceToitClient contour={CONTOUR} epingle={null} leadId={118} />)

    await waitFor(() => expect(crmApi.getLeadPhotoToit).toHaveBeenCalled())
    expect(screen.queryByTestId('photo-toit-overlay')).toBeNull()
    expect(screen.queryByTestId('lw-photo-toit-bascule')).toBeNull()
    // Le tracé du client, lui, reste affiché exactement comme avant VT13.
    expect(document.querySelector('.lw-trace-toit-forme polygon')).toBeTruthy()
  })

  it('n’appelle rien sans lead (fiche en création)', () => {
    render(<TraceToitClient contour={CONTOUR} epingle={null} />)
    expect(crmApi.getLeadPhotoToit).not.toHaveBeenCalled()
    expect(screen.queryByTestId('photo-toit-overlay')).toBeNull()
  })
})
