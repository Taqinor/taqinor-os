"""QJR133 — un moteur PDF indisponible n'impose plus une option contractuelle.

Constat ES2 de l'audit du 30/08/2026, vérifié en code : ``build_quote_data``
était le SEUL détecteur consulté par ``accept_devis``, et son
``except Exception: nb_options, scenario = 1, ''`` faisait disparaître le
garde-fou « deux options → choix explicite » PUIS retombait sur un repli FIXE
(« sans_batterie »).

Or l'option acceptée est AUTORITATIVE en aval (``utils/echeancier`` : « on
facture UNIQUEMENT les lignes de l'option retenue ») : le client se retrouvait
engagé, facturé et approvisionné sur un périmètre qu'il n'avait pas choisi,
sans qu'aucune erreur ne soit levée. Chemin d'atteinte : un POST public sur
``/proposal/<token>/accept`` sans champ ``option``.

CE QUI EST ÉPINGLÉ ICI : le refus explicite quand la détection est
indisponible, ET l'absence totale de changement sur le chemin nominal
(mono-option et deux-options avec un moteur qui répond).

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr133_detection_options_acceptation -v 2
"""
import uuid
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.domain.lignes import creer_ligne
from apps.ventes.models import Devis, ShareLink
from apps.ventes.services import AcceptError, accept_devis
from apps.ventes.utils.options import deux_options_declarees
from authentication.models import Company

#: Ce que le moteur lève quand il ne peut pas construire le document.
MOTEUR_HS = RuntimeError('moteur indisponible (simulé)')

RESEAU = 'Onduleur réseau Huawei 10kW Monophasé'
HYBRIDE = 'Onduleur hybride Deye 10kW Monophasé'
BATTERIE = 'Batterie Dyness 10 kWh'
PANNEAU = 'Panneau Canadian Solar 710W'


def _moteur_en_panne():
    """Patch le SEUL détecteur historique — sur le module qui le PORTE, car
    ``accept_devis`` l'importe au moment de l'appel."""
    return patch('apps.ventes.quote_engine.builder.build_quote_data',
                 side_effect=MOTEUR_HS)


class _BaseOptions(TestCase):
    slug = 'qjr133'

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': self.slug})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR133',
            email='qjr133-%s@example.com' % self.slug)
        self.api = APIClient()
        self._sku = 0

    def _produit(self, nom, prix):
        self._sku += 1
        return Produit.objects.create(
            company=self.company, nom=nom,
            sku='QJR133-%d-%s' % (self._sku, self.company.pk),
            prix_vente=Decimal(prix), prix_achat=Decimal('1'),
            quantite_stock=50)

    def _devis(self, ref, *, lignes, scenario=None):
        devis = Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'),
            mode_installation='residentiel',
            etude_params=({'scenario': scenario} if scenario else {}))
        for nom, qte, pu, variante in lignes:
            creer_ligne(devis, produit=self._produit(nom, pu),
                        designation=nom, quantite=Decimal(qte),
                        prix_unitaire=Decimal(pu), remise=Decimal('0'),
                        variante=variante)
        return devis

    def _deux_options(self, ref):
        """Un vrai devis à deux options : les trois familles + la déclaration
        (c'est exactement ce que ``deux_options_declarees`` exige)."""
        devis = self._devis(ref, scenario='Les deux (Sans + Avec)', lignes=(
            (PANNEAU, '14', '1166.67', ''),
            (RESEAU, '1', '15000.00', ''),
            (HYBRIDE, '1', '23333.33', ''),
            (BATTERIE, '1', '25000.00', ''),
        ))
        self.assertTrue(deux_options_declarees(devis))
        return devis

    def _mono_option(self, ref):
        """Un devis mono-option : onduleur RÉSEAU seul, aucune batterie."""
        devis = self._devis(ref, lignes=(
            (PANNEAU, '10', '1166.67', ''),
            (RESEAU, '1', '15000.00', ''),
        ))
        self.assertFalse(deux_options_declarees(devis))
        return devis

    def _assert_pas_accepte(self, devis):
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertEqual(devis.option_acceptee or '', '')
        self.assertIsNone(devis.date_acceptation)


