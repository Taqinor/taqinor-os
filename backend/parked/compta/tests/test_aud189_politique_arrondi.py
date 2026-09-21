"""AUD189 — UNE politique d'arrondi, un seul helper : ROUND_HALF_UP partout.

``docs/money-convention.md`` impose ``quantize_mad()`` =
``quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)`` et explique que l'arrondi
bancaire (le DÉFAUT de ``Decimal``) « n'est pas la politique moitié-vers-le-haut
attendue en comptabilité marocaine ». Or ``compta.services._arrondi`` — unique
helper d'arrondi du module amortissement — faisait ``quantize(Decimal('0.01'))``
sans ``rounding``, et ``gestion_projet.services`` quantifiait de même alors que
``_ROUND_HALF_UP`` y était importé et jamais utilisé.

``12.505`` devenait 12.50 au lieu de 12.51 et ``0.125`` devenait 0.12 au lieu de
0.13 — sur une dotation d'amortissement comme sur une ligne de régie — pendant
que la CI restait verte.
"""
from decimal import Decimal

from django.test import SimpleTestCase

from core.money import quantize_mad


class TestPolitiqueArrondiUnique(SimpleTestCase):
    """Les deux cas de bascule que l'arrondi bancaire rendait faux."""

    #: Les deux cas nommés par la tâche, plus un contrôle hors bascule.
    BASCULES = [
        (Decimal('12.505'), Decimal('12.51')),
        (Decimal('0.125'), Decimal('0.13')),
    ]
    CAS = BASCULES + [(Decimal('12.504'), Decimal('12.50'))]

    def test_helper_unique(self):
        for valeur, attendu in self.CAS:
            with self.subTest(valeur=valeur):
                self.assertEqual(quantize_mad(valeur), attendu)

    def test_chemin_amortissement(self):
        """``compta.services._arrondi`` délègue au helper unique."""
        from apps.compta.services import _arrondi
        for valeur, attendu in self.CAS:
            with self.subTest(valeur=valeur):
                self.assertEqual(_arrondi(valeur), attendu)

    def test_chemin_regie_cout_interne(self):
        """``gestion_projet.services`` : coût interne d'un timesheet."""
        from apps.gestion_projet.services import cout_timesheet

        class _Ressource:
            cout_horaire = Decimal('0.25')

        # 0.5 h × 0.25 = 0.125 → 0.13 (et non 0.12 en arrondi bancaire).
        self.assertEqual(
            cout_timesheet(_Ressource(), Decimal('0.5')),
            Decimal('0.13'))

    def test_arrondi_bancaire_aurait_donne_autre_chose(self):
        """Preuve que les cas choisis SONT des cas de bascule : le défaut
        `Decimal` (ROUND_HALF_EVEN) donne un autre résultat."""
        for valeur, attendu in self.BASCULES:
            with self.subTest(valeur=valeur):
                bancaire = valeur.quantize(Decimal('0.01'))
                self.assertNotEqual(bancaire, attendu)
