# -*- coding: utf-8 -*-
"""QJR20 (29/08/2026) — l'action sync-layout rafraîchit les études sur le devis
QU'ELLE VIENT D'ÉCRIRE.

LE DÉFAUT. ``sync_devis_from_layout`` recharge le devis sous
``select_for_update()`` et mute CETTE instance-là ; l'appelant, lui, garde celle
chargée en début de requête — et le viewset la charge avec
``prefetch_related('lignes', 'lignes__produit')``. ``rafraichir_etudes_du_devis``
repartait donc de la composition d'AVANT la resynchro et la RÉÉCRIVAIT par-dessus
ce que la resynchro venait de poser. La conception électrique — seule des quatre
études à n'être jamais recalculée à la lecture, et pourtant lue par la page
publique et l'annexe PDF depuis L-1V — persistait alors un schéma FAUX jusqu'à ce
qu'un humain rouvre l'onglet électrique.

Fixtures calquées sur ``test_pv42_boucle_electrique`` (mêmes fiches techniques
réelles : sans fiche, la conception REFUSE de calculer — PVFCH).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_qjr_sync_layout_fraicheur"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead
from apps.stock.models import FicheTechnique, Produit
from apps.ventes import services
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()


def layout_plat(panneaux):
    """Layout SANS géométrie de pans — le nombre de modules de l'étude
    électrique vient alors des LIGNES du devis (``groupes_du_devis`` →
    ``cible_depuis_lignes``), c'est-à-dire exactement du cache périmé que ce
    module épingle."""
    return {
        'scenario': 'reseau',
        'panelWatt': 550,
        'result': {'panels': panneaux,
                   'kwc': round(panneaux * 550 / 1000.0, 2),
                   'annualKwh': panneaux * 900,
                   'savings': panneaux * 800},
    }


class _FraicheurBase(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='qjr20-co', defaults={'nom': 'QJR20 Co'})
        self.user = User.objects.create_user(
            username='qjr20_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau Jinko 550W', sku='QJR20-PAN',
            prix_vente=Decimal('1100'), prix_achat=Decimal('800'),
            quantite_stock=200)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur réseau Huawei 10kW Triphasé',
            sku='QJR20-OND', prix_vente=Decimal('14000'),
            prix_achat=Decimal('11000'), quantite_stock=10)
        FicheTechnique.objects.create(
            company=self.company, produit=self.panneau, type_fiche='module',
            pmax_wc=Decimal('550.00'), voc_v=Decimal('49.90'),
            isc_a=Decimal('14.02'), vmp_v=Decimal('41.80'),
            imp_a=Decimal('13.16'),
            temp_coeff_voc_pct_c=Decimal('-0.270'),
            temp_coeff_pmax_pct_c=Decimal('-0.350'))
        FicheTechnique.objects.create(
            company=self.company, produit=self.onduleur,
            type_fiche='onduleur',
            ond_ac_kw=Decimal('10.00'), ond_phases=3, ond_n_mppt=2,
            ond_mppt_v_min=Decimal('200.0'), ond_mppt_v_max=Decimal('950.0'),
            ond_v_max_abs=Decimal('1100.0'),
            ond_i_max_mppt_a=Decimal('26.0'),
            ond_rendement_euro_pct=Decimal('98.0'), ond_bat_aucune=True)

    def _devis_neuf(self, panneaux=9):
        lead = Lead.objects.create(
            company=self.company, nom='Fraicheur', prenom='QJR20',
            email='qjr20@example.com')
        return services.build_devis_from_layout(
            layout=layout_plat(panneaux), user=self.user,
            company=self.company, lead=lead)

    def _comme_le_viewset(self, devis):
        """L'instance TELLE QUE LA VUE la charge — lignes PRÉCHARGÉES, donc
        servies depuis le cache de prefetch tant qu'on ne le vide pas."""
        return (Devis.objects
                .prefetch_related('lignes', 'lignes__produit')
                .get(pk=devis.pk))

    def _panneaux(self, devis):
        return sum(int(ligne.quantite or 0) for ligne in devis.lignes.all()
                   if 'Panneau' in ligne.designation)


