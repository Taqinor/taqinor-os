import { describe, expect, it } from 'vitest'

import {
  accord, aujourdhuiIso, duree, echeanceTexte, ecartJours, heure, heureDite, jourCourt, jourLong, jourNomme,
} from './textes'

/* TCH46 — formats de texte de l'app Tâches : « jour », « heure », « durée », accords. Les sorties
   attendues viennent de `reference/textes.md` « Conventions d'écriture » (écrites ici à la main,
   jour de référence : mardi 17 novembre 2026). Le JUMEAU Python (`moteur/gabarits.py`, TCH30) doit
   donner les mêmes sorties sur les mêmes dates : à rejouer côté serveur quand TCH30 sera sur `main`
   (ce fichier n'existe pas encore dans ce lot, la comparaison mot pour mot n'est pas faite ici). */

const AUJOURDHUI = '2026-11-17'

// 10 dates : [date, attendu de jourCourt]
const DIX_DATES = [
  ['2026-11-17', "aujourd'hui"],
  ['2026-11-18', 'demain'],
  ['2026-11-19', 'jeu. 19'],
  ['2026-11-23', 'lun. 23'],
  ['2026-11-30', 'lun. 30'], // 13 jours : dans la fenêtre
  ['2026-12-01', 'mar. 1 déc.'], // 14 jours : au-delà
  ['2026-12-25', 'ven. 25 déc.'],
  ['2026-11-16', 'lun. 16/11'], // hier : passé
  ['2026-11-12', 'jeu. 12/11'],
  ['2027-01-04', '04/01/2027'], // autre année
]

describe('TCH46 — jours', () => {
  it.each(DIX_DATES)('jourCourt(%s) = « %s »', (iso, attendu) => {
    expect(jourCourt(iso, AUJOURDHUI)).toBe(attendu)
  })

  it('jourNomme ne dit jamais « aujourd\'hui » ni « demain » : « Reporter à lun. 23 », « → lun. 23 »', () => {
    expect(jourNomme('2026-11-18', AUJOURDHUI)).toBe('mer. 18')
    expect(jourNomme('2026-11-23', AUJOURDHUI)).toBe('lun. 23')
    expect(jourNomme('2026-12-01', AUJOURDHUI)).toBe('mar. 1 déc.')
  })

  it('jourLong : le jour au-dessus du titre, majuscule initiale', () => {
    expect(jourLong('2026-11-20')).toBe('Vendredi 20 novembre')
    expect(jourLong('2026-11-17')).toBe('Mardi 17 novembre')
    expect(jourLong('2026-12-01')).toBe('Mardi 1 décembre')
  })

  it('ecartJours compte en jours entiers, sans dérive d\'heure d\'été', () => {
    expect(ecartJours('2026-11-19', AUJOURDHUI)).toBe(2)
    expect(ecartJours('2026-11-16', AUJOURDHUI)).toBe(-1)
    expect(ecartJours('2026-03-30', '2026-03-28')).toBe(2)
    expect(ecartJours('pas une date', AUJOURDHUI)).toBeNull()
  })

  it('aujourdhuiIso suit le jour LOCAL de l\'appareil', () => {
    expect(aujourdhuiIso(new Date(2026, 10, 17, 23, 59))).toBe('2026-11-17')
    expect(aujourdhuiIso(new Date(2026, 0, 5, 0, 1))).toBe('2026-01-05')
  })

  it('une date vide ou invalide ne produit aucun texte', () => {
    expect(jourCourt(null, AUJOURDHUI)).toBe('')
    expect(jourCourt('', AUJOURDHUI)).toBe('')
    expect(echeanceTexte(null, AUJOURDHUI)).toBeNull()
  })
})

describe('TCH46 — heures et durées', () => {
  it('« 10:00 » sur une puce, « 10 h » / « 10 h 30 » dans une phrase lue', () => {
    expect(heure('10:00:00')).toBe('10:00')
    expect(heure('9:05')).toBe('09:05')
    expect(heure(null)).toBe('')
    expect(heureDite('10:00')).toBe('10 h')
    expect(heureDite('10:30')).toBe('10 h 30')
    expect(heureDite('09:05')).toBe('9 h 05')
  })

  it('« 45 min », « 1 h », « 3 h 10 » ; rien pour 0 ou null', () => {
    expect(duree(45)).toBe('45 min')
    expect(duree(60)).toBe('1 h')
    expect(duree(190)).toBe('3 h 10')
    expect(duree(0)).toBe('')
    expect(duree(null)).toBe('')
  })
})

describe('TCH46 — accords et échéances', () => {
  it('0 et 1 au singulier, 2 et plus au pluriel', () => {
    expect(accord(0, 'tâche')).toBe('0 tâche')
    expect(accord(1, 'faite')).toBe('1 faite')
    expect(accord(2, 'faite')).toBe('2 faites')
    expect(accord(3, 'cheval', 'chevaux')).toBe('3 chevaux')
  })

  it('échéance : rouge (alerte) aujourd\'hui ou dépassée, « fort » sinon', () => {
    expect(echeanceTexte('2026-11-17', AUJOURDHUI)).toEqual({ texte: "échéance aujourd'hui", ton: 'alerte' })
    expect(echeanceTexte('2026-11-12', AUJOURDHUI)).toEqual({ texte: 'échéance dépassée le 12/11', ton: 'alerte' })
    expect(echeanceTexte('2026-11-23', AUJOURDHUI)).toEqual({ texte: 'échéance lun. 23', ton: 'fort' })
    expect(echeanceTexte('2026-11-18', AUJOURDHUI)).toEqual({ texte: 'échéance demain', ton: 'fort' })
  })
})
