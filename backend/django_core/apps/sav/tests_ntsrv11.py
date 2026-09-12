"""NTSRV11 — Pauses HORAIRES ouvrées configurables (étend XSAV5).

Critère d'acceptation : un ticket créé un VENDREDI 17 h avec un SLA de 4 h et
des horaires 8h-18h n'échoit PAS le vendredi à 21 h — le reliquat repart à
l'ouverture du lundi. (XSAV5 n'excluait que les JOURS, jamais la fenêtre
intra-journée.)

Arithmétique exacte de l'exemple : vendredi 17h→18h consomme 1 h, les 3 h
restantes courent lundi dès 8 h → **lundi 11 h**. Le texte du plan illustre
« lundi 9h » ; l'invariant vérifié ici est celui qui compte — l'échéance
tombe le jour ouvré suivant, DANS la fenêtre, jamais à 21 h le vendredi.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_ntsrv11 -v 2
"""
from datetime import date, datetime

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import SavSlaSettings, Ticket
from apps.sav.selectors import (
    ajouter_heures_ouvrees, echeance_sla_heures_ouvrees,
)
from apps.sav.services import compute_sla_due_at

HORAIRES = {'jours': [0, 1, 2, 3, 4], 'debut': '08:00', 'fin': '18:00'}

# 2026-06-05 est un VENDREDI ; 2026-06-08 le lundi suivant.
VENDREDI_17H = datetime(2026, 6, 5, 17, 0)


class NTSRV11HeuresOuvreesTest(TestCase):
    def test_vendredi_17h_plus_4h_bascule_au_lundi(self):
        echeance = ajouter_heures_ouvrees(VENDREDI_17H, 4, HORAIRES)
        self.assertNotEqual(echeance, datetime(2026, 6, 5, 21, 0),
                            'jamais 21 h un vendredi (le trou XSAV5)')
        self.assertEqual(echeance.date(), date(2026, 6, 8), 'lundi')
        self.assertEqual(echeance, datetime(2026, 6, 8, 11, 0))

    def test_dans_la_journee_rien_ne_bascule(self):
        self.assertEqual(
            ajouter_heures_ouvrees(datetime(2026, 6, 5, 9, 0), 2, HORAIRES),
            datetime(2026, 6, 5, 11, 0))

    def test_depart_avant_ouverture_demarre_a_l_ouverture(self):
        self.assertEqual(
            ajouter_heures_ouvrees(datetime(2026, 6, 5, 6, 0), 1, HORAIRES),
            datetime(2026, 6, 5, 9, 0))

    def test_depart_apres_fermeture_demarre_le_jour_suivant(self):
        self.assertEqual(
            ajouter_heures_ouvrees(datetime(2026, 6, 4, 19, 0), 1, HORAIRES),
            datetime(2026, 6, 5, 9, 0))

    def test_le_week_end_est_saute(self):
        self.assertEqual(
            ajouter_heures_ouvrees(datetime(2026, 6, 6, 10, 0), 1, HORAIRES),
            datetime(2026, 6, 8, 9, 0))

    def test_sla_long_traverse_plusieurs_jours(self):
        # 25 h ouvrées à partir du lundi 8 h : 10 h lundi, 10 h mardi, 5 h
        # mercredi → mercredi 13 h.
        self.assertEqual(
            ajouter_heures_ouvrees(datetime(2026, 6, 8, 8, 0), 25, HORAIRES),
            datetime(2026, 6, 10, 13, 0))

    def test_zero_heure_ne_bouge_pas(self):
        self.assertEqual(
            ajouter_heures_ouvrees(VENDREDI_17H, 0, HORAIRES), VENDREDI_17H)

    def test_horaires_personnalises(self):
        horaires = {'jours': [0, 1, 2, 3, 4, 5], 'debut': '09:00',
                    'fin': '13:00'}
        # Samedi ouvré ici : vendredi 12 h + 3 h → 13 h vendredi (1 h) puis
        # samedi 9 h + 2 h = 11 h.
        self.assertEqual(
            ajouter_heures_ouvrees(datetime(2026, 6, 5, 12, 0), 3, horaires),
            datetime(2026, 6, 6, 11, 0))


class NTSRV11ReglagesTest(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sav-ntsrv11', defaults={'nom': 'Sav Co NTSRV11'})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='NTSRV11')

    def test_defaut_off_et_horaires_par_defaut(self):
        reglage = SavSlaSettings.get(self.company)
        self.assertFalse(reglage.sla_heures_ouvrees_actif)
        self.assertIsNone(reglage.horaires_ouvres)
        self.assertEqual(reglage.horaires_effectifs(), HORAIRES)

    def test_selector_renvoie_none_quand_le_flag_est_off(self):
        self.assertIsNone(
            echeance_sla_heures_ouvrees(self.company, VENDREDI_17H, 4))

    def test_selector_calcule_quand_le_flag_est_on(self):
        reglage = SavSlaSettings.get(self.company)
        reglage.sla_heures_ouvrees_actif = True
        reglage.save(update_fields=['sla_heures_ouvrees_actif'])
        self.assertEqual(
            echeance_sla_heures_ouvrees(self.company, VENDREDI_17H, 4),
            datetime(2026, 6, 8, 11, 0))

    def test_configuration_partielle_retombe_sur_le_defaut(self):
        reglage = SavSlaSettings.get(self.company)
        for brut in ({}, {'jours': []}, {'debut': 'nimporte'},
                     {'debut': '20:00', 'fin': '08:00'}, None, 'texte'):
            reglage.horaires_ouvres = brut
            self.assertEqual(reglage.horaires_effectifs(), HORAIRES, brut)

    def test_heures_for_absent_par_defaut(self):
        reglage = SavSlaSettings.get(self.company)
        self.assertIsNone(reglage.heures_for(Ticket.Priorite.URGENTE))
        reglage.sla_par_priorite = {'urgente': {'resolution_heures': 4}}
        self.assertEqual(reglage.heures_for(Ticket.Priorite.URGENTE), 4.0)
        self.assertIsNone(reglage.heures_for(Ticket.Priorite.NORMALE))

    def test_compute_sla_due_at_inchange_sans_configuration_horaire(self):
        reglage = SavSlaSettings.get(self.company)
        reglage.sla_breach_enabled = True
        reglage.sla_resolution_days = 7
        reglage.save()
        self.assertEqual(
            compute_sla_due_at(self.company, self.client_obj,
                               Ticket.Priorite.NORMALE, date(2026, 6, 5)),
            date(2026, 6, 12))

    def test_compute_sla_due_at_en_heures_ouvrees(self):
        reglage = SavSlaSettings.get(self.company)
        reglage.sla_breach_enabled = True
        reglage.sla_heures_ouvrees_actif = True
        reglage.sla_par_priorite = {'urgente': {'resolution_heures': 4}}
        reglage.save()
        echeance = compute_sla_due_at(
            self.company, self.client_obj, Ticket.Priorite.URGENTE,
            date(2026, 6, 5), depart=VENDREDI_17H)
        self.assertEqual(echeance, date(2026, 6, 8),
                         'le reliquat bascule au lundi, pas 21 h le vendredi')
