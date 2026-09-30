import { describe, it, expect } from 'vitest'
import { exempleContrat } from '../../test/fixtures/contractSamples'
import { PARCOURS } from '../../features/crm/relances/parcours'
import {
  comparaisonPrecedent, decimal, duree, familleType, heureCasa, jjmm, jourCourt, jourLong,
  libelleJour, libelleReponse, nomType, numeroJour, phraseExceptions, phrasePeriode,
  phrasePremierContact, phraseResultats, pl, typeDeLaTable, typeEstTache,
} from './controleSuiviTexte'

/* COCKPIT-CONTRÔLE — les phrases du bloc « Contrôle du suivi », en fonctions
   pures. Les entrées sont l'exemple COMMITTÉ du contrat (PACT10) ; les cas
   limites (singulier, pluriel, null) modifient ce SEUL champ. */
const CONTROLE = exempleContrat('crm', 'controle_suivi')
const VIDE = exempleContrat('crm', 'controle_suivi', 'exemple_vide')

describe('accords et formats', () => {
  it('pl : 0 et 1 au singulier, 2 et plus au pluriel', () => {
    expect([0, 1, 2, 10].map((n) => pl(n, 'jour', 'jours')))
      .toEqual(['jour', 'jour', 'jours', 'jours'])
  })

  it('decimal : virgule française, une décimale au plus, « — » pour null', () => {
    expect(decimal(27.5)).toBe('27,5')
    expect(decimal(24)).toBe('24')
    expect(decimal(2.04)).toBe('2')
    expect(decimal(null)).toBe('—')
    expect(decimal(undefined)).toBe('—')
  })

  it('duree : minutes puis heures, « — » pour null', () => {
    expect(duree(42)).toBe('42 min')
    expect(duree(60)).toBe('1 h')
    expect(duree(135)).toBe('2 h 15')
    expect(duree(65)).toBe('1 h 05')
    expect(duree(null)).toBe('—')
  })

  it('jjmm : jour/mois lu sur la chaîne, sans fuseau', () => {
    expect(jjmm('2026-09-27')).toBe('27/09')
    expect(jjmm('2026-01-05')).toBe('05/01')
    expect(jjmm(null)).toBe('—')
    expect(jjmm('pas une date')).toBe('—')
  })

  it('jours de la frise : long, court (sans point), numéro', () => {
    expect(jourLong('2026-09-29')).toBe('mardi 29 septembre')
    expect(jourCourt('2026-09-29')).toBe('mar')
    expect(jourCourt('2026-09-30')).toBe('mer')
    expect(numeroJour('2026-09-05')).toBe(5)
    expect(jourLong(undefined)).toBe('—')
  })

  it('heureCasa : heure de Casablanca (UTC+1 en septembre), jamais celle du navigateur', () => {
    expect(heureCasa('2026-09-07T07:32:10Z')).toBe('08:32')
    expect(heureCasa(null)).toBe(null)
    expect(heureCasa('nimporte quoi')).toBe(null)
  })
})

describe('phraseExceptions', () => {
  it('reprend les cinq listes de l\'exemple, retards d\'abord', () => {
    expect(phraseExceptions(CONTROLE.exceptions, 'attention')).toBe(
      '2 étapes en retard, 1 tâche en attente depuis 4 jours, '
      + '1 étape reportée plusieurs fois, 1 premier contact hors délai.')
  })

  it('accorde le singulier (« 1 étape en retard ») et le pluriel des tâches', () => {
    const exceptions = {
      ...VIDE.exceptions,
      en_retard: { total: 1, lignes: [] },
      taches_en_attente: {
        total: 3, lignes: [{ ouverte_depuis_jours: 6 }, { ouverte_depuis_jours: 2 }],
      },
      sans_prochaine_etape: { total: 2, lignes: [] },
      premier_contact_hors_delai: { total: 4, lignes: [] },
    }
    expect(phraseExceptions(exceptions, 'alerte')).toBe(
      '1 étape en retard, 3 tâches en attente (la plus ancienne depuis 6 jours), '
      + '2 dossiers sans prochaine étape, 4 premiers contacts hors délai.')
  })

  it('aucune exception : une phrase selon le niveau, jamais une liste vide inventée', () => {
    expect(phraseExceptions(VIDE.exceptions, 'ok')).toBe('Rien n\'est en retard ni en attente.')
    expect(phraseExceptions(VIDE.exceptions, 'vide')).toBe('Aucune étape n\'était due sur cette période.')
    expect(phraseExceptions(VIDE.exceptions, 'attention')).toBe('')
    expect(phraseExceptions(undefined, 'ok')).toBe('Rien n\'est en retard ni en attente.')
  })
})

