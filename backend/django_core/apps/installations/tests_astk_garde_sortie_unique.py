"""ASTK129 (C-ASTK-028) — GARDE DE CLASSE « une vente = une sortie ».

Pour CHAQUE chemin par lequel le matériel d'une vente quitte le stock —
facture directe, BC livré (toggle ``reserver_stock_bc`` OFF puis ON),
livraison directe chantier, consommation terrain F11 — suivi du passage
« Installé » (``changer_statut_chantier``), le test exige, sur un devis de 10
panneaux accepté (chantier, réservation 10, stock 30) :

  * Σ SORTIE du produit = 10 (la quantité vendue, jamais 20) ;
  * stock final = 30 + Σ ENTRÉE − 10 (20 partout, 30 pour la livraison
    directe qui reçoit puis sort 10).

LA TABLE DES CHEMINS. Les appelants de ``decompter_stock_lignes`` /
``record_stock_movement`` de type SORTIE dans ``apps/ventes`` et
``apps/stock`` sont RELUS dans le source (AST) et comparés à la table
ci-dessous : un chemin de sortie ajouté sans y être classé (couvert ici, ou
hors vente avec sa raison) fait échouer la garde EN LE NOMMANT.

Sonde RESA-1 (rouge sur 3c7b29427) : facture directe puis Installé → stock
10. Vert après ASTK120 / ASTK135 / ASTK98. Test-du-test : retirer l'appel
d'ASTK135 dans ``marquer-livre`` ⇒ le cas ``bc_livre_toggle_off`` échoue.

Source réelle : services/endpoints ventes, stock et installations réels
(lecture d'autres apps par leurs services publics, autorisé en test).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.installations.tests_astk_garde_sortie_unique"
"""
import ast
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()

QUANTITE_VENDUE = 10
STOCK_INITIAL = 30

#: Chemins de sortie d'une VENTE dans ventes/stock → cas joué ci-dessous.
CHEMINS_COUVERTS = {
    'apps/ventes/domain/facturation_ops.py::reserver_stock_devis_facture':
        'facture_directe',
    'apps/ventes/views/bon_commande.py::BonCommandeViewSet.marquer_livre':
        'bc_livre_toggle_off',
    'apps/stock/services.py::affecter_livraison_directe_chantier':
        'livraison_directe_chantier',
}

#: La primitive elle-même (ses appelants sont classés un par un).
PRIMITIVES = {
    'apps/ventes/domain/facturation_ops.py::decompter_stock_lignes':
        'décompteur unique des ventes (appelé par les chemins couverts)',
}

#: Sorties qui ne sont PAS la sortie du matériel d'une vente de chantier.
HORS_VENTE = {
    'apps/stock/services.py::apply_retour_fournisseur':
        'retour au fournisseur (achat), aucune vente',
    'apps/stock/services.py::annuler_reception_confirmee':
        'annulation d\'une réception fournisseur',
    'apps/stock/services.py::decrementer_stock_dotation_epi':
        'dotation EPI d\'un salarié',
    'apps/stock/services.py::consommer_et_produire_assemblage':
        'consommation des composants d\'un assemblage',
    'apps/stock/services.py::demonter_composite':
        'démontage d\'un composite',
    'apps/stock/services.py::decouper_produit':
        'découpe d\'un produit en sous-produits',
    'apps/stock/services_consignation.py::creer_depot_consignation':
        'dépôt de consignation (facturé par déclaration, ASTK198), sans '
        'chantier',
    'apps/stock/services_wms.py::decrementer_stock_expedition':
        'expédition WMS : ignore explicitement les lignes de chantier '
        '(AUD224), flux e-commerce/B2B seul',
    'apps/stock/services_wms.py::enregistrer_mouvement_scanne':
        'mouvement scanné manuel (type choisi par l\'opérateur)',
    'apps/stock/views/lot_entrepot.py::LotEntrepotViewSet.sortir':
        'sortie manuelle d\'un lot d\'entrepôt',
    'apps/stock/views/mouvement.py::MouvementStockViewSet.perform_create':
        'mouvement manuel saisi au stock',
}

#: DETTE NOMMÉE (ne peut que rétrécir) : chemin de sortie d'une vente qui ne
#: solde PAS encore la réservation du chantier — constat de cette garde, à
#: corriger par une tâche dédiée puis à déplacer dans CHEMINS_COUVERTS.
CHEMINS_EN_DETTE = {
    'apps/ventes/views/bon_commande.py::BonCommandeViewSet.livrer_partiel':
        'XSAL12 livraison partielle d\'un BC : SORTIE par record_stock_movement '
        'sans solder_reservations_chantier_vente — « Installé » ressort le '
        'matériel livré (constat ASTK129, tâche à ouvrir)',
}
CHEMINS_EN_DETTE_PLAFOND = 1

_CIBLES = {'decompter_stock_lignes', 'record_stock_movement'}
_TYPES_NON_SORTIE = ('ENTREE', 'AJUSTEMENT', 'REBUT', 'TRANSFERT',
                     'mouvement_type_entree')


