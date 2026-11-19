"""TCH30 — gabarits de phrases purs : textes.md §0, §3, §4 mot pour mot (unittest pur)."""
import re
import unittest
from datetime import date, time

from apps.taches.moteur import gabarits
from apps.taches.moteur.gabarits import (
    CONSTANTES, arrondir, boutons, format_duree, format_heure, format_heure_dite,
    format_jour, texte, toutes_les_phrases)

J = date(2026, 11, 17)


def nom_pour(objet, usage):
    """Double de `nom_pour` : un objet confidentiel n'a aucun nom pour une notification."""
    if objet == 'secret':
        return None if usage == 'notification' else 'un projet'
    return objet


class Tableau(unittest.TestCase):
    """Rend chaque ligne (type, cle, données, variante, attendu) et compare mot pour mot."""

    def verifier(self, lignes):
        for type_, cle, donnees, var, attendu in lignes:
            with self.subTest(type=type_, cle=cle, variante=var, donnees=donnees):
                self.assertEqual(texte(type_, cle, donnees, var, nom_pour), attendu)


class FormatsTests(unittest.TestCase):
    def test_heure_puce_et_dite(self):
        self.assertEqual(format_heure(time(10, 0)), '10:00')
        self.assertEqual(format_heure(time(8, 5)), '08:05')
        self.assertEqual(format_heure_dite(time(10, 0)), '10 h')
        self.assertEqual(format_heure_dite(time(10, 30)), '10 h 30')
        self.assertEqual(format_heure_dite(time(15, 5)), '15 h 05')

    def test_durees(self):
        self.assertEqual(format_duree(45), '45 min')
        self.assertEqual(format_duree(60), '1 h')
        self.assertEqual(format_duree(190), '3 h 10')

    def test_jours(self):
        self.assertEqual(format_jour(J, J), "aujourd'hui")
        self.assertEqual(format_jour(date(2026, 11, 18), J), 'demain')
        self.assertEqual(format_jour(date(2026, 11, 19), J), 'jeu. 19')
        self.assertEqual(format_jour(date(2026, 11, 30), J), 'lun. 30')  # J + 13
        self.assertEqual(format_jour(date(2026, 12, 1), J), 'mar. 1 déc.')  # J + 14
        self.assertEqual(format_jour(date(2026, 11, 12), J), 'jeu. 12 nov.')  # passé : la même forme que « mar. 1 déc. »
        self.assertEqual(format_jour(date(2027, 1, 5), J), '05/01/2027')

    def test_premier_du_mois_dans_une_phrase(self):
        self.assertEqual(format_jour(date(2026, 12, 1), J, phrase=True), 'mar. 1er décembre')

    def test_arrondi_la_demie_vers_le_bas(self):
        self.assertEqual([arrondir(x) for x in (5.5, 5.51, 4.5, 6.4, 6.6)], [5, 6, 4, 6, 7])


