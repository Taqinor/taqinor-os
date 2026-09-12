"""NTMIG14 — transformations de valeurs par kit (normalisation à la volée).

Pipeline DÉCLARATIF appliqué entre le mapping colonne→champ (posé par le kit,
NTMIG8/12/13) et le commit (moteur ``dataimport``, inchangé) : chaque champ
CIBLE peut porter une liste de noms de transformation, appliqués DANS L'ORDRE
sur la valeur BRUTE de la colonne source correspondante.

Le téléphone est le cas d'école de la tâche : ``normaliser_telephone_ma``
réutilise ``apps.crm.services.normalize_phone`` (JAMAIS réimplémenté) — un
export Odoo ``+212 6 12 34 56 78`` et un export Sage ``0612345678`` produisent
donc la MÊME valeur normalisée cible, quel que soit le kit d'origine.
"""
import datetime
import re
from decimal import Decimal, InvalidOperation


def normaliser_telephone_ma(valeur):
    """Téléphone marocain normalisé — réutilise ``crm.services.normalize_phone``
    (jamais réimplémenté : c'est LA même règle que la dédup CRM applique)."""
    if valeur in (None, ''):
        return valeur
    from apps.crm.services import normalize_phone

    normalise = normalize_phone(valeur)
    return normalise or valeur


def parser_montant_virgule(valeur):
    """Montant en texte brut → forme décimale canonique (point, sans espace).

    Tolère la décimale virgule, les espaces de milliers (dont l'insécable des
    exports Excel FR) et les suffixes ``MAD``/``DH``. Une valeur non parsable
    est renvoyée TELLE QUELLE (jamais vidée) : c'est au contrôle de qualité
    (NTMIG32) de la signaler, pas à cette transformation de la faire
    disparaître.
    """
    if valeur in (None, ''):
        return valeur
    brut = re.sub(r'\s', '', str(valeur)).replace(',', '.')
    # Le suffixe se retire APRÈS la suppression des espaces, donc sans
    # frontière de mot devant : dans « 1500MAD » il n'y a AUCUN ``\b`` entre
    # « 0 » et « M » (deux caractères de mot), et l'ancien ``\b(mad|dh)\b``
    # ne retirait donc jamais rien — « 1500 MAD » repartait tel quel.
    brut = re.sub(r'(?i)(mad|dh)$', '', brut)
    try:
        return str(Decimal(brut))
    except (InvalidOperation, ValueError):
        return valeur


#: Formats de date SOURCE reconnus, testés dans cet ordre (ISO d'abord).
_FORMATS_DATE = (
    '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%Y/%m/%d',
)


def parser_date_multi_format(valeur):
    """Date en texte (plusieurs formats source possibles) → ISO ``YYYY-MM-DD``.

    Une valeur déjà de type date/datetime (ligne XLSX déjà typée par
    ``openpyxl``) est acceptée directement. Une valeur non reconnue est
    renvoyée TELLE QUELLE (jamais vidée), même contrat que
    :func:`parser_montant_virgule`.
    """
    if valeur in (None, ''):
        return valeur
    if isinstance(valeur, (datetime.date, datetime.datetime)):
        d = valeur.date() if isinstance(valeur, datetime.datetime) else valeur
        return d.isoformat()
    texte = str(valeur).strip()
    for fmt in _FORMATS_DATE:
        try:
            return datetime.datetime.strptime(texte, fmt).date().isoformat()
        except ValueError:
            continue
    return valeur


def trim_upper(valeur):
    """Espaces superflus retirés, casse normalisée en MAJUSCULES."""
    if valeur in (None, ''):
        return valeur
    return str(valeur).strip().upper()


def mapper_statut(valeur, table):
    """Statut source → statut cible via une table fournie par le kit.

    Recherche insensible à la casse/espaces ; une valeur absente de la table
    est renvoyée TELLE QUELLE (jamais devinée) — c'est à l'app cible
    (``ventes``/``facturation``) de retomber sur son statut par défaut.
    """
    if valeur in (None, ''):
        return valeur
    cle = str(valeur).strip().lower()
    return (table or {}).get(cle, valeur)


#: Transformations SANS paramètre — celles qui en prennent un
#: (``mapper_statut``) sont gérées à part par :func:`appliquer`.
TRANSFORMATIONS = {
    'normaliser_telephone_ma': normaliser_telephone_ma,
    'parser_montant_virgule': parser_montant_virgule,
    'parser_date_multi_format': parser_date_multi_format,
    'trim_upper': trim_upper,
}


def appliquer(spec, valeur):
    """Applique UNE transformation — ``spec`` est un nom (``str``) ou un dict
    ``{'nom': ..., **params}`` pour une transformation paramétrée
    (``mapper_statut`` attend ``table``). Un nom inconnu laisse la valeur
    inchangée plutôt que de faire échouer tout l'import sur une faute de
    frappe dans un kit."""
    if isinstance(spec, str):
        nom, params = spec, {}
    else:
        spec = dict(spec or {})
        nom = spec.pop('nom', '')
        params = spec
    if nom == 'mapper_statut':
        return mapper_statut(valeur, params.get('table'))
    fonction = TRANSFORMATIONS.get(nom)
    if fonction is None:
        return valeur
    return fonction(valeur)


def appliquer_ligne(row, mapping, transformations):
    """Ligne SOURCE (dict colonne→valeur brute) avec les transformations du
    kit appliquées, colonne par colonne, selon le champ CIBLE que le
    ``mapping`` lui attribue.

    Ne modifie jamais les colonnes absentes de ``mapping`` ou dont le champ
    cible ne porte aucune transformation déclarée — c'est un enrichissement
    STRICTEMENT ADDITIF du pipeline existant (mapping → dry-run/commit),
    jamais un second parseur.
    """
    if not transformations:
        return row
    resultat = dict(row)
    for colonne, champ in (mapping or {}).items():
        specs = transformations.get(champ)
        if not specs or colonne not in resultat:
            continue
        valeur = resultat[colonne]
        for spec in specs:
            valeur = appliquer(spec, valeur)
        resultat[colonne] = valeur
    return resultat
