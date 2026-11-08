"""ALEA23 — garde de classe « liste blanche manuelle sans complétude ».

Les champs CONCRETS et INSCRIPTIBLES de ``LeadSerializer`` sont calculés par
INTROSPECTION : chacun doit être soit suivi au chatter (``TRACKED_FIELDS``),
soit exclu avec une raison (``CHAMPS_NON_SUIVIS``). Rouge sur 51f22174f
(``note``, ``contact_secondaire_nom``, ``contact_secondaire_telephone``,
``contact_preference``, ``structure_produit``, ``lien_maps``, ``tiers``,
``entite``), vert après ALEA16 + ALEA19.
"""
import ast
import pathlib

from django.test import SimpleTestCase

from apps.crm.activity import CHAMPS_NON_SUIVIS, TRACKED_FIELDS
from apps.crm.models import Lead
from apps.crm.serializers import LeadSerializer


def champs_inscriptibles_concrets():
    """Noms des champs inscriptibles du sérialiseur adossés à une colonne
    concrète de ``Lead`` (le nom DRF, ou sa ``source`` si elle diffère)."""
    concrets = {champ.name for champ in Lead._meta.concrete_fields}
    noms = set()
    for nom, champ in LeadSerializer().fields.items():
        if champ.read_only:
            continue
        source = champ.source if champ.source not in (None, '*') else nom
        if source in concrets:
            noms.add(source)
    return noms


class GardeChatterCompletTests(SimpleTestCase):
    def test_introspection_non_vide(self):
        """Anti-faux-vert : la garde voit bien les champs de la fiche."""
        noms = champs_inscriptibles_concrets()
        for attendu in ('nom', 'telephone', 'note', 'stage'):
            self.assertIn(attendu, noms)
        self.assertNotIn('company', noms)

    def test_tout_champ_inscriptible_est_suivi_ou_exclu(self):
        orphelins = sorted(
            champ for champ in champs_inscriptibles_concrets()
            if champ not in TRACKED_FIELDS and champ not in CHAMPS_NON_SUIVIS)
        self.assertEqual(
            orphelins, [],
            '\n'.join(f'Lead.{champ} inscriptible mais ni suivi au chatter '
                      'ni exclu (CHAMPS_NON_SUIVIS)' for champ in orphelins))

    def test_chaque_exclusion_porte_une_raison(self):
        for champ, raison in CHAMPS_NON_SUIVIS.items():
            with self.subTest(champ=champ):
                self.assertTrue(isinstance(raison, str) and raison.strip())

    def test_aucune_cle_perimee(self):
        concrets = {champ.name for champ in Lead._meta.concrete_fields}
        perimes = sorted(
            set(TRACKED_FIELDS) | set(CHAMPS_NON_SUIVIS))
        perimes = [cle for cle in perimes if cle not in concrets]
        self.assertEqual(perimes, [],
                         f'Clé(s) de suivi qui n’existent plus sur Lead : '
                         f'{perimes}')

    def test_suivi_et_exclusion_disjoints(self):
        self.assertFalse(set(TRACKED_FIELDS) & set(CHAMPS_NON_SUIVIS))


# ---------------------------------------------------------------------------
# CRXB5 — façade chatter partout + invariant user=None des chemins système.
# ---------------------------------------------------------------------------
_CRM = pathlib.Path(__file__).resolve().parent
#: Modules SYSTÈME : aucun humain derrière l'écriture — journal_systeme seul.
_MODULES_SYSTEME = ('webhooks.py', 'questionnaire.py', 'intake_photo.py',
                    'odoo_sync.py', 'tasks.py')


def _modules_crm():
    for chemin in sorted(_CRM.rglob('*.py')):
        rel = chemin.relative_to(_CRM).as_posix()
        if rel.startswith(('migrations/', 'golden/')) \
                or chemin.name.startswith(('test_', 'tests')):
            continue
        yield rel, chemin


def _est_systeme(rel):
    return (rel in _MODULES_SYSTEME or rel.startswith('management/')
            or rel.startswith('public_'))


def _appels(arbre):
    """[(fonction englobante, ast.Call)] de tout l'arbre."""
    out = []

    def visite(noeud, englobante):
        for enfant in ast.iter_child_nodes(noeud):
            if isinstance(enfant, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visite(enfant, enfant)
                continue
            if isinstance(enfant, ast.Call):
                out.append((englobante, enfant))
            visite(enfant, englobante)
    visite(arbre, None)
    return out


def _nom_appele(appel):
    f = appel.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        if f.attr == 'create' and isinstance(f.value, ast.Attribute) \
                and f.value.attr == 'objects' \
                and isinstance(f.value.value, ast.Name) \
                and f.value.value.id == 'LeadActivity':
            return 'LeadActivity.objects.create'
        return f.attr
    return None


class FacadeChatterTests(SimpleTestCase):
    """CRXB5 — toute écriture du chatter lead passe par ``activity.py`` ;
    un chemin système n'invente jamais d'auteur."""

    def _inventaire(self):
        for rel, chemin in _modules_crm():
            arbre = ast.parse(chemin.read_text(encoding='utf-8'))
            for englobante, appel in _appels(arbre):
                yield rel, englobante, appel, _nom_appele(appel)

    def test_anti_faux_vert(self):
        noms = {nom for _r, _e, _a, nom in self._inventaire()}
        self.assertIn('journal_systeme', noms)
        self.assertIn('creer_activite', noms)

    def test_aucune_ecriture_brute_hors_activity(self):
        brutes = sorted(f'{rel}:{appel.lineno}'
                        for rel, _e, appel, nom in self._inventaire()
                        if nom == 'LeadActivity.objects.create'
                        and rel != 'activity.py')
        self.assertEqual(brutes, [], 'LeadActivity.objects.create brut : '
                         'passer par activity.creer_activite / journal_systeme')

    def test_chemins_systeme_sans_auteur(self):
        fautifs = sorted(f'{rel}:{appel.lineno}'
                         for rel, _e, appel, nom in self._inventaire()
                         if nom == 'creer_activite' and _est_systeme(rel))
        self.assertEqual(fautifs, [], 'un module système écrit par '
                         'journal_systeme (user=None), jamais creer_activite')

    def test_auteur_relaye_jamais_invente(self):
        """``user=`` de ``creer_activite`` est un PARAMÈTRE de la fonction
        (l'acteur qu'on lui a passé) ou ``request.user`` — jamais
        ``lead.owner``, un ``User.objects…`` ou une constante."""
        fautifs = []
        for rel, englobante, appel, nom in self._inventaire():
            if nom != 'creer_activite' or rel == 'activity.py':
                continue
            valeur = next((k.value for k in appel.keywords if k.arg == 'user'), None)
            params = set()
            if englobante is not None:
                a = englobante.args
                params = {p.arg for p in a.posonlyargs + a.args + a.kwonlyargs}
            ok = (isinstance(valeur, ast.Name) and valeur.id in params) or (
                isinstance(valeur, ast.Attribute) and valeur.attr == 'user'
                and isinstance(valeur.value, ast.Name)
                and valeur.value.id == 'request')
            if not ok:
                fautifs.append(f'{rel}:{appel.lineno}')
        self.assertEqual(fautifs, [])

    def test_portes_executables(self):
        from apps.crm import activity
        with self.assertRaises(TypeError):
            activity.journal_systeme(user=object(), body='x')
        with self.assertRaises(TypeError):
            activity.creer_activite(body='x')
