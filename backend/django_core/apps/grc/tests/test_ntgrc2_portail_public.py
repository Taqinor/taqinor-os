"""NTGRC2 — portail public de dépôt et de suivi d'une demande de droit.

Garanties : un dépôt anonyme crée la ``core.DataSubjectRequest`` au statut
``recue`` avec sa preuve serveur, le jeton de suivi renvoie l'état sans
identifiant interne, le honeypot n'écrit rien, et aucun accès inter-tenant
n'est possible.
"""
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from core.models import DataSubjectRequest

DEPOT = '/api/django/grc/public/demande-droit/'


class PortailPublicDsrTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC2 SA', slug='ntgrc2')
        cls.autre = Company.objects.create(nom='NTGRC2 B', slug='ntgrc2-b')

    def setUp(self):
        super().setUp()
        cache.clear()  # remet à zéro le throttle anonyme entre tests
        self.api = APIClient()

    def _deposer(self, _entetes=None, **extra):
        corps = {
            'societe': 'ntgrc2',
            'identifiant': 'demandeur@exemple.ma',
            'type': 'acces',
        }
        corps.update(extra)
        return self.api.post(DEPOT, corps, format='json', **(_entetes or {}))

    def test_depot_anonyme_cree_la_demande_avec_sa_preuve(self):
        r = self._deposer({'HTTP_USER_AGENT': 'navigateur-test'})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.data['token_suivi'])
        self.assertEqual(r.data['delai_legal_jours'], 30)

        demande = DataSubjectRequest.objects.get(
            subject_identifier='demandeur@exemple.ma')
        self.assertEqual(demande.company_id, self.company.id)
        self.assertEqual(demande.statut, DataSubjectRequest.STATUT_RECUE)
        self.assertEqual(demande.preuve['canal'], 'portail_public')
        self.assertTrue(demande.preuve['depose_le'])
        self.assertEqual(demande.preuve['user_agent'], 'navigateur-test')

    def test_le_token_de_suivi_nest_pas_lidentifiant_reel(self):
        r = self._deposer()
        token = r.data['token_suivi']
        demande = DataSubjectRequest.objects.get(token_suivi=token)
        self.assertNotEqual(token, str(demande.pk))
        self.assertGreaterEqual(len(token), 32)

    def test_suivi_renvoie_letat_sans_identifiant_interne(self):
        token = self._deposer().data['token_suivi']
        r = self.api.get(f'{DEPOT}{token}/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['statut'], 'recue')
        self.assertEqual(r.data['delai_legal_jours'], 30)
        self.assertTrue(r.data['echeance_legale'])
        for interdit in ('id', 'subject_identifier', 'resultat', 'company'):
            self.assertNotIn(interdit, r.data)

    def test_token_inconnu_renvoie_404(self):
        r = self.api.get(f'{DEPOT}jeton-qui-nexiste-pas/')
        self.assertEqual(r.status_code, 404)

    def test_societe_inconnue_nomme_le_champ_fautif(self):
        r = self._deposer(societe='societe-fantome')
        self.assertEqual(r.status_code, 400)
        self.assertIn('societe', r.data)
        self.assertEqual(DataSubjectRequest.objects.count(), 0)

    def test_identifiant_manquant_nomme_le_champ_fautif(self):
        r = self._deposer(identifiant='')
        self.assertEqual(r.status_code, 400)
        self.assertIn('identifiant', r.data)

    def test_type_invalide_nomme_le_champ_fautif(self):
        r = self._deposer(type='tout_supprimer')
        self.assertEqual(r.status_code, 400)
        self.assertIn('type', r.data)
        self.assertEqual(DataSubjectRequest.objects.count(), 0)

    def test_honeypot_nenregistre_rien(self):
        r = self._deposer(ne_pas_remplir='je suis un robot')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(DataSubjectRequest.objects.count(), 0)

    def test_aucun_acces_inter_tenant(self):
        """Le dépôt naît borné à la société du slug, jamais à une autre."""
        self._deposer(societe='ntgrc2-b')
        demande = DataSubjectRequest.objects.get()
        self.assertEqual(demande.company_id, self.autre.id)
        self.assertEqual(
            DataSubjectRequest.objects.filter(company=self.company).count(), 0)