class NotificationsMatinTests(Tableau):
    def test_pousser_gardees(self):
        d3 = {'prevues': 3, 'objectif': 5}
        d1 = {'prevues': 1, 'objectif': 5}
        self.verifier([
            ('notification', 'matin.pousser_gardees', d3, 0, 'Ta journée : 3 prévues · objectif 5.'),
            ('notification', 'matin.pousser_gardees', d1, 0, 'Ta journée : 1 prévue · objectif 5.'),
            ('notification', 'matin.pousser_gardees', d3, 1, 'Bonjour. 3 tâches prévues ; objectif du jour : 5.'),
            ('notification', 'matin.pousser_gardees', d1, 1, 'Bonjour. 1 tâche prévue ; objectif du jour : 5.'),
            ('notification', 'matin.pousser_gardees', d3, 2, 'Plan du jour : choisis ton essentiel (objectif 5).'),
        ])

    def test_pousser_proposees(self):
        d4 = {'proposees': 4, 'objectif': 5}
        d1 = {'proposees': 1, 'objectif': 5}
        self.verifier([
            ('notification', 'matin.pousser_proposees', d4, 0, '4 proposées pour ton objectif de 5.'),
            ('notification', 'matin.pousser_proposees', d1, 0, '1 proposée pour ton objectif de 5.'),
            ('notification', 'matin.pousser_proposees', d4, 1,
             "Bonjour. Proposé pour aujourd'hui : 4 tâches ; objectif 5."),
            ('notification', 'matin.pousser_proposees', d1, 1,
             "Bonjour. Proposé pour aujourd'hui : 1 tâche ; objectif 5."),
            ('notification', 'matin.pousser_proposees', d4, 2,
             'Plan du jour : garde tes tâches et choisis ton essentiel (objectif 5).'),
        ])

    def test_tenir(self):
        d3 = {'prevues': 3, 'bas': 4, 'haut': 6}
        d1 = {'prevues': 1, 'bas': 4, 'haut': 6}
        self.verifier([
            ('notification', 'matin.tenir', d3, 0, 'Ta journée : 3 prévues · ton rythme 4 à 6.'),
            ('notification', 'matin.tenir', d1, 0, 'Ta journée : 1 prévue · ton rythme 4 à 6.'),
            ('notification', 'matin.tenir', d3, 1, "Bonjour. 3 tâches t'attendent ; ton rythme : 4 à 6."),
            ('notification', 'matin.tenir', d1, 1, "Bonjour. 1 tâche t'attend ; ton rythme : 4 à 6."),
            ('notification', 'matin.tenir', d3, 2, 'Plan du jour : choisis ton essentiel (rythme 4 à 6).'),
        ])

    def test_libre(self):
        self.verifier([
            ('notification', 'matin.libre', {'prevues': 3}, 0, 'Ta journée : 3 prévues.'),
            ('notification', 'matin.libre', {'prevues': 1}, 0, 'Ta journée : 1 prévue.'),
            ('notification', 'matin.libre', {'prevues': 3}, 1, "Bonjour. 3 tâches t'attendent."),
            ('notification', 'matin.libre', {'prevues': 1}, 1, "Bonjour. 1 tâche t'attend."),
            ('notification', 'matin.libre', {'prevues': 3}, 2, 'Plan du jour : choisis ton essentiel.'),
        ])

    def test_avec_titres_ajoute_en_tete(self):
        d = {'prevues': 3, 'objectif': 5, 'avec_titres': True, 'titre': 'Appeler Karim'}
        for var, base in enumerate((
                'Ta journée : 3 prévues · objectif 5.',
                'Bonjour. 3 tâches prévues ; objectif du jour : 5.',
                'Plan du jour : choisis ton essentiel (objectif 5).')):
            with self.subTest(variante=var):
                self.assertEqual(texte('notification', 'matin.pousser_gardees', d, var, nom_pour),
                                 base + ' En tête : « Appeler Karim ».')
        t = {'prevues': 3, 'bas': 4, 'haut': 6, 'avec_titres': True, 'titre': 'Appeler Karim'}
        self.assertEqual(texte('notification', 'matin.tenir', t, 2, nom_pour),
                         'Plan du jour : choisis ton essentiel (rythme 4 à 6). En tête : « Appeler Karim ».')
        lib = {'prevues': 3, 'avec_titres': True, 'titre': 'Appeler Karim'}
        self.assertEqual(texte('notification', 'matin.libre', lib, 0, nom_pour),
                         'Ta journée : 3 prévues. En tête : « Appeler Karim ».')

    def test_titre_confidentiel_ou_non_autorise_jamais_montre(self):
        d = {'prevues': 3, 'objectif': 5, 'titre': 'secret', 'avec_titres': True}
        self.assertEqual(texte('notification', 'matin.pousser_gardees', d, 0, nom_pour),
                         'Ta journée : 3 prévues · objectif 5.')
        d = {'prevues': 3, 'objectif': 5, 'titre': 'Appeler Karim', 'avec_titres': False}
        self.assertEqual(texte('notification', 'matin.pousser_gardees', d, 0, nom_pour),
                         'Ta journée : 3 prévues · objectif 5.')
        d['avec_titres'] = True
        self.assertEqual(texte('notification', 'matin.pousser_gardees', d, 0),
                         'Ta journée : 3 prévues · objectif 5.')


