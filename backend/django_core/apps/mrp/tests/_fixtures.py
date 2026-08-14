"""Fixtures partagées des tests `mrp` (Groupe NTMFG) — pas un fichier de tests."""
import ast
import inspect

from django.contrib.auth import get_user_model

from authentication.models import Company

User = get_user_model()


def make_company(slug, nom):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def source_sans_docstrings(module):
    """Code source de `module`, DOCSTRINGS retirées (les commentaires `#` ne
    sont de toute façon jamais capturés par l'AST, donc `ast.unparse` les
    élimine gratuitement). Sert aux gardes anti-fuite-de-prix des PDF
    internes (NTMFG19/23) qui scannent le TEXTE du module pour détecter un
    `prix_achat`/`cout_horaire` codé en dur : une docstring qui EXPLIQUE
    l'interdiction (« aucun `Produit.prix_achat` ») ne doit jamais se
    déclencher elle-même. N'affaiblit pas la garde — un vrai prix codé en
    dur ailleurs que dans une docstring reste détecté."""
    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if not isinstance(
                node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = node.body
        is_docstring = (
            body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str))
        if is_docstring:
            body.pop(0)
    return ast.unparse(tree)
