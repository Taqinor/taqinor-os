"""SPL304 — golden des modèles suivis par le journal d'audit, AVANT tout déplacement.

Capture seule : aucun code de production n'est modifié. Le golden est littéral
dans ce module (``GOLDEN_TRACKED_MODELS`` : les 30 tuples dans l'ordre, relevés
sur ``apps/audit/signals.py`` actuel). Plancher : ajout toléré, jamais retrait
ni réordonnancement. ASTK145 : +6 données maîtres catalogue/tarif (36).
"""
import ast
from pathlib import Path
from types import SimpleNamespace

from django.apps import apps as django_apps
from django.core.management import call_command
from django.db.models.signals import post_delete, post_save, pre_save
from django.test import TestCase

# SPL305 : les deux registres vivent dans modeles_suivis.py ; signals.py
# les importe pour connect() et _on_post_save.
EMPLACEMENT = 'apps.audit.modeles_suivis'
NOMS = ['TRACKED_MODELS', 'MODELES_SANS_UPDATE_GENERIQUE']
RACINE_DJANGO = Path(__file__).resolve().parents[2]

GOLDEN_TRACKED_MODELS = [
    ('crm', 'Lead'),
    ('crm', 'Client'),
    ('ventes', 'Devis'),
    ('facturation', 'Facture'),
    ('facturation', 'Avoir'),
    ('facturation', 'RelanceLog'),
    ('ventes', 'BonCommande'),
    ('facturation', 'Paiement'),
    ('installations', 'Installation'),
    ('installations', 'Intervention'),
    ('sav', 'Ticket'),
    ('sav', 'Equipement'),
    ('sav', 'ContratMaintenance'),
    ('stock', 'Produit'),
    ('stock', 'MouvementStock'),
    ('stock', 'Fournisseur'),
    ('achats', 'BonCommandeFournisseur'),
    ('achats', 'ReceptionFournisseur'),
    ('achats', 'FactureFournisseur'),
    ('achats', 'PaiementFournisseur'),
    ('parametres', 'CompanyProfile'),
    ('authentication', 'CustomUser'),
    ('roles', 'Role'),
    ('publicapi', 'ApiKey'),
    ('publicapi', 'Webhook'),
    ('core', 'ChangelogEntry'),
    ('core', 'ConsentRecord'),
    ('core', 'DataSubjectRequest'),
    ('core', 'RegistreTraitement'),
    ('ventes', 'RegulatoryDossier'),
    # ASTK145 — net-additif : six données maîtres catalogue/tarif fournisseur.
    ('stock', 'Categorie'),
    ('stock', 'Marque'),
    ('stock', 'KitProduit'),
    ('stock', 'KitComposant'),
    ('achats', 'PrixFournisseur'),
    ('stock', 'PalierPrixFournisseur'),
]
GOLDEN_SANS_UPDATE = {('cpq', 'PrixContractuel')}


def est_sous_suite(petit, grand):
    """Vrai si ``petit`` est une sous-suite ORDONNÉE de ``grand``."""
    it = iter(grand)
    return all(any(x == y for y in it) for x in petit)


def _module_receveur(signal, model, uid):
    for entree in signal.receivers:
        cle = entree[0]
        if cle[0] == uid and cle[1] == id(model):
            return True
    return False


def _module_de(chemin):
    rel = chemin.relative_to(RACINE_DJANGO).with_suffix('')
    return '.'.join(rel.parts)


def _resoudre(chemin, node):
    """Module absolu visé par un ``ImportFrom`` (relatifs résolus)."""
    if not node.level:
        return node.module or ''
    parties = _module_de(chemin).split('.')[:-1]  # module -> son paquet
    if node.level > 1:
        parties = parties[:len(parties) - (node.level - 1)]
    if node.module:
        parties = parties + node.module.split('.')
    return '.'.join(parties)


def _pointe(noeud):
    """Chemin pointé d'une chaîne ``Name``/``Attribute`` (sinon ``None``)."""
    morceaux = []
    while isinstance(noeud, ast.Attribute):
        morceaux.append(noeud.attr)
        noeud = noeud.value
    if isinstance(noeud, ast.Name):
        morceaux.append(noeud.id)
        return '.'.join(reversed(morceaux))
    return None