class NotificationsRelanceTests(Tableau):
    def test_echeance(self):
        self.verifier([
            ('notification', 'relance.echeance', {'n': 2}, 0, "2 tâches ont leur échéance aujourd'hui."),
            ('notification', 'relance.echeance', {'n': 1}, 0, "1 tâche a son échéance aujourd'hui."),
            ('notification', 'relance.echeance', {'n': 2}, 1, "Échéance aujourd'hui : 2 tâches encore ouvertes."),
            ('notification', 'relance.echeance', {'n': 1}, 1, "Échéance aujourd'hui : 1 tâche encore ouverte."),
            ('notification', 'relance.echeance', {'n': 2}, 2, 'Avant ce soir : 2 tâches à échéance.'),
            ('notification', 'relance.echeance', {'n': 1}, 2, 'Avant ce soir : 1 tâche à échéance.'),
        ])

    def test_echeance_avec_titres(self):
        seul = {'n': 1, 'avec_titres': True, 'titre': 'Envoyer le devis'}
        autres = {'n': 3, 'avec_titres': True, 'titre': 'Envoyer le devis', 'n_autres': 2}
        un_autre = {'n': 2, 'avec_titres': True, 'titre': 'Envoyer le devis', 'n_autres': 1}
        for var in range(3):
            self.assertEqual(texte('notification', 'relance.echeance', seul, var, nom_pour),
                             "« Envoyer le devis » a son échéance aujourd'hui.")
        self.assertEqual(texte('notification', 'relance.echeance', autres, 0, nom_pour),
                         "« Envoyer le devis » et 2 autres ont leur échéance aujourd'hui.")
        self.assertEqual(texte('notification', 'relance.echeance', un_autre, 1, nom_pour),
                         "« Envoyer le devis » et 1 autre ont leur échéance aujourd'hui.")

    def test_derive_pousser_essentiel_ouvert(self):
        d = {'faites': 2, 'objectif': 5, 'heure': time(15, 0)}
        self.verifier([
            ('notification', 'relance.derive_pousser_essentiel', d, 0,
             '2 sur 5 ; ton essentiel est encore ouvert.'),
            ('notification', 'relance.derive_pousser_essentiel', d, 1, 'À 15 h : 2 sur 5, essentiel à faire.'),
            ('notification', 'relance.derive_pousser_essentiel', d, 2,
             "Point de 15 h : 2 sur 5 ; l'essentiel d'abord ?"),
            ('notification', 'relance.derive_pousser_essentiel',
             dict(d, avec_titres=True, titre='Rédiger le devis'), 1,
             'À 15 h : 2 sur 5, essentiel à faire. Essentiel : « Rédiger le devis ».'),
        ])

    def test_derive_pousser_sans_essentiel(self):
        d = {'faites': 2, 'objectif': 5, 'heure': time(15, 30)}
        self.verifier([
            ('notification', 'relance.derive_pousser_sans_essentiel', d, 0, "2 sur 5 pour l'instant."),
            ('notification', 'relance.derive_pousser_sans_essentiel', d, 1, 'À 15 h 30 : 2 sur 5.'),
            ('notification', 'relance.derive_pousser_sans_essentiel', d, 2, 'Point de 15 h 30 : 2 sur 5.'),
        ])

    def test_derive_tenir(self):
        d = {'faites': 7, 'bas': 4, 'haut': 6}
        un = {'faites': 1, 'bas': 4, 'haut': 6}
        self.verifier([
            ('notification', 'relance.derive_tenir', d, 0,
             '7 faites, ton rythme est 4 à 6 : le reste peut attendre demain.'),
            ('notification', 'relance.derive_tenir', un, 0,
             '1 faite, ton rythme est 4 à 6 : le reste peut attendre demain.'),
            ('notification', 'relance.derive_tenir', d, 1, 'Déjà 7 faites, au-delà de ton rythme (4 à 6).'),
            ('notification', 'relance.derive_tenir', un, 1, 'Déjà 1 faite, au-delà de ton rythme (4 à 6).'),
            ('notification', 'relance.derive_tenir', d, 2, "7 faites aujourd'hui : tu peux t'arrêter là."),
            ('notification', 'relance.derive_tenir', un, 2, "1 faite aujourd'hui : tu peux t'arrêter là."),
        ])

    def test_projet_neglige(self):
        self.verifier([
            ('notification', 'relance.neglige', {}, 0, "Ton projet prioritaire n'a pas avancé depuis 14 jours."),
            ('notification', 'relance.neglige', {}, 1, 'Rien de fait depuis 14 jours dans ton projet prioritaire.'),
            ('notification', 'relance.neglige', {}, 2,
             'Ton projet prioritaire attend une tâche depuis 14 jours.'),
            ('notification', 'relance.neglige', {'avec_titres': True, 'projet': 'Polydesign'}, 1,
             "« Polydesign » n'a pas avancé depuis 14 jours."),
            ('notification', 'relance.neglige', {'avec_titres': True, 'projet': 'secret'}, 1,
             'Rien de fait depuis 14 jours dans ton projet prioritaire.'),
        ])


class NotificationsSoirEtRevueTests(Tableau):
    def test_soir_pousser_et_tenir(self):
        d = {'faites': 3, 'objectif': 5, 'restes': 2}
        self.verifier([
            ('notification', 'soir.pousser', d, 0, 'Bilan : 3 sur 5.'),
            ('notification', 'soir.pousser', d, 1, 'Journée close ? 3 sur 5.'),
            ('notification', 'soir.pousser', d, 2, '3 sur 5, 2 à placer.'),
            ('notification', 'soir.pousser', dict(d, restes=0), 2, '3 sur 5, rien à placer.'),
            ('notification', 'soir.pousser', dict(d, restes=1), 2, '3 sur 5, 1 à placer.'),
        ])

    def test_soir_libre(self):
        d = {'faites': 4, 'restes': 2}
        un = {'faites': 1, 'restes': 2}
        self.verifier([
            ('notification', 'soir.libre', d, 0, 'Bilan : 4 faites.'),
            ('notification', 'soir.libre', un, 0, 'Bilan : 1 faite.'),
            ('notification', 'soir.libre', d, 1, 'Journée close ? 4 tâches faites.'),
            ('notification', 'soir.libre', un, 1, 'Journée close ? 1 tâche faite.'),
            ('notification', 'soir.libre', d, 2, '4 faites, 2 à placer.'),
            ('notification', 'soir.libre', un, 2, '1 faite, 2 à placer.'),
        ])

    def test_revue(self):
        d = {'faites': 12, 'jours': 4, 'projets': 3}
        un = {'faites': 1, 'jours': 1, 'projets': 1}
        self.verifier([
            ('notification', 'revue', d, 0, "Semaine : 12 tâches en 4 jours. La revue t'attend."),
            ('notification', 'revue', un, 0, "Semaine : 1 tâche en 1 jour. La revue t'attend."),
            ('notification', 'revue', d, 1, 'Fin de semaine : 12 faites. On passe tes projets en revue ?'),
            ('notification', 'revue', un, 1, 'Fin de semaine : 1 faite. On passe tes projets en revue ?'),
            ('notification', 'revue', d, 2, 'Revue de la semaine : 3 projets actifs à passer en revue.'),
            ('notification', 'revue', un, 2, 'Revue de la semaine : 1 projet actif à passer en revue.'),
        ])

    def test_revue_semaine_courte_une_seule_formulation(self):
        for var in range(3):
            self.assertEqual(texte('notification', 'revue.courte', {}, var),
                             'Semaine courte : on reprend lundi.')

    def test_test_une_seule_formulation(self):
        for var in range(3):
            self.assertEqual(texte('notification', 'test', {}, var),
                             'Les notifications de Tâches arrivent bien sur cet appareil.')


