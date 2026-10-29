# -*- coding: utf-8 -*-
"""TVA-LIGNE (06/10/2026) — une ligne créée SANS taux prend la TVA de son
produit (DC7 : ``Produit.tva`` fait foi par ligne, 10 % panneaux PV).

Constat en production (depuis le 20/09) : les lignes posées côté serveur
naissaient avec ``taux_tva`` NULL (le PDF leur appliquait le 20 % global du
devis), et le dry-run de composition rendait UN taux (20) pour toutes les
lignes — l'écran l'enregistrait ensuite sur les panneaux. Ces tests figent :

* ``creer_ligne`` sans taux → taux du produit ; un taux EXPLICITE (0 —
  AGR216 —, 20 tapé) n'est jamais touché ; une section reste sans taux ;
* ``remplacer_lignes`` (replace-lines) taux omis → taux du produit ;
* le dry-run ``POST devis/composition/`` rend 10 pour le panneau, 20 pour
  l'onduleur, et un TTC dérivé de CE taux ;
* ``LigneDevisSerializer`` expose ``produit_tva`` (lecture seule), jamais
  ``prix_achat``.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_tva_ligne_produit"
"""
from decimal import ROUND_HALF_UP, Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import Produit
from apps.ventes.domain.lignes import creer_ligne, remplacer_lignes
from apps.ventes.serializers import LigneDevisSerializer
from testkit.factories import (
    CompanyFactory, DevisFactory, ProduitFactory, UserFactory,
)

COMPO_URL = '/api/django/ventes/devis/composition/'


class _Base(TestCase):

    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company, role_legacy='admin')
        self.devis = DevisFactory(company=self.company,
                                  taux_tva=Decimal('20.00'))
        self.panneau = ProduitFactory(
            company=self.company, nom='Panneau Canadien Solar 710W',
            tva=Decimal('10.00'))
        self.onduleur = ProduitFactory(
            company=self.company, nom='Onduleur réseau Huawei 5kW',
            tva=Decimal('20.00'))
        self.sans_taux = ProduitFactory(
            company=self.company, nom='Socles', tva=None)

    def _ligne(self, produit=None, **champs):
        base = {'designation': getattr(produit, 'nom', 'X'),
                'quantite': Decimal('1'), 'prix_unitaire': Decimal('1000')}
        if produit is not None:
            base['produit'] = produit
        base.update(champs)
        return creer_ligne(self.devis, **base)