def fautifs_emplacement(noms, emplacement, racine=None):
    """Violations de la garde d'emplacement : liste de ``(fichier, détail)``.

    (a) un nom défini au premier niveau ailleurs que dans le fichier de
    ``emplacement`` ; (b) un nom lu depuis un autre module que ``emplacement`` :
    ``from … import NOM``, attribut ``alias.NOM`` d'un module importé, ou forme
    chaîne ``import_module('<module>').NOM``.
    """
    racine = racine or RACINE_DJANGO
    noms = set(noms)
    fichier_ref = emplacement.replace('.', '/')
    fautifs = []
    for chemin in sorted(racine.rglob('*.py')):
        try:
            source = chemin.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            continue
        if not any(n in source for n in noms):
            continue
        try:
            arbre = ast.parse(source)
        except SyntaxError:
            continue
        rel = chemin.relative_to(racine).as_posix()
        est_ref = rel in (fichier_ref + '.py', fichier_ref + '/__init__.py')
        for noeud in arbre.body:  # (a) définitions de premier niveau
            cibles = []
            if isinstance(noeud, ast.FunctionDef) and noeud.name in noms:
                cibles = [noeud.name]
            elif isinstance(noeud, ast.Assign):
                cibles = [t.id for t in noeud.targets
                          if isinstance(t, ast.Name) and t.id in noms]
            elif (isinstance(noeud, ast.AnnAssign)
                  and isinstance(noeud.target, ast.Name)
                  and noeud.target.id in noms):
                cibles = [noeud.target.id]
            if cibles and not est_ref:
                fautifs.append((rel, f'définit {sorted(cibles)}'))
        noeuds = list(ast.walk(arbre))
        liaisons = {}
        for noeud in noeuds:  # (b) imports
            if isinstance(noeud, ast.ImportFrom):
                cible = _resoudre(chemin, noeud)
                for alias in noeud.names:
                    if alias.name in noms:
                        if cible != emplacement:
                            fautifs.append(
                                (rel, f'importe {alias.name} depuis {cible}'))
                    elif alias.name != '*':
                        liaisons[alias.asname or alias.name] = (
                            f'{cible}.{alias.name}')
            elif isinstance(noeud, ast.Import):
                for alias in noeud.names:
                    liaisons[alias.asname or alias.name] = alias.name
        for noeud in noeuds:  # (b) attributs
            if not (isinstance(noeud, ast.Attribute) and noeud.attr in noms):
                continue
            cible = None
            valeur = noeud.value
            if (isinstance(valeur, ast.Call) and valeur.args
                    and isinstance(valeur.args[0], ast.Constant)
                    and isinstance(valeur.args[0].value, str)
                    and (_pointe(valeur.func) or '').endswith('import_module')):
                cible = valeur.args[0].value
            else:
                pointe = _pointe(valeur)
                if pointe in liaisons:
                    cible = liaisons[pointe]
            if cible is not None and cible != emplacement:
                fautifs.append((rel, f'lit {noeud.attr} via {cible}'))
    return fautifs


class ModelesSuivisGoldenTests(TestCase):
    def test_plancher_tracked_models(self):
        from apps.audit import modeles_suivis
        self.assertEqual(len(GOLDEN_TRACKED_MODELS), 36)
        self.assertTrue(
            est_sous_suite(GOLDEN_TRACKED_MODELS,
                           list(modeles_suivis.TRACKED_MODELS)),
            'TRACKED_MODELS : tuple retiré ou réordonné',
        )
        self.assertTrue(
            GOLDEN_SANS_UPDATE
            <= set(modeles_suivis.MODELES_SANS_UPDATE_GENERIQUE))

    def test_connect_a_cable_les_trois_signaux(self):
        for app_label, nom in GOLDEN_TRACKED_MODELS:
            model = django_apps.get_model(app_label, nom)
            with self.subTest(modele=f'{app_label}.{nom}'):
                self.assertTrue(_module_receveur(
                    post_save, model, f'audit_save_{app_label}_{nom}'))
                self.assertTrue(_module_receveur(
                    post_delete, model, f'audit_del_{app_label}_{nom}'))
                self.assertTrue(_module_receveur(
                    pre_save, model, f'audit_pre_{app_label}_{nom}'))

    def test_aller_retour_role_ecrit_une_ligne_audit(self):
        from authentication.models import Company
        from apps.audit import recorder
        from apps.audit.models import AuditLog
        from apps.roles.models import Role
        company = Company.objects.create(nom='SPL304 Co', slug='spl304-co')
        recorder.begin_request(SimpleNamespace(user=None))
        try:
            role = Role.objects.create(
                company=company, nom='SPL304 role', permissions=[])
        finally:
            recorder.end_request()
        lignes = AuditLog.objects.filter(
            action=AuditLog.Action.CREATE, object_id=str(role.pk),
            content_type__app_label='roles', content_type__model='role')
        self.assertEqual(lignes.count(), 1)

    def test_makemigrations_audit_sans_changement(self):
        try:
            call_command('makemigrations', 'audit', check=True, dry_run=True,
                         verbosity=0)
        except SystemExit:
            self.fail('makemigrations audit détecte un changement de modèle')

    def test_garde_emplacement(self):
        fautifs = fautifs_emplacement(NOMS, EMPLACEMENT)
        self.assertEqual(
            fautifs, [],
            'noms définis/lus hors de %s :\n%s' % (
                EMPLACEMENT,
                '\n'.join(f'  {f} — {d}' for f, d in fautifs)),
        )