class RappelEtTitresTests(Tableau):
    def test_rappel(self):
        h = time(10, 30)
        self.verifier([
            ('notification', 'rappel', {'n': 1, 'heure': h}, 0, 'Une tâche à 10 h 30.'),
            ('notification', 'rappel', {'n': 3, 'heure': h}, 0, '3 tâches à 10 h 30.'),
            ('notification', 'rappel', {'n': 1, 'heure': h}, 1, 'Rappel de 10 h 30 : 1 tâche.'),
            ('notification', 'rappel', {'n': 3, 'heure': h}, 1, 'Rappel de 10 h 30 : 3 tâches.'),
            ('notification', 'rappel', {'n': 1, 'heure': h}, 2, "C'est l'heure : 1 tâche à 10 h 30."),
            ('notification', 'rappel', {'n': 3, 'heure': h}, 2, "C'est l'heure : 3 tâches à 10 h 30."),
        ])

    def test_rappel_avec_titre(self):
        d = {'n': 1, 'heure': time(10, 0), 'avec_titres': True, 'titre': 'Appeler Karim'}
        for var in range(3):
            self.assertEqual(texte('notification', 'rappel', d, var, nom_pour), '« Appeler Karim » · 10 h')

    def test_titres_des_push(self):
        self.verifier([
            ('notification', 'titre.plan_matin', {}, 0, "Aujourd'hui"),
            ('notification', 'titre.relance', {'heure': time(15, 0)}, 0, 'Message de 15 h'),
            ('notification', 'titre.bilan_soir', {}, 0, 'Bilan du soir'),
            ('notification', 'titre.revue_semaine', {}, 0, 'Revue de la semaine'),
            ('notification', 'titre.rappel', {}, 0, 'Rappel'),
            ('notification', 'titre.test', {}, 0, 'Test des notifications'),
        ])

    def test_variante_hors_de_0_2_tourne(self):
        d = {'prevues': 3, 'objectif': 5}
        self.assertEqual(texte('notification', 'matin.pousser_gardees', d, 5),
                         texte('notification', 'matin.pousser_gardees', d, 2))


