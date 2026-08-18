# -*- coding: utf-8 -*-
"""PVMRQ — offre à deux gammes paramétrable : marque préférée par gamme/rôle
(fondateur 18/08/2026).

Verrouille le contrat de ``ParametresGammes`` / ``services.marque_preferee``
et son câblage dans ``services._pick_product`` :

1. Le réglage est scopé société — jamais de fuite entre deux sociétés.
2. Une société sans réglage explicite obtient le comportement HISTORIQUE
   (aucune préférence, le moins cher gagne) : le get-or-create ne change rien
   par défaut.
3. Une marque préférée réglée pour (gamme, rôle) GAGNE TOUJOURS, même face à
   un candidat moins cher / premier dans le vivier.
4. Une marque préférée SANS AUCUN produit correspondant renvoie ``None`` —
   jamais un repli silencieux sur une autre marque.
5. Un rôle hors ``ROLES_AUTO_COMPOSITION`` (ou une gamme hors des SLOTS fixes)
   est rejeté par ``clean()``/le sérialiseur, jamais silencieusement accepté.
6. ``deux_gammes`` bascule proprement (persist + relecture), et le libellé
   renommable (``nom_premium``) ne déplace jamais les clés JSON de ``marques``
   (indexées par les SLOTS fixes, pas par le libellé affiché).

Run :
    DB_NAME=erp_ventes python manage.py test \
        apps.ventes.tests.test_gammes_marques -v 2
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.stock.models import Produit
from apps.ventes import services
from apps.ventes.models import ParametresGammes
from apps.ventes.serializers import ParametresGammesSerializer
from authentication.models import Company


class ParametresGammesBase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor PVMRQ')

    def _produit(self, nom, sku, *, marque='', prix='10000'):
        return Produit.objects.create(
            company=self.company, nom=nom, sku=sku, marque=marque,
            prix_achat=Decimal('1'), prix_vente=Decimal(prix),
            quantite_stock=10)


# ── 1. Portée société ────────────────────────────────────────────────────

class PorteeSocieteTests(ParametresGammesBase):
    def test_une_societe_ne_lit_jamais_le_reglage_d_une_autre(self):
        autre = Company.objects.create(nom='Autre société PVMRQ')
        ParametresGammes.objects.create(
            company=autre, deux_gammes=True,
            marques={'Essentielle': {'panneau': 'Jinko'}})

        # Aucun réglage pour self.company : marque_preferee doit rester None,
        # jamais lire celui d'``autre`` (fuite cross-tenant).
        self.assertIsNone(
            services.marque_preferee(self.company, 'Essentielle', 'panneau'))

    def test_pick_product_ne_croise_pas_le_reglage_d_une_autre_societe(self):
        autre = Company.objects.create(nom='Autre société PVMRQ 2')
        ParametresGammes.objects.create(
            company=autre, marques={'Essentielle': {'panneau': 'Jinko'}})

        moins_cher = self._produit('Panneau Canadian Solar 550W', 'PVMRQ-X1',
                                   marque='Canadian Solar', prix='900')
        self._produit('Panneau Jinko 550W', 'PVMRQ-X2', marque='Jinko',
                      prix='1500')

        retenu = services._pick_product(
            self.company, services._is_panel, role='panneau',
            gamme='Essentielle')
        self.assertEqual(retenu, moins_cher)


# ── 2. Défaut = comportement historique inchangé ────────────────────────

class DefautSansRegressionTests(ParametresGammesBase):
    def test_get_or_create_ne_change_rien_au_comportement_historique(self):
        moins_cher = self._produit('Panneau Jinko 550W', 'PVMRQ-D1',
                                   marque='Jinko', prix='1000')
        self._produit('Panneau Canadian Solar 550W', 'PVMRQ-D2',
                      marque='Canadian Solar', prix='1200')

        # Aucune ligne ParametresGammes en base : toujours le moins cher.
        retenu = services._pick_product(
            self.company, services._is_panel, role='panneau')
        self.assertEqual(retenu, moins_cher)

        params = services.get_parametres_gammes(self.company)
        self.assertFalse(params.deux_gammes)
        self.assertEqual(params.marques, {})
        self.assertEqual(params.nom_essentielle, 'Essentielle')
        self.assertEqual(params.nom_premium, 'Premium')

        # La ligne existe désormais (get-or-create) : la sélection reste
        # inchangée puisqu'aucune préférence n'y est réglée.
        retenu_apres = services._pick_product(
            self.company, services._is_panel, role='panneau')
        self.assertEqual(retenu_apres, moins_cher)

    def test_role_none_laisse_pick_product_strictement_inchange(self):
        """Un appelant NON migré (``role=None``, le défaut) ne consulte même
        pas le réglage — un préférence réglée serait ignorée."""
        moins_cher = self._produit('Panneau Jinko 550W', 'PVMRQ-D3',
                                   marque='Jinko', prix='900')
        self._produit('Panneau Canadian Solar 550W', 'PVMRQ-D4',
                      marque='Canadian Solar', prix='1400')
        ParametresGammes.objects.create(
            company=self.company,
            marques={'Essentielle': {'panneau': 'Canadian Solar'}})

        retenu = services._pick_product(self.company, services._is_panel)
        self.assertEqual(retenu, moins_cher)


# ── 3. La marque préférée gagne toujours ────────────────────────────────

class MarquePrefereeGagneTests(ParametresGammesBase):
    def test_la_marque_preferee_gagne_meme_moins_chere_pas_premiere(self):
        self._produit('Panneau Jinko 550W', 'PVMRQ-W1',
                      marque='Jinko', prix='900')          # moins cher, PAS préféré
        premium = self._produit('Panneau Canadian Solar 550W', 'PVMRQ-W2',
                                marque='Canadian Solar', prix='1500')

        ParametresGammes.objects.create(
            company=self.company,
            marques={'Essentielle': {'panneau': 'Canadian Solar'}})

        retenu = services._pick_product(
            self.company, services._is_panel, role='panneau',
            gamme='Essentielle')
        self.assertEqual(retenu, premium)

    def test_marque_via_nom_produit_quand_le_champ_marque_est_vide(self):
        # ``marque`` NON renseigné sur la fiche (``marque=''``) : repli sur le
        # NOM du produit, qui doit seulement CONTENIR la marque préférée.
        self._produit('Onduleur Deye 10kW Réseau', 'PVMRQ-W3', prix='8000')
        huawei_par_nom = self._produit(
            'Onduleur Huawei SUN2000 10kW Réseau', 'PVMRQ-W4', prix='9500')

        ParametresGammes.objects.create(
            company=self.company,
            marques={'Essentielle': {'onduleur_reseau': 'Huawei'}})

        retenu = services._pick_product(
            self.company, services._is_reseau_inverter,
            role='onduleur_reseau', gamme='Essentielle')
        self.assertEqual(retenu, huawei_par_nom)

    def test_les_deux_gammes_ont_chacune_leur_propre_marque(self):
        essentielle = self._produit('Panneau Jinko 550W', 'PVMRQ-W5',
                                    marque='Jinko', prix='900')
        premium = self._produit('Panneau Canadian Solar 550W', 'PVMRQ-W6',
                                marque='Canadian Solar', prix='1500')

        ParametresGammes.objects.create(
            company=self.company, deux_gammes=True,
            marques={
                'Essentielle': {'panneau': 'Jinko'},
                'Premium': {'panneau': 'Canadian Solar'},
            })

        self.assertEqual(
            services._pick_product(self.company, services._is_panel,
                                   role='panneau', gamme='Essentielle'),
            essentielle)
        self.assertEqual(
            services._pick_product(self.company, services._is_panel,
                                   role='panneau', gamme='Premium'),
            premium)


# ── 4. Marque réglée sans match ⇒ None, jamais un repli silencieux ──────

class MarqueAbsenteRenvoieNoneTests(ParametresGammesBase):
    def test_marque_reglee_sans_aucun_produit_correspondant_renvoie_none(self):
        self._produit('Panneau Jinko 550W', 'PVMRQ-N1', marque='Jinko',
                      prix='900')

        ParametresGammes.objects.create(
            company=self.company,
            marques={'Essentielle': {'panneau': 'LONGi'}})  # marque absente

        retenu = services._pick_product(
            self.company, services._is_panel, role='panneau',
            gamme='Essentielle')
        self.assertIsNone(retenu)

    def test_jamais_un_repli_silencieux_sur_une_autre_marque(self):
        """Deux candidats D'AUTRES marques existent : la fonction ne doit en
        piocher AUCUN — c'est le cœur de la règle « jamais de repli »."""
        self._produit('Panneau Jinko 550W', 'PVMRQ-N2', marque='Jinko',
                      prix='900')
        self._produit('Panneau Canadian Solar 550W', 'PVMRQ-N3',
                      marque='Canadian Solar', prix='1100')

        ParametresGammes.objects.create(
            company=self.company,
            marques={'Essentielle': {'panneau': 'LONGi'}})

        retenu = services._pick_product(
            self.company, services._is_panel, role='panneau',
            gamme='Essentielle')
        self.assertIsNone(retenu)


