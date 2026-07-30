"""WIR96 — câblage ventes ↔ marketing des deux modèles restés inertes.

Avant : ``marketing.OuverturePartage`` et ``marketing.RelanceDevisAbandonne``
étaient routés mais JAMAIS écrits (aucun appelant de
``enregistrer_ouverture_partage`` hors action manuelle, aucun de
``enregistrer_relance_devis_abandonne``).

Ce test verrouille les deux sens :
  - ouvrir un lien de partage (le point exact où ShareLink est horodaté)
    consigne une ``OuverturePartage`` et l'incrémente aux ouvertures suivantes ;
  - une relance QJ4 réellement déclenchée consigne une
    ``RelanceDevisAbandonne`` ;
  - les deux sont lisibles depuis la fiche devis via
    ``GET /ventes/devis/<id>/suivi-partage/``.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_wir96_marketing_wiring -v 2
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.marketing.models import OuverturePartage, RelanceDevisAbandonne
from apps.ventes.models import Devis, ShareLink

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='wir96-co', nom='WIR96 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class WIR96MarketingWiringTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='wir96_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Partage', prenom='Suivi',
            email='wir96@example.com', telephone='+212600000096')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-9601',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            date_envoi=timezone.now() - timedelta(days=30),
            created_by=self.user)

    # ── Sens 1 : ouverture du lien public → OuverturePartage ─────────────
    def test_ouverture_lien_partage_enregistre_une_ouverture(self):
        from apps.ventes.public_views import _stamp_view

        link = ShareLink.objects.create(
            company=self.company, devis=self.devis)
        self.assertEqual(OuverturePartage.objects.count(), 0)

        _stamp_view(link)
        ouverture = OuverturePartage.objects.get(
            company=self.company, token=link.token)
        self.assertEqual(ouverture.nb_ouvertures, 1)
        self.assertEqual(ouverture.cible, 'devis')
        self.assertEqual(ouverture.cible_reference, self.devis.reference)
        self.assertIsNotNone(ouverture.premier_vu_le)
        self.assertIsNotNone(ouverture.dernier_vu_le)

        # Deuxième ouverture : incrément idempotent, jamais un doublon.
        _stamp_view(link)
        ouverture.refresh_from_db()
        self.assertEqual(ouverture.nb_ouvertures, 2)
        self.assertEqual(OuverturePartage.objects.count(), 1)

    # ── Sens 2 : relance QJ4 déclenchée → RelanceDevisAbandonne ──────────
    def test_relance_declenchee_est_journalisee(self):
        from apps.ventes.services import send_devis_followup_nudges

        self.assertEqual(RelanceDevisAbandonne.objects.count(), 0)
        total = send_devis_followup_nudges()
        self.assertGreater(total, 0)

        relances = RelanceDevisAbandonne.objects.filter(
            company=self.company, devis_id=self.devis.pk)
        self.assertEqual(relances.count(), total)
        premiere = relances.order_by('id').first()
        self.assertEqual(premiere.devis_reference, self.devis.reference)
        self.assertGreater(premiere.jours_sans_reponse, 0)
        self.assertTrue(premiere.canal)

    # ── Lecture depuis la fiche devis ────────────────────────────────────
    def test_suivi_partage_endpoint_expose_ouverture_et_relances(self):
        from apps.ventes.public_views import _stamp_view
        from apps.marketing.services import (
            enregistrer_relance_devis_abandonne)

        link = ShareLink.objects.create(
            company=self.company, devis=self.devis)
        _stamp_view(link)
        enregistrer_relance_devis_abandonne(
            self.company, devis_id=self.devis.pk,
            devis_reference=self.devis.reference,
            jours_sans_reponse=5, canal='email', note='Relance test WIR96')

        r = self.api.get(
            f'/api/django/ventes/devis/{self.devis.id}/suivi-partage/')
        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(r.data['ouverture'])
        self.assertEqual(r.data['ouverture']['nb_ouvertures'], 1)
        self.assertEqual(len(r.data['relances']), 1)
        self.assertEqual(r.data['relances'][0]['canal'], 'email')
        self.assertEqual(r.data['relances'][0]['jours_sans_reponse'], 5)

    def test_suivi_partage_vide_sans_ouverture_ni_relance(self):
        r = self.api.get(
            f'/api/django/ventes/devis/{self.devis.id}/suivi-partage/')
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data['ouverture'])
        self.assertEqual(r.data['relances'], [])

    # ── Isolation multi-société ──────────────────────────────────────────
    def test_ouverture_et_relances_bornees_societe(self):
        from apps.marketing.selectors import (
            ouverture_partage_pour_token, relances_devis_abandonne)

        autre = make_company(slug='wir96-co-2', nom='WIR96 Co 2')
        OuverturePartage.objects.create(
            company=autre, token='jeton-autre-societe', nb_ouvertures=7)
        RelanceDevisAbandonne.objects.create(
            company=autre, devis_id=self.devis.pk, jours_sans_reponse=9)

        self.assertIsNone(ouverture_partage_pour_token(
            self.company, 'jeton-autre-societe'))
        self.assertEqual(
            relances_devis_abandonne(self.company, self.devis.pk), [])

    def test_journalisation_relance_nexplose_jamais(self):
        """Miroir best-effort : une panne marketing ne casse pas la relance."""
        from unittest.mock import patch

        from apps.ventes.services import _journaliser_relance_marketing

        with patch('apps.marketing.services.'
                   'enregistrer_relance_devis_abandonne',
                   side_effect=RuntimeError('boom')):
            # Ne doit rien lever.
            _journaliser_relance_marketing(
                self.devis, jours=2, canal='email', niveau=0)
        self.assertEqual(
            RelanceDevisAbandonne.objects.filter(
                company=self.company).count(), 0)

    def test_suivi_partage_nexpose_aucun_cout(self):
        """Garde-fou : le suivi de partage n'expose ni coût ni marge."""
        from apps.ventes.public_views import _stamp_view

        link = ShareLink.objects.create(
            company=self.company, devis=self.devis)
        _stamp_view(link)
        r = self.api.get(
            f'/api/django/ventes/devis/{self.devis.id}/suivi-partage/')
        payload = str(r.data)
        self.assertNotIn('prix_achat', payload)
        self.assertNotIn('marge', payload)
