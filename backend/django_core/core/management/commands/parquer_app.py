"""SOLMVP2 — ``manage.py parquer_app <label>`` : coquiller une app parquée.

Outil UNIQUE du parcage (décision fondateur du 20/09/2026, « fully out ») : il
applique mécaniquement le contrat « coquille de migrations » de
:mod:`core.parked` / ``docs/parked-modules.md`` §2 sur une app dont le label
figure dans :data:`core.parked.APPS_PARQUEES` :

1. écrit la migration finale d'ÉTAT SEUL
   ``SeparateDatabaseAndState(state_operations=[DeleteModel…],
   database_operations=[])`` — **aucune table supprimée, aucune ligne de
   ``django_migrations`` touchée** ;
2. vide ``models.py`` (docstring français seul) ;
3. réécrit ``apps.py`` au minimum (``name``/``label``/``default_auto_field``,
   ``parked = True``, manifeste ``'parked': True``, plus aucun ``ready()``
   important un module supprimé) ;
4. supprime TOUT le reste du dossier de l'app (vues, serializers, services,
   selectors, urls, tasks, admin, tests, templates, management,
   ``contract_samples/``, ``agent_actions/``, receivers…) ;
5. retire les ``include(...)`` de l'app dans ``erp_agentique/urls.py`` (forme
   ``path(...)`` comme forme helper ``*_si_active(...)``/``*_inclure(...)``, y
   compris les urls publiques ``public_urls``) ;
6. retire ses entrées de ``beat_schedule`` (sous ``erp_agentique/``) ;
7. supprime les specs ``frontend/e2e/**`` dédiées au module.

Idempotent : relancée sur une coquille, elle ne réécrit rien et se contente de
re-vérifier le câblage (urls / beat / e2e). ``--dry-run`` n'écrit RIEN et
imprime le plan ; ``--check`` sort en erreur (code 1) si une app parquée n'est
pas encore une coquille — c'est la preuve que les lanes SOLMVP30-36 réclament.

Usage ::

    python manage.py parquer_app statuspage --dry-run
    python manage.py parquer_app statuspage
    python manage.py parquer_app --check           # les 49 labels
    python manage.py parquer_app statuspage --check

``core`` reste fondation : ce module n'importe AUCUNE app métier (il ne
manipule que des chemins de fichiers, l'``ast`` et le graphe de migrations).
"""
from __future__ import annotations

import ast
import shutil
from pathlib import Path

from django.apps import apps as registre_apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import migrations as ops_migrations
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.state import ProjectState

from core import parked

# Seul contenu autorisé dans une coquille (contrat de core/parked.py, repris
# tel quel par core/tests/test_parked_registry.py).
CONTENU_COQUILLE = {'__init__.py', 'apps.py', 'models.py', 'migrations'}
NOM_MIGRATION = 'solmvp_coquille'


# --------------------------------------------------------------------------
# Lecture de l'état des migrations (sans base de données)
# --------------------------------------------------------------------------
def _ops_etat(operations):
    """Aplatit les opérations, en descendant dans ``SeparateDatabaseAndState``."""
    for op in operations:
        if isinstance(op, ops_migrations.SeparateDatabaseAndState):
            yield from _ops_etat(op.state_operations)
        else:
            yield op


def cible_app(champ, app_courante):
    """Label d'app visé par ``champ`` (relation), ou ``None``.

    Dans un état de migration, la cible est presque toujours une CHAÎNE
    (``'ged.Document'``, ``'self'``, ``'ModeleVoisin'``) résolue paresseusement.
    """
    distant = getattr(champ, 'remote_field', None)
    if distant is None:
        return None
    modele = getattr(distant, 'model', None)
    if modele is None:
        return None
    if isinstance(modele, str):
        if modele.lower() == 'self':
            return app_courante
        if '.' in modele:
            return modele.split('.', 1)[0].lower()
        return app_courante
    return modele._meta.app_label