def appelants_sortie():
    """``{'apps/<app>/<fichier>.py::<Classe.fonction>'}`` des appelants de
    ``decompter_stock_lignes`` / ``record_stock_movement`` de type SORTIE
    (ou de type non littéral) dans ``apps/ventes`` et ``apps/stock``."""
    racine = Path(settings.BASE_DIR)
    sites = set()
    for app in ('ventes', 'stock'):
        for chemin in sorted((racine / 'apps' / app).rglob('*.py')):
            parties = set(chemin.relative_to(racine).parts)
            if (parties & {'migrations', 'tests', 'management'}
                    or chemin.name.startswith('test')):
                continue
            source = chemin.read_text(encoding='utf-8')
            relatif = chemin.relative_to(racine).as_posix()

            def parcourir(noeud, pile):
                for enfant in ast.iter_child_nodes(noeud):
                    if isinstance(enfant, (ast.FunctionDef,
                                           ast.AsyncFunctionDef,
                                           ast.ClassDef)):
                        parcourir(enfant, pile + [enfant.name])
                        continue
                    if isinstance(enfant, ast.Call):
                        f = enfant.func
                        nom = (f.id if isinstance(f, ast.Name) else
                               f.attr if isinstance(f, ast.Attribute)
                               else None)
                        if nom in _CIBLES and pile:
                            type_src = next((
                                ast.get_source_segment(source, k.value) or ''
                                for k in enfant.keywords
                                if k.arg == 'type_mouvement'), '')
                            if not any(t in type_src
                                       for t in _TYPES_NON_SORTIE):
                                sites.add(f'{relatif}::{".".join(pile)}')
                    parcourir(enfant, pile)

            parcourir(ast.parse(source), [])
    return sites


class TableDesCheminsTests(SimpleTestCase):
    """La table des chemins suit le source : rien d'oublié, rien de périmé."""

    def test_chaque_chemin_de_sortie_est_classe(self):
        classes = (set(CHEMINS_COUVERTS) | set(PRIMITIVES) | set(HORS_VENTE)
                   | set(CHEMINS_EN_DETTE))
        oublies = sorted(appelants_sortie() - classes)
        self.assertEqual(
            oublies, [],
            'Chemin(s) de SORTIE de stock non classé(s) : '
            + ', '.join(oublies) + ' — une sortie de VENTE doit solder la '
            'réservation du chantier (installations.services.'
            'solder_reservations_vente) et être jouée par GardeSortieUnique ; '
            'sinon classez-la HORS_VENTE avec sa raison.')

    def test_la_table_nest_pas_perimee(self):
        sites = appelants_sortie()
        classes = (set(CHEMINS_COUVERTS) | set(PRIMITIVES) | set(HORS_VENTE)
                   | set(CHEMINS_EN_DETTE))
        self.assertEqual(sorted(classes - sites), [],
                         'entrée(s) de table sans appelant : retirez-les.')

    def test_la_dette_ne_peut_que_retrecir(self):
        self.assertLessEqual(len(CHEMINS_EN_DETTE), CHEMINS_EN_DETTE_PLAFOND)
        self.assertEqual(set(CHEMINS_EN_DETTE) & set(CHEMINS_COUVERTS), set())

    def test_chaque_chemin_couvert_est_joue(self):
        self.assertLessEqual(set(CHEMINS_COUVERTS.values()),
                             set(GardeSortieUnique.CAS))


