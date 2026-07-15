"""YRBAC13 — allow/deny sur un échantillon des @action compta fine-grainées.

Ces @action étaient gatées SEULEMENT par le grossier ``IsResponsableOrAdmin``
de ``_ComptaBaseViewSet`` (comptage YRBAC4 : 212 @action non gardées).
YRBAC13 ajoute un ``get_permissions`` PAR CLASSE (10 viewsets, dont les
viewsets marketing-en-compta ré-exportés inchangés par
``apps/marketing/views.py``) qui route sur les codes COMPTA40 existants
(``compta_saisir``/``compta_valider``) — purement additif, aucun nouveau code
de permission, aucune régression pour Directeur/Administrateur/Responsable
(qui portent déjà les deux par défaut).

La garde ``permission_classes``/``get_permissions`` s'applique AVANT
``get_object()`` (``check_permissions`` dans ``APIView.initial()``) : un 403
ne nécessite donc aucun objet réel en base — ``pk=999999`` suffit. Le cas
« autorisé » vérifie seulement l'ABSENCE de 403 (l'objet inexistant renvoie
un 404 métier, jamais un 403 RBAC).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

User = get_user_model()


def _client_for(user):
    api = APIClient()
    token = str(AccessToken.for_user(user))
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api


class _ComptaActionAllowDenyMixin:
    """Exerce allow/deny POST sur ``self.action_path`` (pk inexistant).

    Sous-classes déclarent : ``label`` (préfixe de test unique),
    ``action_path`` (endpoint détail + action), ``required_code``
    (``compta_saisir`` ou ``compta_valider``).
    """
    label = None
    action_path = None
    required_code = None

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.get_or_create(
            slug=f"yrbac13-{cls.label}",
            defaults={"nom": f"YRBAC13 {cls.label}"},
        )[0]

    def _user(self, suffix, perms):
        role = Role.objects.create(
            company=self.company,
            nom=f"{self.label}-{suffix}",
            permissions=perms,
        )
        return User.objects.create_user(
            username=f"yrbac13-{self.label}-{suffix}",
            password="x",
            role=role,
            company=self.company,
        )

    def test_sans_le_code_requis_refuse(self):
        """Un rôle fin portant une AUTRE permission d'écriture (donc
        ``is_responsable`` historique passerait) mais PAS le code comptable
        requis est refusé — la garde YRBAC13 est bien PAR CODE, pas par
        palier grossier."""
        user = self._user("sans-code", perms=["ventes_creer"])
        resp = _client_for(user).post(
            self.action_path, {}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_avec_le_code_requis_pas_de_403(self):
        user = self._user("avec-code", perms=[self.required_code])
        resp = _client_for(user).post(
            self.action_path, {}, format="json")
        # Objet inexistant (pk=999999) → 404 métier, jamais 403 RBAC.
        self.assertNotEqual(resp.status_code, 403)

    def test_compte_legacy_garde_acces_historique(self):
        """Compte SANS rôle fin (repli HasPermissionOrLegacy) : accès
        préservé — aucune régression pour les comptes hérités."""
        from authentication.models import CustomUser
        user = User.objects.create_user(
            username=f"yrbac13-{self.label}-legacy",
            password="x",
            company=self.company,
            role_legacy=CustomUser.ROLE_RESPONSABLE,
        )
        resp = _client_for(user).post(
            self.action_path, {}, format="json")
        self.assertNotEqual(resp.status_code, 403)


class EffetEncaisserAllowDenyTests(_ComptaActionAllowDenyMixin, TestCase):
    """EffetViewSet.encaisser — saisie comptable (FG127)."""
    label = "effet-encaisser"
    action_path = "/api/django/compta/effets/999999/encaisser/"
    required_code = "compta_saisir"


class NoteFraisValiderAllowDenyTests(_ComptaActionAllowDenyMixin, TestCase):
    """NoteFraisViewSet.valider — poste la charge (débit 6/crédit 4432)."""
    label = "notefrais-valider"
    action_path = "/api/django/compta/notes-frais/999999/valider/"
    required_code = "compta_valider"


class DeclarationTvaDeposerAllowDenyTests(_ComptaActionAllowDenyMixin, TestCase):
    """DeclarationTVAViewSet.deposer — dépôt officiel de la déclaration."""
    label = "tva-deposer"
    action_path = "/api/django/compta/declarations-tva/999999/deposer/"
    required_code = "compta_valider"


class CampagneEnvoyerAllowDenyTests(_ComptaActionAllowDenyMixin, TestCase):
    """CampagneViewSet.envoyer (marketing-en-compta, ré-exportée par
    ``apps/marketing/views.py``) — déclenche un envoi réel."""
    label = "campagne-envoyer"
    action_path = "/api/django/compta/campagnes/999999/envoyer/"
    required_code = "compta_valider"


class EtatsComptablesReadOnlyTests(TestCase):
    """EtatsComptablesViewSet — 100% lecture (GET), garde explicite
    ajoutée pour le scanner YRBAC4 mais comportement STRICTEMENT inchangé :
    ``IsResponsableOrAdmin`` (palier grossier, pas de code fin)."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.get_or_create(
            slug="yrbac13-etats",
            defaults={"nom": "YRBAC13 Etats"},
        )[0]

    def test_role_lecture_seule_refuse(self):
        role = Role.objects.create(
            company=self.company, nom="etats-voir-seul",
            permissions=["reporting_voir"],
        )
        user = User.objects.create_user(
            username="yrbac13-etats-voir-seul", password="x",
            role=role, company=self.company,
        )
        resp = _client_for(user).get("/api/django/compta/etats/grand_livre/")
        self.assertEqual(resp.status_code, 403)

    def test_role_avec_permission_ecriture_autorise(self):
        role = Role.objects.create(
            company=self.company, nom="etats-gerer",
            permissions=["compta_saisir"],
        )
        user = User.objects.create_user(
            username="yrbac13-etats-gerer", password="x",
            role=role, company=self.company,
        )
        resp = _client_for(user).get("/api/django/compta/etats/grand_livre/")
        self.assertNotEqual(resp.status_code, 403)