def liens_internes(modeles, label):
    """``{Modele: {champ: ModeleCible}}`` pour les FK/M2M INTERNES à l'app.

    Les cibles d'un état de migration sont des chaînes dont la casse varie
    (``'ged.Document'`` comme ``'ged.document'``) : on rapproche donc les noms
    en minuscules avant de rendre le nom de classe RÉEL (celui attendu par
    ``DeleteModel(name=…)``). Les auto-références sont exclues : elles
    n'imposent aucun ordre.
    """
    noms = {etat_modele.name_lower: etat_modele.name
            for etat_modele in modeles.values()}
    liens = {}
    for etat_modele in modeles.values():
        champs = {}
        for nom, champ in etat_modele.fields.items():
            if cible_app(champ, label) != label:
                continue
            cible = champ.remote_field.model
            if isinstance(cible, str):
                cible_nom = (etat_modele.name_lower if cible.lower() == 'self'
                             else cible.split('.')[-1].lower())
            else:
                cible_nom = cible._meta.model_name
            reel = noms.get(cible_nom)
            if reel is not None and reel != etat_modele.name:
                champs[nom] = reel
        liens[etat_modele.name] = champs
    return liens


def _champ_etat(etat, app_label, model_name, field_name):
    modele = etat.models.get((app_label, str(model_name).lower()))
    if modele is None:
        return None
    return modele.fields.get(field_name)


def _retire_une_reference(migration, etat, label):
    """Vrai si ``migration`` (d'une AUTRE app) coupe un lien vers ``label``.

    C'est la DÉCOUVERTE générique des dépendances : les ``RemoveField`` des
    apps gardées (SOLMVP12 stock, SOLMVP14 sav, SOLMVP16 portail…) comme les
    ``DeleteModel`` des coquilles déjà passées. Aucun nom de migration n'est
    codé en dur : on interroge l'ÉTAT juste avant l'opération.
    """
    for op in _ops_etat(migration.operations):
        if isinstance(op, ops_migrations.RemoveField):
            champ = _champ_etat(etat, migration.app_label, op.model_name, op.name)
            if champ is not None and cible_app(champ, migration.app_label) == label:
                return True
        elif isinstance(op, ops_migrations.DeleteModel):
            modele = etat.models.get((migration.app_label, str(op.name).lower()))
            if modele is not None and any(
                    cible_app(c, migration.app_label) == label
                    for c in modele.fields.values()):
                return True
    return False


def rejouer_le_graphe(label):
    """Rejoue TOUT le graphe de migrations et renvoie ``(état final, retraits)``.

    ``retraits`` = ``{app: dernier nœud qui coupe un lien vers ``label``}`` :
    les dépendances à déclarer dans la migration-coquille. Aucune base de
    données n'est touchée (``MigrationLoader(None)``), comme ``makemigrations``.
    """
    chargeur = MigrationLoader(None, ignore_no_migrations=True)
    graphe = chargeur.graph
    vus = set()
    ordre = []
    for feuille in graphe.leaf_nodes():
        for noeud in graphe.forwards_plan(feuille):
            if noeud not in vus:
                vus.add(noeud)
                ordre.append(noeud)
    etat = ProjectState()
    retraits = {}
    for noeud in ordre:
        migration = graphe.nodes[noeud]
        if noeud[0] != label and _retire_une_reference(migration, etat, label):
            retraits[noeud[0]] = noeud
        migration.mutate_state(etat, preserve=False)
    feuilles = sorted(graphe.leaf_nodes(label))
    return etat, retraits, feuilles


# --------------------------------------------------------------------------
# Ordre des DeleteModel (tri topologique)
# --------------------------------------------------------------------------
def ordonner_suppressions(liens):
    """Ordonne les ``DeleteModel`` pour respecter les FK INTERNES à l'app.

    ``liens`` = ``{Modele: {champ: ModeleCible}}`` (cibles dans la même app,
    auto-références exclues). Un modèle POINTÉ par un autre est supprimé en
    DERNIER : on émet d'abord ses dépendants. Renvoie
    ``(ordre, retraits_de_cycle)`` où ``retraits_de_cycle`` est la liste des
    ``(modele, champ)`` à passer en ``RemoveField`` d'état pour casser un cycle
    de FK mutuelles (sinon aucun ordre n'existe).
    """
    referenceurs = {m: set() for m in liens}
    for modele, champs in liens.items():
        for cible in champs.values():
            if cible != modele and cible in referenceurs:
                referenceurs[cible].add(modele)
    restants = dict(liens)
    ordre = []
    retraits = []
    while restants:
        libres = sorted(m for m in restants
                        if not (referenceurs[m] & set(restants)))
        if not libres:
            # Cycle de FK mutuelles : aucun ordre n'existe. On coupe les liens
            # SORTANTS d'un modèle (le plus petit qui en a, ordre déterministe)
            # par des RemoveField d'état : ses cibles deviennent supprimables,
            # et lui part APRÈS elles.
            candidats = sorted(m for m in restants
                               if set(restants[m].values()) & set(restants))
            bloque = candidats[0] if candidats else sorted(restants)[0]
            coupes = 0
            for champ, cible in sorted(restants[bloque].items()):
                if cible != bloque and cible in restants:
                    retraits.append((bloque, champ))
                    referenceurs[cible].discard(bloque)
                    coupes += 1
            if coupes:
                continue
            libres = [bloque]  # garde-fou : jamais de boucle infinie
        for modele in libres:
            ordre.append(modele)
            restants.pop(modele, None)
    return ordre, retraits