class GardeSortieUnique(TestCase):
    #: Cas joués (les chemins couverts + ceux portés par installations).
    CAS = ('facture_directe', 'bc_livre_toggle_off', 'bc_livre_toggle_on',
           'livraison_directe_chantier', 'consommation_terrain_f11')

    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company

        self.company = Company.objects.create(
            nom='Co ASTK129', slug='co-astk129')
        self.user = User.objects.create_user(
            username='resp-astk129', password='x', company=self.company,
            role_legacy='responsable')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Site', prenom='Client',
            email='astk129@example.invalid')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self._n = 0

    def _suivant(self):
        self._n += 1
        return self._n

    def _vente(self):
        """Devis de 10 panneaux accepté, chantier créé (réservation 10),
        stock 30 — un produit NEUF par cas : les cas ne se mélangent pas."""
        from apps.crm.models import Lead
        from apps.installations.models import StockReservation
        from apps.installations.services import create_installation_from_devis
        from apps.stock.models import Produit
        from apps.ventes.models import Devis, LigneDevis

        n = self._suivant()
        panneau = Produit.objects.create(
            company=self.company, nom=f'Panneau ASTK129-{n}',
            sku=f'SKU-ASTK129-{n}', prix_vente=Decimal('100'),
            prix_achat=Decimal('60'), quantite_stock=STOCK_INITIAL,
            tva=Decimal('20.00'))
        lead = Lead.objects.create(
            company=self.company, nom='Site', prenom=f'Client {n}',
            stage='SIGNED', type_installation='residentiel')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ASTK129-{n}',
            client=self.client_obj, lead=lead, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'), mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=devis, produit=panneau, designation='Panneau',
            quantite=Decimal(QUANTITE_VENDUE), prix_unitaire=Decimal('100'),
            taux_tva=Decimal('20.00'))
        inst, _ = create_installation_from_devis(
            devis, self.user, self.company)
        resa = StockReservation.objects.get(
            installation=inst, produit=panneau)
        self.assertEqual(resa.quantite, QUANTITE_VENDUE)
        return devis, inst, panneau

    # ── Les chemins de sortie ─────────────────────────────────────────────

    def _facture_directe(self, devis, inst, panneau):
        from apps.ventes.domain.facturation_ops import facturer_devis_complet
        facturer_devis_complet(
            devis=devis, user=self.user, company=self.company, paiements=[])

    def _bc_livre(self, devis, toggle):
        from apps.parametres.models import CompanyProfile
        from apps.ventes.models import BonCommande

        profil = CompanyProfile.get(company=self.company)
        profil.reserver_stock_bc = toggle
        profil.save()
        bc = BonCommande.objects.create(
            company=self.company, reference=f'BC-ASTK129-{self._suivant()}',
            devis=devis, client=self.client_obj,
            statut=BonCommande.Statut.CONFIRME)
        rep = self.api.post(
            f'/api/django/ventes/bons-commande/{bc.id}/marquer-livre/')
        self.assertEqual(rep.status_code, 200, getattr(rep, 'data', rep))
        profil.reserver_stock_bc = False  # les cas suivants : défaut société
        profil.save()

    def _bc_livre_toggle_off(self, devis, inst, panneau):
        self._bc_livre(devis, toggle=False)

    def _bc_livre_toggle_on(self, devis, inst, panneau):
        self._bc_livre(devis, toggle=True)

    def _livraison_directe_chantier(self, devis, inst, panneau):
        from apps.stock.models import BonCommandeFournisseur, Fournisseur

        fournisseur = Fournisseur.objects.create(
            company=self.company, nom=f'Fournisseur {self._suivant()}')
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company,
            reference=f'BCF-ASTK129-{self._suivant()}',
            fournisseur=fournisseur, chantier_livraison=inst,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne = bcf.lignes.create(
            produit=panneau, quantite=QUANTITE_VENDUE,
            prix_achat_unitaire=Decimal('60'))
        rep = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bcf.id}/'
            'recevoir/',
            {'receptions': [{'ligne': ligne.id,
                             'quantite': QUANTITE_VENDUE}]},
            format='json')
        self.assertEqual(rep.status_code, 200, getattr(rep, 'data', rep))

    def _consommation_terrain_f11(self, devis, inst, panneau):
        from apps.installations import field_capture
        from apps.installations.models import Intervention

        intervention = Intervention.objects.create(
            company=self.company, installation=inst)
        cons = field_capture.ensure_consommation(intervention)
        lignes = list(cons.lignes.filter(produit=panneau))
        self.assertEqual(
            [ligne.quantite_utilisee for ligne in lignes],
            [Decimal(QUANTITE_VENDUE)],
            'F11 : la réconciliation ne reprend pas la nomenclature vendue')
        field_capture.validate_consommation(cons, self.user)

    # ── La garde ──────────────────────────────────────────────────────────

    def _installer(self, inst):
        from apps.installations.models import Installation
        from apps.installations.services import changer_statut_chantier
        inst.refresh_from_db()
        changer_statut_chantier(
            inst, Installation.Statut.INSTALLE, self.user,
            verifier_gates=False)

    def test_une_vente_une_sortie(self):
        from apps.stock.models import MouvementStock
        from apps.stock.services import (
            mouvement_type_entree, mouvement_type_sortie,
        )

        for cas in self.CAS:
            with self.subTest(chemin=cas):
                devis, inst, panneau = self._vente()
                getattr(self, f'_{cas}')(devis, inst, panneau)
                self._installer(inst)

                mouvements = MouvementStock.objects.filter(produit=panneau)
                sorties = mouvements.filter(
                    type_mouvement=mouvement_type_sortie()).aggregate(
                        t=Sum('quantite'))['t'] or 0
                entrees = mouvements.filter(
                    type_mouvement=mouvement_type_entree()).aggregate(
                        t=Sum('quantite'))['t'] or 0
                self.assertEqual(
                    sorties, QUANTITE_VENDUE,
                    f'« {cas} » puis « Installé » : {sorties} unité(s) '
                    f'sortie(s) pour {QUANTITE_VENDUE} vendue(s) — la sortie '
                    'de la vente doit solder la réservation du chantier '
                    '(solder_reservations_vente).')
                panneau.refresh_from_db()
                self.assertEqual(
                    panneau.quantite_stock,
                    STOCK_INITIAL + entrees - QUANTITE_VENDUE, cas)
