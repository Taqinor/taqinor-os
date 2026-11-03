"""ASAV75 — garde de classe : aucune écriture directe de ``Ticket.statut``.

Parcourt (AST) le code de ``apps/sav`` (tests et migrations exclus) et
refuse toute écriture du statut d'un ticket hors des DEUX points de
transition : ``machine_etats.changer_statut`` et
``services.appliquer_transition_ticket``. Liste d'exceptions VIDE.

Formes détectées :
  * ``<ticket>.statut = …`` (cible dont le nom contient « ticket », ou
    valeur ``Ticket.Statut.*``) ;
  * ``setattr(<ticket>, 'statut', …)`` ;
  * ``….update(statut=…)`` sur ``Ticket.objects`` / un nom « ticket ».

Les statuts d'autres modèles (équipement, alarme, prêt) ne sont pas visés.

Run :
    python manage.py test apps.sav.tests_asav75_garde_statut -v2
"""
import ast
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

RACINE_SAV = Path(__file__).resolve().parent

#: Les SEULS points autorisés à écrire ``Ticket.statut`` (fichier, fonction).
POINTS_AUTORISES = {
    ('machine_etats.py', 'changer_statut'),
    ('services.py', 'appliquer_transition_ticket'),
}

MESSAGE = (
    "Écriture directe de Ticket.statut interdite : passez par "
    "services.appliquer_transition_ticket (machine d'états, gardes et effets "
    "complets).")


def _est_ticket_statut(noeud):
    """``Ticket.Statut`` (ou ``Ticket.Statut.X``) apparaît dans ``noeud``."""
    for sous in ast.walk(noeud):
        if (isinstance(sous, ast.Attribute) and sous.attr == 'Statut'
                and isinstance(sous.value, ast.Name)
                and sous.value.id == 'Ticket'):
            return True
    return False


def _nom_ticket(noeud, noms=frozenset()):
    """Le nom de base d'une chaîne d'attributs contient « ticket » (ou est un
    nom lié à un ``Ticket`` dans la fonction, ASAV127)."""
    while isinstance(noeud, (ast.Attribute, ast.Call, ast.Subscript)):
        noeud = noeud.func if isinstance(noeud, ast.Call) else noeud.value
    return isinstance(noeud, ast.Name) and (
        'ticket' in noeud.id.lower() or noeud.id in noms)


def _noms_ticket(fonction):
    """ASAV127 — noms liés à un ``Ticket`` par TYPE : paramètre annoté
    ``Ticket``, affectation depuis ``Ticket.objects…``, variable de boucle sur
    un tel queryset (ou sur un nom déjà lié)."""
    noms = set()
    for arg in (fonction.args.args + fonction.args.kwonlyargs):
        if arg.annotation is not None and ast.unparse(
                arg.annotation).strip("'\"") == 'Ticket':
            noms.add(arg.arg)
    for n in ast.walk(fonction):
        if isinstance(n, ast.Assign):
            cibles, valeur = n.targets, n.value
        elif isinstance(n, (ast.For, ast.AsyncFor)):
            cibles, valeur = [n.target], n.iter
        else:
            continue
        if 'Ticket.objects' in ast.unparse(valeur) or _nom_ticket(
                valeur, noms):
            noms.update(c.id for c in cibles if isinstance(c, ast.Name))
    return noms