describe('phrasePeriode et comparaisonPrecedent', () => {
  it('la phrase de période de l\'exemple', () => {
    expect(phrasePeriode(CONTROLE.verdict, CONTROLE.periode_jours)).toBe(
      'Sur 14 jours : 36 étapes sur 42 traitées à temps (86 %), '
      + '3 rattrapées en retard, 1 sautée, 2 encore ouvertes.')
  })

  it('singulier partout, et « — » quand le pourcentage est null', () => {
    const v = {
      du: 1, a_temps: 1, en_retard: 1, sautees: 1, ouvert: 1, a_temps_pct: null,
    }
    expect(phrasePeriode(v, 7)).toBe(
      'Sur 7 jours : 1 étape sur 1 traitée à temps (—), 1 rattrapée en retard, 1 sautée, 1 encore ouverte.')
  })

  it('rien de dû : aucune étape, aucun pourcentage', () => {
    expect(phrasePeriode(VIDE.verdict, 14)).toBe('Sur 14 jours : aucune étape n\'était due.')
  })

  it('la comparaison se lit sur les pourcentages tels qu\'affichés (arrondis)', () => {
    expect(comparaisonPrecedent(CONTROLE.verdict)).toEqual({
      sens: 'hausse', fleche: '↑',
      texte: '↑ 8 points par rapport à la période précédente (78 %)',
    })
    expect(comparaisonPrecedent({ a_temps_pct: 85.4, precedent_a_temps_pct: 78.6 }).texte)
      .toBe('↑ 6 points par rapport à la période précédente (79 %)')
    expect(comparaisonPrecedent({ a_temps_pct: 80, precedent_a_temps_pct: 81 }).texte)
      .toBe('↓ 1 point par rapport à la période précédente (81 %)')
    expect(comparaisonPrecedent({ a_temps_pct: 80, precedent_a_temps_pct: 80 }))
      .toEqual({ sens: 'stable', fleche: '→', texte: '→ Stable par rapport à la période précédente (80 %)' })
  })

  it('rien à comparer si l\'un des deux pourcentages est null', () => {
    expect(comparaisonPrecedent({ a_temps_pct: null, precedent_a_temps_pct: 80 })).toBe(null)
    expect(comparaisonPrecedent({ a_temps_pct: 80, precedent_a_temps_pct: null })).toBe(null)
    expect(comparaisonPrecedent(VIDE.verdict)).toBe(null)
  })
})

describe('libelleJour (nom accessible d\'une case)', () => {
  const jour = (surcharge) => ({
    date: '2026-09-29', ouvre: true, aujourdhui: false, du: 0, a_temps: 0, en_retard: 0, sautees: 0, ouvert: 0,
    etat: 'vide', ...surcharge,
  })

  it('les compteurs non nuls seulement, dans l\'ordre dues / à temps / rattrapées / sautées / ouvertes', () => {
    expect(libelleJour(jour({
      du: 9, a_temps: 4, en_retard: 2, sautees: 1, ouvert: 2,
    }))).toBe('mardi 29 septembre : 9 dues, 4 à temps, 2 rattrapées en retard, 1 sautée, 2 encore ouvertes')
    expect(libelleJour(jour({ du: 1, ouvert: 1 }))).toBe('mardi 29 septembre : 1 due, 1 encore ouverte')
  })

  it('rien de dû, jour non ouvré, aujourd\'hui', () => {
    expect(libelleJour(jour({}))).toBe('mardi 29 septembre : rien de dû')
    expect(libelleJour(jour({ ouvre: false })))
      .toBe('mardi 29 septembre (jour non ouvré) : rien de dû')
    expect(libelleJour(jour({ aujourdhui: true, du: 2, ouvert: 2 })))
      .toBe('mardi 29 septembre (aujourd\'hui) : 2 dues, 2 encore ouvertes')
  })
})