class CreerLignePrendLaTvaDuProduit(_Base):

    def test_sans_taux_prend_celui_du_produit(self):
        ligne = self._ligne(self.panneau)
        ligne.refresh_from_db()
        self.assertEqual(ligne.taux_tva, Decimal('10.00'))

    def test_taux_none_explicite_prend_celui_du_produit(self):
        ligne = self._ligne(self.panneau, taux_tva=None)
        ligne.refresh_from_db()
        self.assertEqual(ligne.taux_tva, Decimal('10.00'))

    def test_par_produit_id_aussi(self):
        ligne = creer_ligne(
            self.devis, produit_id=self.panneau.pk, designation='P',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
        ligne.refresh_from_db()
        self.assertEqual(ligne.taux_tva, Decimal('10.00'))

    def test_zero_explicite_reste_zero(self):
        # AGR216 — un 0 % explicite n'est jamais remplacé par la fiche.
        ligne = self._ligne(self.panneau, taux_tva=Decimal('0'),
                            tva_base_legale='Art. 92-I')
        ligne.refresh_from_db()
        self.assertEqual(ligne.taux_tva, Decimal('0'))

    def test_vingt_tape_reste_vingt(self):
        ligne = self._ligne(self.panneau, taux_tva=Decimal('20'))
        ligne.refresh_from_db()
        self.assertEqual(ligne.taux_tva, Decimal('20.00'))

    def test_produit_sans_taux_prend_celui_du_devis(self):
        # ATOT20 — pas de fiche ⇒ le taux du DEVIS est POSÉ (celui qui
        # s'appliquait déjà) : plus aucune ligne produit NULL.
        ligne = self._ligne(self.sans_taux)
        ligne.refresh_from_db()
        self.assertEqual(ligne.taux_tva, Decimal('20.00'))
        self.assertEqual(ligne.taux_tva_effectif, Decimal('20.00'))

    def test_section_reste_sans_taux(self):
        ligne = creer_ligne(
            self.devis, produit=None, designation='Kit',
            quantite=None, prix_unitaire=None, type_ligne='section')
        ligne.refresh_from_db()
        self.assertIsNone(ligne.taux_tva)


class ReplaceLinesTauxOmis(_Base):

    def test_taux_omis_prend_celui_du_produit(self):
        remplacer_lignes(self.devis, [
            {'produit': self.panneau.id, 'quantite': '10',
             'prix_unitaire': '1000'},
            {'produit': self.onduleur.id, 'quantite': '1',
             'prix_unitaire': '14000'},
            {'produit': self.panneau.id, 'quantite': '1',
             'prix_unitaire': '1000', 'taux_tva': '20'},
        ], self.company)
        taux = list(self.devis.lignes.order_by('ordre', 'id')
                    .values_list('taux_tva', flat=True))
        self.assertEqual(taux, [Decimal('10.00'), Decimal('20.00'),
                                Decimal('20.00')])


class DryRunCompositionTauxParLigne(TestCase):

    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company, role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        for nom, prix, tva in (
                ('Panneau Canadien Solar 710W', '1450', Decimal('10.00')),
                ('Onduleur réseau Huawei 5kW Monophasé', '14000',
                 Decimal('20.00')),
                ('Onduleur hybride Deye 5kW Monophasé', '17000',
                 Decimal('20.00')),
                ('Structures acier', '500', None),
                ('Structures aluminium', '850', None),
                ('Socles', '80', None),
                ('Transport', '1000', None)):
            Produit.objects.create(
                company=self.company, nom=nom, prix_vente=Decimal(prix),
                prix_achat=Decimal('1'), quantite_stock=1000, tva=tva)

    def test_panneau_10_onduleur_20(self):
        r = self.api.post(COMPO_URL, {
            'kwc': 5, 'panel_watt': 710, 'scenario': 'sans',
        }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        par_nom = {ligne['designation']: ligne for ligne in r.data['lignes']}
        panneau = next(v for k, v in par_nom.items() if 'Panneau' in k)
        onduleur = next(v for k, v in par_nom.items() if 'Onduleur' in k)
        self.assertEqual(panneau['taux_tva'], '10')
        self.assertEqual(onduleur['taux_tva'], '20')
        # Le TTC est dérivé du taux DE LA LIGNE.
        self.assertEqual(
            Decimal(panneau['prix_unitaire_ttc']),
            (Decimal(panneau['prix_unitaire_ht']) * Decimal('1.10')
             ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        self.assertEqual(
            Decimal(onduleur['prix_unitaire_ttc']),
            (Decimal(onduleur['prix_unitaire_ht']) * Decimal('1.20')
             ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        # Une ligne sans fiche de taux garde le taux demandé.
        for ligne in r.data['lignes']:
            if 'Structures' in ligne['designation']:
                self.assertEqual(ligne['taux_tva'], '20')


class SerialiseurExposeProduitTva(_Base):

    def test_produit_tva_en_lecture(self):
        ligne = self._ligne(self.panneau)
        data = LigneDevisSerializer(ligne).data
        self.assertEqual(Decimal(data['produit_tva']), Decimal('10.00'))
        self.assertNotIn('prix_achat', data)

    def test_produit_tva_null_sans_produit(self):
        ligne = creer_ligne(
            self.devis, produit=None, designation='Kit',
            quantite=None, prix_unitaire=None, type_ligne='section')
        data = LigneDevisSerializer(ligne).data
        self.assertIsNone(data['produit_tva'])

    def test_produit_tva_read_only(self):
        self.assertTrue(
            LigneDevisSerializer().fields['produit_tva'].read_only)


class SerialiseurExposeGroupeClient(_Base):
    """R2 (fondateur 28/10/2026) — ``groupe_client`` ('tableau_ci' |
    'supervision_ci' (R3) | 'installation_ci' | null), calculé du ``role_ci`` du PRODUIT (une seule
    source : ``moteur_ci.composition``), en lecture seule ; la ligne reste une
    par composant en base."""

    def setUp(self):
        super().setUp()
        # Le regroupement n'existe que sur un devis commercial / industriel.
        self.devis.mode_installation = 'commercial'
        self.devis.save(update_fields=['mode_installation'])

    def _produit_ci(self, nom, role_ci):
        return ProduitFactory(company=self.company, nom=nom, role_ci=role_ci,
                              tva=Decimal('20.00'))

    def test_null_hors_commercial_industriel(self):
        ligne = self._ligne(self._produit_ci('Coffret DC C&I', 'coffret_dc'))
        for mode in ('residentiel', 'agricole', ''):
            self.devis.mode_installation = mode
            self.devis.save(update_fields=['mode_installation'])
            ligne.refresh_from_db()
            self.assertIsNone(
                LigneDevisSerializer(ligne).data['groupe_client'], mode)
        self.devis.mode_installation = 'industriel'
        self.devis.save(update_fields=['mode_installation'])
        ligne.refresh_from_db()
        self.assertEqual(LigneDevisSerializer(ligne).data['groupe_client'],
                         'tableau_ci')

    def test_organe_du_tableau(self):
        for role in ('coffret_dc', 'coffret_ac', 'protection_ac',
                     'protection_dc', 'mise_a_la_terre'):
            ligne = self._ligne(self._produit_ci('Organe %s' % role, role))
            self.assertEqual(LigneDevisSerializer(ligne).data['groupe_client'],
                             'tableau_ci', role)

    def test_supervision_et_comptage(self):
        # R3.4 (fondateur 28/10/2026 soir) — le Smart Meter SORT du tableau.
        for role in ('compteur_injection', 'controleur_injection',
                     'logger_supervision'):
            ligne = self._ligne(self._produit_ci('Organe %s' % role, role))
            self.assertEqual(LigneDevisSerializer(ligne).data['groupe_client'],
                             'supervision_ci', role)

    def test_prestation_et_autres(self):
        pose = self._ligne(self._produit_ci('Pose des modules C&I',
                                            'pose_modules'))
        self.assertEqual(LigneDevisSerializer(pose).data['groupe_client'],
                         'installation_ci')
        cable = self._ligne(self._produit_ci('Câble AC', 'cable_ac'))
        self.assertIsNone(LigneDevisSerializer(cable).data['groupe_client'])
        self.assertIsNone(
            LigneDevisSerializer(self._ligne(self.panneau)).data['groupe_client'])
        section = creer_ligne(
            self.devis, produit=None, designation='Protection',
            quantite=None, prix_unitaire=None, type_ligne='section')
        self.assertIsNone(LigneDevisSerializer(section).data['groupe_client'])

    def test_lecture_seule_et_servi_par_l_api(self):
        self.assertTrue(
            LigneDevisSerializer().fields['groupe_client'].read_only)
        ligne = self._ligne(self._produit_ci('Coffret DC C&I', 'coffret_dc'))
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        reponse = api.get(f'/api/django/ventes/devis-lignes/{ligne.pk}/')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(reponse.json()['groupe_client'], 'tableau_ci')
        self.assertNotIn('prix_achat', reponse.json())
        devis = api.get(f'/api/django/ventes/devis/{self.devis.pk}/').json()
        self.assertEqual([li['groupe_client'] for li in devis['lignes']],
                         ['tableau_ci'])