# ── 5. Gamme/rôle inconnus, valeur vide ──────────────────────────────────

class GammeEtRoleTests(ParametresGammesBase):
    def test_gamme_inconnue_ne_matche_aucun_slot_renvoie_none(self):
        ParametresGammes.objects.create(
            company=self.company,
            marques={'Essentielle': {'panneau': 'Jinko'}})

        self.assertIsNone(
            services.marque_preferee(self.company, 'Gamme Fantôme', 'panneau'))

    def test_gamme_vide_ou_none_retombe_sur_essentielle(self):
        ParametresGammes.objects.create(
            company=self.company,
            marques={'Essentielle': {'panneau': 'Jinko'}})

        self.assertEqual(
            services.marque_preferee(self.company, '', 'panneau'), 'Jinko')
        self.assertEqual(
            services.marque_preferee(self.company, None, 'panneau'), 'Jinko')

    def test_role_inconnu_renvoie_none_sans_lever(self):
        ParametresGammes.objects.create(
            company=self.company,
            marques={'Essentielle': {'panneau': 'Jinko'}})

        self.assertIsNone(
            services.marque_preferee(self.company, 'Essentielle', 'role_zzz'))

    def test_marque_vide_stockee_vaut_aucune_preference(self):
        ParametresGammes.objects.create(
            company=self.company,
            marques={'Essentielle': {'panneau': '   '}})

        self.assertIsNone(
            services.marque_preferee(self.company, 'Essentielle', 'panneau'))

    def test_aucune_ligne_parametresgammes_renvoie_none(self):
        # Lecture directe (sans passer par get_parametres_gammes) : aucune
        # ligne en base ⇒ None, jamais une exception.
        self.assertIsNone(
            services.marque_preferee(self.company, 'Essentielle', 'panneau'))