describe('lecture de la table du parcours', () => {
  it('nomType / familleType / typeEstTache lisent la table, jamais une liste écrite ici', () => {
    const devis = PARCOURS.etapes.find((t) => t.id === 'devis')
    expect(nomType('devis')).toBe(devis.nom)
    expect(familleType('devis')).toBe(devis.famille)
    expect(typeEstTache('devis')).toBe(true)
    expect(typeEstTache('contact_appel')).toBe(false)
    expect(typeDeLaTable('devis')).toBe(devis)
  })

  it('un type absent de la table : l\'identifiant tel quel, jamais un blanc ; vide → vide', () => {
    expect(nomType('type_inconnu')).toBe('type_inconnu')
    expect(nomType('')).toBe('')
    expect(nomType(undefined)).toBe('')
    expect(familleType('type_inconnu')).toBe('')
    expect(typeEstTache('type_inconnu')).toBe(false)
  })

  it('libelleReponse : première réponse dont l\'issue ou la réponse vaut la clé', () => {
    // outcome
    expect(libelleReponse('contact_appel', 'joint')).toBe('Client joint')
    expect(libelleReponse('contact_appel', 'non_joint')).toBe('Pas de réponse')
    // `reponse` (et non outcome)
    expect(libelleReponse('contact_appel', 'plus_tard')).toBe('Plus tard — pas maintenant')
    // libellé propre au type
    expect(libelleReponse('devis', 'rappel')).toBe('Pas encore — à rappeler le…')
  })

  it('libelleReponse : sans_issue → « Fait », clé inconnue → la clé', () => {
    expect(libelleReponse('devis', 'sans_issue')).toBe('Fait')
    expect(libelleReponse('type_inconnu', 'sans_issue')).toBe('Fait')
    expect(libelleReponse('contact_appel', 'rien_de_connu')).toBe('rien_de_connu')
    expect(libelleReponse('type_inconnu', 'joint')).toBe('joint')
  })
})

describe('phrasePremierContact et phraseResultats', () => {
  it('reprend l\'exemple : dans le délai, médiane, plus longue attente', () => {
    expect(phrasePremierContact(CONTROLE.premier_contact)).toBe(
      '8 sur 9 dans le délai (24 h) · médiane 42 min · plus longue attente 27,5 h')
  })

  it('aucun nouveau lead / aucun lead en attente / médiane inconnue', () => {
    expect(phrasePremierContact(VIDE.premier_contact)).toBe('Aucun nouveau lead sur la période.')
    expect(phrasePremierContact({
      ...CONTROLE.premier_contact, mediane_minutes: null, plus_longue_attente_heures: null,
    })).toBe('8 sur 9 dans le délai (24 h) · médiane — · aucun lead en attente')
  })

  it('résultats : accord au pluriel / singulier', () => {
    expect(phraseResultats(CONTROLE.resultats))
      .toBe('3 visites planifiées · 4 devis envoyés · 1 devis accepté')
    expect(phraseResultats(VIDE.resultats))
      .toBe('0 visite planifiée · 0 devis envoyé · 0 devis accepté')
    expect(phraseResultats({ visites_planifiees: 2, devis_envoyes: 2, devis_acceptes: 2 }))
      .toBe('2 visites planifiées · 2 devis envoyés · 2 devis acceptés')
  })
})
