# -*- coding: utf-8 -*-
"""QJR225 — la resynchro n'écrit plus le kWc du CALEPINAGE en repli.

TEST ROUGE D'ABORD : ``domain/resynchronisation`` écrivait
``etude_params['puissance_kwc']`` depuis le kWc du LAYOUT quand le propriétaire
(``domain.scenario.puissance_kwc_du_devis``) ne savait pas répondre. Deux
contradictions à la fois : la règle « écrivain unique » de QJR63
(``poser_puissance_kwc``, seul écrivain déclaré) et la préférence Z2 du module
lui-même — OMETTRE une valeur inconnue plutôt que la fabriquer. Le calepinage
modélise à watt constant : ce n'est pas le panneau vendu.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr225_kwc_ecrivain_unique -v 2
"""
import inspect
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.domain import resynchronisation as _resync
from apps.ventes.domain.scenario import puissance_kwc_du_devis
from apps.ventes.models import Devis
from apps.ventes.services import sync_devis_from_layout
from apps.ventes.tests.test_pv18_sync_layout import layout, make_company

User = get_user_model()

#: Un panneau dont le WATTAGE est ILLISIBLE : ni fiche technique, ni chiffre
#: dans la désignation. ``panneaux_et_watt_lu`` compte les panneaux mais rend
#: ``watt = None`` — le propriétaire du kWc ne sait donc pas répondre.
PANNEAU_SANS_WATT = 'Panneau photovoltaïque monocristallin'
RESEAU = 'Onduleur réseau Huawei 5kW'


class TestQJR225(TestCase):

    def setUp(self):
        self.company = make_company('qjr225-co')
        self.user = User.objects.create_user(
            username='qjr225user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client QJR225')
        self.panneau = Produit.objects.create(
            company=self.company, nom=PANNEAU_SANS_WATT, sku='QJR225-PAN',
            prix_vente=Decimal('1100'), prix_achat=Decimal('1'),
            quantite_stock=100)
        self.onduleur = Produit.objects.create(
            company=self.company, nom=RESEAU, sku='QJR225-ONDR',
            prix_vente=Decimal('14000'), prix_achat=Decimal('1'),
            quantite_stock=100)

    def _devis(self):
        devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR225-0001',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            created_by=self.user, taux_tva=Decimal('20'))
        devis.lignes.create(
            produit=self.panneau, designation=PANNEAU_SANS_WATT,
            quantite=Decimal('12'), prix_unitaire=Decimal('1100'),
            remise=Decimal('0'), ordre=1)
        devis.lignes.create(
            produit=self.onduleur, designation=RESEAU, quantite=Decimal('1'),
            prix_unitaire=Decimal('14000'), remise=Decimal('0'), ordre=2)
        return devis

    # ── LE ROUGE ────────────────────────────────────────────────────────────
    def test_sans_kwc_lisible_la_cle_reste_ABSENTE(self):
        """ROUGE AVANT : la resynchro écrivait le kWc du LAYOUT (8.8)."""
        devis = self._devis()
        self.assertIsNone(puissance_kwc_du_devis(devis),
                          'la fixture doit rendre le propriétaire muet')

        sync_devis_from_layout(devis, layout(panels=12, kwc=8.8),
                               user=self.user)

        devis.refresh_from_db()
        self.assertNotIn('puissance_kwc', devis.etude_params or {})

    def test_le_repli_layout_a_disparu_du_code(self):
        """Le grep, exécuté : plus AUCUNE écriture depuis le kWc du layout."""
        source = inspect.getsource(_resync)
        ecritures = [ligne.strip() for ligne in source.splitlines()
                     if ligne.strip().startswith("etude['puissance_kwc']")]
        self.assertEqual(
            ecritures, ["etude['puissance_kwc'] = _kwc_proprietaire"],
            ecritures)

    def test_avec_un_kwc_lisible_le_proprietaire_ecrit_toujours(self):
        """Non-régression : quand le propriétaire SAIT, il écrit — c'est sa
        valeur, jamais celle du layout."""
        devis = self._devis()
        ligne = devis.lignes.get(designation=PANNEAU_SANS_WATT)
        ligne.designation = 'Panneau Jinko 550W'
        ligne.save(update_fields=['designation'])
        self.panneau.nom = 'Panneau Jinko 550W'
        self.panneau.save(update_fields=['nom'])

        attendu = puissance_kwc_du_devis(devis)
        self.assertIsNotNone(attendu)

        sync_devis_from_layout(devis, layout(panels=12, kwc=8.8),
                               user=self.user)
        devis.refresh_from_db()
        stocke = (devis.etude_params or {}).get('puissance_kwc')
        self.assertIsNotNone(stocke)
        self.assertNotEqual(stocke, 8.8,
                            'le kWc du LAYOUT ne doit jamais être stocké')
        self.assertAlmostEqual(
            float(stocke), float(puissance_kwc_du_devis(devis)), places=2)
