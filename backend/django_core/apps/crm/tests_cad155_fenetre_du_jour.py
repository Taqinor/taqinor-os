"""CAD155 — pendant le Ramadan, l'appel du soir n'existe pas : le panneau le DIT.

Contrat servi : ``apps/crm/contract_samples/panneau_appel.json``, bloc
``fenetre_du_jour``.

Le garde-fou de la tâche : la fenêtre affichée est LUE DU MOTEUR
(``apps.crm.horaires.fenetre_du_jour``, celle qu'il applique aux touches), et
jamais recopiée — sinon l'écran divergerait au premier réglage de la société.
Ces tests le prouvent de deux façons : en simulant le moteur (le panneau rend
EXACTEMENT ce qu'il reçoit, rien de plus), puis en base avec une période de
Ramadan SAISIE (exécuté par la CI).
"""
import datetime
import json
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from apps.crm import panneau_appel as panneau
from apps.crm.models import Lead
from apps.parametres.models import CompanyProfile

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'panneau_appel.json').read_text(encoding='utf-8'))

#: Un mercredi (jour ouvré par défaut), en plein Ramadan 1448 (plage
#: 2027-02-08 → 2027-03-08 de ``apps.ventes.ramadan.RAMADAN_PLAGES``), et un
#: vendredi ordinaire. L'instant est AWARE : le jour est lu à Casablanca.
MERCREDI_RAMADAN = datetime.datetime(2027, 2, 17, 11, 0,
                                     tzinfo=datetime.timezone.utc)
VENDREDI = datetime.datetime(2026, 9, 25, 11, 0, tzinfo=datetime.timezone.utc)


def _servie(fenetre, ramadan, maintenant=MERCREDI_RAMADAN):
    with mock.patch('apps.crm.horaires.fenetre_du_jour',
                    return_value=fenetre) as moteur, \
            mock.patch('apps.crm.horaires.est_en_ramadan',
                       return_value=ramadan):
        servie = panneau.fenetre_du_jour_servie(
            Lead(nom='Prospect'), maintenant=maintenant)
    return servie, moteur


class LePanneauRendCeQueLeMoteurApplique(SimpleTestCase):
    def test_ramadan_saisi_10h_14h_sans_soir(self):
        servie, moteur = _servie(
            (datetime.time(10, 0), datetime.time(14, 0), None), True)
        self.assertEqual(servie, {
            'date': '2027-02-17', 'appelable': True, 'debut': '10:00',
            'fin': '14:00', 'pause': None, 'ramadan': True})
        # Le moteur est interrogé pour un APPEL, sur le jour de Casablanca.
        args, kwargs = moteur.call_args
        self.assertEqual(args[0], datetime.date(2027, 2, 17))
        self.assertEqual(kwargs.get('canal'), 'appel')

    def test_vendredi_la_pause_de_la_priere_est_servie(self):
        servie, _moteur = _servie(
            (datetime.time(9, 0), datetime.time(20, 0),
             (datetime.time(11, 30), datetime.time(15, 0))),
            False, maintenant=VENDREDI)
        self.assertEqual(servie['pause'], {'debut': '11:30', 'fin': '15:00'})
        self.assertFalse(servie['ramadan'])

    def test_un_jour_non_ouvre_n_est_pas_appelable(self):
        servie, _moteur = _servie(None, False)
        self.assertFalse(servie['appelable'])
        self.assertIsNone(servie['debut'])
        self.assertIsNone(servie['fin'])

    def test_un_moteur_illisible_ne_sert_AUCUN_horaire_suppose(self):
        with mock.patch('apps.crm.horaires.fenetre_du_jour',
                        side_effect=RuntimeError('profil illisible')):
            self.assertIsNone(panneau.fenetre_du_jour_servie(
                Lead(nom='Prospect'), maintenant=MERCREDI_RAMADAN))

    def test_la_forme_est_celle_du_contrat(self):
        servie, _moteur = _servie(
            (datetime.time(10, 0), datetime.time(14, 0), None), True)
        for variante in ('exemple', 'exemple_sans_cadence_active',
                         'exemple_tout_repondu', 'exemple_ramadan'):
            self.assertEqual(set(servie),
                             set(CONTRAT[variante]['fenetre_du_jour']),
                             variante)
        self.assertEqual(servie, CONTRAT['exemple_ramadan']['fenetre_du_jour'])

    def test_aucune_heure_n_est_ecrite_dans_le_module(self):
        """Le garde-fou, lu dans le code : le panneau ne porte aucune heure
        littérale — elles viennent toutes du moteur."""
        source = Path(panneau.__file__).read_text(encoding='utf-8')
        self.assertNotIn('datetime.time(', source)


class LaPeriodeSaisieEnBase(TestCase):
    """Chemin complet : une société qui a SAISI son Ramadan et sa fenêtre."""

    def setUp(self):
        self.company = Company.objects.create(slug='cad155', nom='cad155')
        CompanyProfile.objects.create(
            company=self.company,
            ramadan_debut=datetime.date(2027, 2, 8),
            ramadan_fin=datetime.date(2027, 3, 8),
            ramadan_appel_debut=datetime.time(10, 0),
            ramadan_appel_fin=datetime.time(14, 0))
        self.lead = Lead.objects.create(company=self.company, nom='Prospect')

    def test_en_ramadan_le_panneau_annonce_10h_14h_et_aucun_soir(self):
        servie = panneau.fenetre_du_jour_servie(
            self.lead, maintenant=MERCREDI_RAMADAN)
        self.assertEqual(servie['debut'], '10:00')
        self.assertEqual(servie['fin'], '14:00')
        self.assertIsNone(servie['pause'])
        self.assertTrue(servie['ramadan'])

    def test_hors_periode_la_fenetre_ordinaire_revient(self):
        servie = panneau.fenetre_du_jour_servie(
            self.lead, maintenant=VENDREDI)
        self.assertFalse(servie['ramadan'])
        self.assertEqual(servie['pause'], {'debut': '11:30', 'fin': '15:00'})
