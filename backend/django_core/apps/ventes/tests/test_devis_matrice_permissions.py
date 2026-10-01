"""QJR649 — ``DevisViewSet.get_permissions`` réduit à sa vraie table, avec une
matrice (action, rôle) FIGÉE avant et après.

La table ``FIGEE`` ci-dessous est la garde EFFECTIVE de chaque action sur le
code d'AVANT la réduction (``declared_action_permissions`` prime ; repli :
list / retrieve / variante_config → IsAnyRole, create / update /
partial_update → IsResponsableOrAdmin, destroy et tout le reste →
IsAdminRole). Toute divergence après la réduction est un changement de
comportement — rouge.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_devis_matrice_permissions"
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.roles.models import Role
from apps.ventes.views.devis import DevisViewSet
from authentication.models import Company

User = get_user_model()

ANY = 'IsAnyRole'
RESP = 'IsResponsableOrAdmin'
ADMIN = 'IsAdminRole'
VALIDER = 'HasPermissionOrLegacy_ventes_valider'
PORTAIL = 'IsInternalWriterOrPortalClientOwner'

#: La garde effective de CHAQUE action, capturée sur le code d'avant QJR649.
FIGEE = {
    # Actions standard du ModelViewSet (non décorées).
    'list': ANY, 'retrieve': ANY,
    'create': RESP, 'update': RESP, 'partial_update': RESP,
    'destroy': ADMIN,
    # Seule @action sans ``permission_classes`` déclaré.
    'variante_config': ANY,
    # Action inconnue / future non déclarée : fermée par défaut.
    'action_future_non_declaree': ADMIN,
    # @actions déclarées.
    'accepter': VALIDER, 'refuser': VALIDER,
    'action_requise': ANY, 'etat_pdf': ANY, 'historique': ANY,
    # CALX288 (views/economie.py, rattachée au viewset pivot) : lecture.
    'economie': ANY,
    'prefill_site': ANY, 'superior_contact_status': ANY,
    'approuver_remise': ADMIN,
    'proposal': PORTAIL,
    'ajouter_boq_electrique': RESP, 'apply_preset': RESP, 'atomic': RESP,
    'auto': RESP, 'composition': RESP, 'conception_electrique': RESP,
    'contacter_superieur': RESP, 'convertir_en_bc': RESP,
    'design_context': RESP, 'dupliquer': RESP, 'dupliquer_variante': RESP,
    'dupliquer_variante_gamme': RESP, 'envoyer_email': RESP,
    'etude_params': RESP, 'from_layout': RESP, 'generer_facture': RESP,
    'generer_pdf': RESP, 'historique_configuration': RESP, 'layout': RESP,
    'lecture_client': RESP, 'lots': RESP, 'noter': RESP,
    'offres_tailles': RESP, 'offres_tailles_appliquer': RESP,
    'offres_tailles_config': RESP, 'offres_tailles_regenerer': RESP,
    'overrides': RESP, 'proforma_pdf': RESP, 'renouveler': RESP,
    'replace_lines': RESP, 'reviser': RESP, 'roof_image': RESP,
    'save_preset': RESP, 'share_link': RESP, 'simulation_status': RESP,
    'simuler': RESP, 'sync_layout': RESP, 'telecharger_pdf': RESP,
    'variantes': RESP, 'whatsapp': RESP, 'whatsapp_preview': RESP,
}

#: Table de vérité des trois gardes « à palier » (inchangées par QJR649).
ROLES = ('admin', 'responsable', 'commercial', 'technicien', 'sans_role')
VERITE = {
    ANY: {'admin': True, 'responsable': True, 'commercial': True,
          'technicien': True, 'sans_role': True},
    RESP: {'admin': True, 'responsable': True, 'commercial': True,
           'technicien': False, 'sans_role': False},
    ADMIN: {'admin': True, 'responsable': False, 'commercial': False,
            'technicien': False, 'sans_role': False},
}


def _gardes(action):
    vue = DevisViewSet()
    vue.action = action
    vue.request = None
    vue.format_kwarg = None
    return vue.get_permissions()


class MatricePermissionsDevis(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='qjr649-co', defaults={'nom': 'QJR649 Co'})
        commercial = Role.objects.create(
            company=self.company, nom='Commercial QJR649',
            permissions=['ventes_voir', 'ventes_creer'])
        technicien = Role.objects.create(
            company=self.company, nom='Technicien QJR649',
            permissions=['ventes_voir'])
        self.users = {
            'admin': User.objects.create_user(
                username='qjr649_admin', password='x', role_legacy='admin',
                company=self.company),
            'responsable': User.objects.create_user(
                username='qjr649_resp', password='x',
                role_legacy='responsable', company=self.company),
            'commercial': User.objects.create_user(
                username='qjr649_com', password='x', role_legacy='normal',
                role=commercial, company=self.company),
            'technicien': User.objects.create_user(
                username='qjr649_tech', password='x', role_legacy='normal',
                role=technicien, company=self.company),
            'sans_role': User.objects.create_user(
                username='qjr649_sans', password='x', role_legacy='normal',
                company=self.company),
        }

    def test_toute_action_du_viewset_est_dans_la_table(self):
        extras = {a.__name__ for a in DevisViewSet.get_extra_actions()}
        self.assertEqual(extras - set(FIGEE), set(),
                         'nouvelle @action : figez sa garde dans FIGEE')

    def test_la_garde_effective_de_chaque_action_est_figee(self):
        for action, attendu in FIGEE.items():
            with self.subTest(action=action):
                self.assertEqual(
                    [type(p).__name__ for p in _gardes(action)], [attendu])

    def test_matrice_action_role(self):
        fabrique = APIRequestFactory()
        for action, garde in FIGEE.items():
            if garde not in VERITE:
                continue  # gardes fines : couvertes par la table des classes
            for role in ROLES:
                with self.subTest(action=action, role=role):
                    requete = Request(fabrique.get('/'))
                    requete.user = self.users[role]
                    vue = DevisViewSet()
                    vue.action = action
                    autorise = all(p.has_permission(requete, vue)
                                   for p in _gardes(action))
                    self.assertEqual(autorise, VERITE[garde][role])