# ── 6. Renommage du libellé : les clés JSON ne bougent jamais ──────────

class RenommageLibelleTests(ParametresGammesBase):
    def test_renommer_premium_en_luxe_ne_deplace_pas_les_cles_json(self):
        ParametresGammes.objects.create(
            company=self.company, deux_gammes=True, nom_premium='Luxe',
            marques={'Premium': {'panneau': 'Canadian Solar'}})

        # Le vendeur tape 'Luxe' (le libellé AFFICHÉ) sur le devis :
        # marque_preferee doit quand même résoudre le SLOT fixe 'Premium'.
        self.assertEqual(
            services.marque_preferee(self.company, 'Luxe', 'panneau'),
            'Canadian Solar')


# ── 7. Rôle/gamme invalides rejetés à l'écriture ────────────────────────

class RoleEtGammeInvalidesRejetesTests(ParametresGammesBase):
    def test_clean_rejette_un_role_hors_du_tuple(self):
        params = ParametresGammes(
            company=self.company,
            marques={'Essentielle': {'ROLE_INEXISTANT': 'Jinko'}})
        with self.assertRaises(ValidationError):
            params.full_clean()

    def test_clean_rejette_une_gamme_hors_des_slots_fixes(self):
        params = ParametresGammes(
            company=self.company,
            marques={'Luxe': {'panneau': 'Jinko'}})
        with self.assertRaises(ValidationError):
            params.full_clean()

    def test_clean_accepte_un_reglage_valide(self):
        params = ParametresGammes(
            company=self.company,
            marques={'Essentielle': {'panneau': 'Jinko'},
                     'Premium': {'panneau': 'Canadian Solar'}})
        params.full_clean()  # ne doit PAS lever

    def test_serializer_rejette_un_role_hors_du_tuple(self):
        params = ParametresGammes.objects.create(company=self.company)
        serializer = ParametresGammesSerializer(
            params,
            data={'marques': {'Essentielle': {'ROLE_INEXISTANT': 'Jinko'}}},
            partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn('marques', serializer.errors)

    def test_serializer_rejette_une_gamme_hors_des_slots_fixes(self):
        params = ParametresGammes.objects.create(company=self.company)
        serializer = ParametresGammesSerializer(
            params, data={'marques': {'Luxe': {'panneau': 'Jinko'}}},
            partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn('marques', serializer.errors)

    def test_serializer_accepte_un_reglage_valide(self):
        params = ParametresGammes.objects.create(company=self.company)
        serializer = ParametresGammesSerializer(
            params,
            data={'deux_gammes': True,
                  'marques': {'Essentielle': {'panneau': 'Jinko'}}},
            partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)


# ── 8. deux_gammes bascule proprement ────────────────────────────────────

class DeuxGammesToggleTests(ParametresGammesBase):
    def test_deux_gammes_bascule_proprement(self):
        params = services.get_parametres_gammes(self.company)
        self.assertFalse(params.deux_gammes)

        params.deux_gammes = True
        params.save(update_fields=['deux_gammes'])

        relu = services.get_parametres_gammes(self.company)
        self.assertTrue(relu.deux_gammes)
        self.assertEqual(relu.pk, params.pk)  # toujours le même singleton

        relu.deux_gammes = False
        relu.save(update_fields=['deux_gammes'])
        self.assertFalse(
            services.get_parametres_gammes(self.company).deux_gammes)

    def test_unicite_par_societe(self):
        services.get_parametres_gammes(self.company)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ParametresGammes.objects.create(company=self.company)


# ── 9. Les SLOTS fixes ne dérivent jamais de GAMME_NOMS_DEFAUT ─────────

class SlotsMiroirServicesTests(TestCase):
    def test_slots_fixes_miroir_exact_de_gamme_noms_defaut(self):
        self.assertEqual(ParametresGammes.SLOTS, services.GAMME_NOMS_DEFAUT)


class ParametresGammesLecturePourTousTests(TestCase):
    """PVMRQ (suivi 18/08) — la LECTURE du réglage est ouverte à tout
    utilisateur authentifié de la société : l'épinglage de marque doit
    s'appliquer aux devis de TOUS les commerciaux (un GET réservé au
    responsable faisait retomber leurs compositions en « aucune préférence »
    en silence). L'ÉCRITURE reste Admin/Responsable."""

    def _user(self, company, username, role):
        from django.contrib.auth import get_user_model
        return get_user_model().objects.create_user(
            username=username, password='x', company=company,
            role_legacy=role)

    def test_commercial_lit_mais_ne_modifie_pas(self):
        from rest_framework.test import APIClient
        from authentication.models import Company
        company = Company.objects.create(slug='pvmrq-lecture', nom='PVMRQ L')
        commercial = self._user(company, 'pvmrq-commercial', 'commercial')
        api = APIClient()
        api.force_authenticate(commercial)
        resp = api.get('/api/django/ventes/parametres-gammes/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('marques', resp.json())
        patch = api.patch('/api/django/ventes/parametres-gammes/',
                          {'deux_gammes': True}, format='json')
        self.assertEqual(patch.status_code, 403)

    def test_anonyme_toujours_refuse(self):
        from rest_framework.test import APIClient
        resp = APIClient().get('/api/django/ventes/parametres-gammes/')
        self.assertIn(resp.status_code, (401, 403))
