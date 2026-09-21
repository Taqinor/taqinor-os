"""AOF32 — le résultat d'ouverture des plis, enfin exploité.

``ResultatAO`` existait et n'était JAMAIS écrit : l'app s'arrêtait au dépôt,
alors que la valeur récurrente est en AVAL — classement, attributaire, prix du
moins-disant, motif de perte. C'est cette donnée qui alimentera la bibliothèque
de prix et le KPI de taux de réussite.

Quatre invariants :
  1. le taux de réussite est CALCULÉ, jamais saisi ;
  2. un AO perdu enregistre son ÉCART de prix (en MAD et en %) ;
  3. la transition ``depose → gagne|perdu`` passe PAR LE SERVICE de statut —
     jamais une mutation directe — donc ``ao_gagne`` est émis ;
  4. aucune permission élargie : la surface reste ``ao_voir``/``ao_gerer``.

Run :
    python manage.py test apps.ao.tests.test_resultat_ao -v2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import services
from apps.ao.models import AppelOffre, ResultatAO
from apps.roles.models import COMMERCIAL_PERMISSIONS, DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company
from core import events

User = get_user_model()

URL = '/api/django/ao/resultats-ao/'


class BaseResultat(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF32 Co', slug='aof32-co')

    def _ao(self, reference, statut=AppelOffre.Statut.DEPOSE):
        return AppelOffre.objects.create(
            company=self.company, reference=reference, objet='Résultat',
            statut=statut)


class TestEnregistrementDuResultat(BaseResultat):
    def test_gagne_fait_suivre_le_statut(self):
        ao = self._ao('AO-32-G')
        services.enregistrer_resultat_ao(
            ao, issue=ResultatAO.Issue.GAGNE,
            date_ouverture=datetime.date(2026, 3, 10), nombre_plis=5,
            notre_rang=1, notre_prix=Decimal('4200000.00'),
            prix_gagnant=Decimal('4200000.00'))
        ao.refresh_from_db()
        self.assertEqual(ao.statut, AppelOffre.Statut.GAGNE)

    def test_perdu_fait_suivre_le_statut_et_enregistre_l_ecart(self):
        ao = self._ao('AO-32-P')
        resultat = services.enregistrer_resultat_ao(
            ao, issue=ResultatAO.Issue.PERDU,
            notre_prix=Decimal('4380000.00'),
            prix_gagnant=Decimal('4200000.00'),
            motif='Moins-disant plus agressif sur la pose')
        ao.refresh_from_db()
        self.assertEqual(ao.statut, AppelOffre.Statut.PERDU)
        self.assertEqual(resultat.ecart_prix, Decimal('180000.00'))
        self.assertEqual(resultat.ecart_prix_pct, Decimal('4.29'))

    def test_infructueux_ne_change_pas_le_statut(self):
        """Ni gagné ni perdu : le dossier est sans suite du fait de l'acheteur."""
        ao = self._ao('AO-32-I')
        services.enregistrer_resultat_ao(
            ao, issue=ResultatAO.Issue.INFRUCTUEUX)
        ao.refresh_from_db()
        self.assertEqual(ao.statut, AppelOffre.Statut.DEPOSE)

    def test_le_classement_complet_est_conserve(self):
        ao = self._ao('AO-32-C')
        classement = [
            {'rang': 1, 'soumissionnaire': 'Concurrent A',
             'montant': 4200000.0},
            {'rang': 2, 'soumissionnaire': 'Nous', 'montant': 4380000.0},
        ]
        resultat = services.enregistrer_resultat_ao(
            ao, issue=ResultatAO.Issue.PERDU, classement=classement,
            notre_rang=2, nombre_plis=2)
        resultat.refresh_from_db()
        self.assertEqual(resultat.classement[0]['soumissionnaire'],
                         'Concurrent A')
        self.assertEqual(resultat.notre_rang, 2)

    def test_enregistrement_idempotent(self):
        ao = self._ao('AO-32-ID')
        services.enregistrer_resultat_ao(
            ao, issue=ResultatAO.Issue.PERDU, nombre_plis=3)
        services.enregistrer_resultat_ao(
            ao, issue=ResultatAO.Issue.PERDU, nombre_plis=4)
        self.assertEqual(
            ResultatAO.objects.filter(appel_offre=ao).count(), 1)
        ao.resultat.refresh_from_db()
        self.assertEqual(ao.resultat.nombre_plis, 4)

    def test_issue_inconnue_refusee(self):
        ao = self._ao('AO-32-X')
        with self.assertRaises(ValidationError) as ctx:
            services.enregistrer_resultat_ao(ao, issue='peut_etre')
        self.assertIn('issue', ctx.exception.message_dict)

    def test_transition_interdite_refusee(self):
        """Un AO encore ``identifie`` ne peut pas devenir « gagné »."""
        ao = self._ao('AO-32-T', statut=AppelOffre.Statut.IDENTIFIE)
        with self.assertRaises(ValidationError) as ctx:
            services.enregistrer_resultat_ao(
                ao, issue=ResultatAO.Issue.GAGNE)
        self.assertIn('statut', ctx.exception.message_dict)

    def test_le_statut_n_est_jamais_mute_directement(self):
        """Le service de statut est le SEUL chemin : ``ao_gagne`` est émis."""
        ao = self._ao('AO-32-E')
        recus = []
        events.ao_gagne.connect(
            lambda **kw: recus.append(kw), dispatch_uid='aof32-test',
            weak=False)
        try:
            services.enregistrer_resultat_ao(
                ao, issue=ResultatAO.Issue.GAGNE)
        finally:
            events.ao_gagne.disconnect(dispatch_uid='aof32-test')
        self.assertEqual(len(recus), 1)
        self.assertEqual(recus[0]['ancien_statut'], AppelOffre.Statut.DEPOSE)


