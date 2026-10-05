"""SPL306 — golden des portées de l'API publique (capture AVANT déplacement).

Les codes de portée sont des IDENTIFIANTS PUBLIÉS (clés d'API déjà émises) : ils
ne changent jamais. Ce golden fige les 17 constantes ``SCOPE_*``, leurs libellés
et l'ordre d'affichage, les deux tables par entité, et garde l'EMPLACEMENT du
bloc (définition unique + aucun import depuis un autre module). SPL307 déplace
le bloc vers ``portees.py`` en posant ``EMPLACEMENT = 'apps.publicapi.portees'``.
"""
import ast
import importlib
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from authentication.models import Company

EMPLACEMENT = 'apps.publicapi.constants'

NOMS_BLOC_HORS_PORTEES = (
    'SCOPE_CHOICES', 'ALL_SCOPES',
    'EXPORT_SCOPE_BY_ENTITY', 'IMPORT_SCOPE_BY_ENTITY',
)

# ── Golden littéral (capturé sur le code actuel) ─────────────────────────────
PORTEES = {
    'SCOPE_READ_LEADS': 'read:leads',
    'SCOPE_READ_DEVIS': 'read:devis',
    'SCOPE_READ_FACTURES': 'read:factures',
    'SCOPE_READ_CHANTIERS': 'read:chantiers',
    'SCOPE_READ_STOCK': 'read:stock',
    'SCOPE_READ_LICENCE': 'read:licence',
    'SCOPE_READ_JURIDIQUE': 'juridique:read',
    'SCOPE_READ_EVENTS': 'read:events',
    'SCOPE_READ_FAVORIS': 'read:favoris',
    'SCOPE_READ_VUES': 'read:vues',
    'SCOPE_READ_CALEPINAGES': 'read:calepinages',
    'SCOPE_READ_ACHATS': 'lecture_achats',
    'SCOPE_READ_FIABILITE': 'fiabilite:lecture',
    'SCOPE_WRITE_LEADS': 'leads:write',
    'SCOPE_WRITE_ACTIVITIES': 'activities:write',
    'SCOPE_WRITE_DEVIS': 'devis:write',
    'SCOPE_WRITE_TICKETS': 'tickets:write',
}

CHOIX = [
    ('read:leads', 'Lire les leads'),
    ('read:devis', 'Lire les devis'),
    ('read:factures', 'Lire les factures'),
    ('read:chantiers', 'Lire les chantiers'),
    ('read:stock', 'Lire le stock (disponibilité, sans coûts)'),
    ('read:licence', 'Lire le statut de licence (plan, modules, sièges)'),
    ('juridique:read',
     'Lire les dossiers juridiques non confidentiels et leur budget'),
    ('read:events',
     "Lire le flux d'évènements (limité aux familles déjà autorisées)"),
    ('read:favoris',
     "Lire les favoris épinglés d'un utilisateur consentant (?owner=)"),
    ('read:vues',
     "Lire les vues sauvegardées d'équipe, ou d'un utilisateur consentant "
     "(?owner=)"),
    ('read:calepinages',
     'Lire les calepinages (sans géométrie brute ni coût interne)'),
    ('lecture_achats',
     "Lire les demandes d'achat et les demandes de prix (sans aucun prix "
     "d'achat)"),
    ('fiabilite:lecture',
     'Lire la fiabilité (sauvegardes, rapport SLA mensuel, limites & usage)'),
    ('leads:write', 'Créer/mettre à jour des leads'),
    ('activities:write', 'Créer des activités (notes) sur un lead'),
    ('devis:write', 'Créer un devis brouillon (jamais envoyé/accepté)'),
    ('tickets:write', 'Créer un ticket SAV correctif'),
]

EXPORT_PAR_ENTITE = {
    'leads': 'read:leads',
    'devis': 'read:devis',
    'factures': 'read:factures',
    'chantiers': 'read:chantiers',
    'produits': 'read:stock',
}

IMPORT_PAR_ENTITE = {
    'leads': 'leads:write',
    'activites': 'activities:write',
}


def _racine_django():
    return Path(__file__).resolve().parents[2]


def _module_du_fichier(chemin):
    rel = chemin.relative_to(_racine_django()).with_suffix('')
    parts = list(rel.parts)
    if parts[-1] == '__init__':
        parts.pop()
    return parts


def _fichier_de(module):
    return _racine_django().joinpath(*module.split('.')).with_suffix('.py')


