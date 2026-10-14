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

    def test_chemin_devis_lit_l_occupation_du_bloc(self):
        """CI #752 — l'écran n'envoie pas ``mode_installation`` : l'aperçu
        d'un devis RÉSIDENTIEL applique quand même le défaut fondateur
        ``presence_jour`` que le bloc du devis applique (mode lu sur le
        devis), jamais le défaut non résidentiel ``absence_jour``
        (couverture écran 28 % contre 47,51 % à la proposition)."""
        from apps.ventes.courbes_journalieres import (
            OCCUPATION_PRESENCE, occupation_du_devis)
        attendu, _src = occupation_du_devis(
            self.devis, {'mode_installation': self.devis.mode_installation})
        self.assertEqual(attendu, OCCUPATION_PRESENCE)
        vues = self._kwargs_vus({'devis': self.devis.pk, 'kwc': 4.26})
        self.assertEqual(vues['occupation'], attendu)
        # Un mode FOURNI par l'appelant n'est jamais écrasé.
        vues = self._kwargs_vus({'devis': self.devis.pk, 'kwc': 4.26,
                                 'mode_installation': 'industriel'})
        self.assertEqual(
            vues['occupation'],
            occupation_du_devis(self.devis,
                                {'mode_installation': 'industriel'})[0])

    def test_chemin_devis_lit_le_gps_du_chantier(self):
        """L'écran envoie la ville de calcul du lead : l'aperçu prend AUSSI le
        GPS du chantier, comme le bloc du devis (ville + GPS du lead). Une
        AUTRE ville tapée (simulation) n'emprunte pas ce GPS."""
        Lead.objects.filter(pk=self.lead.pk).update(
            gps_lat=Decimal('33.573110'), gps_lng=Decimal('-7.589843'))
        self.lead.refresh_from_db()
        vues = self._kwargs_vus({'devis': self.devis.pk, 'kwc': 4.26,
                                 'ville': 'Casablanca'})
        self.assertEqual((vues['ville'], vues['lat'], vues['lon']),
                         ('Casablanca', self.lead.gps_lat, self.lead.gps_lng))
        vues = self._kwargs_vus({'devis': self.devis.pk, 'kwc': 4.26,
                                 'ville': 'Agadir'})
        self.assertEqual((vues['ville'], vues['lat'], vues['lon']),
                         ('Agadir', None, None))

    def _bloc_range(self):
        from apps.ventes.courbes_journalieres import occupation_du_devis
        occupation, _src = occupation_du_devis(
            self.devis, {'mode_installation': self.devis.mode_installation})
        return {
            'kwc': 4.26, 'occupation': occupation, 'batterie_kwh_utile': None,
            'annuel': {'production_kwh': 6543.0, 'consommation_kwh': 3600.0,
                       'economie_sans_mad': 4580.0,
                       'economie_avec_mad': 4580.0},
            'mois': [{'economie_sans_mad': 381.0, 'economie_avec_mad': 381.0}
                     for _ in range(12)],
            '_empreinte_entrees': 'empreinte',
        }

    def _poster_avec_bloc_range(self, corps, bloc):
        appels = []

        def _espion(**kwargs):
            appels.append(kwargs)
            return None

        with mock.patch('apps.ventes.domain.etudes.bloc_horaire_enregistre_pour',
                        return_value=bloc), \
                mock.patch('apps.ventes.etude_horaire.calculer_etude_horaire',
                           side_effect=_espion):
            resp = self.api.post(URL, corps, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.json()['etude'], appels

    def test_bloc_range_frais_est_servi_tel_quel(self):
        """L'écran qui décrit ce que le document chiffre (même kWc, même
        batterie, ville du chantier) lit le bloc RANGÉ — celui du PDF — sans
        recalcul : écran et document affichent la MÊME étude."""
        bloc = self._bloc_range()
        etude, appels = self._poster_avec_bloc_range(
            {'devis': self.devis.pk, 'kwc': 4.26, 'ville': 'Casablanca'}, bloc)
        attendu = {k: v for k, v in bloc.items() if k != '_empreinte_entrees'}
        self.assertEqual(etude, attendu)
        self.assertEqual(appels, [])

    def test_ecran_qui_explore_recalcule(self):
        """Une autre batterie, une autre ville, des coordonnées ou un autre
        marché (donc une autre occupation) demandés à l'écran : le bloc rangé
        ne décrit plus l'écran, l'aperçu recalcule comme avant."""
        bloc = self._bloc_range()
        for corps in ({'batterie_kwh': 5}, {'ville': 'Agadir'},
                      {'lat': 30.42, 'lon': -9.6},
                      {'mode_installation': 'industriel'}):
            etude, appels = self._poster_avec_bloc_range(
                {'devis': self.devis.pk, 'kwc': 4.26, **corps}, bloc)
            self.assertIsNone(etude, corps)
            self.assertEqual(len(appels), 1, corps)


class BlocHoraireEnregistrePourTests(TestCase):
    """``etudes.bloc_horaire_enregistre_pour`` : le bloc rangé que le
    document lira — frais ET accepté par la garde du moteur."""

    BLOC = {
        'kwc': 4.26, 'batterie_kwh_utile': None,
        'annuel': {'production_kwh': 6813.0, 'consommation_kwh': 3600.0,
                   'economie_sans_mad': 2742.0, 'economie_avec_mad': 5932.0},
        'mois': [{'economie_sans_mad': 228.0, 'economie_avec_mad': 494.0}
                 for _ in range(12)],
    }

    def _devis(self, bloc):
        return mock.Mock(reference='DEV-T', etude_params={'etude_horaire': bloc})

    def test_bloc_frais_et_lisible(self):
        from apps.ventes.domain import etudes
        with mock.patch.object(etudes, '_bloc_horaire_deja_a_jour',
                               return_value=True):
            self.assertIs(etudes.bloc_horaire_enregistre_pour(
                self._devis(self.BLOC), 4.26), self.BLOC)
            # Refusé par la garde du moteur (économie nulle) : le document ne
            # le lira pas, l'écran non plus.
            mutile = dict(self.BLOC, annuel=dict(self.BLOC['annuel'],
                                                 economie_avec_mad=0))
            self.assertIsNone(etudes.bloc_horaire_enregistre_pour(
                self._devis(mutile), 4.26))
            self.assertIsNone(etudes.bloc_horaire_enregistre_pour(
                self._devis(self.BLOC), None))

    def test_bloc_perime(self):
        from apps.ventes.domain import etudes
        with mock.patch.object(etudes, '_bloc_horaire_deja_a_jour',
                               return_value=False):
            self.assertIsNone(etudes.bloc_horaire_enregistre_pour(
                self._devis(self.BLOC), 4.26))
