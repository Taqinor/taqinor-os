"""TCH38-TCH40 — analyseur de saisie rapide : la table de test de reference/regles.md §1.11
(86 phrases : A1-A39, E1-E16, pièges P1-P25, captures C1-C6). `analyser` doit rendre
EXACTEMENT les champs listés (vide = nul, 0 ou absent) ; unittest pur, sans base ni horloge.

Repère §0 : mardi 17/11/2026 10:00 ; projets Polydesign (id 3, actif) et Maison (id 5,
actif, étape Achats id 8) ; aucun férié, aucune étiquette existante.
"""
import unittest
from datetime import date, time

from apps.taches.saisie.analyseur import analyser
from apps.taches.saisie.grammaire import ProjetConnu

MARDI = (date(2026, 11, 17), time(10, 0))
PROJETS = (ProjetConnu(3, 'Polydesign', 'actif', 1), ProjetConnu(5, 'Maison', 'actif', 2))
SECTIONS = ((5, 8, 'Achats'),)


def j(jour, mois=11, annee=2026):
    return f'{annee}-{mois:02d}-{jour:02d}'


def rec(frequence, n=1, masque='0000000', jour_du_mois=None, rang=None,
        mode='calendrier'):
    return {'frequence': frequence, 'intervalle': n, 'jours_semaine': masque,
            'jour_du_mois': jour_du_mois, 'rang_dans_mois': rang, 'mode': mode,
            'date_debut': '2026-11-17'}