class TestTauxDeReussiteCalcule(BaseResultat):
    def test_le_taux_est_calcule_jamais_saisi(self):
        for i in range(3):
            services.enregistrer_resultat_ao(
                self._ao(f'AO-32-W{i}'), issue=ResultatAO.Issue.GAGNE)
        services.enregistrer_resultat_ao(
            self._ao('AO-32-L0'), issue=ResultatAO.Issue.PERDU)
        stats = services.taux_reussite_ao(self.company)
        self.assertEqual(stats['gagnes'], 3)
        self.assertEqual(stats['perdus'], 1)
        self.assertEqual(stats['taux_reussite_pct'], Decimal('75.00'))

    def test_aucun_champ_de_taux_stocke(self):
        noms = {f.name for f in ResultatAO._meta.local_fields}
        for interdit in ('taux', 'taux_reussite', 'taux_reussite_pct'):
            self.assertNotIn(interdit, noms, interdit)

    def test_les_infructueux_ne_comptent_pas(self):
        services.enregistrer_resultat_ao(
            self._ao('AO-32-W'), issue=ResultatAO.Issue.GAGNE)
        services.enregistrer_resultat_ao(
            self._ao('AO-32-N'), issue=ResultatAO.Issue.INFRUCTUEUX)
        stats = services.taux_reussite_ao(self.company)
        self.assertEqual(stats['total_decides'], 1)
        self.assertEqual(stats['total_resultats'], 2)

    def test_taux_scope_societe(self):
        autre = Company.objects.create(nom='AOF32 X', slug='aof32-x')
        services.enregistrer_resultat_ao(
            self._ao('AO-32-S'), issue=ResultatAO.Issue.GAGNE)
        self.assertEqual(services.taux_reussite_ao(autre)['total_resultats'],
                         0)


class TestApiResultat(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF32 API', slug='aof32-api')
        self.role_dir = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='aof32_dir', password='x', company=self.company,
            role=self.role_dir)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-32-API', objet='API',
            statut=AppelOffre.Statut.DEPOSE)

    def test_enregistrer_via_l_api(self):
        r = self.api.post(f'{URL}enregistrer/', {
            'appel_offre': self.ao.id, 'issue': 'perdu',
            'date_ouverture': '2026-03-10', 'nombre_plis': 4, 'notre_rang': 2,
            'notre_prix': '4380000.00', 'prix_gagnant': '4200000.00',
            'motif': 'Moins-disant plus agressif',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['ecart_prix'], '180000.00')
        self.assertEqual(r.data['ecart_prix_pct'], '4.29')
        self.ao.refresh_from_db()
        self.assertEqual(self.ao.statut, AppelOffre.Statut.PERDU)

    def test_ao_d_une_autre_societe_refuse(self):
        autre = Company.objects.create(nom='AOF32 Y', slug='aof32-y')
        etranger = AppelOffre.objects.create(
            company=autre, reference='AO-32-Y', objet='Y',
            statut=AppelOffre.Statut.DEPOSE)
        r = self.api.post(f'{URL}enregistrer/', {
            'appel_offre': etranger.id, 'issue': 'gagne',
        }, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_stats_repond_le_taux_calcule(self):
        services.enregistrer_resultat_ao(
            self.ao, issue=ResultatAO.Issue.GAGNE)
        r = self.api.get(f'{URL}stats/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['gagnes'], 1)

    def test_aucune_permission_elargie(self):
        """Un Commercial n'accède ni à la liste ni aux stats."""
        role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=list(COMMERCIAL_PERMISSIONS))
        commercial = User.objects.create_user(
            username='aof32_com', password='x', company=self.company,
            role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(commercial)}')
        self.assertEqual(api.get(URL).status_code, 403)
        self.assertEqual(api.get(f'{URL}stats/').status_code, 403)
        self.assertEqual(
            api.post(f'{URL}enregistrer/', {'appel_offre': self.ao.id,
                                            'issue': 'gagne'},
                     format='json').status_code, 403)

    def test_filtre_par_issue(self):
        services.enregistrer_resultat_ao(
            self.ao, issue=ResultatAO.Issue.GAGNE)
        r = self.api.get(URL, {'issue': 'gagne'})
        self.assertEqual(r.status_code, 200, r.data)
        lignes = r.data['results'] if isinstance(r.data, dict) \
            and 'results' in r.data else r.data
        self.assertEqual(len(lignes), 1)
