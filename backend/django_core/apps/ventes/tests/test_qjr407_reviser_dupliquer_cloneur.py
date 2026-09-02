"""QJR407 — S5-1 / S5-2 / S5-4 : `reviser` et `dupliquer-variante` passent par
le CLONEUR DU DOMAINE.

TEST ROUGE D'ABORD. Les deux vues réimplémentaient ``Devis.objects.create(...)``
à la main et OMETTAIENT les SEPT champs que le cloneur du domaine porte
explicitement depuis QJR146(a) : ``devise``, ``taux_change``, ``echeancier``,
``acompte_pct``, ``acompte_montant``, ``entite``, ``custom_data``. C'est le bug
corrigé ailleurs et jamais propagé ici — atteignable depuis ``DevisList.jsx`` en
usage quotidien, et financièrement porteur (un échéancier NÉGOCIÉ et un acompte
perdus : c'est la première tranche que l'email de confirmation annonce au
client).

Deux défauts de la même famille, dans les mêmes lignes :
(a) ``reviser`` assignait ``etude_params=old.etude_params`` PAR RÉFÉRENCE BRUTE
    (le piège d'aliasing que QJR117/QJR146(b) ont fermé partout ailleurs) ;
(b) les deux vues créaient le devis PUIS clonaient ses lignes SANS
    ``transaction.atomic()`` — un incident entre les deux étapes laissait un
    brouillon orphelin sans lignes.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_qjr407_reviser_dupliquer_cloneur"
"""
from decimal import Decimal
from unittest import mock

from django.test import TestCase

from apps.ventes.models import Devis
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)


LIGNES = [
    ('Onduleur réseau Huawei 10kW Triphasé', '1', '16666.67'),
    ('Panneau Canadian Solar 710W', '14', '1166.67'),
    ('Installation', '1', '5000'),
]

#: Les SEPT champs que les deux vues perdaient, avec une valeur NON par défaut.
ECHEANCIER_NEGOCIE = [
    {'libelle': 'Acompte', 'type': 'pct', 'pct_or_montant': 45},
    {'libelle': 'Solde', 'type': 'pct', 'pct_or_montant': 55},
]


class _Base(TestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.source = make_devis(
            self.company, self.user, self.client_obj, LIGNES,
            reference='DEV-QJR407-0001',
            etude_params={'scenario': 'Sans batterie',
                          'production_annuelle': 14000})
        Devis.objects.filter(pk=self.source.pk).update(
            devise='EUR', taux_change=Decimal('11.0000'),
            echeancier=ECHEANCIER_NEGOCIE,
            acompte_pct=Decimal('45.00'), acompte_montant=Decimal('1234.56'),
            entite='TAQINOR SARL', custom_data={'dossier': 'X-42'})
        self.source.refresh_from_db()

    def _assert_les_sept_champs(self, copie):
        self.assertEqual(copie.devise, 'EUR')
        self.assertEqual(Decimal(str(copie.taux_change)), Decimal('11.0000'))
        self.assertEqual(copie.echeancier, ECHEANCIER_NEGOCIE)
        self.assertEqual(Decimal(str(copie.acompte_pct)), Decimal('45.00'))
        self.assertEqual(Decimal(str(copie.acompte_montant)),
                         Decimal('1234.56'))
        self.assertEqual(copie.entite, 'TAQINOR SARL')
        self.assertEqual(copie.custom_data, {'dossier': 'X-42'})


class Reviser(_Base):

    def _reviser(self):
        from apps.ventes.domain.creation import cloner_devis
        return cloner_devis(
            self.source, user=self.user, note=self.source.note,
            version=self.source.version + 1,
            version_parent=self.source.version_parent or self.source)

    def test_la_revision_porte_les_sept_champs(self):
        """ROUGE AVANT : la révision en perdait sept."""
        self._assert_les_sept_champs(self._reviser())

    def test_pas_d_aliasing_sur_etude_params(self):
        """ROUGE AVANT : ``etude_params=old.etude_params`` par référence."""
        copie = self._reviser()
        copie.etude_params['scenario'] = 'Avec batterie'
        self.source.refresh_from_db()
        self.assertEqual(self.source.etude_params.get('scenario'),
                         'Sans batterie')

    def test_les_lignes_sont_clonees(self):
        self.assertEqual(self._reviser().lignes.count(), len(LIGNES))


class DupliquerVariante(_Base):

    def _variante(self, scale='0.8'):
        from apps.ventes.domain.creation import cloner_devis

        def _echelle(ligne):
            return {'quantite': ligne.quantite * Decimal(scale),
                    'quantite_manuelle': False}

        return cloner_devis(
            self.source, user=self.user, note='[Variante −20 %]',
            version=self.source.version + 1,
            version_parent=self.source, remplacements=_echelle)

    def test_la_variante_porte_les_sept_champs(self):
        """ROUGE AVANT : la variante en perdait sept."""
        self._assert_les_sept_champs(self._variante())

    def test_l_echelle_reste_appliquee(self):
        variante = self._variante()
        panneau = variante.lignes.get(designation__startswith='Panneau')
        self.assertEqual(Decimal(str(panneau.quantite)),
                         Decimal('14') * Decimal('0.8'))


class AtomiciteDuClonage(_Base):

    def test_une_erreur_pendant_le_clonage_ne_laisse_aucun_devis(self):
        """ROUGE AVANT : le devis était créé PUIS les lignes clonées, hors
        transaction — un incident entre les deux laissait un brouillon
        orphelin sans lignes."""
        from apps.ventes.domain import creation

        avant = Devis.objects.filter(company=self.company).count()
        with mock.patch.object(creation, 'cloner_lignes',
                               side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                creation.cloner_devis(self.source, user=self.user)
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)


class NonRegressionDuCheminDejaCorrect(_Base):
    """``dupliquer_devis`` (déjà correct) est inchangé au centime."""

    def test_dupliquer_devis_inchange(self):
        from apps.ventes.domain.creation import dupliquer_devis
        copie = dupliquer_devis(self.source, user=self.user)
        self._assert_les_sept_champs(copie)
        self.assertEqual(copie.version, 1)
        self.assertIsNone(copie.version_parent)
        self.assertEqual(copie.statut, Devis.Statut.BROUILLON)
        self.assertTrue(copie.note.startswith('[Copie de '))
        self.assertEqual(Decimal(str(copie.total_ttc)),
                         Decimal(str(self.source.total_ttc)))