# (identifiant, saisie, titre attendu, champs attendus hors priorite 0, alertes, repère, porte)
# Repère par défaut : MARDI. Porte par défaut : rapide.
LIGNES = [
    ('A1', 'Appeler Karim demain', 'Appeler Karim', {'jour_prevu': j(18)}),
    ('A2', 'Call Karim tomorrow', 'Call Karim', {'jour_prevu': j(18)}),
    ('A3', 'Envoyer le devis lundi #Polydesign', 'Envoyer le devis',
     {'jour_prevu': j(23), 'projet_id': 3}),
    ('A4', 'Relancer banque lundi prochain', 'Relancer banque', {'jour_prevu': j(23)}),
    ('A5', 'Send invoice next monday', 'Send invoice', {'jour_prevu': j(23)}),
    ('A6', 'Payer CNSS dans 3 jours', 'Payer CNSS', {'jour_prevu': j(20)}),
    ('A7', 'Review contract in 3 days', 'Review contract', {'jour_prevu': j(20)}),
    ('A8', 'Réunion fournisseur 25/11 à 15h', 'Réunion fournisseur',
     {'jour_prevu': j(25), 'heure_debut': '15:00', 'moment': 'apres_midi'}),
    ('A9', 'Rapport TVA fin de mois !!!', 'Rapport TVA',
     {'jour_prevu': j(30), 'priorite': 3}),
    ('A10', 'Rapport TVA pour fin de mois', 'Rapport TVA', {'echeance': j(30)}),
    ('A11', 'Préparer offre ce soir', 'Préparer offre',
     {'jour_prevu': j(17), 'moment': 'soir'}),
    ('A12', 'Lire contrat demain matin', 'Lire contrat',
     {'jour_prevu': j(18), 'moment': 'matin'}),
    ('A13', 'Call supplier at 3pm', 'Call supplier',
     {'jour_prevu': j(17), 'heure_debut': '15:00', 'moment': 'apres_midi'}),
    ('A14', 'Point équipe 9h', 'Point équipe',
     {'jour_prevu': j(18), 'heure_debut': '09:00', 'moment': 'matin'}, ('heure_passee',)),
    ('A15', 'Écrire article 2h', 'Écrire article', {'estimation_minutes': 120}),
    ('A16', 'Trier emails 30 min', 'Trier emails', {'estimation_minutes': 30}),
    ('A17', 'Prepare slides for 2h', 'Prepare slides', {'estimation_minutes': 120}),
    ('A18', 'Dossier subvention pour vendredi', 'Dossier subvention', {'echeance': j(20)}),
    ('A19', 'Finish report due friday 15:00', 'Finish report',
     {'echeance': j(20), 'echeance_heure': '15:00'}),
    ('A20', 'Préparer visite jeudi pour vendredi', 'Préparer visite',
     {'jour_prevu': j(19), 'echeance': j(20)}),
    ('A21', 'Arroser plantes tous les 2 jours', 'Arroser plantes',
     {'jour_prevu': j(17), 'recurrence': rec('quotidien', 2)}),
    ('A22', 'Rapport hebdo chaque lundi #Polydesign', 'Rapport hebdo',
     {'jour_prevu': j(23), 'projet_id': 3, 'recurrence': rec('hebdo', 1, '1000000')}),
    ('A23', 'Check bank every weekday', 'Check bank',
     {'jour_prevu': j(17), 'recurrence': rec('jours_ouvres')}),
    ('A24', 'Payer loyer chaque mois le 5', 'Payer loyer',
     {'jour_prevu': j(5, 12), 'recurrence': rec('mensuel', 1, jour_du_mois=5)}),
    ('A25', 'Changer filtre tous les 3 mois après fait', 'Changer filtre',
     {'jour_prevu': j(17), 'recurrence': rec('mensuel', 3, mode='apres_fait')}),
    ('A26', 'Water plants every! 3 days', 'Water plants',
     {'jour_prevu': j(17), 'recurrence': rec('quotidien', 3, mode='apres_fait')}),
    ('A27', 'Acheter câbles #Maison /Achats %magasin', 'Acheter câbles',
     {'projet_id': 5, 'section_id': 8, 'etiquettes': [{'nom': 'magasin'}]}),
    ('A28', 'Maquette #SiteWeb !!', 'Maquette',
     {'nouveau_projet': {'nom': 'SiteWeb', 'priorite': 2}, 'priorite': 2}),
    ('A29', 'Plan lancement #Nouveau_site p1', 'Plan lancement',
     {'nouveau_projet': {'nom': 'Nouveau site', 'priorite': 2}, 'priorite': 3}),
    ('A30', "Lire « Demain dès l'aube »", "Lire « Demain dès l'aube »", {}),
    ('A31', 'Rappeler Ali 5/6', 'Rappeler Ali', {'jour_prevu': j(5, 6, 2027)}),
    ('A32', 'Meeting 3/1', 'Meeting', {'jour_prevu': j(3, 1, 2027)}),
    ('A33', 'Appeler Karim demain rappel 9h', 'Appeler Karim',
     {'jour_prevu': j(18),
      'rappel': {'ancre': 'jour_prevu', 'decalage_jours': 0, 'heure': '09:00'}}),
    ('A34', 'Envoyer rapport monthly', 'Envoyer rapport monthly', {}),
    ('A35', 'Remise 10% pour facture #12 !', 'Remise 10% pour facture #12 !', {}),
    ('A36', 'Dîner ce soir 9h', 'Dîner',
     {'jour_prevu': j(17), 'heure_debut': '21:00', 'moment': 'soir'}),
    ('A37', "Apprendre l'arabe classique un jour", "Apprendre l'arabe classique",
     {'quelque_jour': True}),
    ('A38', 'Fix bug Nov 25 at 10am', 'Fix bug',
     {'jour_prevu': j(25), 'heure_debut': '10:00', 'moment': 'matin'}),
    ('A39', 'Inventaire ce week-end', 'Inventaire', {'jour_prevu': j(21)}),
    ('E1', 'Email the accountant tomorrow at 9am #Polydesign', 'Email the accountant',
     {'jour_prevu': j(18), 'heure_debut': '09:00', 'moment': 'matin', 'projet_id': 3}),
    ('E2', 'Book flight to London next friday', 'Book flight to London',
     {'jour_prevu': j(20)}),
    ('E3', 'Call Lydec this afternoon', 'Call Lydec',
     {'jour_prevu': j(17), 'moment': 'apres_midi'}),
    ('E4', 'Pay rent every month on the 5', 'Pay rent',
     {'jour_prevu': j(5, 12), 'recurrence': rec('mensuel', 1, jour_du_mois=5)}),
    ('E5', 'Review slides in 2 weeks p2', 'Review slides',
     {'jour_prevu': j(1, 12), 'priorite': 2}),
    ('E6', 'Prepare offer due Nov 30 !!!', 'Prepare offer',
     {'echeance': j(30), 'priorite': 3}),
    ('E7', 'Gym every weekday at 7am', 'Gym',
     {'jour_prevu': j(17), 'heure_debut': '07:00', 'moment': 'matin',
      'recurrence': rec('jours_ouvres')}, ('heure_passee',)),
    ('E8', 'Send quote to Karim by end of week', 'Send quote to Karim',
     {'echeance': j(20)}),
    ('E9', 'Meeting with bank 2026-12-03 at 14:30', 'Meeting with bank',
     {'jour_prevu': j(3, 12), 'heure_debut': '14:30', 'moment': 'apres_midi'}),
    ('E10', 'Appeler Karim tomorrow 10 h', 'Appeler Karim',
     {'jour_prevu': j(18), 'heure_debut': '10:00', 'moment': 'matin'}),
    ('E11', 'Relancer devis Settat tomorrow due friday #Polydesign', 'Relancer devis Settat',
     {'jour_prevu': j(18), 'echeance': j(20), 'projet_id': 3}),
    ('E12', 'Prepare slides for 2h tomorrow morning', 'Prepare slides',
     {'jour_prevu': j(18), 'moment': 'matin', 'estimation_minutes': 120}),
    ('E13', 'Lunch at noon', 'Lunch',
     {'jour_prevu': j(17), 'heure_debut': '12:00', 'moment': 'apres_midi'}),
    ('E14', 'Learn Spanish someday', 'Learn Spanish', {'quelque_jour': True}),
    ('E15', 'Call mum tomorrow remind me at 18:00', 'Call mum',
     {'jour_prevu': j(18),
      'rappel': {'ancre': 'jour_prevu', 'decalage_jours': 0, 'heure': '18:00'}}),
    ('E16', 'Change filter every 3 months', 'Change filter',
     {'jour_prevu': j(17), 'recurrence': rec('mensuel', 3, jour_du_mois=17)}),
    ('P1', 'Réunion 5/6 à 9h', 'Réunion',
     {'jour_prevu': j(5, 6, 2027), 'heure_debut': '09:00', 'moment': 'matin'}),
    ('P2', 'Appel client 15h', 'Appel client',
     {'jour_prevu': j(17), 'heure_debut': '15:00', 'moment': 'apres_midi'}),
    ('P3', 'Réviser 15 min', 'Réviser', {'estimation_minutes': 15}),
    ('P4', 'Atelier pendant 3h', 'Atelier', {'estimation_minutes': 180}),
    ('P5', 'Rapport pour 9h', 'Rapport',
     {'echeance': j(18), 'echeance_heure': '09:00'}, ('heure_passee',)),
    ('P6', 'Rapport pour 6h', 'Rapport', {'estimation_minutes': 360}),
    ('P7', 'Réunion lundi', 'Réunion', {'jour_prevu': j(30)}, (),
     (date(2026, 11, 23), time(10, 0))),
    ('P8', 'Dîner mardi soir', 'Dîner', {'jour_prevu': j(24), 'moment': 'soir'}),
    ('P9', 'Bilan fin de semaine', 'Bilan', {'jour_prevu': j(20)}, (),
     (date(2026, 11, 20), time(10, 0))),
    ('P10', 'Lire Demain dès l\'aube', 'Lire dès l\'aube', {'jour_prevu': j(18)}),
    ('P11', 'Préparer le soir de gala', 'Préparer le soir de gala', {}),
    ('P12', 'Réunion du matin', 'Réunion du matin', {}),
    ('P13', 'Train 6h30 demain', 'Train',
     {'jour_prevu': j(18), 'heure_debut': '06:30', 'moment': 'matin'}),
    ('P14', 'Appel 1h30', 'Appel', {'estimation_minutes': 90}),
    ('P15', 'Appeler aujourd’hui', 'Appeler', {'jour_prevu': j(17)}),
    ('P16', 'Payer le 1er décembre', 'Payer', {'jour_prevu': j(1, 12)}),
    ('P17', 'Payer facture le 31/11', 'Payer facture le 31/11', {}, ('date_invalide',)),
    ('P18', 'Point 10 h 30 demain', 'Point',
     {'jour_prevu': j(18), 'heure_debut': '10:30', 'moment': 'matin'}),
    ('P19', 'Facture #12 pour demain', 'Facture #12', {'echeance': j(18)}),
    ('P20', 'Karim ! demain', 'Karim !', {'jour_prevu': j(18)}),
    ('P21', 'Appeler demain et vendredi', 'Appeler et vendredi',
     {'jour_prevu': j(18)}, ('deux_jour',)),
    ('P22', 'Déjeuner à midi', 'Déjeuner',
     {'jour_prevu': j(17), 'heure_debut': '12:00', 'moment': 'apres_midi'}),
    ('P23', 'Trier emails 2 min', 'Trier emails 2 min', {}, ('duree_hors_bornes',)),
    ('P24', 'Appeler 3pm demain', 'Appeler',
     {'jour_prevu': j(18), 'heure_debut': '15:00', 'moment': 'apres_midi'}),
    ('P25', 'Call May 5', 'Call', {'jour_prevu': j(5, 5, 2027)}),
    ('C1', 'Lait demain #Maison %magasin rappel 9h', 'Lait %magasin rappel',
     {'jour_prevu': j(18), 'heure_debut': '09:00', 'moment': 'matin', 'projet_id': 5},
     (), None, 'capture', 'journee'),
    ('C2', 'Appeler Karim un jour', 'Appeler Karim un jour', {}, (), None, 'capture',
     'a_trier'),
    ('C3', 'Maquette #SiteWeb', 'Maquette #SiteWeb', {}, (), None, 'capture', 'a_trier'),
    ('C4', 'appeler le fournisseur demain 10 h', 'appeler le fournisseur',
     {'jour_prevu': j(18), 'heure_debut': '10:00', 'moment': 'matin'}, (), None,
     'capture', 'journee'),
    ('C5', 'projet Maison acheter du lait demain', 'acheter du lait',
     {'jour_prevu': j(18), 'projet_id': 5}, (), None, 'capture', 'journee'),
    ('C6', 'Rapport pour vendredi', 'Rapport', {'echeance': j(20)}, (), None, 'capture',
     'a_trier'),
]

