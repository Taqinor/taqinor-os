"""ERR-QAH-FIG-EDITION-ETUDE-LIVE-VS-DOCUMENT — l'aperçu de l'« Édition
complète » calcule sur la MÊME consommation que le bloc horaire du devis.

L'aperçu (``etude_horaire_view._profil_depuis_devis``) appelait
``profil_depuis_factures`` SANS le kWh mensuel déclaré du lead (CAD166) ni le
barème de la société, alors que le bloc du devis passe par
``etude_horaire.profil_conso_du_devis`` : même production, autres économies
(écran 2 742 / 5 932 MAD/an, document 5 158 / 7 822).

Technique : espionner les kwargs reçus par ``calculer_etude_horaire`` (comme
``test_qjr432_apercu_jour_reference``).

Lancer :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_err_apercu_meme_conso_que_devis"
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.domain import entrees as E
from apps.ventes.etude_horaire import profil_conso_du_devis
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()

URL = '/api/django/ventes/etude-horaire/preview/'


class ApercuMemeConsoQueLeDevisTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='ERR apercu',
                                              slug='err-apercu-conso')
        self.user = User.objects.create_user(
            username='err_apercu_user', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        client_obj = Client.objects.create(company=self.company, nom='C')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead', prenom='apercu',
            telephone='+212600000002', ville='Casablanca',
            facture_hiver=900, ete_differente=False,
            conso_mensuelle_kwh=Decimal('300'))
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-ERR-APERCU-01',
            client=client_obj, lead=self.lead, statut='brouillon',
            taux_tva=Decimal('20'), mode_installation='residentiel')

    def _kwargs_vus(self, corps):
        vues = {}

        def _espion(**kwargs):
            vues.update(kwargs)
            return None

        with mock.patch('apps.ventes.etude_horaire.calculer_etude_horaire',
                        side_effect=_espion):
            resp = self.api.post(URL, corps, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        return vues

    def test_chemin_devis_lit_la_conso_du_bloc(self):
        tranches, charges = E._reglages_tarifaires_de(self.company)
        attendu, source, _d = profil_conso_du_devis(
            self.devis, tranches=tranches, charges_fixes_mad=charges)
        self.assertEqual(source, 'kwh_mensuel_saisi')
        # L'écran envoie aussi la facture d'hiver : le devis prime toujours.
        vues = self._kwargs_vus({'devis': self.devis.pk, 'kwc': 4.26,
                                 'facture_hiver': 900})
        self.assertEqual(list(vues['conso_kwh_mensuelles']), list(attendu))
        self.assertEqual(vues['source_conso'], 'kwh_mensuel_saisi')

    def test_chemin_lead_lit_le_kwh_declare(self):
        vues = self._kwargs_vus({'lead': self.lead.pk, 'kwc': 4.26})
        self.assertEqual(vues['source_conso'], 'kwh_mensuel_saisi')
        self.assertEqual(list(vues['conso_kwh_mensuelles']), [300.0] * 12)
