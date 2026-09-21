"""AOF13 — statuts étendus, transitions déclaratives, service unique, 2 événements.

Ce que ce test verrouille :
  1. les SIX valeurs historiques survivent à l'élargissement (aucune migration
     de données, aucune ligne existante invalidée) ;
  2. ``TRANSITIONS_AO`` couvre TOUS les statuts et ne cible que des statuts
     valides ; les trois issues sont terminales ;
  3. ``changer_statut_ao`` est le SEUL point de mutation : écrire
     ``ao.statut = …; ao.save()`` lève ;
  4. une transition interdite répond 400 avec un message FRANÇAIS ;
  5. ``ao_depose`` et ``ao_gagne`` sont émis par le SERVICE (jamais par un
     modèle) et ont chacun un abonné RÉEL qui avance le lead lié ;
  6. aucun signal ``ao_*`` orphelin n'est déclaré (``core.event_coverage``).

Run :
    python manage.py test apps.ao.tests.test_statuts_ao -v2
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import services
from apps.ao.models import AppelOffre
from apps.crm import stages
from apps.crm.models import Lead
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company
from core import events

User = get_user_model()

S = AppelOffre.Statut

STATUTS_HISTORIQUES = (
    'identifie', 'en_preparation', 'depose', 'gagne', 'perdu', 'abandonne',
)


class TestStatutsEtTransitions(SimpleTestCase):
    def test_les_six_valeurs_historiques_survivent(self):
        valeurs = {v for v, _ in S.choices}
        for historique in STATUTS_HISTORIQUES:
            self.assertIn(historique, valeurs, historique)

    def test_le_cycle_complet_est_declare(self):
        valeurs = {v for v, _ in S.choices}
        for attendu in ('analyse_cps', 'releve', 'etude', 'chiffrage',
                        'dossier', 'pret_a_deposer'):
            self.assertIn(attendu, valeurs, attendu)

    def test_table_de_transitions_complete_et_close(self):
        valeurs = {v for v, _ in S.choices}
        self.assertEqual(set(services.TRANSITIONS_AO), valeurs)
        for depart, cibles in services.TRANSITIONS_AO.items():
            for cible in cibles:
                self.assertIn(cible, valeurs, f'{depart} → {cible}')

    def test_les_issues_sont_terminales(self):
        for terminal in (S.GAGNE, S.PERDU, S.ABANDONNE):
            self.assertEqual(services.transitions_possibles(terminal), ())

    def test_statut_historique_ne_coince_aucune_ligne(self):
        """``en_preparation`` rejoint toute étape du nouveau cycle."""
        cibles = services.transitions_possibles(S.EN_PREPARATION)
        for attendu in (S.ANALYSE_CPS, S.RELEVE, S.ETUDE, S.CHIFFRAGE,
                        S.DOSSIER, S.PRET_A_DEPOSER, S.DEPOSE):
            self.assertIn(attendu, cibles, attendu)


class TestServiceSeulPointDeMutation(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF13 Co', slug='aof13-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-13-1', objet='Cycle')

    def test_mutation_directe_refusee(self):
        self.ao.statut = S.DEPOSE
        with self.assertRaises(ValidationError) as ctx:
            self.ao.save()
        self.assertIn('statut', ctx.exception.message_dict)

    def test_mutation_directe_refusee_meme_avec_update_fields(self):
        self.ao.statut = S.GAGNE
        with self.assertRaises(ValidationError):
            self.ao.save(update_fields=['statut'])

    def test_sauvegarde_sans_changement_de_statut_reste_libre(self):
        self.ao.objet = 'Cycle (modifié)'
        self.ao.save()
        self.ao.refresh_from_db()
        self.assertEqual(self.ao.objet, 'Cycle (modifié)')

    def test_creation_a_n_importe_quelle_etape_reste_libre(self):
        """Un import d'historique doit pouvoir naître ``depose``."""
        autre = AppelOffre.objects.create(
            company=self.company, reference='AO-13-2', objet='Import',
            statut=S.DEPOSE)
        self.assertEqual(autre.statut, S.DEPOSE)

    def test_service_applique_la_transition(self):
        services.changer_statut_ao(self.ao, S.ANALYSE_CPS)
        self.ao.refresh_from_db()
        self.assertEqual(self.ao.statut, S.ANALYSE_CPS)

    def test_transition_interdite_leve(self):
        with self.assertRaises(ValidationError) as ctx:
            services.changer_statut_ao(self.ao, S.GAGNE)
        message = ' '.join(ctx.exception.message_dict['statut'])
        self.assertIn('Transition interdite', message)
        self.assertIn('Identifié', message)

    def test_statut_inconnu_leve(self):
        with self.assertRaises(ValidationError) as ctx:
            services.changer_statut_ao(self.ao, 'pas_un_statut')
        self.assertIn('Statut inconnu',
                      ' '.join(ctx.exception.message_dict['statut']))

    def test_transition_vers_le_meme_statut_est_un_no_op(self):
        retour = services.changer_statut_ao(self.ao, S.IDENTIFIE)
        self.assertEqual(retour.statut, S.IDENTIFIE)

    def test_changement_journalise_au_chatter_records(self):
        from apps.records.services import chatter_qs
        services.changer_statut_ao(self.ao, S.ANALYSE_CPS,
                                   motif='CPS reçu ce matin')
        entrees = list(chatter_qs(self.ao, company=self.company))
        self.assertEqual(len(entrees), 1)
        self.assertEqual(entrees[0].field, 'statut')
        self.assertEqual(entrees[0].body, 'CPS reçu ce matin')


