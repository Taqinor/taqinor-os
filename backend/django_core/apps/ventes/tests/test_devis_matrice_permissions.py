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
    # ASEC74 / ASEC71 — la grille « Créer » / « Modifier » en plus du palier.
    'create': (RESP, 'DroitDeLaGrille_ventes_creer'),
    'update': (RESP, 'DroitDeLaGrille_ventes_modifier'),
    'partial_update': (RESP, 'DroitDeLaGrille_ventes_modifier'),
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
    'ajouter_boq_electrique': (RESP, 'DroitDeLaGrille_ventes_modifier'),
    'composition': RESP, 'conception_electrique': RESP,
    'contacter_superieur': RESP, 'convertir_en_bc': RESP,
    'design_context': RESP, 'dupliquer': RESP, 'dupliquer_variante': RESP,
    'dupliquer_variante_gamme': RESP, 'envoyer_email': RESP,
    'etude_params': RESP, 'from_layout': RESP, 'generer_facture': RESP,
    'generer_pdf': RESP, 'historique_configuration': RESP, 'layout': RESP,
    'lecture_client': RESP, 'lots': RESP, 'noter': RESP,
    'offres_tailles': RESP, 'offres_tailles_appliquer': RESP,
    'offres_tailles_config': RESP, 'offres_tailles_regenerer': RESP,
    'override_regenerer': RESP, 'overrides': RESP, 'proforma_pdf': RESP, 'renouveler': RESP,
    'reviser': RESP, 'roof_image': RESP,
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
    # ATOT62 — confirmer l'avoir de révision en attente : même palier ;
    # ASEC85 (D-ASEC-VER-1) — un avoir émis exige aussi ``encaisser``.
    'confirmer_avoir_revision': PALIER_VENTE + ('HasPermissionOrLegacy_encaisser',),
    # ASEC86 — la vraie porte d'édition du générateur : grille « Modifier ».
    'replace_lines': (RESP, 'DroitDeLaGrille_ventes_modifier'),
    # ASEC87 — les créations réelles d'un devis : grille « Créer ».
    'atomic': (RESP, 'DroitDeLaGrille_ventes_creer'),
    'auto': (RESP, 'DroitDeLaGrille_ventes_creer'),
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

    def test_lignes_et_listes_prix_bornees_au_module_ou_au_chantier(self):
        """APFS108 (D-APFS-4) — Admin RH et Commercial terrain : 403 sur les
        lignes et les listes de prix ; Technicien (octroi
        ``installation_voir``) : les lignes du devis de SON chantier
        seulement, 403 sur les listes de prix ; Commercial : 200."""
        from decimal import Decimal

        from apps.installations.models import Installation
        from apps.ventes.models import LigneDevis

        client = Client.objects.create(company=self.company, nom='APFS108')
        commercial = self._compte('Commercial', registre.COMMERCIAL_PERMISSIONS)
        technicien = self._compte('Technicien', registre.TECHNICIEN_PERMISSIONS)
        d1, d2 = (Devis.objects.create(
            company=self.company, reference=f'DEV-APFS108-{n}', client=client,
            created_by=commercial) for n in (1, 2))
        for devis in (d1, d2):
            LigneDevis.objects.create(
                devis=devis, designation='Panneau', quantite=Decimal('1'),
                prix_unitaire=Decimal('100'), remise=Decimal('0'))
        Installation.objects.create(
            company=self.company, reference='CH-APFS108-1', client=client,
            devis=d1, technicien_responsable=technicien)
        Installation.objects.create(
            company=self.company, reference='CH-APFS108-2', client=client,
            devis=d2)

        def lire(user, url):
            api = APIClient()
            api.force_authenticate(user)
            return api.get(url)

        lignes = '/api/django/ventes/devis-lignes/'
        prix = '/api/django/ventes/listes-prix/'
        for nom, codes in (('Admin RH', registre.ADMIN_RH_PERMISSIONS),
                           ('Commercial terrain',
                            registre.COMMERCIAL_TERRAIN_PERMISSIONS)):
            with self.subTest(role=nom):
                compte = self._compte(nom, codes)
                self.assertEqual(lire(compte, lignes).status_code, 403)
                self.assertEqual(lire(compte, prix).status_code, 403)

        def ids(reponse):
            corps = reponse.data
            rangs = corps.get('results', corps) if isinstance(corps, dict) \
                else corps
            return {ligne['devis'] for ligne in rangs}

        # Le Technicien ne lit QUE les lignes du devis de son chantier (D1).
        r1 = lire(technicien, lignes)
        self.assertEqual(r1.status_code, 200, r1.data)
        self.assertEqual(ids(r1), {d1.pk})
        self.assertEqual(lire(technicien, prix).status_code, 403)
        self.assertEqual(lire(commercial, lignes).status_code, 200)
        self.assertEqual(lire(commercial, prix).status_code, 200)

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

    def test_patch_exige_ventes_modifier(self):
        """ASEC71 (C-ASEC-VER4-040, D-ASEC-4) — un rôle = Commercial du
        registre SANS ``ventes_modifier`` reçoit 403 ``droit_manquant`` au
        PATCH d'un devis, note inchangée ; le Commercial du registre (porte
        le code) : 200. Mutant : retirer ``DroitDeLaGrille`` ⇒ échec."""
        client = Client.objects.create(company=self.company, nom='ASEC71')
        prive = self._compte('Commercial sans modifier', [
            c for c in registre.COMMERCIAL_PERMISSIONS
            if c != 'ventes_modifier'])
        commercial = self._compte('Commercial', registre.COMMERCIAL_PERMISSIONS)
        devis = Devis.objects.create(
            company=self.company, reference='DEV-ASEC71-1', client=client,
            statut=Devis.Statut.BROUILLON, created_by=prive, note='Origine')
        url = '/api/django/ventes/devis/%s/' % devis.pk
        api = APIClient()
        api.force_authenticate(prive)
        r = api.patch(url, {'note': 'Pirate'}, format='json')
        self.assertEqual(r.status_code, 403, r.data)
        self.assertEqual(r.data.get('code'), 'droit_manquant', r.data)
        devis.refresh_from_db()
        self.assertEqual(devis.note, 'Origine')
        Devis.objects.filter(pk=devis.pk).update(created_by=commercial)
        api.force_authenticate(commercial)
        r = api.patch(url, {'note': 'Revue'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

    def test_creation_exige_ventes_creer(self):
        """ASEC74 (C-ASEC-VER4-040) — un rôle = Commercial du registre SANS
        ``ventes_creer`` reçoit 403 ``droit_manquant`` à ``POST
        /ventes/devis/``, aucun devis créé ; le Commercial du registre : 201.
        Mutant : retirer la garde ⇒ échec."""
        client = Client.objects.create(company=self.company, nom='ASEC74')
        prive = self._compte('Commercial sans creer', [
            c for c in registre.COMMERCIAL_PERMISSIONS if c != 'ventes_creer'])
        commercial = self._compte('Commercial', registre.COMMERCIAL_PERMISSIONS)
        corps = {'client': client.pk, 'taux_tva': '20'}
        api = APIClient()
        api.force_authenticate(prive)
        avant = Devis.objects.filter(company=self.company).count()
        r = api.post('/api/django/ventes/devis/', corps, format='json')
        self.assertEqual(r.status_code, 403, r.data)
        self.assertEqual(r.data.get('code'), 'droit_manquant', r.data)
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)
        api.force_authenticate(commercial)
        r = api.post('/api/django/ventes/devis/', corps, format='json')
        self.assertEqual(r.status_code, 201, r.data)

    def test_replace_lines_exige_ventes_modifier(self):
        """ASEC86 (C-ASEC-VER5-071, D-ASEC-4) — un rôle = Commercial du
        registre SANS ``ventes_modifier`` reçoit 403 ``droit_manquant`` à
        ``POST replace-lines``, lignes intactes ; le Commercial du registre :
        200. Mutant : ôter ``DroitDeLaGrille`` ⇒ échec."""
        from decimal import Decimal

        from apps.ventes.models import LigneDevis
        client = Client.objects.create(company=self.company, nom='ASEC86')
        prive = self._compte('Commercial sans modifier', [
            c for c in registre.COMMERCIAL_PERMISSIONS
            if c != 'ventes_modifier'])
        commercial = self._compte('Commercial', registre.COMMERCIAL_PERMISSIONS)
        devis = Devis.objects.create(
            company=self.company, reference='DEV-ASEC86-1', client=client,
            statut=Devis.Statut.BROUILLON, created_by=prive)
        LigneDevis.objects.create(
            devis=devis, designation='Panneau', quantite=Decimal('1'),
            prix_unitaire=Decimal('100'), remise=Decimal('0'))
        url = '/api/django/ventes/devis/%s/replace-lines/' % devis.pk
        # Ligne de SECTION : valide sans produit — le refus ne peut venir que du droit.
        corps = {'lignes': [{'type_ligne': 'section', 'designation': 'Pirate'}]}
        api = APIClient()
        api.force_authenticate(prive)
        r = api.post(url, corps, format='json')
        self.assertEqual(r.status_code, 403, r.data)
        self.assertEqual(r.data.get('code'), 'droit_manquant', r.data)
        # CLAUSE PERSISTANCE — relu en base : « Panneau » seule.
        self.assertEqual(list(LigneDevis.objects.filter(devis=devis)
                              .values_list('designation', flat=True)),
                         ['Panneau'])
        Devis.objects.filter(pk=devis.pk).update(created_by=commercial)
        api.force_authenticate(commercial)
        r = api.post(url, corps, format='json')
        self.assertEqual(r.status_code, 200, r.data)

    def test_ajouter_boq_electrique_exige_ventes_modifier(self):
        """ASEC94 — un rôle = Commercial du registre SANS ``ventes_modifier``
        reçoit 403 ``droit_manquant`` à ``POST ajouter-boq-electrique``, lignes
        intactes ; le Commercial du registre : 200, 5 lignes. Mutant : ôter
        ``DroitDeLaGrille`` ⇒ échec."""
        from decimal import Decimal

        from apps.ventes.models import LigneDevis
        client = Client.objects.create(company=self.company, nom='ASEC94')
        prive = self._compte('Commercial sans modifier', [
            c for c in registre.COMMERCIAL_PERMISSIONS if c != 'ventes_modifier'])
        commercial = self._compte('Commercial', registre.COMMERCIAL_PERMISSIONS)
        bom = [{'designation': d, 'quantite': 1, 'spec': ''} for d in (
            'Câble solaire H1Z2Z2-K 6,0 mm²', 'Parafoudre DC Type 2',
            'Disjoncteur AC bipolaire 32 A', 'Coffret AC')]
        devis = Devis.objects.create(
            company=self.company, reference='DEV-ASEC94-1', client=client,
            statut=Devis.Statut.BROUILLON, created_by=prive, electrical_design={'bom': bom})
        LigneDevis.objects.create(
            devis=devis, designation='Panneau', quantite=Decimal('1'),
            prix_unitaire=Decimal('100'), remise=Decimal('0'))
        url = '/api/django/ventes/devis/%s/ajouter-boq-electrique/' % devis.pk
        api = APIClient()
        api.force_authenticate(prive)
        r = api.post(url, {}, format='json')
        self.assertEqual(r.status_code, 403, r.data)
        self.assertEqual(r.data.get('code'), 'droit_manquant', r.data)
        # CLAUSE PERSISTANCE — relu en base : « Panneau » seule.
        self.assertEqual(list(LigneDevis.objects.filter(devis=devis)
                              .values_list('designation', flat=True)), ['Panneau'])
        Devis.objects.filter(pk=devis.pk).update(created_by=commercial)
        api.force_authenticate(commercial)
        r = api.post(url, {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(LigneDevis.objects.filter(devis=devis).count(), 5)

    def test_atomic_et_auto_exigent_ventes_creer(self):
        """ASEC87 (C-ASEC-VER5-074, D-ASEC-4) — un rôle = Commercial du
        registre SANS ``ventes_creer`` reçoit 403 ``droit_manquant`` à
        ``POST devis/atomic/`` ET ``POST devis/auto/``, aucun devis créé ;
        le Commercial du registre : ``atomic`` 201. Mutant : ôter la garde
        d'un décorateur ⇒ échec."""
        from decimal import Decimal

        from apps.crm.models import Lead
        from apps.stock.models import Produit
        client = Client.objects.create(company=self.company, nom='ASEC87')
        lead = Lead.objects.create(company=self.company, nom='Lead ASEC87')
        produit = Produit.objects.create(
            company=self.company, nom='Câblage ASEC87', sku='ASEC87-1',
            prix_vente=Decimal('100'), prix_achat=Decimal('50'),
            quantite_stock=10, tva=Decimal('20'))
        prive = self._compte('Commercial sans creer', [
            c for c in registre.COMMERCIAL_PERMISSIONS if c != 'ventes_creer'])
        commercial = self._compte('Commercial', registre.COMMERCIAL_PERMISSIONS)
        corps = {'client': client.pk, 'taux_tva': '20', 'lignes': [{
            'produit': produit.pk, 'designation': 'Câblage ASEC87',
            'quantite': '1', 'prix_unitaire': '100.00', 'taux_tva': '20'}]}
        base = '/api/django/ventes/devis/'
        api = APIClient()
        api.force_authenticate(prive)
        avant = Devis.objects.filter(company=self.company).count()
        for route, donnees in (('atomic/', corps), ('auto/', {'lead': lead.pk})):
            r = api.post(base + route, donnees, format='json')
            self.assertEqual(r.status_code, 403, (route, r.data))
            self.assertEqual(r.data.get('code'), 'droit_manquant', r.data)
        # CLAUSE PERSISTANCE — garde : devis de la société inchangés.
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)
        api.force_authenticate(commercial)
        r = api.post(base + 'atomic/', corps, format='json')
        self.assertEqual(r.status_code, 201, r.data)
