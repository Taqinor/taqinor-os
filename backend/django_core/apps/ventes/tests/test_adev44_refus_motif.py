"""ADEV44 (C-ADEV-001) — « Refuser » conserve le MOTIF choisi à l'écran.

Corps selon ``contract_samples/devis_refuser.json`` : ``motif`` = NOM d'un
MotifPerte actif de la société (validé par ``apps.crm.services.
motif_refus_valide``, sans casse), ``note`` = détail libre. Un nom inconnu ⇒
400 ``{motif: [...]}`` et le devis reste ``envoye`` ; un refus SANS motif
reste accepté (question fondateur AGRM37 ouverte).

Test-du-test : retirer l'appel à ``motif_refus_valide`` ⇒
``test_motif_inconnu_400`` échoue.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_adev44_refus_motif -v 2
"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import MotifPerte
from apps.ventes.models import Devis, DevisActivity
from apps.ventes.tests.test_l_niv_niveau import (
    make_client, make_company, make_devis, make_user,
)


class RefusMotifTests(TestCase):

    def setUp(self):
        self.company = make_company('adev44')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.user, self.client_obj,
                                'DEV-ADEV44-0001')
        MotifPerte.objects.create(company=self.company,
                                  nom='Budget insuffisant')
        MotifPerte.objects.create(company=self.company, nom='Archivé',
                                  archived=True)
        autre = make_company('adev44-autre')
        MotifPerte.objects.create(company=autre, nom='Motif autre société')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.evenements = []
        from core.events import devis_refused

        def _ecoute(sender, **kwargs):
            self.evenements.append(kwargs.get('motif_refus'))

        devis_refused.connect(_ecoute, dispatch_uid='adev44', weak=False)
        self.addCleanup(devis_refused.disconnect, dispatch_uid='adev44')

    def _refuser(self, corps):
        return self.api.post(
            f'/api/django/ventes/devis/{self.devis.pk}/refuser/', corps,
            format='json')

    def _refuses_sans_motif(self):
        return list(Devis.objects.filter(
            company=self.company, statut=Devis.Statut.REFUSE)
            .exclude(motif_refus__gt='').values_list('pk', flat=True))

    def test_motif_nomme_est_conserve(self):
        r = self._refuser({'motif': 'budget INSUFFISANT',
                           'note': 'Le client attend une subvention.'})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['motif_refus'], 'Budget insuffisant')
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.REFUSE)
        self.assertEqual(self.devis.motif_refus, 'Budget insuffisant')
        self.assertIsNotNone(self.devis.date_refus)
        self.assertEqual(self.evenements, ['Budget insuffisant'])
        corps = DevisActivity.objects.get(
            devis=self.devis, field_label='Refus').body
        self.assertIn('Budget insuffisant', corps)
        self.assertIn('subvention', corps)

    def test_motif_inconnu_400(self):
        for nom in ('inconnu', 'Archivé', 'Motif autre société'):
            r = self._refuser({'motif': nom})
            self.assertEqual(r.status_code, 400, (nom, r.data))
            self.assertEqual(
                r.data, {'motif': ['Choisissez un motif de refus de la liste.']})
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ENVOYE)
        self.assertEqual(self.devis.motif_refus, '')
        self.assertEqual(self.evenements, [])

    def test_hors_panier_refuses_sans_motif(self):
        self._refuser({'motif': 'Budget insuffisant'})
        self.assertNotIn(self.devis.pk, self._refuses_sans_motif())

    def test_sans_motif_reste_accepte_agrm37(self):
        r = self._refuser({})
        self.assertEqual(r.status_code, 200, r.data)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.REFUSE)
        self.assertIn(self.devis.pk, self._refuses_sans_motif())
