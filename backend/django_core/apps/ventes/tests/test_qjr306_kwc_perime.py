# -*- coding: utf-8 -*-
"""QJR306 — un kWc PÉRIMÉ ne survit plus à une resynchro dont le propriétaire
ne sait pas répondre.

TEST ROUGE D'ABORD : ``domain/resynchronisation.py:958`` recopie l'étude
existante (``etude = dict(verrou.etude_params or {})``) et ``:983-986``
n'écrit ``etude['puissance_kwc']`` QUE si le propriétaire
(``domain.scenario.puissance_kwc_du_devis``) sait répondre — quand il ne sait
pas, la clé HÉRITÉE d'une exécution précédente est reconduite telle quelle.
QJR225 avait retiré le REPLI sur le kWc du calepinage, pas la valeur PÉRIMÉE :
la garantie « omettre plutôt que fabriquer » (règle Z2) ne tenait donc que
pour un devis qui n'avait JAMAIS eu la clé.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr306_kwc_perime -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
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
PANNEAU_LISIBLE = 'Panneau Jinko 550W'


class TestQJR306(TestCase):

    def setUp(self):
        self.company = make_company('qjr306-co')
        self.user = User.objects.create_user(
            username='qjr306user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client QJR306')
        self.panneau = Produit.objects.create(
            company=self.company, nom=PANNEAU_SANS_WATT, sku='QJR306-PAN',
            prix_vente=Decimal('1100'), prix_achat=Decimal('1'),
            quantite_stock=100)
        self.onduleur = Produit.objects.create(
            company=self.company, nom=RESEAU, sku='QJR306-ONDR',
            prix_vente=Decimal('14000'), prix_achat=Decimal('1'),
            quantite_stock=100)

    def _devis(self, *, etude_params=None):
        devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR306-0001',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            created_by=self.user, taux_tva=Decimal('20'),
            etude_params=etude_params or {})
        devis.lignes.create(
            produit=self.panneau, designation=PANNEAU_SANS_WATT,
            quantite=Decimal('12'), prix_unitaire=Decimal('1100'),
            remise=Decimal('0'), ordre=1)
        devis.lignes.create(
            produit=self.onduleur, designation=RESEAU, quantite=Decimal('1'),
            prix_unitaire=Decimal('14000'), remise=Decimal('0'), ordre=2)
        return devis

    # ── LE ROUGE ────────────────────────────────────────────────────────────
    def test_kwc_perime_est_omis_quand_proprietaire_ne_repond_pas(self):
        """ROUGE AVANT : un ``puissance_kwc`` hérité d'une exécution
        précédente (7.1) survit à la resynchro même quand le propriétaire,
        cette fois, ne sait plus répondre (panneau au watt illisible)."""
        devis = self._devis(etude_params={'puissance_kwc': 7.1})
        self.assertIsNone(puissance_kwc_du_devis(devis),
                          'la fixture doit rendre le propriétaire muet')

        sync_devis_from_layout(devis, layout(panels=12, kwc=8.8),
                               user=self.user)

        devis.refresh_from_db()
        self.assertNotIn(
            'puissance_kwc', devis.etude_params or {},
            "la clé périmée (7.1) doit être OMISE, pas reconduite")

    def test_proprietaire_sait_repondre_ecrit_la_nouvelle_valeur(self):
        """Non-régression : quand le propriétaire SAIT répondre, la
        nouvelle valeur est bien écrite (même en partant d'une clé
        périmée)."""
        devis = self._devis(etude_params={'puissance_kwc': 7.1})
        ligne = devis.lignes.get(designation=PANNEAU_SANS_WATT)
        ligne.designation = PANNEAU_LISIBLE
        ligne.save(update_fields=['designation'])
        self.panneau.nom = PANNEAU_LISIBLE
        self.panneau.save(update_fields=['nom'])

        attendu = puissance_kwc_du_devis(devis)
        self.assertIsNotNone(attendu)

        sync_devis_from_layout(devis, layout(panels=12, kwc=8.8),
                               user=self.user)
        devis.refresh_from_db()
        stocke = (devis.etude_params or {}).get('puissance_kwc')
        self.assertIsNotNone(stocke)
        self.assertNotEqual(stocke, 7.1,
                            'le kWc périmé ne doit jamais survivre')
        self.assertAlmostEqual(
            float(stocke), float(puissance_kwc_du_devis(devis)), places=2)

    def test_aucun_autre_champ_etude_params_nest_touche(self):
        """Le retrait du kWc périmé ne doit toucher AUCUN autre champ de
        ``etude_params`` — ni le supprimer, ni le modifier."""
        devis = self._devis(etude_params={
            'puissance_kwc': 7.1,
            'un_champ_qui_doit_survivre': 'valeur-intacte',
        })
        self.assertIsNone(puissance_kwc_du_devis(devis))

        sync_devis_from_layout(devis, layout(panels=12, kwc=8.8),
                               user=self.user)

        devis.refresh_from_db()
        etude = devis.etude_params or {}
        self.assertNotIn('puissance_kwc', etude)
        self.assertEqual(
            etude.get('un_champ_qui_doit_survivre'), 'valeur-intacte',
            "un champ etude_params sans rapport avec puissance_kwc a été "
            "touché par le retrait")