class InstanceAppelanteRecaleeTests(_FraicheurBase):
    def test_le_service_recale_les_lignes_de_l_instance_qu_on_lui_passe(self):
        """ROUGE avant QJR20 : le cache de prefetch servait encore 9 panneaux
        APRÈS une resynchro qui en avait écrit 20."""
        devis = self._devis_neuf(9)
        prefetche = self._comme_le_viewset(devis)
        self.assertEqual(self._panneaux(prefetche), 9)

        services.sync_devis_from_layout(prefetche, layout_plat(20),
                                        user=self.user)
        self.assertEqual(self._panneaux(prefetche), 20)

    def test_le_service_recale_aussi_le_calepinage_et_l_etude(self):
        devis = self._devis_neuf(9)
        prefetche = self._comme_le_viewset(devis)
        avant = prefetche.layout_hash

        services.sync_devis_from_layout(prefetche, layout_plat(20),
                                        user=self.user)
        self.assertNotEqual(prefetche.layout_hash, avant)
        self.assertEqual(prefetche.roof_layout['result']['panels'], 20)
        self.assertAlmostEqual(
            float(prefetche.etude_params['puissance_kwc']), 11.0, places=2)

    def test_une_resynchro_sans_changement_ne_casse_rien(self):
        """Non-régression : renvoyer le MÊME layout ne fait aucune écriture et
        l'instance de l'appelant reste utilisable."""
        devis = self._devis_neuf(9)
        prefetche = self._comme_le_viewset(devis)
        resultat = services.sync_devis_from_layout(
            prefetche, layout_plat(9), user=self.user)
        self.assertTrue(resultat['inchange'])
        self.assertEqual(self._panneaux(prefetche), 9)


class EtudeElectriquePersisteeTests(_FraicheurBase):
    def test_l_etude_persistee_decrit_les_20_panneaux_resynchronises(self):
        """LE bug tel qu'il se voyait : après la resynchro, la conception
        ÉLECTRIQUE persistée décrivait encore 9 modules — un schéma faux servi
        à la page publique et à l'annexe PDF jusqu'à réouverture manuelle de
        l'onglet électrique."""
        devis = self._devis_neuf(9)
        devis.refresh_from_db()
        self.assertIsNotNone(
            devis.electrical_design,
            'fixture invalide : la conception initiale doit être calculable')
        self.assertEqual(devis.electrical_design['materiel']['nb_modules'], 9)

        prefetche = self._comme_le_viewset(devis)
        services.sync_devis_from_layout(prefetche, layout_plat(20),
                                        user=self.user)
        # EXACTEMENT ce que fait la vue juste après la resynchro.
        services.rafraichir_etudes_du_devis(prefetche)

        devis.refresh_from_db()
        self.assertEqual(devis.electrical_design['materiel']['nb_modules'], 20)

    def test_bout_en_bout_par_l_endpoint_sync_layout(self):
        devis = self._devis_neuf(9)
        resp = self.api.post(
            f'/api/django/ventes/devis/{devis.pk}/sync-layout/',
            layout_plat(20), format='json')
        self.assertEqual(resp.status_code, 200, resp.content[:400])
        self.assertFalse(resp.data['inchange'])
        self.assertEqual(resp.data['panneaux'], 20)

        devis.refresh_from_db()
        self.assertEqual(self._panneaux(devis), 20)
        self.assertEqual(devis.electrical_design['materiel']['nb_modules'], 20)

    def test_le_statut_n_est_jamais_ecrit(self):
        """Règle #4 — la resynchro LIT le statut, ne l'écrit jamais."""
        devis = self._devis_neuf(9)
        resp = self.api.post(
            f'/api/django/ventes/devis/{devis.pk}/sync-layout/',
            layout_plat(20), format='json')
        self.assertEqual(resp.status_code, 200, resp.content[:400])
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