class TestEvenementsM6(TestCase):
    """Deux signaux, deux abonnés RÉELS — jamais un signal « pour plus tard »."""

    def setUp(self):
        self.company = Company.objects.create(nom='AOF13 Ev', slug='aof13-ev')
        self.lead = Lead.objects.create(
            company=self.company, nom='Établissement', stage=stages.NEW)
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-13-EV', objet='Événements',
            statut=S.PRET_A_DEPOSER, lead_id=self.lead.id)

    def test_seuls_deux_signaux_ao_sont_declares(self):
        noms = [n for n in dir(events) if n.startswith('ao_')]
        self.assertEqual(sorted(noms), ['ao_depose', 'ao_gagne'])

    def test_chaque_signal_ao_a_un_abonne_reel(self):
        for signal in (events.ao_depose, events.ao_gagne):
            self.assertTrue(signal.receivers, signal)

    def test_depot_emet_et_avance_le_lead(self):
        recus = []
        events.ao_depose.connect(
            lambda **kw: recus.append(kw), dispatch_uid='aof13-test-depose',
            weak=False)
        try:
            services.changer_statut_ao(self.ao, S.DEPOSE)
        finally:
            events.ao_depose.disconnect(dispatch_uid='aof13-test-depose')
        self.assertEqual(len(recus), 1)
        self.assertEqual(recus[0]['ancien_statut'], S.PRET_A_DEPOSER)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.QUOTE_SENT)

    def test_attribution_emet_et_avance_le_lead(self):
        services.changer_statut_ao(self.ao, S.DEPOSE)
        services.changer_statut_ao(self.ao, S.GAGNE)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.SIGNED)

    def test_lead_perdu_n_est_jamais_avance(self):
        self.lead.perdu = True
        self.lead.save(update_fields=['perdu'])
        services.changer_statut_ao(self.ao, S.DEPOSE)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.NEW)

    def test_ao_sans_lead_ne_casse_rien(self):
        sans_lead = AppelOffre.objects.create(
            company=self.company, reference='AO-13-NL', objet='Sans lead',
            statut=S.PRET_A_DEPOSER)
        services.changer_statut_ao(sans_lead, S.DEPOSE)
        sans_lead.refresh_from_db()
        self.assertEqual(sans_lead.statut, S.DEPOSE)


class TestApiChangerStatut(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF13 API', slug='aof13-api')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='aof13_dir', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-13-API', objet='API')
        self.url = f'/api/django/ao/appels-offres/{self.ao.id}/changer-statut/'

    def test_transition_valide_repond_200(self):
        r = self.api.post(self.url, {'statut': 'analyse_cps'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['statut'], 'analyse_cps')

    def test_transition_interdite_repond_400_en_francais(self):
        r = self.api.post(self.url, {'statut': 'gagne'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        message = ' '.join(r.data['statut'])
        self.assertIn('Transition interdite', message)
        self.assertIn('atteignables', message)

    def test_endpoint_transitions_liste_les_cibles(self):
        url = f'/api/django/ao/appels-offres/{self.ao.id}/transitions/'
        r = self.api.get(url)
        self.assertEqual(r.status_code, 200, r.data)
        valeurs = [t['valeur'] for t in r.data['transitions']]
        self.assertIn('analyse_cps', valeurs)
        self.assertNotIn('gagne', valeurs)