# --------------------------------------------------------------------------
# Édition de fichiers texte (urls.py, celery.py) par plages de lignes
# --------------------------------------------------------------------------
def _parents(arbre):
    liens = {}
    for parent in ast.walk(arbre):
        for enfant in ast.iter_child_nodes(parent):
            liens[enfant] = parent
    return liens


def _etendre_aux_commentaires(lignes, debut):
    """Remonte le bloc de commentaires contigu collé au-dessus (1-based)."""
    i = debut - 1
    while i >= 1:
        texte = lignes[i - 1].strip()
        if texte.startswith('#'):
            i -= 1
        else:
            break
    return i + 1


def plages_urls(source, label):
    """Plages de lignes à retirer dans ``urls.py`` pour ``label``.

    Repère toute chaîne ``'apps.<label>[.…]'`` (``urls``, ``public_urls``,
    ``urls_gouvernance``…), remonte à l'ÉLÉMENT de liste qui la contient —
    donc indifféremment ``path(...)`` sur une ou deux lignes et la forme helper
    ``*_si_active(...)`` / ``*_inclure(...)`` — et y joint son commentaire.
    """
    arbre = ast.parse(source)
    lignes = source.splitlines()
    liens = _parents(arbre)
    prefixe = 'apps.%s' % label
    plages, orphelins = [], []
    for noeud in ast.walk(arbre):
        if not (isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)):
            continue
        valeur = noeud.value
        if valeur != prefixe and not valeur.startswith(prefixe + '.'):
            continue
        element, trouve = noeud, False
        while element in liens:
            if isinstance(liens[element], (ast.List, ast.Tuple)):
                trouve = True
                break
            element = liens[element]
        if not trouve:
            orphelins.append('%s (ligne %d)' % (valeur, noeud.lineno))
            continue
        plages.append((_etendre_aux_commentaires(lignes, element.lineno),
                       element.end_lineno))
    return sorted(set(plages)), orphelins


def _dicts_beat(arbre):
    """Les dictionnaires LITTÉRAUX affectés à un ``…beat_schedule``.

    On ne balaie JAMAIS tous les dicts du fichier : ``CELERY_TASK_ROUTES`` et
    autres réglages voisins ne doivent pas être touchés.
    """
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Assign) or not isinstance(noeud.value, ast.Dict):
            continue
        for cible in noeud.targets:
            nom = (cible.attr if isinstance(cible, ast.Attribute)
                   else cible.id if isinstance(cible, ast.Name) else '')
            if nom.endswith('beat_schedule'):
                yield noeud.value


def plages_beat(source, label):
    """Plages de lignes des entrées ``beat_schedule`` de l'app ``label``.

    Le nom d'une tâche porte l'app en préfixe (``ged.purge_corbeille_echue``,
    ``apps.ged.tasks.x``) : les deux formes sont reconnues.
    """
    arbre = ast.parse(source)
    lignes = source.splitlines()
    prefixes = ('%s.' % label, 'apps.%s.' % label)
    plages = []
    for noeud in _dicts_beat(arbre):
        for cle, valeur in zip(noeud.keys, noeud.values):
            if cle is None or not isinstance(valeur, ast.Dict):
                continue
            tache = None
            for k, v in zip(valeur.keys, valeur.values):
                if (isinstance(k, ast.Constant) and k.value == 'task'
                        and isinstance(v, ast.Constant)
                        and isinstance(v.value, str)):
                    tache = v.value
            if tache and tache.startswith(prefixes):
                plages.append((_etendre_aux_commentaires(lignes, cle.lineno),
                               valeur.end_lineno))
    return sorted(set(plages))


def retirer_plages(source, plages):
    """Renvoie ``source`` privé des lignes des ``plages`` (1-based, inclusives)."""
    a_retirer = set()
    for debut, fin in plages:
        a_retirer.update(range(debut, (fin or debut) + 1))
    lignes = source.splitlines(keepends=True)
    return ''.join(ligne for i, ligne in enumerate(lignes, start=1)
                   if i not in a_retirer)


