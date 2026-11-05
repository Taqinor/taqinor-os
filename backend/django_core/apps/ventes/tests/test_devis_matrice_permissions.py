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
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory

from apps.crm.models import Client
from apps.roles import permissions_registre as registre
from apps.roles.models import Role
from apps.ventes.models import Devis
from apps.ventes.views.devis import DevisViewSet
from authentication.models import Company

User = get_user_model()

ANY = 'IsAnyRole'
RESP = 'IsResponsableOrAdmin'
ADMIN = 'IsAdminRole'
VALIDER = 'HasPermissionOrLegacy_ventes_valider'
PORTAIL = 'IsInternalWriterOrPortalClientOwner'
#: ADVS23 — lecture bornée aux rôles du module Ventes (D-ASEC11-LECTURE-FACTURES).
LECTURE = 'LectureVentes'
#: VNT60 — garde à deux classes (tuple : comparé tel quel, hors VERITE).
PALIER_VENTE = ('IsAdminOrResponsableTier', 'IsResponsableOrAdmin')

#: La garde effective de CHAQUE action, capturée sur le code d'avant QJR649.
FIGEE = {
    # Actions standard du ModelViewSet (non décorées).
    'list': LECTURE, 'retrieve': LECTURE,
    'create': RESP, 'update': RESP, 'partial_update': RESP,
    # ASEC50 / D-ASEC-4 — le palier admin ET le code ``ventes_supprimer``.
    'destroy': ('IsAdminRole', 'DroitDeLaGrille_ventes_supprimer'),
    # Seule @action sans ``permission_classes`` déclaré.
    'variante_config': ANY,
    # Action inconnue / future non déclarée : fermée par défaut.
    'action_future_non_declaree': ADMIN,
    # @actions déclarées.
    'accepter': VALIDER, 'refuser': VALIDER,
    'action_requise': ANY, 'etat_pdf': ANY, 'historique': LECTURE,
    # CALX288 (views/economie.py, rattachée au viewset pivot) : lecture.
    'economie': ANY,
    # AGR206 (views/economie_pompage.py, même patron) : lecture du bloc
    # économie de pompage, garde déclarée IsAnyRole comme `economie`.
    'economie_pompage': ANY,
    # CIQ210 (views/economie_ci.py, même patron) : lecture du bloc
    # économie C&I, garde déclarée IsAnyRole.
    'economie_ci': ANY,
    'prefill_site': LECTURE, 'superior_contact_status': ANY,
    'approuver_remise': ADMIN,
    'proposal': (PORTAIL, 'LectureVentesHorsPortail'),
    'ajouter_boq_electrique': RESP, 'atomic': RESP,
    'auto': RESP, 'composition': RESP, 'conception_electrique': RESP,
    'contacter_superieur': RESP, 'convertir_en_bc': RESP,
    'design_context': RESP, 'dupliquer': RESP, 'dupliquer_variante': RESP,
    'dupliquer_variante_gamme': RESP, 'envoyer_email': RESP,
    'etude_params': RESP, 'from_layout': RESP, 'generer_facture': RESP,
    'generer_pdf': RESP, 'historique_configuration': RESP, 'layout': RESP,
    'lecture_client': RESP, 'lots': RESP, 'noter': RESP,
    'offres_tailles': RESP, 'offres_tailles_appliquer': RESP,
    'offres_tailles_config': RESP, 'offres_tailles_regenerer': RESP,
    'override_regenerer': RESP, 'overrides': RESP, 'proforma_pdf': RESP, 'renouveler': RESP,
    'replace_lines': RESP, 'reviser': RESP, 'roof_image': RESP,
    'save_preset': RESP, 'share_link': RESP, 'simulation_status': RESP,
    'simuler': RESP, 'sync_layout': RESP, 'telecharger_pdf': RESP,
    'variantes': RESP, 'whatsapp': RESP, 'whatsapp_preview': RESP,
    # QJR588 (lot 4 QJR5) : deux nouvelles @actions d'écriture, déclarées
    # IsResponsableOrAdmin comme les autres écritures du devis.
    'reappliquer_lead': RESP, 'acquitter_derive': RESP,
    # QJR659 (décision fondateur 01/10) : partager le PDF vaut envoi.
    'pdf_partage': RESP,
    # Fondateur 05/10/2026 : « Facturer » un devis accepté (écriture).
    # ASEC29 / D-ASEC-1 — garde INVERSÉE par la tâche : geste d'argent,
    # réservé au code ``encaisser``.
    'facturer_complet': 'HasPermissionOrLegacy_encaisser',
    # VNT31 : « Facturer la vente » — créer un brouillon = écriture ventes ;
    # émettre / encaisser exigent en plus ``encaisser`` (garde dans la vue).
    'facturer': RESP,

    # ADOC131 (D-ADOC-4) : « Révoquer le lien client » (écriture).
    'revoquer_lien_public': RESP,
    # ACAL314 : LECTURE des octets de l'affiche (proxy même origine).
    'roof_image_fichier': ANY,
    # VNT60 — gestes d'argent de la vente (arbitrage 5) : DEUX gardes, le
    # palier écarte un Commercial qui porte ``ventes_valider``.
    'prix_negocie': PALIER_VENTE,
    'avenant_demander_signature': PALIER_VENTE,
    # VNT66 — réécrire l'échéancier d'une vente : même palier.
    'echeancier_vente': PALIER_VENTE,
    # ATOT62 — confirmer l'avoir de révision en attente : même palier.
    'confirmer_avoir_revision': PALIER_VENTE,
    # CADV82 — l'appel J28 prolonge la validité d'un envoyé (écriture).
    'prolonger_validite': RESP,
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
                    [type(p).__name__ for p in _gardes(action)],
                    list(attendu) if isinstance(attendu, tuple)
                    else [attendu])

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

    def _compte(self, nom, permissions):
        role = Role.objects.create(company=self.company, nom=nom,
                                   permissions=list(permissions))
        return User.objects.create_user(
            username='advs23_%s' % nom.replace(' ', '_'), password='x',
            role=role, company=self.company)

    def _cinq_lectures(self, user, devis, client):
        api = APIClient()
        api.force_authenticate(user)
        base = '/api/django/ventes/devis/'
        return {
            'liste': api.get(base).status_code,
            'fiche': api.get('%s%s/' % (base, devis.pk)).status_code,
            'historique': api.get('%s%s/historique/' % (base, devis.pk)).status_code,
            'proposal': api.get('%s%s/proposal/' % (base, devis.pk)).status_code,
            'prefill': api.get('%sprefill-site/?client=%s' % (base, client.pk)).status_code,
        }

    def test_lecture_devis_refusee_hors_module_ventes(self):
        # ADVS23 — Admin RH, Commercial terrain et les deux techniciens : 403 ×5.
        client = Client.objects.create(company=self.company, nom='ADVS23')
        commercial = self._compte('Commercial', registre.COMMERCIAL_PERMISSIONS)
        devis = Devis.objects.create(
            company=self.company, reference='DEV-ADVS23-1', client=client,
            statut=Devis.Statut.ENVOYE, created_by=commercial)
        for nom, codes in (('Admin RH', registre.ADMIN_RH_PERMISSIONS),
                           ('Commercial terrain', registre.COMMERCIAL_TERRAIN_PERMISSIONS),
                           ('Technicien', registre.TECHNICIEN_PERMISSIONS),
                           ('Technicien responsable', registre.TECHNICIEN_RESP_PERMISSIONS)):
            with self.subTest(role=nom):
                codes_lus = self._cinq_lectures(self._compte(nom, codes), devis, client)
                self.assertEqual(set(codes_lus.values()), {403}, codes_lus)
        # Un rôle du module Ventes et un compte sans rôle fin : inchangés.
        with patch('apps.ventes.quote_engine.generate_premium_devis_pdf',
                   return_value='cle'), \
                patch('apps.ventes.utils.pdf.download_pdf', return_value=b'%PDF-'):
            codes_lus = self._cinq_lectures(commercial, devis, client)
        self.assertEqual(set(codes_lus.values()), {200}, codes_lus)
        viewer = self._compte('Viewer', registre.VIEWER_PERMISSIONS)
        Devis.objects.filter(pk=devis.pk).update(created_by=viewer)
        codes_lus = self._cinq_lectures(viewer, devis, client)
        self.assertEqual(codes_lus.pop('proposal'), 403)  # palier inchangé (lecture seule)
        self.assertEqual(set(codes_lus.values()), {200}, codes_lus)
        api = APIClient()
        api.force_authenticate(User.objects.create_user(
            username='advs23_sans_role', password='x', role_legacy='normal',
            company=self.company))
        self.assertEqual(api.get('/api/django/ventes/devis/').status_code, 200)
