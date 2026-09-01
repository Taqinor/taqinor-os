# -*- coding: utf-8 -*-
"""QJR232 — ``jour_reference`` épinglé PAR DEVIS, lu par les surcharges,
partagé par le balayage comparatif.

CORRECTIF CONJOINT — trois symptômes du MÊME trou :

(a) ``domain/entrees.empreinte_entrees`` fait entrer ``jour_reference`` (à
    raison, QJR45) mais la date valait « aujourd'hui » : le bloc le plus
    coûteux était invalidé UNE FOIS PAR JOUR CIVIL ET PAR DEVIS, alors que le
    module promet « recalcule SI ET SEULEMENT SI une entrée a bougé ».
(b) ``etude.jour_reference`` était accepté et PERSISTÉ par le registre D12 et
    AUCUN chemin moteur ne le lisait.
(c) ``profils_comparatifs`` — seul appelant de ``recommander_taille`` à relire
    la fiche à la main — OMETTAIT ``jour_reference`` : une SECONDE lecture
    d'horloge sous une empreinte qui épingle la date du devis.

INTERDIT, et vérifié ici : retirer ``jour_reference`` de l'empreinte (ce serait
recréer l'irreproductibilité Ramadan que QJR45 a fermée).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr232_jour_reference_epingle -v 2
"""
import inspect
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes import profils_comparatifs as _pc
from apps.ventes.domain import entrees as _entrees
from apps.ventes.domain import overrides as _overrides
from apps.ventes.models import Devis
from apps.ventes.tests.test_pv18_sync_layout import make_company

User = get_user_model()

DATE_DECLAREE = '2026-03-15'


class _Base(TestCase):

    def setUp(self):
        self.company = make_company('qjr232-co')
        self.user = User.objects.create_user(
            username='qjr232user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client QJR232')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau Jinko 550W', sku='QJR232-PAN',
            prix_vente=Decimal('1100'), prix_achat=Decimal('1'),
            quantite_stock=100)
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR232-0001',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            created_by=self.user, taux_tva=Decimal('20'),
            mode_installation='residentiel',
            etude_params={'conso_kwh_mensuelles': [800] * 12})
        self.devis.lignes.create(
            produit=self.panneau, designation='Panneau Jinko 550W',
            quantite=Decimal('12'), prix_unitaire=Decimal('1100'),
            remise=Decimal('0'), ordre=1)


class EmpreinteStableDUnJourALAutre(_Base):
    """(1) — deux calculs à deux JOURS CIVILS différents, mêmes entrées."""

    def _empreinte(self, aujourdhui):
        with mock.patch.object(_entrees, 'jour_reference_par_defaut',
                               return_value=aujourdhui):
            return _entrees.empreinte_entrees_du_devis(self.devis)

    def test_la_meme_empreinte_deux_jours_de_suite(self):
        """LE ROUGE : l'empreinte changeait une fois par jour civil."""
        jour1 = date(2026, 8, 31)
        jour2 = jour1 + timedelta(days=1)
        self.assertEqual(self._empreinte(jour1), self._empreinte(jour2))

    def test_la_date_reste_DANS_l_empreinte(self):
        """INTERDIT : la retirer recréerait l'irreproductibilité Ramadan."""
        source = inspect.getsource(_entrees.empreinte_entrees)
        self.assertIn("'jour_reference'", source)

    def test_deux_dates_declarees_donnent_deux_empreintes(self):
        """La date TRACE toujours le calcul : la changer change l'empreinte."""
        avant = _entrees.empreinte_entrees_du_devis(self.devis)
        _overrides.ecrire_colonne(self.devis, _overrides.poser(
            self.devis, 'etude.jour_reference', DATE_DECLAREE))
        self.assertNotEqual(_entrees.empreinte_entrees_du_devis(self.devis),
                            avant)


class LaSurchargeD12EstLue(_Base):
    """(2) — un PATCH ``etude.jour_reference`` change le dimensionnement."""

    def _date_du_devis(self):
        from django.utils import timezone
        self.devis.refresh_from_db()
        return timezone.localdate(self.devis.date_creation)

    def test_sans_surcharge_la_date_est_celle_du_devis(self):
        self.assertEqual(
            _entrees.jour_reference_du_devis(self.devis),
            self._date_du_devis())

    def test_avec_surcharge_la_date_declaree_gagne(self):
        """LE ROUGE : aucun chemin moteur ne lisait ce chemin."""
        _overrides.ecrire_colonne(self.devis, _overrides.poser(
            self.devis, 'etude.jour_reference', DATE_DECLAREE))
        self.assertEqual(_entrees.jour_reference_du_devis(self.devis),
                         date(2026, 3, 15))

    def test_la_date_declaree_atteint_les_entrees_du_moteur(self):
        _overrides.ecrire_colonne(self.devis, _overrides.poser(
            self.devis, 'etude.jour_reference', DATE_DECLAREE))
        entrees = _entrees.entrees_depuis_devis(self.devis)
        self.assertIsNotNone(entrees)
        self.assertEqual(entrees.jour_reference, date(2026, 3, 15))

    def test_une_surcharge_illisible_ne_decide_rien(self):
        """Zéro date inventée : un texte libre vaut une absence."""
        _overrides.ecrire_colonne(self.devis, _overrides.poser(
            self.devis, 'etude.jour_reference', 'un jour de printemps'))
        self.assertEqual(_entrees.jour_reference_du_devis(self.devis),
                         self._date_du_devis())


class ProfilsComparatifsPartagentLHorloge(_Base):
    """(3) — le balayage comparatif lit la MÊME date que l'étude principale."""

    def test_recommander_taille_recoit_la_date_du_devis(self):
        vues = {}

        def _espion(**kwargs):
            vues.update(kwargs)
            return None

        with mock.patch('apps.ventes.dimensionnement.recommander_taille',
                        side_effect=_espion):
            _pc._dimensionnement_variante(self.devis, 'jour')

        self.assertIn('jour_reference', vues,
                      'le balayage comparatif OMETTAIT la date')
        self.assertEqual(vues['jour_reference'],
                         _entrees.jour_reference_du_devis(self.devis))

    def test_la_surcharge_declaree_atteint_aussi_le_balayage(self):
        _overrides.ecrire_colonne(self.devis, _overrides.poser(
            self.devis, 'etude.jour_reference', DATE_DECLAREE))
        vues = {}

        with mock.patch('apps.ventes.dimensionnement.recommander_taille',
                        side_effect=lambda **kw: vues.update(kw)):
            _pc._dimensionnement_variante(self.devis, 'jour')

        self.assertEqual(vues.get('jour_reference'), date(2026, 3, 15))