# --------------------------------------------------------------------------
# Specs e2e
# --------------------------------------------------------------------------
def specs_e2e(racine_depot, label, labels_gardes):
    """Specs e2e dédiées au module : ``(à supprimer, conservées multi-module)``.

    Une spec part si son NOM DE FICHIER nomme le module ; une spec qui ne le
    nomme que dans ses 30 premières lignes ne part que si elle ne nomme AUCUNE
    app gardée — une spec de fumée transverse n'est jamais supprimée.
    """
    dossier = racine_depot / 'frontend' / 'e2e'
    if not dossier.is_dir():
        return [], []
    tiret = label.replace('_', '-')
    jetons = {label, tiret}
    a_supprimer, gardees = [], []
    for chemin in sorted(dossier.rglob('*.spec.*')):
        if chemin.suffix not in ('.js', '.ts'):
            continue
        normalise = '-' + ''.join(
            c if c.isalnum() else '-' for c in chemin.name.lower()) + '-'
        par_le_nom = any('-%s-' % j in normalise for j in jetons)
        if par_le_nom:
            a_supprimer.append(chemin)
            continue
        try:
            tete = '\n'.join(
                chemin.read_text(encoding='utf-8').splitlines()[:30]).lower()
        except OSError:
            continue
        if not any(motif in tete for motif in
                   ('apps/%s' % label, 'features/%s' % label, '/%s/' % tiret,
                    "'%s'" % tiret, '"%s"' % tiret)):
            continue
        autres = [g for g in labels_gardes
                  if g != label and ('apps/%s' % g in tete
                                     or 'features/%s' % g in tete
                                     or '/%s/' % g.replace('_', '-') in tete)]
        if autres:
            gardees.append((chemin, sorted(autres)[:4]))
        else:
            a_supprimer.append(chemin)
    return a_supprimer, gardees


# --------------------------------------------------------------------------
# Gabarits écrits sur le disque
# --------------------------------------------------------------------------
def _rendre_valeur(valeur, indentation):
    if isinstance(valeur, dict):
        lignes = ['{']
        for cle, sous in valeur.items():
            lignes.append('%s    %r: %s,' % (
                indentation, cle, _rendre_valeur(sous, indentation + '    ')))
        lignes.append('%s}' % indentation)
        return '\n'.join(lignes)
    return repr(valeur)


def rendre_apps_py(infos):
    """Génère le ``apps.py`` minimal d'une coquille."""
    lignes = [
        '"""Configuration de l\'app « %s » — PARQUÉE (voir ``core.parked``)."""'
        % infos['label'],
        'from django.apps import AppConfig',
        '',
        '',
        'class %s(AppConfig):' % infos['classe'],
        '    """%s — app PARQUÉE du MVP solaire (20/09/2026).' % (
            infos.get('verbose_name') or infos['label']),
        '',
        '    Coquille de migrations : plus aucun modèle, aucune url, aucune',
        '    tâche, aucun écran. Le code complet est dans l\'archive',
        '    ``%s`` ; recette de retour : docs/parked-modules.md §5.' % (
            parked.ARCHIVE_REF),
        '',
        '    L\'app RESTE dans INSTALLED_APPS : c\'est ce qui garde valide le',
        '    graphe de migrations des apps gardées (jamais de squash).',
        '    """',
        '',
    ]
    for attribut in ('default_auto_field', 'name', 'label', 'verbose_name'):
        if infos.get(attribut) is not None:
            lignes.append('    %s = %r' % (attribut, infos[attribut]))
    lignes += [
        '    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).',
        '    parked = True',
    ]
    if infos.get('manifeste_source'):
        lignes.append('    module_manifest = %s' % infos['manifeste_source'])
    elif infos.get('manifeste'):
        lignes.append('    module_manifest = %s'
                      % _rendre_valeur(infos['manifeste'], '    '))
    return '\n'.join(lignes) + '\n'


def rendre_models_py(label):
    return (
        '"""Modèles de l\'app « %s » — PARQUÉE (MVP solaire, 20/09/2026).\n'
        '\n'
        'Fichier VIDE À DESSEIN : les modèles sont sortis de l\'état Django par\n'
        'la migration ``%s`` (état seul, ``database_operations=[]``). Les TABLES\n'
        'et toutes leurs lignes sont INTACTES en base — rien n\'est perdu.\n'
        '\n'
        'Ne rien remettre ici : le retour du module se fait par la recette de\n'
        '``docs/parked-modules.md`` §5 (restauration depuis ``%s``).\n'
        '"""\n' % (label, NOM_MIGRATION, parked.ARCHIVE_REF))