class ConfirmationsEtCartesTests(Tableau):
    def test_confirmations(self):
        self.verifier([
            ('confirmation', 'objectif_dit', {'nb': 4}, 0, "Objectif du jour : 4, dès aujourd'hui."),
            ('confirmation', 'plus', {'nb': 6}, 0, "Objectif du jour : 6 (un de plus), dès aujourd'hui."),
            ('confirmation', 'moins', {'nb': 4}, 0, "Objectif du jour : 4 (un de moins), dès aujourd'hui."),
            ('confirmation', 'en_faire_plus', {'nb': 6}, 0,
             "En faire plus : objectif du jour 6. Je te proposerai d'aller plus loin quand tu le tiens."),
            ('confirmation', 'garder_ce_rythme', {'R': 5, 'bas': 4, 'haut': 6}, 0,
             "Garder ce rythme : environ 5 tâches par jour (4 à 6). Je ne te pousse plus ; "
             "je te préviens seulement si tu t'en éloignes."),
            ('confirmation', 'garder_ce_rythme', {'R': 1, 'bas': 1, 'haut': 2}, 0,
             "Garder ce rythme : environ 1 tâche par jour (1 à 2). Je ne te pousse plus ; "
             "je te préviens seulement si tu t'en éloignes."),
            ('confirmation', 'garder_ce_rythme', {'R': 5.5, 'bas': 4.4, 'haut': 6.6}, 0,
             "Garder ce rythme : environ 5 tâches par jour (4 à 7). Je ne te pousse plus ; "
             "je te préviens seulement si tu t'en éloignes."),
            ('confirmation', 'garder_ce_rythme.provisoire', {'R': 5, 'bas': 4, 'haut': 6}, 0,
             "Garder ce rythme : environ 5 tâches par jour (4 à 6). Je ne te pousse plus ; "
             "je te préviens seulement si tu t'en éloignes. À confirmer sur 14 jours travaillés."),
            # R3-004 (C-15) : moins de 5 jours évalués, le palier est gardé et le geste le dit
            ('confirmation', 'garder_ce_rythme.palier', {'R': 6, 'bas': 5, 'haut': 7}, 0,
             "Pas encore assez de jours pour mesurer ton rythme : je garde 6 pour l'instant."),
            ('confirmation', 'sans_objectif', {}, 0,
             'Sans objectif : plus de nombre visé. Tes faites, ton essentiel et tes tâches prévues restent affichés.'),
            ('confirmation', 'comprendre_eteint', {}, 0,
             "C'est éteint : plus rien n'est calculé ni gardé sur ton rythme."),
        ])

    def test_cartes_de_palier(self):
        self.verifier([
            ('carte', 'palier.monter', {'N': 5, 'N1': 6, 'tenus': 7}, 0,
             'Ces 10 jours travaillés, tu as fait au moins 5 tâches 7 fois. On passe à 6 ?'),
            ('carte', 'palier.monter', {'N': 1, 'N1': 2, 'tenus': 1}, 0,
             'Ces 10 jours travaillés, tu as fait au moins 1 tâche 1 fois. On passe à 2 ?'),
            ('carte', 'palier.baisser', {'N': 7, 'N_1': 6, 'tenus': 2}, 0,
             'Ces 10 jours travaillés, 7 tâches ou plus : 2 fois. Revenir à 6 pour un temps ?'),
            ('carte', 'palier.premier', {'type': 7}, 0,
             "J'ai 10 jours de toi : ta journée type est 7 tâches. "
             'Ton objectif est encore la valeur par défaut, 5. Le mettre à 7 ?'),
            ('carte', 'palier.journee_type', {'type': 3, 'dit': 4}, 0,
             "J'ai 10 jours de toi : ta journée type est 3 tâches ; "
             "ton objectif est 4, comme tu l'as choisi. Le mettre à 3 ?"),
            ('carte', 'garde_taille', {'med': 25, 'ref': 40}, 0,
             "Tes tâches terminées sont plus courtes qu'au départ (25 min en médiane contre 40) "
             ': je ne propose pas de monter.'),
        ])

    def test_cartes_de_derive(self):
        self.verifier([
            ('carte', 'derive.sous', {'moyenne': 3.4, 'bas': 4, 'haut': 6, 'R': 5, 'm': 4}, 0,
             'Ces 14 jours travaillés : 3,4 tâches par jour, sous ton rythme (4 à 6). '
             'Garder 5, ou descendre à 4 ?'),
            ('carte', 'derive.au_dessus', {'moyenne': 6.9, 'bas': 4, 'haut': 6, 'R': 5, 'm': 6}, 0,
             'Ces 14 jours travaillés : 6,9 tâches par jour, au-dessus de ton rythme (4 à 6). '
             'Garder 5, ou monter à 6 ?'),
            ('carte', 'derive.sous', {'moyenne': 1.5, 'bas': 2, 'haut': 3, 'R': 2, 'm': 1}, 0,
             'Ces 14 jours travaillés : 1,5 tâche par jour, sous ton rythme (2 à 3). '
             'Garder 2, ou descendre à 1 ?'),
        ])

    def test_carte_pause_pour_chaque_type(self):
        base = {'ignorees': 14}
        self.verifier([
            ('carte', 'pause', dict(base, type_pause='plan_matin'), 0,
             "J'ai mis en pause le message du matin : 14 de suite sans être ouverts. Le réactiver ?"),
            ('carte', 'pause', dict(base, type_pause='relance', heure=time(15, 0)), 0,
             "J'ai mis en pause le message de 15 h : 14 de suite sans être ouverts. Le réactiver ?"),
            ('carte', 'pause', dict(base, type_pause='bilan_soir'), 0,
             "J'ai mis en pause le bilan du soir : 14 de suite sans être ouverts. Le réactiver ?"),
            ('carte', 'pause', dict(base, type_pause='revue_semaine', ignorees=15), 0,
             "J'ai mis en pause la revue de la semaine : 15 de suite sans être ouverts. Le réactiver ?"),
        ])

    def test_carte_retour_et_cle_retour(self):
        attendu = 'Tu reviens après 5 jours : 8 tâches attendaient.'
        self.verifier([
            ('carte', 'retour', {'jours': 5, 'taches': 8}, 0, attendu),
            ('retour', 'carte', {'jours': 5, 'taches': 8}, 0, attendu),
            ('carte', 'retour', {'jours': 1, 'taches': 1}, 0, 'Tu reviens après 1 jour : 1 tâche attendait.'),
            ('carte', 'retour', {'jours': 4, 'taches': 0}, 0, ''),
        ])

    def test_boutons(self):
        self.assertEqual(boutons('palier.monter', {'N1': 6}),
                         [('Monter à 6', 'oui'), ('Pas maintenant', 'pas_maintenant')])
        self.assertEqual(boutons('palier.monter', {'N1': 6, 'refus': 3})[-1],
                         ('Garder ce rythme', 'garder_ce_rythme'))
        self.assertEqual(boutons('palier.baisser', {'N': 7, 'N_1': 6}),
                         [('Descendre à 6', 'oui'), ('Garder 7', 'garder')])
        self.assertEqual(boutons('palier.premier', {'type': 7}),
                         [('Monter à 7', 'oui'), ('Garder 5', 'garder')])
        self.assertEqual(boutons('palier.premier', {'type': 3}),
                         [('Descendre à 3', 'oui'), ('Garder 5', 'garder')])
        self.assertEqual(boutons('palier.journee_type', {'type': 3, 'dit': 4}),
                         [('Descendre à 3', 'oui'), ('Pas maintenant', 'pas_maintenant')])
        self.assertEqual(boutons('garde_taille', {}),
                         [('Mes tâches ont changé', 'taches_changees'), ('OK', 'ok')])
        self.assertEqual(boutons('derive.sous', {'R': 5, 'm': 4}),
                         [('Garder 5', 'garder'), ('Descendre à 4', 'passer')])
        self.assertEqual(boutons('derive.au_dessus', {'R': 5, 'm': 6}),
                         [('Garder 5', 'garder'), ('Monter à 6', 'passer')])
        self.assertEqual(boutons('pause', {}), [('Le réactiver', 'reactiver'), ('OK', 'ok')])
        self.assertEqual(boutons('retour', {}),
                         [('Les remettre dans Proposé', 'remettre_dans_propose'),
                          ('Les voir une par une', 'une_par_une')])
        self.assertEqual(boutons('constat', {}), [('Oui', 'oui'), ('Pas maintenant', 'pas_maintenant')])
        self.assertEqual(boutons('constat.information', {}), [('OK', 'ok')])


