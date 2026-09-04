"""AUD407 — `init_roles` ne réinitialise plus SILENCIEUSEMENT un rôle système.

`init_roles` écrase volontairement un rôle système divergent pour propager une
politique CHANGÉE dans le code — comportement voulu et testé
(`apps/stock/test_qg4_creation_produits.py::test_init_roles_repare_les_roles_deployes`).
Le défaut n'est pas la convergence, c'est son SILENCE : `deploy-prod.ps1` et
`auto-deploy.sh` relancent la commande à CHAQUE déploiement, donc une permission
retirée à la main par un Administrateur via Paramètres → Rôles (chemin supporté,
qui écrit LUI une ligne d'audit) était restaurée sans aucune trace, pour toutes
les sociétés, au merge suivant.

Ces tests sont ROUGES avant le correctif (aucune ligne d'audit n'est écrite) et
VERTS après.
"""
from django.core.management import call_command
from django.test import TestCase

from authentication.models import Company, CustomUser
from apps.parametres.models import SettingsAuditLog
from apps.roles.models import Role, CANONICAL_SYSTEM_ROLES


def _preset(nom):
    for role_nom, perms in CANONICAL_SYSTEM_ROLES:
        if role_nom == nom:
            return list(perms)
    raise AssertionError(f'Rôle canonique inconnu : {nom}')


class Aud407InitRolesLaisseUneTraceTests(TestCase):
    NOM = 'Responsable'

    def setUp(self):
        self.company = Company.objects.create(
            nom='AUD407 Co', slug='aud407-co')
        CustomUser.objects.create_user(
            username='aud407_u', password='pw-aud407-x', company=self.company,
            role_legacy='responsable')

    def _role_diverge(self):
        """Rôle système déployé DONT un Administrateur a retiré une permission
        (décision de sécurité prise via l'écran Rôles)."""
        preset = _preset(self.NOM)
        self.retiree = preset[0]
        Role.objects.create(
            company=self.company, nom=self.NOM, est_systeme=True,
            permissions=[p for p in preset if p != self.retiree])

    def _lignes(self):
        return SettingsAuditLog.objects.filter(
            company=self.company, section='roles',
            field=f'role:{self.NOM}')

    def test_la_restauration_est_tracee(self):
        self._role_diverge()
        self.assertEqual(self._lignes().count(), 0)

        call_command('init_roles', verbosity=0)

        lignes = list(self._lignes())
        self.assertEqual(len(lignes), 1, 'une trace exactement')
        self.assertIn('init_roles', lignes[0].field_label)
        # La permission restaurée est NOMMÉE dans la trace.
        self.assertIn(self.retiree, lignes[0].new_value)

    def test_la_convergence_reste_le_comportement(self):
        """Non-régression : on trace, on n'empêche pas (la commande sert à
        propager une politique changée dans le code)."""
        self._role_diverge()
        call_command('init_roles', verbosity=0)
        role = Role.objects.get(company=self.company, nom=self.NOM)
        self.assertIn(self.retiree, role.permissions)
        self.assertEqual(sorted(role.permissions), sorted(_preset(self.NOM)))

    def test_aucune_trace_quand_rien_ne_diverge(self):
        """Idempotence : un second passage n'écrit rien (sinon le journal se
        remplirait d'une ligne par rôle et par déploiement)."""
        self._role_diverge()
        call_command('init_roles', verbosity=0)
        avant = SettingsAuditLog.objects.filter(
            company=self.company, section='roles').count()

        call_command('init_roles', verbosity=0)

        apres = SettingsAuditLog.objects.filter(
            company=self.company, section='roles').count()
        self.assertEqual(apres, avant)

    def test_creation_initiale_ne_trace_rien(self):
        """Semer un rôle absent n'écrase rien : rien à tracer."""
        call_command('init_roles', verbosity=0)
        self.assertEqual(
            SettingsAuditLog.objects.filter(
                company=self.company, section='roles').count(), 0)
        # Les rôles canoniques ont bien été semés.
        self.assertTrue(
            Role.objects.filter(company=self.company, nom=self.NOM).exists())

    def test_la_trace_na_pas_dacteur_humain(self):
        """L'acteur est un DÉPLOIEMENT, jamais un utilisateur : ne pas
        attribuer la réécriture à qui n'en a pas décidé."""
        self._role_diverge()
        call_command('init_roles', verbosity=0)
        self.assertIsNone(self._lignes().first().user_id)