def rendre_migration(label, feuille, dependances, suppressions, retraits_cycle):
    lignes = [
        '"""SOLMVP — coquille de migrations de l\'app « %s ».' % label,
        '',
        'Migration d\'ÉTAT SEUL générée par ``manage.py parquer_app %s`` :' % label,
        '``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de',
        '``django_migrations`` touchée. Les modèles sortent seulement de l\'état',
        'Django ; les données restent intégralement en base.',
        '',
        'Retour du module : ``manage.py migrate %s %s`` (renverse cet état),' % (
            label, feuille),
        'puis suppression de ce fichier — docs/parked-modules.md §5.',
        '"""',
        'from django.db import migrations',
        '',
        '',
        'class Migration(migrations.Migration):',
        '',
        '    dependencies = [',
    ]
    for app, nom in dependances:
        lignes.append('        (%r, %r),' % (app, nom))
    lignes += [
        '    ]',
        '',
        '    operations = [',
        '        migrations.SeparateDatabaseAndState(',
        '            state_operations=[',
    ]
    for modele, champ in retraits_cycle:
        lignes.append(
            '                migrations.RemoveField(model_name=%r, name=%r),'
            % (modele.lower(), champ))
    for modele in suppressions:
        lignes.append('                migrations.DeleteModel(name=%r),' % modele)
    lignes += [
        '            ],',
        '            database_operations=[],',
        '        ),',
        '    ]',
    ]
    return '\n'.join(lignes) + '\n'


# --------------------------------------------------------------------------
# apps.py : lecture des attributs à conserver
# --------------------------------------------------------------------------
def lire_apps_py(chemin, label):
    source = chemin.read_text(encoding='utf-8')
    arbre = ast.parse(source)
    for noeud in arbre.body:
        if not isinstance(noeud, ast.ClassDef):
            continue
        if not any('AppConfig' in ast.dump(base) for base in noeud.bases):
            continue
        infos = {'classe': noeud.name, 'label': label}
        for element in noeud.body:
            if not isinstance(element, ast.Assign) or len(element.targets) != 1:
                continue
            cible = element.targets[0]
            if not isinstance(cible, ast.Name):
                continue
            if cible.id in ('default_auto_field', 'name', 'label', 'verbose_name'):
                if isinstance(element.value, ast.Constant):
                    infos[cible.id] = element.value.value
            elif cible.id == 'module_manifest':
                try:
                    manifeste = ast.literal_eval(element.value)
                except (ValueError, SyntaxError):
                    manifeste = None
                if isinstance(manifeste, dict):
                    manifeste['parked'] = True
                    infos['manifeste'] = manifeste
                else:
                    # Manifeste non littéral : on garde sa SOURCE verbatim et
                    # on y injecte le drapeau, plutôt que de le perdre.
                    brut = ast.get_source_segment(source, element.value) or '{}'
                    infos['manifeste_source'] = brut.replace(
                        '{', "{\n        'parked': True,", 1)
        return infos
    raise CommandError(
        '%s : aucune classe AppConfig trouvée — apps.py doit être ajusté à la '
        'main avant de coquiller l\'app.' % chemin)


def est_coquille(dossier):
    if not dossier.is_dir():
        return False
    for entree in dossier.iterdir():
        if entree.name == '__pycache__':
            continue
        if entree.name not in CONTENU_COQUILLE:
            return False
    if not (dossier / 'migrations').is_dir():
        return False
    modeles = dossier / 'models.py'
    if not modeles.is_file():
        return False
    corps = ast.parse(modeles.read_text(encoding='utf-8')).body
    return not corps or (
        len(corps) == 1 and isinstance(corps[0], ast.Expr)
        and isinstance(corps[0].value, ast.Constant)
        and isinstance(corps[0].value.value, str))