class BilanTests(Tableau):
    BASE = {'faites': 5, 'objectif': 5, 'ef': 2, 'ep': 2, 'pt': 4, 'pl': 5}

    def test_pousser_atteint(self):
        self.verifier([
            ('bilan', 'texte', dict(self.BASE, mode='pousser'), 0,
             '5 sur 5 · objectif atteint · essentiel fait'),
        ])

    def test_pousser_non_atteint(self):
        d = dict(self.BASE, mode='pousser', faites=3, ef=1)
        self.verifier([('bilan', 'texte', d, 0, '3 sur 5 · essentiel 1 sur 2')])

    def test_tenir(self):
        d = dict(self.BASE, mode='tenir', faites=5, bas=4, haut=6, ef=1)
        self.verifier([('bilan', 'texte', d, 0,
                        '5 sur 5 (ton rythme : 4 à 6) · essentiel 1 sur 2')])

    def test_libre(self):
        self.verifier([
            ('bilan', 'texte', dict(self.BASE, mode='libre', faites=3, ef=0), 0,
             '3 faites · essentiel 0 sur 2'),
            ('bilan', 'texte', dict(self.BASE, mode='libre', faites=1, ep=0), 0,
             '1 faite'),
        ])

    def test_parties_sans_objet_omises(self):
        sans_essentiel = dict(self.BASE, mode='pousser', faites=3, ep=0)
        self.verifier([('bilan', 'texte', sans_essentiel, 0, '3 sur 5')])
        rien_garde = dict(self.BASE, mode='pousser', faites=3, pl=0, pt=0)
        self.verifier([('bilan', 'texte', rien_garde, 0, '3 sur 5 · essentiel 2 sur 2')])

    def test_jour_court(self):
        d = dict(self.BASE, mode='pousser', faites=3, objectif=4, jour_court=True, ef=1)
        self.verifier([('bilan', 'texte', d, 0,
                        '3 sur 4 (jour court : objectif 4) · essentiel 1 sur 2')])

    def test_jamais_x_des_y_gardees(self):
        """R3-001 (choix C-14) — le bilan tient en UNE ligne : « x des y gardées », second chiffre de la même journée,
        n'est plus rendu, quels que soient `pt`/`pl` (servis pour la nuit, jamais montrés)."""
        for mode in ('pousser', 'tenir', 'libre'):
            for pt, pl in ((1, 1), (4, 5), (0, 3)):
                with self.subTest(mode=mode, pt=pt, pl=pl):
                    rendu = texte('bilan', 'texte', dict(self.BASE, mode=mode, bas=4, haut=6, pt=pt, pl=pl))
                    self.assertNotIn('gardée', rendu)
                    self.assertNotIn('\n', rendu)


class ConstatsTests(Tableau):
    """R2-014 — le texte servi d'une carte de constat est la PHRASE suivie de sa QUESTION (textes.md §4.4) : les boutons
    « Oui · Pas maintenant » répondent à une question posée à l'écran. `Cn.question` seule reste rendable."""

    def test_c1(self):
        self.verifier([
            ('constat', 'C1', {}, 0, "Tu finis plus souvent ton essentiel quand il est placé avant midi. "
                                     "Mettre l'essentiel le matin ?"),
            ('constat', 'C1.detail', {'p1': 70, 'p2': 40, 'n1': 31, 'n2': 33}, 0,
             "Fini : 70 % de tes tâches prévues le matin, 40 % de celles d'après 16 h (31 et 33 lignes)."),
            ('constat', 'C1.question', {}, 0, "Mettre l'essentiel le matin ?"),
        ])

    def test_c2_c3_c4(self):
        self.verifier([
            ('constat', 'C2', {'a': 12, 'na': 15, 'b': 6, 'nb': 15}, 0,
             'Essentiel fait 12 fois sur 15 quand il est en tête de ta journée, 6 sur 15 sinon. '
             'Le mettre en tête par défaut ?'),
            ('constat', 'C2.question', {}, 0, 'Le mettre en tête par défaut ?'),
            ('constat', 'C3', {'jour': 4, 'm1': 2.5, 'm2': 4.2}, 0,
             'Vendredi : 2,5 tâches en moyenne, 4,2 les autres jours. En faire un jour court (un de moins) ?'),
            ('constat', 'C3', {'jour': 'Lundi', 'm1': 1.0, 'm2': 4.2}, 0,
             'Lundi : 1,0 tâche en moyenne, 4,2 les autres jours. En faire un jour court (un de moins) ?'),
            ('constat', 'C3.question', {}, 0, 'En faire un jour court (un de moins) ?'),
            ('constat', 'C4', {'p': 6, 'f': 4, 'n': 12, 'f1': 5}, 0,
             'Tu gardes 6 tâches, tu en finis 4 (au milieu de tes 12 dernières journées). Te proposer 5 à garder ?'),
            ('constat', 'C4', {'p': 1, 'f': 1, 'n': 12, 'f1': 2}, 0,
             'Tu gardes 1 tâche, tu en finis 1 (au milieu de tes 12 dernières journées). Te proposer 2 à garder ?'),
            ('constat', 'C4.question', {'f1': 5}, 0, 'Te proposer 5 à garder ?'),
        ])

    def test_c5_information_sans_question(self):
        self.verifier([
            ('constat', 'C5', {'p': 60, 'n': 40, 'h1': 14, 'h2': 16}, 0,
             '60 % de tes 40 tâches finies entre 14 h et 16 h.'),
        ])

    def test_c6_c7(self):
        self.verifier([
            ('constat', 'C6', {'projet': 'Maison', 'ratio': 1.5, 'n': 6}, 0,
             "Tes tâches « Maison » ont pris 1,5 fois leur durée (6 tâches). Corriger leur durée à l'avenir ?"),
            ('constat', 'C6', {'projet': 'secret', 'ratio': 1.5, 'n': 6}, 0,
             "Tes tâches « un projet » ont pris 1,5 fois leur durée (6 tâches). Corriger leur durée à l'avenir ?"),
            ('constat', 'C6.question', {}, 0, "Corriger leur durée à l'avenir ?"),
            ('constat', 'C7', {'n': 4}, 0, '4 tâches reportées 3 fois ou plus. Les revoir maintenant ?'),
            ('constat', 'C7', {'n': 1}, 0, '1 tâche reportée 3 fois ou plus. Les revoir maintenant ?'),
            ('constat', 'C7.question', {}, 0, 'Les revoir maintenant ?'),
        ])

    def test_c8_liste_et_ecran(self):
        self.verifier([
            ('constat', 'C8', {}, 0, "Ton projet prioritaire n'a pas avancé depuis 14 jours. "
                                     "Mettre une de ses tâches dans Proposé demain ?"),
            ('constat', 'C8.ecran', {'projet': 'Polydesign'}, 0,
             "« Polydesign » n'a pas avancé depuis 14 jours. Mettre une de ses tâches dans Proposé demain ?"),
            ('constat', 'C8.question', {}, 0, 'Mettre une de ses tâches dans Proposé demain ?'),
        ])

    def test_chaque_constat_a_action_se_termine_par_sa_question(self):
        """C1-C4 et C6-C8 posent une question (les boutons « Oui » y répondent) ; C5, information, n'en pose aucune."""
        donnees = {'f1': 5, 'projet': 'P', 'n': 3, 'p': 5, 'f': 3, 'a': 1, 'na': 2, 'b': 1, 'nb': 2, 'jour': 4,
                   'm1': 2.0, 'm2': 3.0, 'ratio': 1.5, 'h1': 14, 'h2': 16}
        for code in ('C1', 'C2', 'C3', 'C4', 'C6', 'C7', 'C8'):
            with self.subTest(code=code):
                phrase = texte('constat', code, donnees)
                self.assertTrue(phrase.endswith('?'), phrase)
                self.assertTrue(phrase.endswith(texte('constat', f'{code}.question', donnees)), phrase)
        self.assertNotIn('?', texte('constat', 'C5', donnees))


