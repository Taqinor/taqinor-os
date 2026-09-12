"""NTJUR40 — permission fine « approuver les engagements juridiques ».

Critère d'acceptation : « retirer la permission à un utilisateur nommé dans une
étape en cours bloque immédiatement son bouton "Approuver" côté API ».
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.juridique import services
from apps.juridique.models import (
    CabinetAvocat, DossierJuridique, EtapeApprobationJuridique, MandatAvocat,
    RegleApprobationJuridique,
)
from apps.roles.models import ALL_PERMISSIONS, PERMISSION_MODULE, Role

from ._base import auth, make_company

User = get_user_model()
DOSSIERS = '/api/django/juridique/dossiers/'

PERMISSION = 'juridique_approuver_engagement'


class PermissionApprobationTests(TestCase):
    def setUp(self):
        self.company = make_company('jur-p40-co', 'Juridique P40')
        self.dossier = DossierJuridique.objects.create(
            company=self.company, reference='JUR-2026-0001',
            titre='Engagement cabinet', date_ouverture=date(2026, 4, 1))
        cabinet = CabinetAvocat.objects.create(
            company=self.company, nom='Cabinet Idrissi')
        RegleApprobationJuridique.objects.create(
            company=self.company, libelle='Seuil 100k',
            montant_min=Decimal('100000'), nombre_approbateurs=1)
        self.mandat = MandatAvocat.objects.create(
            company=self.company, dossier=self.dossier, cabinet=cabinet,
            date_mandat=date(2026, 4, 2),
            mode_facturation=MandatAvocat.ModeFacturation.FORFAIT,
            montant_forfait=Decimal('150000'))

    def _user_avec(self, username, permissions):
        role = Role.objects.create(
            company=self.company, nom=f'Rôle {username}',
            permissions=list(permissions))
        return User.objects.create_user(
            username=username, password='x', company=self.company, role=role)

    def test_la_permission_est_bien_au_catalogue(self):
        """Un code déclaré par un viewset mais absent du catalogue renverrait
        403 à TOUT LE MONDE, Directeur compris (bug WIR169)."""
        self.assertIn(PERMISSION, ALL_PERMISSIONS)
        self.assertEqual(PERMISSION_MODULE[PERMISSION], 'juridique')

    def test_gerer_sans_approuver_engagement_recoit_403(self):
        user = self._user_avec(
            'jur-p40-sans', ['juridique_voir', 'juridique_gerer'])
        etapes = services.lancer_approbation_mandat(
            self.mandat, approbateurs=[user])
        resp = auth(user).post(
            f'{DOSSIERS}{self.dossier.id}/approuver-etape/',
            {'etape': etapes[0].id}, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)
        etapes[0].refresh_from_db()
        self.assertEqual(etapes[0].statut,
                         EtapeApprobationJuridique.Statut.EN_ATTENTE)

    def test_le_rejet_est_garde_par_la_meme_permission(self):
        user = self._user_avec(
            'jur-p40-sans-rejet', ['juridique_voir', 'juridique_gerer'])
        etapes = services.lancer_approbation_mandat(self.mandat)
        resp = auth(user).post(
            f'{DOSSIERS}{self.dossier.id}/rejeter-etape/',
            {'etape': etapes[0].id}, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_avec_la_permission_l_approbation_passe(self):
        user = self._user_avec(
            'jur-p40-avec',
            ['juridique_voir', 'juridique_gerer', PERMISSION])
        etapes = services.lancer_approbation_mandat(
            self.mandat, approbateurs=[user])
        resp = auth(user).post(
            f'{DOSSIERS}{self.dossier.id}/approuver-etape/',
            {'etape': etapes[0].id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        etapes[0].refresh_from_db()
        self.assertEqual(etapes[0].statut,
                         EtapeApprobationJuridique.Statut.APPROUVE)
        self.assertEqual(etapes[0].approbateur_id, user.id)

    def test_etape_nommee_refuse_un_autre_porteur_de_la_permission(self):
        """Défense en profondeur : la permission ne suffit pas à décider
        l'étape NOMMÉE de quelqu'un d'autre (403, pas 400)."""
        designe = self._user_avec(
            'jur-p40-designe',
            ['juridique_voir', 'juridique_gerer', PERMISSION])
        autre = self._user_avec(
            'jur-p40-autre',
            ['juridique_voir', 'juridique_gerer', PERMISSION])
        etapes = services.lancer_approbation_mandat(
            self.mandat, approbateurs=[designe])
        resp = auth(autre).post(
            f'{DOSSIERS}{self.dossier.id}/approuver-etape/',
            {'etape': etapes[0].id}, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_approbateur_designe_d_une_autre_societe_refuse(self):
        autre_company = make_company('jur-p40-ext', 'Juridique P40 Ext')
        intrus = User.objects.create_user(
            username='jur-p40-intrus', password='x', company=autre_company,
            role_legacy='admin')
        admin = self._user_avec(
            'jur-p40-admin',
            ['juridique_voir', 'juridique_gerer', PERMISSION])
        resp = auth(admin).post(
            f'{DOSSIERS}{self.dossier.id}/lancer-approbation-mandat/',
            {'mandat': self.mandat.id, 'approbateurs': [intrus.id]},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('approbateurs', resp.data)
        self.assertFalse(EtapeApprobationJuridique.objects.exists())
