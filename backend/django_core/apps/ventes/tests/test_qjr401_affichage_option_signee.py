"""QJR401 / DR1 — après signature, l'argent AFFICHÉ suit l'option SIGNÉE.

TEST ROUGE D'ABORD. ``build_quote_data`` et ``display_totals`` ne lisaient
**jamais** ``Devis.option_acceptee`` ni ``Devis.statut`` : leur sortie était
octet-pour-octet identique avant et après la signature, et ``display_total``
restait ``totaux_avec`` dès qu'il y avait deux options. Pendant ce temps
``utils.options.option_effective`` faisait suivre l'acceptation à
``Devis.total_ttc``, au solde, à l'échéancier et à la nomenclature : le client
signait « Sans batterie » et l'ERP AFFICHAIT le prix « Avec ».

Quatre surfaces héritent de la source (aucun fichier frontend n'est touché) :
la liste + le Kanban (``DevisSerializer.total_affiche``), le « CA signé » du
tableau de bord, la page publique des gammes, et la salle de vente PUBLIQUE
(``crm/public_views`` pose ``str(display_totals(devis)['total'])``).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_qjr401_affichage_option_signee"
"""
from decimal import Decimal

from django.test import TestCase

from apps.ventes.models import Devis
from apps.ventes.quote_engine.builder import build_quote_data, display_totals
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)
from apps.ventes.utils.echeancier import solde_devis
from apps.ventes.utils.options import SANS_BATTERIE


LIGNES_DEUX_OPTIONS = [
    ('Onduleur réseau Huawei 10kW Triphasé', '1', '16666.67'),
    ('Onduleur hybride Deye 10kW Triphasé', '1', '23333.33'),
    ('Batterie Dyness 10 kWh', '1', '25000'),
    ('Panneau Canadian Solar 710W', '14', '1166.67'),
    ('Installation', '1', '5000'),
]


class _Base(TestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(
            self.company, self.user, self.client_obj, LIGNES_DEUX_OPTIONS,
            reference='DEV-QJR401-0001', etude_params=dict(DEUX_OPTIONS))

    def _signer(self, option=SANS_BATTERIE):
        Devis.objects.filter(pk=self.devis.pk).update(
            option_acceptee=option, statut=Devis.Statut.ACCEPTE)
        self.devis.refresh_from_db()


class ApresSignature(_Base):
    """LE ROUGE : le total affiché == le total du noyau == le solde."""

    def test_le_total_affiche_suit_l_option_signee(self):
        avant = display_totals(self.devis)['total']
        self._signer()
        apres = display_totals(self.devis)['total']
        self.assertNotEqual(
            Decimal(str(avant)).quantize(Decimal('1')),
            Decimal(str(apres)).quantize(Decimal('1')),
            "le total affiché n'a pas bougé après la signature de l'option "
            '« sans batterie » — il décrit toujours l\'option « avec »')
        noyau = Decimal(str(self.devis.total_ttc))
        self.assertLessEqual(
            abs(Decimal(str(apres)) - noyau), Decimal('1'),
            'total affiché %s != Devis.total_ttc %s' % (apres, noyau))

    def test_le_solde_de_l_echeancier_dit_la_meme_chose(self):
        self._signer()
        solde = Decimal(str(solde_devis(self.devis)['total_ttc']))
        affiche = Decimal(str(display_totals(self.devis)['total']))
        self.assertLessEqual(abs(solde - affiche), Decimal('1'),
                             'solde %s != total affiché %s' % (solde, affiche))

    def test_la_source_est_build_quote_data(self):
        """La correction est À LA SOURCE : les quatre surfaces en héritent."""
        self._signer()
        data = build_quote_data(self.devis, {'pdf_mode': 'onepage'})
        self.assertEqual(data['display_total'], data['total_sans'])


class AvantSignatureRienNeChange(_Base):
    """Non-régression STRICTE : la sortie d'aujourd'hui, à l'octet."""

    def test_le_document_est_inchange(self):
        data = build_quote_data(self.devis, {'pdf_mode': 'onepage'})
        self.assertEqual(data['nb_options'], 2)
        self.assertEqual(data['display_total'], data['total_avec'])

    def test_le_repli_sans_moteur_est_inchange(self):
        from apps.ventes.utils.options import totaux_affichage_repli
        repli = totaux_affichage_repli(self.devis)
        self.assertEqual(repli['nb_options'], 2)
        data = build_quote_data(self.devis, {'pdf_mode': 'onepage'})
        self.assertLessEqual(
            abs(Decimal(str(repli['total']))
                - Decimal(str(data['total_avec']))), Decimal('1'))


class LesQuatreSurfacesHeritent(_Base):
    """Salle de vente publique et ``total_affiche`` portent la valeur signée."""

    def test_total_affiche_et_salle_de_vente(self):
        self._signer()
        from apps.ventes.serializers import DevisSerializer
        attendu = Decimal(str(self.devis.total_ttc))

        total_affiche = Decimal(str(
            DevisSerializer(self.devis).data['total_affiche']))
        self.assertLessEqual(abs(total_affiche - attendu), Decimal('1'),
                             'total_affiche %s' % total_affiche)

        # La salle de vente publique sert EXACTEMENT cette valeur
        # (``crm/public_views`` : ``str(display_totals(devis)['total'])``).
        salle = Decimal(str(display_totals(self.devis)['total']))
        self.assertLessEqual(abs(salle - attendu), Decimal('1'),
                             'salle de vente %s' % salle)

    def test_le_repli_sans_moteur_suit_aussi_la_signature(self):
        from apps.ventes.utils.options import totaux_affichage_repli
        self._signer()
        repli = Decimal(str(totaux_affichage_repli(self.devis)['total']))
        self.assertLessEqual(
            abs(repli - Decimal(str(self.devis.total_ttc))), Decimal('1'))