class RevueTests(Tableau):
    """R2-034 — la tête de la Revue se lit d'un coup d'œil : « Cette semaine : 18 faites (15 la précédente). » (plus
    « 4 tâches en 1 jour (précédente : 9) »)."""
    BASE = {'debut': date(2026, 11, 16), 'fin': date(2026, 11, 20), 'faites': 18, 'jours': 5, 'prec': 15,
            'oa': 3, 'e': 4, 'je': 5, 'pt': 14, 'pl': 18, 'non_travailles': 0, 'mode': 'pousser'}

    def test_complete(self):
        self.verifier([('revue', 'entete', self.BASE, 0,
                        'Cette semaine : 18 faites (15 la précédente). '
                        'Essentiel 4 sur 5.')])

    def test_sans_semaine_precedente(self):
        d = dict(self.BASE, prec=None)
        self.verifier([('revue', 'entete', d, 0,
                        'Cette semaine : 18 faites. '
                        'Essentiel 4 sur 5.')])

    def test_libre_sans_objectif_atteint(self):
        d = dict(self.BASE, mode='libre', oa=None)
        self.verifier([('revue', 'entete', d, 0,
                        'Cette semaine : 18 faites (15 la précédente). '
                        'Essentiel 4 sur 5.')])

    def test_parties_sans_objet_omises_et_accords(self):
        d = dict(self.BASE, faites=1, jours=1, oa=1, je=0, pl=0, prec=None, non_travailles=1)
        self.verifier([('revue', 'entete', d, 0,
                        'Cette semaine : 1 faite. Jour non travaillé : 1.')])
        d = dict(d, non_travailles=2)
        self.assertTrue(texte('revue', 'entete', d).endswith('Jours non travaillés : 2.'))

    def test_semaine_deja_passee_garde_ses_dates(self):
        """Une revue demandée pour une AUTRE semaine (`courante` faux) ne se dit jamais « cette semaine »."""
        d = dict(self.BASE, courante=False)
        self.verifier([('revue', 'entete', d, 0,
                        'Du lun. 16 au ven. 20 : 18 faites (15 la précédente). '
                        'Essentiel 4 sur 5.')])

    def test_jamais_objectif_atteint_ni_gardees(self):
        """R3-001, R3-003 (choix C-14, C-16) — la tête de la Revue ne dit ni « Objectif atteint X jours sur N » ni
        « x des y gardées », quels que soient les nombres passés."""
        rendu = texte('revue', 'entete', dict(self.BASE, oa=0, jours=1, pt=20, pl=24))
        self.assertEqual(rendu, 'Cette semaine : 18 faites (15 la précédente). Essentiel 4 sur 5.')

    def test_semaine_courte(self):
        d = dict(self.BASE, semaine_courte=True)
        self.verifier([('revue', 'entete', d, 0, 'Semaine courte, on reprend lundi.')])