# TCH38 : les 32 lignes obligatoires ; les autres restent en `expectedFailure` jusqu'à TCH39.
OBLIGATOIRES_TCH38 = frozenset(
    'A1 A2 A4 A5 A6 A7 A8 A10 A11 A12 A13 A14 A15 A16 A17 A18 A19 A20 A30 A32 A34 A36 A38 A39 '
    'E2 E3 E5 E8 E9 E10 E12 E13'.split())
A_VENIR_TCH39 = frozenset(
    'A3 A21 A22 A23 A24 A25 A26 A27 A28 A29 A33 A37 C1 C5 E1 E4 E7 E11 E14 E15 E16'.split())


class PartageTch38Tests(unittest.TestCase):
    def test_les_32_lignes_obligatoires_passent_sans_expected_failure(self):
        self.assertEqual(len(OBLIGATOIRES_TCH38), 32)
        self.assertFalse(OBLIGATOIRES_TCH38 & A_VENIR_TCH39)
        identifiants = {ligne[0] for ligne in LIGNES}
        self.assertLessEqual(OBLIGATOIRES_TCH38 | A_VENIR_TCH39, identifiants)
        self.assertEqual(len(identifiants), 86)


def _rendre(ligne):
    ident, saisie, titre, champs = ligne[:4]
    alertes = ligne[4] if len(ligne) > 4 else ()
    repere = (ligne[5] if len(ligne) > 5 else None) or MARDI
    porte = ligne[6] if len(ligne) > 6 else 'rapide'
    return ident, saisie, titre, champs, alertes, repere, porte


