import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import ArbreHistorique, { entreeArbre } from './ArbreHistorique'

/* QJ-ARBRE — l'arbre « Historique en un coup d'œil » (colonne droite du Suivi
   commercial) : filtrage du bruit, jalons devis accentués, groupement par
   jour, précédence historique > chatter_recent, présentation pure (aucun
   réseau — tout vient des props). */

afterEach(cleanup)

const act = (kind, over = {}) => ({
  id: over.id ?? Math.floor(Math.random() * 1e9),
  kind,
  body: '',
  outcome: '',
  created_at: '2026-09-08T10:00:00+00:00',
  user_nom: 'Meryem',
  ...over,
})

describe('entreeArbre — filtrage et rendu par type (logique pure)', () => {
  it('garde appels/WhatsApp/e-mails/notes/jalons devis, avec badge de résultat', () => {
    expect(entreeArbre(act('appel', { outcome: 'joint' }))).toMatchObject({
      label: 'Appel', badge: 'Joint',
    })
    expect(entreeArbre(act('whatsapp'))).toMatchObject({ label: 'WhatsApp' })
    expect(entreeArbre(act('email', { outcome: 'refuse' }))).toMatchObject({
      label: 'E-mail', badge: 'Refus',
    })
    expect(entreeArbre(act('note', { body: 'Rappeler jeudi' }))).toMatchObject({
      label: 'Note', texte: 'Rappeler jeudi',
    })
    expect(entreeArbre(act('devis_sent'))).toMatchObject({
      label: 'Devis envoyé', accent: 'jalon',
    })
    expect(entreeArbre(act('devis_signed'))).toMatchObject({ accent: 'gagne' })
    expect(entreeArbre(act('devis_refused'))).toMatchObject({ accent: 'perdu' })
  })

  it('exclut le bruit : modifications de champ ordinaires, kinds inconnus', () => {
    expect(entreeArbre(act('modification', { field: 'telephone', old_value: 'a', new_value: 'b' }))).toBeNull()
    expect(entreeArbre(act('kind_inconnu'))).toBeNull()
    expect(entreeArbre(null)).toBeNull()
  })

  it("garde le SEUL champ qui raconte le parcours : l'étape funnel", () => {
    const stage = entreeArbre(act('modification', {
      field: 'stage', old_value: 'Nouveau', new_value: 'Devis envoyé',
    }))
    expect(stage).toMatchObject({ label: 'Étape', accent: 'jalon' })
    expect(stage.texte).toBe('Nouveau → Devis envoyé')
  })
})

describe('ArbreHistorique — rendu', () => {
  it('vide → message dédié, jamais un arbre fantôme', () => {
    render(<ArbreHistorique historique={[]} chatterRecent={[]} />)
    expect(screen.getByText("Historique en un coup d'œil")).toBeInTheDocument()
    expect(screen.getByText('Aucun échange enregistré pour l\'instant.')).toBeInTheDocument()
  })

  it('groupe par jour, ligne condensée avec badge, bruit filtré, compte juste', () => {
    // Heures de MIDI UTC : un décalage horaire local (CI UTC, poste UTC+1…)
    // ne peut jamais faire basculer une entrée sur le jour voisin (leçon
    // wall-clock #29 du catalogue CI).
    const historique = [
      act('appel', { id: 1, outcome: 'joint', body: 'Appel de suivi', created_at: '2026-09-08T12:00:00+00:00' }),
      act('modification', { id: 2, field: 'telephone', created_at: '2026-09-08T13:00:00+00:00' }),
      act('devis_opened', { id: 3, body: 'DEV-2026-001', created_at: '2026-09-07T12:00:00+00:00' }),
    ]
    render(<ArbreHistorique historique={historique} chatterRecent={[]} />)
    const arbre = screen.getByTestId('arbre-historique')
    expect(within(arbre).getByText('Appel')).toBeInTheDocument()
    expect(within(arbre).getByText('Joint')).toBeInTheDocument()
    expect(within(arbre).getByText('Devis ouvert')).toBeInTheDocument()
    // Le log de champ « telephone » est du bruit : absent, et le compteur ne
    // compte que les 2 lignes réellement montrées.
    expect(within(arbre).getByText('2')).toBeInTheDocument()
    // Deux groupes-jour distincts (8 puis 7 septembre).
    expect(arbre.querySelectorAll('.lw-arbre-jour').length).toBe(2)
  })

  it('repli chatter_recent quand historique est vide (précédence LW30/LW41)', () => {
    render(<ArbreHistorique
      historique={[]}
      chatterRecent={[act('whatsapp', { id: 9, body: 'Message envoyé' })]}
    />)
    expect(screen.getByText('WhatsApp')).toBeInTheDocument()
  })
})
