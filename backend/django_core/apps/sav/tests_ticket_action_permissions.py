"""Verrouille la correspondance entre le kwarg ``permission_classes`` de chaque
``@action`` de ``TicketViewSet`` et le tier réellement appliqué par
``get_permissions()``.

Contexte du bug : ``TicketViewSet.get_permissions()`` est une surcharge qui
n'inspecte PAS ``self.permission_classes`` — elle branche sur ``self.action``
via des listes en dur. Toute ``@action`` décorée avec ``permission_classes=[…]``
mais ABSENTE de ces listes retombe silencieusement sur ``IsAdminRole`` (plus
restrictif que voulu — le kwarg du décorateur devient du code mort).

Le test central lit dynamiquement le ``permission_classes`` déclaré par chaque
``@action`` et vérifie que ``get_permissions()`` renvoie EXACTEMENT le même tier
— donc il attrape aussi toute future ``@action`` ajoutée sans mise à jour de
``get_permissions()``.
"""
import inspect

from django.test import TestCase

from apps.sav.views import TicketViewSet


def _action_methods():
    """Toutes les méthodes ``@action`` de TicketViewSet (marquées par DRF avec
    un attribut ``mapping``) portant un ``permission_classes`` explicite."""
    out = {}
    for name, method in inspect.getmembers(TicketViewSet, inspect.isfunction):
        if not hasattr(method, 'mapping'):
            continue  # pas une @action
        declared = (getattr(method, 'kwargs', {}) or {}).get('permission_classes')
        if declared:
            out[name] = declared
    return out


def _tiers(action):
    view = TicketViewSet()
    view.action = action
    return [type(p).__name__ for p in view.get_permissions()]


def _tier_name(action):
    # ACSV62 : le premier garde est le palier ``sav_*`` ; un droit métier
    # (``DroitDeLaGrille``) peut s'y ajouter derrière.
    perms = _tiers(action)
    assert perms, f"{action}: aucune permission"
    return perms[0]