def _noms_du_bloc():
    return set(PORTEES) | set(NOMS_BLOC_HORS_PORTEES)


def _module_importe(chemin, noeud):
    """Module absolu visé par un ``ImportFrom`` (relatifs résolus)."""
    if not noeud.level:
        return noeud.module or ''
    paquet = _module_du_fichier(chemin)
    if chemin.name != '__init__.py':
        paquet = paquet[:-1]
    if noeud.level > 1:
        paquet = paquet[:-(noeud.level - 1)]
    return '.'.join(paquet + ([noeud.module] if noeud.module else []))


class PorteesGoldenTests(TestCase):
    def setUp(self):
        self.mod = importlib.import_module(EMPLACEMENT)

    def test_codes_exacts(self):
        for nom, code in PORTEES.items():
            self.assertTrue(hasattr(self.mod, nom), nom)
            self.assertEqual(getattr(self.mod, nom), code, nom)

    def test_choix_sous_suite_ordonnee_et_all_scopes(self):
        vivants = list(self.mod.SCOPE_CHOICES)
        it = iter(vivants)
        for item in CHOIX:
            self.assertTrue(any(item == v for v in it),
                            f'{item!r} absent ou hors ordre dans SCOPE_CHOICES')
        self.assertEqual(self.mod.ALL_SCOPES, [c for c, _ in vivants])

    def test_tables_par_entite(self):
        self.assertLessEqual(set(EXPORT_PAR_ENTITE.items()),
                             set(self.mod.EXPORT_SCOPE_BY_ENTITY.items()))
        self.assertLessEqual(set(IMPORT_PAR_ENTITE.items()),
                             set(self.mod.IMPORT_SCOPE_BY_ENTITY.items()))

    def test_issue_ne_garde_que_les_codes_connus(self):
        from .models import ApiKey
        company, _ = Company.objects.get_or_create(
            slug='spl306', defaults={'nom': 'SPL306'})
        for code in PORTEES.values():
            cle, _raw = ApiKey.issue(
                company=company, label=code, scopes=[code, 'portee:inconnue'])
            self.assertEqual(cle.scopes, [code])

    def test_catalogue_servi_dans_l_ordre_du_golden(self):
        from .serializers import scope_catalogue
        codes = [s['code'] for s in scope_catalogue()['scopes']]
        attendus = list(PORTEES.values())
        self.assertEqual([c for c in codes if c in attendus], attendus)

    def test_pas_de_migration_induite(self):
        try:
            call_command('makemigrations', 'publicapi',
                         check=True, dry_run=True, verbosity=0)
        except SystemExit:
            self.fail('makemigrations publicapi --check détecte un changement')

    def test_garde_emplacement(self):
        noms = _noms_du_bloc()
        fichier_ref = _fichier_de(EMPLACEMENT).resolve()
        fautifs = []
        definitions_ref = set()
        for chemin in sorted(_racine_django().rglob('*.py')):
            try:
                arbre = ast.parse(chemin.read_text(encoding='utf-8'))
            except (SyntaxError, UnicodeDecodeError):
                continue
            est_ref = chemin.resolve() == fichier_ref
            for noeud in arbre.body:
                cibles = []
                if isinstance(noeud, ast.Assign):
                    cibles = [t.id for t in noeud.targets
                              if isinstance(t, ast.Name)]
                elif isinstance(noeud, ast.AnnAssign) and isinstance(
                        noeud.target, ast.Name):
                    cibles = [noeud.target.id]
                for nom in cibles:
                    if nom in noms:
                        if est_ref:
                            definitions_ref.add(nom)
                        else:
                            fautifs.append(f'{chemin}: définit {nom}')
            for noeud in ast.walk(arbre):
                if not isinstance(noeud, ast.ImportFrom):
                    continue
                pris = {a.name for a in noeud.names} & noms
                if not pris:
                    continue
                module = _module_importe(chemin, noeud)
                if module == EMPLACEMENT:
                    continue
                if (chemin.name == 'models.py'
                        and chemin.parent.name == 'publicapi'
                        and pris == {'SCOPE_CHOICES'}):
                    continue
                fautifs.append(
                    f'{chemin}:{noeud.lineno}: importe {sorted(pris)} '
                    f'depuis {module!r}')
        manquants = sorted(noms - definitions_ref)
        self.assertEqual(manquants, [],
                         f'noms non définis dans {EMPLACEMENT}')
        self.assertEqual(fautifs, [], 'Fautifs :\n' + '\n'.join(fautifs))