class ContratEtLexiqueTests(unittest.TestCase):
    # Mots interdits de textes.md §1 (colonne « Interdits ») qui ne peuvent jamais se lire dans
    # une phrase de ces gabarits, plus les marqueurs de récompense, de reproche, de points et de série.
    INTERDITS = (
        'mes tâches', 'ma journée', 'jour prévu', 'important', 'focus', 'épingl', 'plan proposé',
        'décharg', 'boîte de réception', 'inbox', 'à décider', 'en retard', 'jour ouvré', 'jours ouvrés',
        'ouvré', 'plan tenu', 'journée réussie', 'journée ratée', 'palier', 'score', 'série', 'deadline',
        'estimation', 'capacité', 'coach', 'urgent', 'corbeille', 'replanifi', 'repousser', 'cadrage',
        'relance', 'bravo', 'félicit', 'points', 'jeton', 'bloquée', '!', 'vous', 'votre', 'vos ',
    )
    MOTS_ENTIERS = ('ia', 'agent', 'tenir', 'pousser', 'zone', 'tâche privée')

    def test_aucun_mot_interdit_dans_aucun_gabarit(self):
        for phrase in toutes_les_phrases():
            bas = phrase.lower()
            for mot in self.INTERDITS:
                with self.subTest(phrase=phrase, mot=mot):
                    self.assertNotIn(mot, bas)
            for mot in self.MOTS_ENTIERS:
                with self.subTest(phrase=phrase, mot=mot):
                    self.assertIsNone(re.search(r'\b' + re.escape(mot) + r'\b', bas))

    def test_aucun_chiffre_tape_dans_un_gabarit(self):
        for phrase in toutes_les_phrases():
            with self.subTest(phrase=phrase):
                self.assertIsNone(re.search(r'\d', re.sub(r'\{[^}]*\}', '', phrase)))

    def test_tutoiement_seul(self):
        for phrase in toutes_les_phrases():
            self.assertIsNone(re.search(r"\b(vous|votre|vos|nous|notre)\b", phrase.lower()), phrase)

    def test_les_chiffres_rendus_viennent_des_donnees_ou_des_constantes(self):
        donnees = {
            'prevues': 811, 'proposees': 823, 'objectif': 829, 'bas': 839, 'haut': 853, 'faites': 857,
            'n': 859, 'n_autres': 863, 'restes': 877, 'jours': 881, 'projets': 883, 'taches': 887,
            'N': 907, 'N1': 911, 'N_1': 919, 'tenus': 929, 'type': 937, 'dit': 941, 'med': 947,
            'ref': 953, 'moyenne': 967.5, 'R': 971, 'm': 977, 'ignorees': 983,
            'ef': 701, 'ep': 709, 'pt': 719, 'pl': 727, 'p1': 733, 'p2': 739, 'n1': 743, 'n2': 751,
            'a': 757, 'na': 761, 'b': 769, 'nb': 773, 'm1': 787.5, 'm2': 797.5, 'p': 601, 'f': 607,
            'f1': 613, 'h1': 617, 'h2': 619, 'ratio': 631.5, 'oa': 641, 'e': 643, 'je': 647, 'prec': 653,
            'non_travailles': 659, 'jour': 2, 'heure': time(13, 47), 'mode': 'pousser',
            'debut': date(2026, 11, 16), 'fin': date(2026, 11, 20), 'projet': 'P', 'titre': 'T',
            'avec_titres': True, 'type_pause': 'relance', 'refus': 4,
        }
        permis = {str(v) for v in CONSTANTES.values()}
        permis.update({'13', '47', '16', '20'})  # heure 13 h 47 et dates du 16 et du 20 de la donnée
        for v in donnees.values():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                permis.update(re.findall(r'\d+', str(v)))
        cas = self._cas_complets()
        for type_, cle, var in cas:
            with self.subTest(type=type_, cle=cle, variante=var):
                sortie = texte(type_, cle, donnees, var, nom_pour)
                for nombre in re.findall(r'\d+', sortie):
                    self.assertIn(nombre, permis, f'{nombre} tapé en dur dans : {sortie}')

    def _cas_complets(self):
        cas = []
        for cle in gabarits._NOTIFICATIONS:
            cas += [('notification', cle, v) for v in range(3)]
        cas += [('notification', cle, 0) for cle in gabarits._TITRES]
        cas += [('carte', cle, 0) for cle in ('palier.monter', 'palier.baisser', 'palier.premier',
                                              'palier.journee_type', 'garde_taille', 'derive.sous',
                                              'derive.au_dessus', 'pause', 'retour')]
        cas += [('confirmation', cle, 0) for cle in gabarits._CONFIRMATIONS]
        cas += [('constat', cle, 0) for cle in gabarits._CONSTATS]
        cas += [('bilan', 'texte', 0), ('revue', 'entete', 0)]
        return [c for c in cas if c[1] not in ('rappel.plusieurs', 'soir.pousser.sans_reste')]

    def test_variable_manquante_leve_une_erreur(self):
        with self.assertRaises(KeyError):
            texte('notification', 'matin.libre', {}, 0)

    def test_type_inconnu(self):
        with self.assertRaises(ValueError):
            texte('inconnu', 'x', {}, 0)


if __name__ == '__main__':
    unittest.main()