class LeMoteurEnPanneNImposePlusUneOption(_BaseOptions):
    """ES2 — le cœur de QJR133."""

    slug = 'qjr133-panne'

    def test_deux_options_sans_choix_est_refuse(self):
        devis = self._deux_options('DEV-QJR133-A1')
        with _moteur_en_panne():
            with self.assertRaises(AcceptError) as leve:
                accept_devis(devis=devis, user=None, nom='M. Client')
        self.assertIn('deux options', leve.exception.message)
        self._assert_pas_accepte(devis)

    def test_mono_option_sans_choix_est_refuse_aussi(self):
        """Sans détection, on ne fige RIEN — pas même sur un devis qui semble
        mono-option : c'est le repli « sans_batterie » qui engageait le client
        en silence."""
        devis = self._mono_option('DEV-QJR133-A2')
        with _moteur_en_panne():
            with self.assertRaises(AcceptError) as leve:
                accept_devis(devis=devis, user=None, nom='M. Client')
        self.assertIn("n'a pas pu être construit", leve.exception.message)
        self._assert_pas_accepte(devis)

    def test_une_option_explicite_passe_malgre_le_moteur(self):
        """Le client A choisi : il n'y a plus rien à deviner, donc rien à
        refuser."""
        devis = self._deux_options('DEV-QJR133-A3')
        with _moteur_en_panne():
            accept_devis(devis=devis, user=None, nom='M. Client',
                         option='sans_batterie')
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(devis.option_acceptee, 'sans_batterie')

    def test_le_refus_est_un_400_sur_le_chemin_public(self):
        """Le chemin d'atteinte NOMMÉ par l'audit : POST public sans
        ``option``. Il rendait 200 en engageant « sans_batterie »."""
        devis = self._deux_options('DEV-QJR133-A4')
        link = ShareLink.objects.create(
            company=self.company, devis=devis, token=str(uuid.uuid4()))
        with _moteur_en_panne():
            resp = self.api.post(
                f'/api/django/public/proposal/{link.token}/accept/',
                {'nom': 'M. Client', 'consent_esign': True}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('deux options', resp.data.get('detail', ''))
        self._assert_pas_accepte(devis)


class LeCheminNominalEstInchange(_BaseOptions):
    """Le TÉMOIN : avec un moteur qui répond, rien ne bouge."""

    slug = 'qjr133-nominal'

    def test_mono_option_accepte_sans_choix_explicite(self):
        devis = self._mono_option('DEV-QJR133-B1')
        accept_devis(devis=devis, user=None, nom='M. Client')
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(devis.option_acceptee, 'sans_batterie')

    def test_mono_option_avec_batterie_garde_son_option(self):
        """Un devis hybride + batterie déclaré « Avec batterie » : le repli
        historique lisait le scénario du moteur, il le lit toujours."""
        devis = self._devis('DEV-QJR133-B2', scenario='Avec batterie', lignes=(
            (PANNEAU, '14', '1166.67', ''),
            (HYBRIDE, '1', '23333.33', ''),
            (BATTERIE, '1', '25000.00', ''),
        ))
        accept_devis(devis=devis, user=None, nom='M. Client')
        devis.refresh_from_db()
        self.assertEqual(devis.option_acceptee, 'avec_batterie')

    def test_deux_options_exige_toujours_un_choix_explicite(self):
        devis = self._deux_options('DEV-QJR133-B3')
        with self.assertRaises(AcceptError) as leve:
            accept_devis(devis=devis, user=None, nom='M. Client')
        self.assertIn('deux options', leve.exception.message)
        self._assert_pas_accepte(devis)

    def test_deux_options_avec_choix_explicite_passe(self):
        devis = self._deux_options('DEV-QJR133-B4')
        accept_devis(devis=devis, user=None, nom='M. Client',
                     option='avec_batterie')
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(devis.option_acceptee, 'avec_batterie')