class Command(BaseCommand):
    help = ('Coquille une app parquée (SOLMVP2) : migration d\'état seul, '
            'models.py vide, apps.py minimal, reste du dossier supprimé, '
            'urls/beat/e2e nettoyés. --dry-run n\'écrit rien.')

    def add_arguments(self, analyseur):
        analyseur.add_argument('label', nargs='?',
                               help='label de l\'app (ex. statuspage)')
        analyseur.add_argument('--dry-run', action='store_true',
                               help='imprime le plan sans rien écrire')
        analyseur.add_argument(
            '--check', action='store_true',
            help='sort en erreur si l\'app parquée n\'est pas une coquille '
                 '(sans label : les 49 labels du registre)')

    # -- points d'entrée ---------------------------------------------------
    def handle(self, *args, **options):
        label = options.get('label')
        if options['check']:
            return self._check(label)
        if not label:
            raise CommandError('label requis (ou --check pour tout vérifier).')
        self._valider(label)
        dossier = self._dossier(label)
        if est_coquille(dossier):
            self.stdout.write(self.style.WARNING(
                '%s : DÉJÀ une coquille — migration/models/apps inchangés.'
                % label))
            self._cablage(label, options['dry_run'])
            return
        plan = self._plan(label, dossier)
        self._imprimer_plan(plan)
        if options['dry_run']:
            self.stdout.write(self.style.WARNING(
                '--dry-run : RIEN n\'a été écrit.'))
            return
        self._appliquer(plan)
        self.stdout.write(self.style.SUCCESS(
            '%s : coquille posée (aucune table supprimée).' % label))

    def _check(self, label):
        labels = [label] if label else list(parked.APPS_PARQUEES)
        if label:
            self._valider(label)
        manquants = [lab for lab in labels
                     if not est_coquille(self._dossier(lab))]
        if manquants:
            raise CommandError(
                '%d app(s) parquée(s) pas encore coquillée(s) : %s\n'
                'Lancer `manage.py parquer_app <label>` (lanes SOLMVP30-36).'
                % (len(manquants), ', '.join(manquants)))
        self.stdout.write(self.style.SUCCESS(
            'parquer_app --check : %d app(s) parquée(s), toutes en coquille.'
            % len(labels)))

    # -- aides -------------------------------------------------------------
    def _valider(self, label):
        if not parked.est_parquee(label):
            raise CommandError(
                '%s n\'est pas dans core.parked.APPS_PARQUEES : cette commande '
                'ne coquille QUE les apps parquées (registre unique, décision '
                'fondateur).' % label)

    def _dossier(self, label):
        try:
            config = registre_apps.get_app_config(label)
        except LookupError as exc:
            raise CommandError(
                '%s : app absente du registre Django (INSTALLED_APPS) — une app '
                'parquée RESTE installée. %s' % (label, exc))
        return Path(config.path)

    @property
    def _racine_backend(self):
        return Path(settings.BASE_DIR)

    @property
    def _racine_depot(self):
        return self._racine_backend.parent.parent

    def _fichiers_urls(self):
        chemin = self._racine_backend / 'erp_agentique' / 'urls.py'
        return [chemin] if chemin.is_file() else []

    def _fichiers_beat(self):
        dossier = self._racine_backend / 'erp_agentique'
        if not dossier.is_dir():
            return []
        return [p for p in sorted(dossier.rglob('*.py'))
                if 'beat_schedule' in p.read_text(encoding='utf-8')]

    def _labels_gardes(self):
        dossier_apps = self._racine_backend / 'apps'
        if not dossier_apps.is_dir():
            return []
        return sorted(p.name for p in dossier_apps.iterdir()
                      if p.is_dir() and not parked.est_parquee(p.name))

    # -- plan --------------------------------------------------------------
    def _plan(self, label, dossier):
        etat, retraits, feuilles = rejouer_le_graphe(label)
        if len(feuilles) > 1:
            raise CommandError(
                '%s : %d feuilles de migration (%s) — résoudre le conflit '
                'avant de coquiller.' % (label, len(feuilles),
                                         ', '.join(n for _, n in feuilles)))
        modeles = {cle[1]: etat.models[cle] for cle in etat.models
                   if cle[0] == label}
        bloquants = self._bloquants(etat, label)
        if bloquants:
            raise CommandError(
                '%s est encore référencée par : %s\nCouper ces liens d\'abord '
                '(RemoveField côté app gardée — SOLMVP12/14/16 ; ou coquiller '
                'd\'abord l\'app parquée dépendante, ordre de core.parked.'
                'GROUPES).' % (label, ', '.join(bloquants)))
        if modeles and not feuilles:
            raise CommandError(
                '%s a %d modèle(s) dans l\'état mais AUCUNE migration : '
                'générer d\'abord ses migrations.' % (label, len(modeles)))
        suppressions, retraits_cycle = ordonner_suppressions(
            liens_internes(modeles, label))
        dependances = ([feuilles[0]] if feuilles else []) + [
            retraits[app] for app in sorted(retraits)]
        # Numéro = plus haut préfixe présent sur le disque + 1 (jamais un
        # count() : une migration au nom non numéroté ne doit pas décaler).
        numeros = [int(p.name[:4])
                   for p in (dossier / 'migrations').glob('*.py')
                   if p.name[:4].isdigit()]
        fichier = (dossier / 'migrations'
                   / ('%04d_%s.py' % ((max(numeros) + 1) if numeros else 1,
                                      NOM_MIGRATION)))
        deja = sorted((dossier / 'migrations').glob('*_%s.py' % NOM_MIGRATION))
        a_supprimer = sorted(
            p for p in dossier.iterdir() if p.name not in CONTENU_COQUILLE)
        plages_par_fichier = []
        for chemin in self._fichiers_urls():
            source = chemin.read_text(encoding='utf-8')
            plages, orphelins = plages_urls(source, label)
            if plages or orphelins:
                plages_par_fichier.append((chemin, plages, orphelins))
        beat_par_fichier = []
        for chemin in self._fichiers_beat():
            plages = plages_beat(chemin.read_text(encoding='utf-8'), label)
            if plages:
                beat_par_fichier.append((chemin, plages))
        e2e, e2e_gardees = specs_e2e(self._racine_depot, label,
                                     self._labels_gardes())
        return {
            'label': label, 'dossier': dossier, 'feuille': feuilles,
            'modeles': suppressions, 'retraits_cycle': retraits_cycle,
            'dependances': dependances, 'fichier_migration': fichier,
            'a_supprimer': a_supprimer, 'urls': plages_par_fichier,
            'beat': beat_par_fichier, 'e2e': e2e, 'e2e_gardees': e2e_gardees,
            'migration_deja_la': deja,
        }

    def _bloquants(self, etat, label):
        """Références ENTRANTES encore vivantes vers ``label``.

        Deux sources, complémentaires : l'ÉTAT final des migrations (ce que
        verra ``DeleteModel``) et le registre RÉEL des modèles (ce que le code
        des apps gardées déclare encore, y compris pour une app sans
        migrations). Supprimer un modèle encore pointé casserait l'état.
        """
        trouves = {}

        def _marque(app):
            return ('parquée, pas encore coquillée' if parked.est_parquee(app)
                    else 'app GARDÉE')

        def _noter(app, modele, champ, source):
            trouves.setdefault((app, modele, champ), set()).add(source)

        for (app, _), modele in etat.models.items():
            if app == label:
                continue
            for nom, champ in modele.fields.items():
                if cible_app(champ, app) == label:
                    _noter(app, modele.name, nom, 'état')
        for modele in registre_apps.get_models():
            app = modele._meta.app_label
            if app == label:
                continue
            # UNIQUEMENT les champs SORTANTS (jamais les relations inverses,
            # qui pointeraient dans l'autre sens).
            champs = (list(modele._meta.concrete_fields)
                      + list(modele._meta.local_many_to_many))
            for champ in champs:
                distant = getattr(champ.remote_field, 'model', None) \
                    if champ.remote_field is not None else None
                if distant is not None and not isinstance(distant, str) \
                        and distant._meta.app_label == label:
                    _noter(app, modele.__name__, champ.name, 'modèle')
        return ['%s.%s.%s [%s, %s]' % (app, modele, champ,
                                       '+'.join(sorted(sources)), _marque(app))
                for (app, modele, champ), sources in sorted(trouves.items())]

    def _relatif(self, chemin):
        try:
            return chemin.relative_to(self._racine_backend)
        except ValueError:
            return chemin

    def _imprimer_plan(self, plan):
        ecrire = self.stdout.write
        ecrire('=== parquer_app %s — plan ===' % plan['label'])
        if plan['migration_deja_la']:
            ecrire(self.style.WARNING(
                'migration-coquille DÉJÀ écrite (%s) — conservée, ménage seul.'
                % plan['migration_deja_la'][0].name))
        ecrire('migration d\'état : %s'
               % self._relatif(plan['fichier_migration']))
        ecrire('  dependencies : %s' % (
            ', '.join('%s.%s' % d for d in plan['dependances']) or '(aucune)'))
        for modele, champ in plan['retraits_cycle']:
            ecrire('  RemoveField (cycle) : %s.%s' % (modele, champ))
        ecrire('  DeleteModel (%d, dépendants d\'abord) : %s'
               % (len(plan['modeles']), ', '.join(plan['modeles']) or '(aucun)'))
        ecrire('models.py vidé, apps.py réécrit (parked = True)')
        ecrire('supprimés (%d) : %s' % (
            len(plan['a_supprimer']),
            ', '.join(p.name for p in plan['a_supprimer']) or '(rien)'))
        for chemin, plages, orphelins in plan['urls']:
            ecrire('urls %s : lignes %s' % (
                chemin.name,
                ', '.join('%d-%d' % p for p in plages) or '(aucune)'))
            for orphelin in orphelins:
                ecrire(self.style.WARNING(
                    '  À REVOIR À LA MAIN (hors liste d\'urls) : %s' % orphelin))
        for chemin, plages in plan['beat']:
            ecrire('beat %s : %d entrée(s), lignes %s'
                   % (chemin.name, len(plages),
                      ', '.join('%d-%d' % p for p in plages)))
        ecrire('specs e2e supprimées (%d) : %s' % (
            len(plan['e2e']),
            ', '.join(p.name for p in plan['e2e']) or '(aucune)'))
        for chemin, autres in plan['e2e_gardees']:
            ecrire('  conservée (spec multi-module, cite %s) : %s'
                   % ('/'.join(autres), chemin.name))

    # -- application -------------------------------------------------------
    def _appliquer(self, plan):
        label, dossier = plan['label'], plan['dossier']
        if plan['migration_deja_la']:
            # Reprise après un run interrompu : la migration-coquille est déjà
            # écrite (donc l'état ne contient plus de modèle) — on ne la
            # regénère JAMAIS, on finit seulement le ménage.
            self.stdout.write(
                '%s : migration-coquille déjà présente (%s) — conservée.'
                % (label, plan['migration_deja_la'][0].name))
        elif plan['modeles'] or plan['retraits_cycle']:
            plan['fichier_migration'].write_text(
                rendre_migration(label, plan['feuille'][0][1],
                                 plan['dependances'], plan['modeles'],
                                 plan['retraits_cycle']),
                encoding='utf-8')
        else:
            self.stdout.write(
                '%s : aucun modèle dans l\'état — pas de migration à écrire.'
                % label)
        infos = lire_apps_py(dossier / 'apps.py', label)
        (dossier / 'models.py').write_text(
            rendre_models_py(label), encoding='utf-8')
        (dossier / 'apps.py').write_text(rendre_apps_py(infos), encoding='utf-8')
        for chemin in plan['a_supprimer']:
            if chemin.is_dir():
                shutil.rmtree(chemin)
            else:
                chemin.unlink()
        # Bytecode périmé : un .pyc d'un module supprimé reste importable.
        for cache in sorted(dossier.rglob('__pycache__')):
            shutil.rmtree(cache, ignore_errors=True)
        self._ecrire_cablage(plan)

    def _ecrire_cablage(self, plan):
        for chemin, plages, _ in plan['urls']:
            if plages:
                source = chemin.read_text(encoding='utf-8')
                chemin.write_text(retirer_plages(source, plages),
                                  encoding='utf-8')
        for chemin, plages in plan['beat']:
            source = chemin.read_text(encoding='utf-8')
            chemin.write_text(retirer_plages(source, plages), encoding='utf-8')
        for chemin in plan['e2e']:
            chemin.unlink()

    def _cablage(self, label, dry_run):
        """Re-vérifie urls/beat/e2e sur une app DÉJÀ coquillée (idempotence)."""
        reste = {'urls': [], 'beat': [], 'e2e': []}
        for chemin in self._fichiers_urls():
            plages, _ = plages_urls(chemin.read_text(encoding='utf-8'), label)
            if plages:
                reste['urls'].append((chemin, plages, []))
        for chemin in self._fichiers_beat():
            plages = plages_beat(chemin.read_text(encoding='utf-8'), label)
            if plages:
                reste['beat'].append((chemin, plages))
        reste['e2e'] = specs_e2e(self._racine_depot, label,
                                 self._labels_gardes())[0]
        if not any(reste.values()):
            self.stdout.write('%s : câblage déjà propre (urls, beat, e2e).'
                              % label)
            return
        self.stdout.write(self.style.WARNING(
            '%s : résidus de câblage → urls %d, beat %d, e2e %d'
            % (label, len(reste['urls']), len(reste['beat']),
               len(reste['e2e']))))
        if dry_run:
            self.stdout.write('--dry-run : rien n\'a été écrit.')
            return
        self._ecrire_cablage({'urls': reste['urls'], 'beat': reste['beat'],
                              'e2e': reste['e2e']})
        self.stdout.write(self.style.SUCCESS('%s : câblage nettoyé.' % label))