class TicketActionPermissionTierTests(TestCase):
    def test_get_permissions_honors_every_action_decorator(self):
        """Chaque @action doit obtenir, via get_permissions(), le MÊME tier que
        son décorateur permission_classes déclare (jamais un IsAdminRole subi)."""
        decorated = _action_methods()
        self.assertTrue(decorated, "aucune @action détectée — test cassé ?")
        for name, declared in decorated.items():
            with self.subTest(action=name):
                # ex. [HasPermissionOrLegacy_sav_gerer] ; ASEC50 : la garde
                # de la grille s'ajoute (reaffecter-equipe → sav_reassign).
                expected = [c.__name__ for c in declared]
                actual = _tiers(name)
                self.assertEqual(
                    actual, expected,
                    f"@action '{name}' déclare {expected} mais get_permissions() "
                    f"renvoie {actual} — ajoute '{name}' au bon bucket de "
                    f"TicketViewSet.get_permissions().")

    def test_no_ticket_action_falls_through_to_admin(self):
        """Aucune @action de TicketViewSet n'est censée être admin-only : une
        qui retombe sur IsAdminRole trahit un oubli dans get_permissions()."""
        for name in _action_methods():
            with self.subTest(action=name):
                self.assertNotIn(
                    'IsAdminRole', _tiers(name),
                    f"@action '{name}' retombe sur IsAdminRole (oubli dans "
                    f"get_permissions()).")

    def test_previously_broken_actions_regression(self):
        """Régression explicite : ces endpoints déclaraient sav_gerer/sav_voir
        mais exigeaient IsAdminRole avant le correctif."""
        gerer = ['pieces_compatibles', 'premier_reponse', 'pieces',
                 'supprimer_piece', 'pieces_retirees', 'generer_facture',
                 'prets_equipement', 'retourner_pret', 'creer_lead', 'checklist']
        for name in gerer:
            with self.subTest(action=name):
                self.assertEqual(_tier_name(name), 'HasPermissionOrLegacy_sav_gerer')
        self.assertEqual(_tier_name('triage_ia'), 'HasPermissionOrLegacy_sav_voir')

    def test_destroy_stays_admin_only(self):
        self.assertEqual(_tier_name('destroy'), 'IsAdminRole')

    def test_reads_stay_sav_voir(self):
        for name in ['historique', 'rapport_pdf', 'lien_client', 'similaires']:
            with self.subTest(action=name):
                self.assertEqual(_tier_name(name), 'HasPermissionOrLegacy_sav_voir')

    def test_lectures_sav_bornees_au_module(self):
        """APFS107 (C-APFS-080, D-APFS-4) — balai du routeur ``sav`` : la
        lecture ``list`` de CHAQUE vue est refusée à Admin RH et Commercial
        terrain (aucun code sav) ; Technicien, Commercial et Directeur
        (``sav_voir``) et le compte hérité lisent les 14 vues ouvertes."""
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        from apps.roles import permissions_registre as registre
        from apps.roles.models import Role
        from apps.sav.urls import router
        from authentication.models import Company
        from authentication.tests_asec11_responsable_module import (
            lectures_acceptees,
        )

        societe = Company.objects.create(nom='APFS107', slug='apfs107')
        User = get_user_model()

        def compte(nom, permissions):
            role = Role.objects.create(company=societe, nom=nom,
                                       permissions=list(permissions),
                                       est_systeme=False)
            return User.objects.create_user(
                username=f'apfs107-{nom}', password='x', company=societe,
                role=role, role_legacy='responsable')
        refuses = {nom: compte(nom, perms) for nom, perms in (
            ('admin_rh', registre.ADMIN_RH_PERMISSIONS),
            ('commercial_terrain', registre.COMMERCIAL_TERRAIN_PERMISSIONS))}
        admis = {nom: compte(nom, perms) for nom, perms in (
            ('technicien', registre.TECHNICIEN_PERMISSIONS),
            ('commercial', registre.COMMERCIAL_PERMISSIONS),
            ('directeur', registre.DIRECTEUR_PERMISSIONS))}
        admis['herite'] = User.objects.create_user(
            username='apfs107-herite', password='x', company=societe,
            role_legacy='responsable')
        vues = [vs for _prefixe, vs, _nom in router.registry]
        deja_fermees = {'TicketViewSet', 'EquipementViewSet', 'ProblemeViewSet'}
        ouvertes = [vs for vs in vues if vs.__name__ not in deja_fermees]
        self.assertEqual(len(ouvertes), 14, [vs.__name__ for vs in ouvertes])
        for (vue, nom), accepte in lectures_acceptees(vues, refuses).items():
            self.assertFalse(accepte, f'{vue} : lecture ouverte à {nom}')
        for (vue, nom), accepte in lectures_acceptees(ouvertes, admis).items():
            self.assertTrue(accepte, f'{vue} : lecture refusée à {nom}')
        for user, attendu in ((refuses['admin_rh'], 403),
                              (admis['technicien'], 200)):
            api = APIClient()
            api.force_authenticate(user)
            r = api.get('/api/django/sav/warranty-claims/')
            self.assertEqual(r.status_code, attendu, r.content[:200])

    def test_gestes_ventes_et_stock_exigent_leur_droit(self):
        """ACSV62 / D-ACSV-3 : en plus de ``sav_gerer``, facturer / devis exigent
        ``ventes_creer`` et tout mouvement de stock d'un ticket
        ``stock_mouvement`` (403 nommé, rien d'écrit)."""
        from decimal import Decimal

        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        from apps.crm.models import Client
        from apps.roles.models import Role
        from apps.roles.permissions_registre import TECHNICIEN_PERMISSIONS
        from apps.sav.models import PieceConsommee, Ticket
        from apps.stock.models import Produit
        from authentication.models import Company

        User = get_user_model()
        societe = Company.objects.create(nom='ACSV62', slug='acsv62')
        client = Client.objects.create(company=societe, nom='C')
        ticket = Ticket.objects.create(
            company=societe, reference='SAV-ACSV62', client=client,
            couverture='facturable')
        produit = Produit.objects.create(
            company=societe, nom='Onduleur', sku='OND-ACSV62',
            prix_vente=Decimal('5000'), quantite_stock=Decimal('5'))

        def _api(nom, permissions):
            # Le test porte sur les DROITS, pas sur la portée : le marqueur
            # « records_scope_equipe » du Technicien masquerait le ticket (404).
            role = Role.objects.create(
                company=societe, nom=nom, permissions=[
                    p for p in permissions if not p.startswith('records_scope_')])
            user = User.objects.create_user(
                username=f'acsv62_{nom}', password='x', company=societe,
                role=role)
            api = APIClient()
            api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
            return api

        base = f'/api/django/sav/tickets/{ticket.pk}'
        technicien = _api('Technicien', [
            p for p in TECHNICIEN_PERMISSIONS if p != 'ventes_creer'])
        commercial = _api('Commercial', [
            p for p in TECHNICIEN_PERMISSIONS if p != 'stock_mouvement'
        ] + ['ventes_creer'])
        for porte in ('facturer', 'generer-facture', 'creer-devis'):
            r = _api_post(technicien, f'{base}/{porte}/', {})
            self.assertEqual(r.status_code, 403, (porte, r.data))
            self.assertEqual(r.data['code'], 'droit_manquant')
        r = _api_post(commercial, f'{base}/pieces/', {
            'produit': produit.pk, 'quantite': '1', 'decrement': True})
        self.assertEqual(r.status_code, 403, r.data)
        r = _api_post(commercial, f'{base}/pieces-retirees/', {
            'produit': produit.pk, 'quantite': '1',
            'destination': 'stock_occasion'})
        self.assertEqual(r.status_code, 403, r.data)
        r = _api_post(commercial, f'{base}/prets-equipement/', {
            'produit': produit.pk})
        self.assertEqual(r.status_code, 403, r.data)
        produit.refresh_from_db()
        self.assertEqual(produit.quantite_stock, Decimal('5'))
        r = _api_post(commercial, f'{base}/pieces/', {
            'produit': produit.pk, 'quantite': '1', 'decrement': False})
        self.assertEqual(r.status_code, 201, r.data)
        r = _api_post(technicien, f'{base}/pieces/', {
            'produit': produit.pk, 'quantite': '1', 'decrement': True})
        self.assertEqual(r.status_code, 201, r.data)
        piece = PieceConsommee.objects.get(ticket=ticket, stock_decremente=True)
        r = commercial.delete(f'{base}/pieces/{piece.pk}/')
        self.assertEqual(r.status_code, 403, r.data)
        produit.refresh_from_db()
        self.assertEqual(produit.quantite_stock, Decimal('4'))


def _api_post(api, url, corps):
    return api.post(url, corps, format='json')
