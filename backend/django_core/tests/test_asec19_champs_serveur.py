"""ASEC19 (C-ASEC-009, classe) — GARDE DES CHAMPS POSÉS PAR LE SERVEUR.

Une liste DÉCLARATIVE ``CHAMPS_SERVEUR`` (modèle, champ, geste légitime) :
chaque champ est PATCHé par l'endpoint générique de son modèle avec une valeur
différente, puis relu EN BASE — il doit être inchangé (champ en lecture seule
→ 200 ignoré, ou 400). Chaque entrée nomme le geste légitime (action dédiée /
service) qui, lui seul, le modifie.

La liste ne fait que GRANDIR (ajouts seulement) : un nouveau champ serveur
s'y déclare. Complémentaire de ``scripts/check_machine_etats_statut_readonly.py``
(AUD515, statique, ``statut`` des modèles à machine d'états) : cette garde
couvre les champs serveur hors ``statut`` et prouve au RUNTIME.

Rouge sur 51f22174f (V5 : facture ``payee``/``validee``, mandat révoqué →
actif, signature posée, FlightPlan actif). Test-du-test : remettre ``statut``
inscriptible dans ``FactureWriteSerializer`` ⇒ le cas ``Facture.statut``
échoue.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "tests.test_asec19_champs_serveur"
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()

V = '/api/django'


def _entree(objet, modele, champ, valeur, geste, *, pose_par_la_vue=False):
    return {'objet': objet, 'modele': modele, 'champ': champ,
            'valeur': valeur, 'geste': geste,
            'pose_par_la_vue': pose_par_la_vue}


#: LA LISTE DÉCLARATIVE (ajouts seulement). ``objet`` = clé de la fixture
#: (``self.objets``), ``valeur`` = valeur DIFFÉRENTE envoyée au PATCH (une
#: valeur appelable reçoit le TestCase, pour les FK).
CHAMPS_SERVEUR = [
    # ── Facture (ASEC27) ──────────────────────────────────────────────────
    _entree('facture', 'Facture', 'statut', 'payee',
            'actions valider / encaisser / annuler (services facturation)'),
    _entree('facture', 'Facture', 'revue_statut', 'validee',
            'action de revue (valider-revue)'),
    _entree('facture', 'Facture', 'abandon_motif', 'irrecouvrable',
            'action abandon-creance'),
    _entree('facture', 'Facture', 'abandon_montant', '10.00',
            'action abandon-creance'),
    _entree('facture', 'Facture', 'abandon_date', '2026-10-01T10:00:00Z',
            'action abandon-creance'),
    _entree('facture', 'Facture', 'abandon_auto', True,
            'abandon automatique des écarts (service encaissements)'),
    _entree('facture', 'Facture', 'abandon_par',
            lambda t: t.collegue.pk, 'action abandon-creance'),
    _entree('facture', 'Facture', 'retenue_liberee_le', '2026-10-01',
            'action liberer-retenue (CIQ214)'),
    _entree('facture', 'Facture', 'statut_teledeclaration', 'soumise',
            'télédéclaration DGI (N39, service)'),
    _entree('facture', 'Facture', 'fichier_ubl', 'pirate.xml',
            'génération UBL (service e-facture)'),
    _entree('facture', 'Facture', 'pdf_render_meta', {'pirate': 1},
            'rendu PDF (utils.pdf)'),
    _entree('facture', 'Facture', 'updated_by', lambda t: t.collegue.pk,
            'posé par la vue à chaque écriture (VX98)',
            pose_par_la_vue=True),
    # MandatPaiement (ASEC28) : route `mandats-paiement` PARQUÉE (AFAC19) —
    # plus aucun PATCH générique à sonder.
    # ── Intervention (ASEC32) ─────────────────────────────────────────────
    _entree('intervention', 'Intervention', 'signature_client',
            'data:image/png;base64,AAAA', 'action signer-client'),
    _entree('intervention', 'Intervention', 'signataire_nom', 'Pirate',
            'action signer-client'),
    _entree('intervention', 'Intervention', 'signe_le',
            '2026-10-01T10:00:00Z', 'action signer-client'),
    # ── Installation (ASEC32 etape, AUD305 signature) ─────────────────────
    _entree('installation', 'Installation', 'etape',
            lambda t: t.etape_autre.pk,
            'transitions de chantier (changer_statut_chantier, CH2)'),
    _entree('installation', 'Installation', 'signature_client',
            'data:image/png;base64,AAAA', 'action signer-client (AUD305)'),
    _entree('installation', 'Installation', 'signataire_nom', 'Pirate',
            'action signer-client (AUD305)'),
    _entree('installation', 'Installation', 'signe_le',
            '2026-10-01T10:00:00Z', 'action signer-client (AUD305)'),
    # ── Ticket SAV (ASEC34) ───────────────────────────────────────────────
    _entree('ticket', 'Ticket', 'non_facturable', True,
            'qualification garantie (service SAV)'),
    _entree('ticket', 'Ticket', 'est_recidive', True,
            'détection de récidive (service SAV)'),
    _entree('ticket', 'Ticket', 'cout', '999999.00',
            'cumul des coûts d\'intervention (service SAV)'),
    # ── Approbations (ASEC30) ─────────────────────────────────────────────
    _entree('demande', 'ApprovalRequest', 'request_type',
            lambda t: t.type_autre.pk, 'aucun après décision (figée)'),
    _entree('demande', 'ApprovalRequest', 'payload', {'montant': 999999},
            'aucun après décision (figée)'),
    _entree('delegation', 'ApprovalDelegation', 'delegant',
            lambda t: t.collegue.pk, 'posé à la création (utilisateur)'),
    # ── Moteur publicitaire (ASEC41) ──────────────────────────────────────
    _entree('plan_vol', 'FlightPlan', 'status', 'actif',
            'flightplan.materialize (préflight compris)'),
    _entree('creatif', 'CreativeAsset', 'depicts_real_client', False,
            'provenance posée par la lane de génération'),
    _entree('creatif', 'CreativeAsset', 'source_lane', 'autre',
            'provenance posée par la lane de génération'),
    _entree('creatif', 'CreativeAsset', 'parent', None,
            'variation dérivée (service de génération)'),
    # ── Patrons déjà appliqués ────────────────────────────────────────────
    _entree('devis', 'Devis', 'statut', 'accepte',
            'actions envoyer / accepter / refuser (QJR541)'),
    _entree('bon_commande', 'BonCommande', 'statut', 'livre',
            'actions confirmer / marquer-livre / annuler (AUD506)'),
]

#: Champs EXIGÉS par la tâche ASEC19 (la liste initiale) : la garde échoue
#: si l'un d'eux disparaît de ``CHAMPS_SERVEUR``.
EXIGES = {
    ('Facture', 'statut'), ('Facture', 'revue_statut'),
    ('Facture', 'abandon_motif'), ('Facture', 'abandon_montant'),
    ('Facture', 'abandon_date'), ('Facture', 'abandon_par'),
    ('Facture', 'retenue_liberee_le'), ('Facture', 'statut_teledeclaration'),
    ('Facture', 'fichier_ubl'), ('Facture', 'pdf_render_meta'),
    ('Facture', 'updated_by'),
    ('Intervention', 'signature_client'), ('Intervention', 'signataire_nom'),
    ('Intervention', 'signe_le'), ('Installation', 'etape'),
    ('Ticket', 'non_facturable'), ('Ticket', 'est_recidive'),
    ('Ticket', 'cout'),
    ('ApprovalRequest', 'request_type'), ('ApprovalRequest', 'payload'),
    ('ApprovalDelegation', 'delegant'), ('FlightPlan', 'status'),
    ('CreativeAsset', 'depicts_real_client'),
    ('CreativeAsset', 'source_lane'), ('CreativeAsset', 'parent'),
    ('Devis', 'statut'), ('BonCommande', 'statut'),
    ('Installation', 'signature_client'),
}


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ChampsServeurTests(TestCase):
    def setUp(self):
        from apps.adsengine.models import CreativeAsset, FlightPlan
        from apps.automation.models import (
            ApprovalDelegation, ApprovalRequest, ApprovalRequestType,
        )
        from apps.crm.models import Client
        from apps.installations.models import Installation, Intervention
        from apps.installations.models_chantier import StageModele
        from apps.roles.models import Role
        from apps.sav.models import Ticket
        from apps.ventes.models import (
            BonCommande, Devis, Facture, LigneDevis,
        )
        from authentication.models import Company

        self.company = Company.objects.create(
            nom='ASEC19 Co', slug='asec19-co')
        self.admin = User.objects.create_user(
            username='asec19_admin', password='x', role_legacy='admin',
            company=self.company)
        self.collegue = User.objects.create_user(
            username='asec19_collegue', password='x', role_legacy='normal',
            company=self.company)
        role_ads = Role.objects.create(
            company=self.company, nom='asec19-ads',
            permissions=['adsengine_view', 'adsengine_manage'])
        self.ads_user = User.objects.create_user(
            username='asec19_ads', password='x', role=role_ads,
            company=self.company)
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ASEC19',
            email='asec19@example.invalid', telephone='+212600000019')

        devis = Devis.objects.create(
            company=self.company, reference='DEV-ASEC19-1', client=client,
            statut=Devis.Statut.BROUILLON, taux_tva=Decimal('20.00'),
            mode_installation='residentiel', created_by=self.admin)
        LigneDevis.objects.create(
            devis=devis, designation='Centrale', quantite=Decimal('1'),
            prix_unitaire=Decimal('10000'), taux_tva=Decimal('20.00'))
        installation = Installation.objects.create(
            company=self.company, reference='CHT-ASEC19', client=client)
        self.etape_autre = StageModele.objects.create(
            company=self.company, cle='remise-asec19',
            libelle='Remise client', ordre=9)
        self.type_autre = ApprovalRequestType.objects.create(
            company=self.company, nom='Autre ASEC19')
        maintenant = timezone.now()
        base_creatif = CreativeAsset.objects.create(
            company=self.company, asset_type='static')

        self.objets = {
            'facture': Facture.objects.create(
                company=self.company, reference='FAC-ASEC19-1',
                client=client, statut=Facture.Statut.BROUILLON,
                taux_tva=Decimal('20.00'), created_by=self.admin),
            'intervention': Intervention.objects.create(
                company=self.company, installation=installation),
            'installation': installation,
            'ticket': Ticket.objects.create(
                company=self.company, reference='ASEC19-T1', client=client,
                cout=Decimal('100.00')),
            'demande': ApprovalRequest.objects.create(
                company=self.company,
                request_type=ApprovalRequestType.objects.create(
                    company=self.company, nom='Achat ASEC19'),
                demandeur=self.collegue, payload={'montant': 100},
                status=ApprovalRequest.Status.APPROVED),
            'delegation': ApprovalDelegation.objects.create(
                company=self.company, delegant=self.admin,
                suppleant=self.collegue,
                date_debut=maintenant - timedelta(days=1),
                date_fin=maintenant + timedelta(days=1)),
            'plan_vol': FlightPlan.objects.create(
                company=self.company, name='Plan ASEC19'),
            'creatif': CreativeAsset.objects.create(
                company=self.company, asset_type='static',
                source_lane='chantier', depicts_real_client=True,
                parent=base_creatif),
            'devis': devis,
            'bon_commande': BonCommande.objects.create(
                company=self.company, reference='BC-ASEC19-1',
                client=client, statut=BonCommande.Statut.EN_ATTENTE),
        }
        self.urls = {
            'facture': f'{V}/ventes/factures/{{}}/',
            'intervention': f'{V}/installations/interventions/{{}}/',
            'installation': f'{V}/installations/chantiers/{{}}/',
            'ticket': f'{V}/sav/tickets/{{}}/',
            'demande': f'{V}/automation/approval-requests/{{}}/',
            'delegation': f'{V}/automation/approval-delegations/{{}}/',
            'plan_vol': f'{V}/adsengine/plans-vol/{{}}/',
            'creatif': f'{V}/adsengine/creatifs/{{}}/',
            'devis': f'{V}/ventes/devis/{{}}/',
            'bon_commande': f'{V}/ventes/bons-commande/{{}}/',
        }
        self.clients_api = {'admin': _api(self.admin),
                            'ads': _api(self.ads_user)}

    def _api_pour(self, objet):
        return self.clients_api[
            'ads' if objet in ('plan_vol', 'creatif') else 'admin']

    @staticmethod
    def _valeur_lue(instance, champ):
        field = instance._meta.get_field(champ)
        return getattr(instance, field.attname)

    def test_liste_declarative_complete(self):
        declares = {(e['modele'], e['champ']) for e in CHAMPS_SERVEUR}
        self.assertEqual(EXIGES - declares, set(),
                         'Champ serveur retiré de la liste déclarative.')
        for entree in CHAMPS_SERVEUR:
            self.assertTrue(entree['geste'].strip(),
                            f'{entree["modele"]}.{entree["champ"]} : geste '
                            'légitime non nommé.')
            instance = self.objets[entree['objet']]
            self.assertEqual(type(instance).__name__, entree['modele'])

    def test_patch_generique_ne_modifie_aucun_champ_serveur(self):
        for entree in CHAMPS_SERVEUR:
            objet, champ = entree['objet'], entree['champ']
            with self.subTest(modele=entree['modele'], champ=champ):
                instance = self.objets[objet]
                instance.refresh_from_db()
                avant = self._valeur_lue(instance, champ)
                valeur = entree['valeur']
                if callable(valeur):
                    valeur = valeur(self)
                r = self._api_pour(objet).patch(
                    self.urls[objet].format(instance.pk), {champ: valeur},
                    format='json')
                self.assertIn(
                    r.status_code, (200, 400),
                    f'{entree["modele"]}.{champ} : PATCH → '
                    f'{r.status_code} {getattr(r, "data", "")}')
                instance.refresh_from_db()
                apres = self._valeur_lue(instance, champ)
                if entree['pose_par_la_vue']:
                    # La vue le pose elle-même (l'auteur de la requête) :
                    # jamais la valeur du corps.
                    self.assertNotEqual(apres, valeur, (
                        f'{entree["modele"]}.{champ} lu du corps du PATCH.'))
                    self.assertIn(apres, (avant, self.admin.pk))
                    continue
                self.assertEqual(
                    apres, avant,
                    f'{entree["modele"]}.{champ} modifié par un PATCH '
                    f'générique — seul « {entree["geste"]} » doit le poser.')