def _ecritures(arbre):
    """[(fonction, ligne)] des écritures directes de statut d'un ticket."""
    trouvees = []

    def visiter(noeud, fonction, noms=frozenset()):
        for enfant in ast.iter_child_nodes(noeud):
            nom, lies = fonction, noms
            if isinstance(enfant, (ast.FunctionDef, ast.AsyncFunctionDef)):
                nom = enfant.name
                lies = noms | _noms_ticket(enfant)
            if isinstance(enfant, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                cibles = (enfant.targets if isinstance(enfant, ast.Assign)
                          else [enfant.target])
                for cible in cibles:
                    if (isinstance(cible, ast.Attribute)
                            and cible.attr == 'statut'
                            and (_nom_ticket(cible.value, lies)
                                 or (enfant.value is not None
                                     and _est_ticket_statut(enfant.value)))):
                        trouvees.append((nom, enfant.lineno))
            if isinstance(enfant, ast.Call):
                func = enfant.func
                if (isinstance(func, ast.Name) and func.id == 'setattr'
                        and len(enfant.args) >= 2
                        and isinstance(enfant.args[1], ast.Constant)
                        and enfant.args[1].value == 'statut'
                        and _nom_ticket(enfant.args[0], lies)):
                    trouvees.append((nom, enfant.lineno))
                if (isinstance(func, ast.Attribute) and func.attr == 'update'
                        and any(k.arg == 'statut' for k in enfant.keywords)):
                    base = func.value
                    texte = ast.unparse(base)
                    if 'Ticket.objects' in texte or _nom_ticket(base, lies):
                        trouvees.append((nom, enfant.lineno))
            visiter(enfant, nom, lies)

    visiter(arbre, '<module>')
    return trouvees


def scanner(racine):
    """Clés ``fichier::fonction`` (ligne) des écritures interdites."""
    signalees = []
    for chemin in sorted(Path(racine).rglob('*.py')):
        rel = chemin.relative_to(racine)
        if ('migrations' in rel.parts or chemin.name.startswith('tests')
                or chemin.name.startswith('test_')):
            continue
        arbre = ast.parse(chemin.read_text(encoding='utf-8'))
        for fonction, ligne in _ecritures(arbre):
            if (chemin.name, fonction) in POINTS_AUTORISES:
                continue
            signalees.append(f'{rel.as_posix()}::{fonction} (ligne {ligne})')
    return signalees


class GardeStatutTicketTests(SimpleTestCase):

    def test_depot_sans_ecriture_directe(self):
        signalees = scanner(RACINE_SAV)
        self.assertEqual(
            signalees, [],
            MESSAGE + '\n' + '\n'.join(f'  - {s}' for s in signalees))

    def test_fixture_signalee(self):
        with tempfile.TemporaryDirectory() as dossier:
            (Path(dossier) / 'fixture.py').write_text(
                'def cloturer_vite(ticket):\n'
                "    ticket.statut = 'cloture'\n"
                '    ticket.save()\n',
                encoding='utf-8')
            signalees = scanner(dossier)
        self.assertEqual(len(signalees), 1)
        self.assertTrue(signalees[0].startswith('fixture.py::cloturer_vite'))
        self.assertIn('appliquer_transition_ticket', MESSAGE)

    def test_autres_modeles_ignores(self):
        with tempfile.TemporaryDirectory() as dossier:
            (Path(dossier) / 'fixture.py').write_text(
                'def acquitter(alarme, equipement):\n'
                '    alarme.statut = AlarmeOnduleur.Statut.ACQUITTEE\n'
                "    equipement.statut = 'remplace'\n",
                encoding='utf-8')
            self.assertEqual(scanner(dossier), [])

    def test_fixture_typee_signalee(self):
        """ASAV127 — reconnu par le TYPE de la cible, pas seulement le nom."""
        source = chr(10).join([
            'def a(principal: Ticket):',
            "    principal.statut = 'cloture'",
            'def b():',
            '    t = Ticket.objects.get(pk=1)',
            "    t.statut = 'cloture'",
            'def c(c):',
            '    qs = Ticket.objects.filter(company=c)',
            "    qs.update(statut='cloture')",
            'def d(ids):',
            '    for x in Ticket.objects.filter(pk__in=ids):',
            "        x.statut = 'resolu'",
            'def e(ticket):',
            "    ticket.statut = 'cloture'",
            'def f(alarme):',
            '    e = Equipement.objects.first()',
            "    e.statut = 'remplace'",
        ]) + chr(10)
        with tempfile.TemporaryDirectory() as dossier:
            (Path(dossier) / 'fixture.py').write_text(source, encoding='utf-8')
            signalees = scanner(dossier)
        self.assertEqual(
            sorted(s.split(' ')[0] for s in signalees),
            [f'fixture.py::{f}' for f in 'abcde'])