class TableDeTestTests(unittest.TestCase):
    """Une méthode par ligne de la table (`test_<identifiant>`)."""

    def verifier(self, ligne):
        ident, saisie, titre, champs, alertes, repere, porte = _rendre(ligne)
        analyse = analyser(saisie, repere[0], repere[1], projets=PROJETS,
                           sections=SECTIONS, porte=porte)
        self.assertEqual(analyse.titre, titre, ident)
        self.assertEqual(analyse.champs, {'priorite': 0, **champs}, ident)
        self.assertEqual(set(analyse.alertes), set(alertes), ident)
        self.assertEqual(analyse.erreurs, {}, ident)
        self.verifier_positions(saisie, analyse)

    def verifier_positions(self, saisie, analyse):
        """Chaque jeton dit OÙ il a été lu : `debut`/`fin` redonnent `source`, sans chevauchement."""
        fin_precedente = 0
        for jeton in analyse.jetons:
            self.assertEqual(saisie[jeton['debut']:jeton['fin']], jeton['source'])
            self.assertGreaterEqual(jeton['debut'], fin_precedente)
            fin_precedente = jeton['fin']


def _fabriquer(ligne):
    def cas(self):
        self.verifier(ligne)
    cas.__name__ = f'test_{ligne[0]}'
    cas.__doc__ = f'{ligne[0]} — {ligne[1]}'
    if ligne[0] in A_VENIR_TCH39:
        return unittest.expectedFailure(cas)
    return cas


for _ligne in LIGNES:
    setattr(TableDeTestTests, f'test_{_ligne[0]}', _fabriquer(_ligne))


if __name__ == '__main__':
    unittest.main()
