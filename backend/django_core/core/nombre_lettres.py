"""Conversion d'un montant en lettres (français / MAD) — fondation `core` (AOF108).

Radical de fondation `core.nombre_lettres` : la conversion « chiffres → lettres »
longtemps logée dans `apps/ventes/utils/nombre_lettres.py` (XFAC9, pour la
quittance de paiement) est relogée ICI, dans la couche fondation — exactement le
patron `apps/ventes/utils/references.py` → `core.numbering` (ARC6).

Motif : `apps.ao` (fabrique documentaire des appels d'offres) a besoin du montant
en lettres pour l'arrêté du bordereau des prix et pour les prix unitaires ligne à
ligne, et le contrat import-linter `ao-models-decoupled` lui interdit d'importer
un module d'app domaine. Une fonction purement arithmétique consommée par trois
domaines (ventes, compta, ao) est une primitive de fondation, pas un utilitaire
de `ventes`.

`core` reste une couche de base : ce module n'importe QUE la stdlib — aucun
modèle, aucun réglage Django, aucune app métier. `apps.ventes.utils.nombre_lettres`
n'est plus qu'un shim de ré-export BIT-IDENTIQUE (mêmes objets, pas des copies),
pour que les appelants existants (quittance `ventes`, reçu de note de frais
`compta`) continuent de marcher sans aucune édition.

Implémentation MAISON en Python pur (aucune nouvelle dépendance) : couvre les
montants usuels d'une facture (jusqu'aux milliards), avec les règles françaises
« vingt/cent » qui prennent un 's' sauf suivis d'un autre nombre, et « un »
invariable devant « mille ». MAD (dirhams/centimes).

DEUX MODES (AOF109)
-------------------
* ``mode='defaut'`` — le rendu HISTORIQUE, figé : tout est relié par des traits
  d'union (« Mille-deux-cent-cinquante dirhams »). Les appelants existants
  (quittance `ventes`, reçu de note de frais `compta`) ne bougent pas d'un
  caractère : c'est le mode par défaut et il est verrouillé par des tests de
  non-régression.
* ``mode='administratif'`` — le rendu d'ARRÊTÉ, exigé par l'appel d'offres :
  « QUATRE MILLIONS NEUF CENT QUATRE-VINGT-DIX-NEUF MILLE NEUF CENT VINGT
  DIRHAMS ». Un arrêté mal orthographié est un motif de rejet d'offre, donc ce
  mode applique les vraies règles typographiques françaises (voir
  `montant_en_lettres_administratif`), là où le mode par défaut se contente
  d'une concaténation mécanique.
"""
from decimal import Decimal, ROUND_HALF_UP

_UNITES = [
    '', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf',
    'dix', 'onze', 'douze', 'treize', 'quatorze', 'quinze', 'seize',
    'dix-sept', 'dix-huit', 'dix-neuf',
]
_DIZAINES = [
    '', '', 'vingt', 'trente', 'quarante', 'cinquante', 'soixante',
    'soixante', 'quatre-vingt', 'quatre-vingt',
]


def _moins_de_cent(n):
    if n < 20:
        return _UNITES[n]
    dizaine, reste = divmod(n, 10)
    if dizaine in (7, 9):
        # soixante-dix / quatre-vingt-dix : dizaine réelle -1, reste +10.
        dizaine -= 1
        reste += 10
    mot = _DIZAINES[dizaine]
    if reste == 0:
        # "quatre-vingts" prend un s, "vingt"/"trente"... seuls ne le prennent
        # pas ; "quatre-vingt" en est la seule exception avec un s au pluriel.
        if dizaine == 8:
            return mot + 's'
        return mot
    liaison = '-et-' if reste == 1 and dizaine not in (8,) else '-'
    return f'{mot}{liaison}{_UNITES[reste]}'


def _moins_de_mille(n):
    centaine, reste = divmod(n, 100)
    parts = []
    if centaine > 0:
        if centaine == 1:
            parts.append('cent')
        else:
            suffixe_cent = 's' if reste == 0 else ''
            parts.append(f'{_UNITES[centaine]}-cent{suffixe_cent}')
    if reste > 0:
        parts.append(_moins_de_cent(reste))
    return '-'.join(parts) if parts else 'zéro'


_TRANCHES = [
    (1_000_000_000, 'milliard'),
    (1_000_000, 'million'),
    (1_000, 'mille'),
]


def _entier_en_lettres(n):
    if n == 0:
        return 'zéro'
    parts = []
    reste = n
    for valeur, mot in _TRANCHES:
        if reste >= valeur:
            quotient, reste = divmod(reste, valeur)
            if valeur == 1_000:
                # "mille" est invariable et "un mille" ne s'écrit pas "un".
                prefix = '' if quotient == 1 else f'{_moins_de_mille(quotient)}-'
                parts.append(f'{prefix}{mot}')
            else:
                prefix = _moins_de_mille(quotient)
                suffixe = 's' if quotient > 1 else ''
                parts.append(f'{prefix}-{mot}{suffixe}')
    if reste > 0:
        parts.append(_moins_de_mille(reste))
    return '-'.join(parts)


MODE_DEFAUT = 'defaut'
MODE_ADMINISTRATIF = 'administratif'
MODES = (MODE_DEFAUT, MODE_ADMINISTRATIF)


def montant_en_lettres(montant, devise='dirhams', sous_unite='centimes',
                       mode=MODE_DEFAUT):
    """Montant Decimal/float/str → chaîne française pleine lettre + devise.

    Ex. ``Decimal('1250.50')`` → « mille-deux-cent-cinquante dirhams et
    cinquante centimes ». Toujours positif (une facture/quittance ne porte
    jamais de montant négatif en lettres) ; arrondi au centime le plus proche.

    ``mode='administratif'`` bascule sur le rendu d'arrêté
    (`montant_en_lettres_administratif`). La valeur par défaut du paramètre
    ``sous_unite`` ('centimes') vaut « laisse la devise décider » dans ce
    mode-là, où le singulier/pluriel est accordé (« et un centime »).
    """
    if mode == MODE_ADMINISTRATIF:
        return montant_en_lettres_administratif(
            montant, devise=devise,
            sous_unite=None if sous_unite == 'centimes' else sous_unite)
    if mode != MODE_DEFAUT:
        raise ValueError(
            f'mode inconnu : {mode!r} (attendus : {", ".join(MODES)})')

    montant = Decimal(str(montant)).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    montant = abs(montant)
    entier = int(montant)
    centimes = int((montant - entier) * 100)

    texte = f'{_entier_en_lettres(entier)} {devise}'
    if centimes:
        texte += f' et {_entier_en_lettres(centimes)} {sous_unite}'
    return texte[0].upper() + texte[1:]


# ---------------------------------------------------------------------------
# Mode « administratif » (AOF109) — l'orthographe de l'arrêté
# ---------------------------------------------------------------------------
#
# RÈGLES APPLIQUÉES (chacune est un motif de rejet quand elle est fautive) :
#
# 1. ESPACES entre les classes, traits d'union UNIQUEMENT à l'intérieur des
#    composés inférieurs à cent : « neuf cent quatre-vingt-dix-neuf mille »,
#    jamais « neuf-cent-quatre-vingt-dix-neuf-mille ».
# 2. LIAISON « et » sans traits d'union pour 21/31/41/51/61 et 71 :
#    « vingt et un », « soixante et onze » — pas pour 81/91
#    (« quatre-vingt-un », « quatre-vingt-onze »). Le mode par défaut rend
#    « soixante-onze » : c'est le défaut historique que ce mode corrige.
# 3. ACCORDS « vingt » et « cent » : le 's' du pluriel tombe dès qu'un ADJECTIF
#    numéral suit (« quatre-vingt mille », « six cent mille ») mais se pose
#    devant un NOM (« quatre-vingts millions », « six cents dirhams ») et en fin
#    de nombre (« six cents »).
# 4. LIAISON « de » quand le nombre s'arrête sur un million/milliard, qui sont
#    des noms : « un million DE dirhams » (et non « un million dirhams »),
#    tandis que « mille » — adjectif — ne la prend jamais (« mille dirhams »).
#    Désactivable par ``liaison_de=False`` si le fondateur préfère l'autre usage.
# 5. ACCORD DE LA DEVISE : « zéro dirham », « un dirham », « deux dirhams »,
#    « et un centime ». Zéro centime ne s'écrit pas : la mention est OMISE.
# 6. MAJUSCULES accentuées (« ZÉRO ») — l'usage administratif français conserve
#    l'accent sur la capitale.

_DIZAINES_LIAISON_ET = (2, 3, 4, 5, 6)

# devise → (singulier, pluriel, sous-unité singulier, sous-unité pluriel).
_DEVISES_ADMINISTRATIF = {
    'dirham': ('dirham', 'dirhams', 'centime', 'centimes'),
    'dirhams': ('dirham', 'dirhams', 'centime', 'centimes'),
    'mad': ('MAD', 'MAD', 'centime', 'centimes'),
    'dh': ('DH', 'DH', 'centime', 'centimes'),
    'euro': ('euro', 'euros', 'cent', 'cents'),
    'euros': ('euro', 'euros', 'cent', 'cents'),
}


def _admin_moins_de_cent(n, termine=True):
    """0-99 en style administratif. ``termine`` : rien de numéral ne suit."""
    if n < 20:
        return _UNITES[n]
    dizaine, reste = divmod(n, 10)
    if dizaine in (7, 9):
        # soixante-dix / quatre-vingt-dix : dizaine réelle -1, reste +10.
        dizaine -= 1
        reste += 10
    mot = _DIZAINES[dizaine]
    if reste == 0:
        # « quatre-vingts » ne prend son 's' que si aucun adjectif numéral ne
        # le suit : « quatre-vingts dirhams » mais « quatre-vingt mille ».
        return mot + 's' if (dizaine == 8 and termine) else mot
    if reste in (1, 11) and dizaine in _DIZAINES_LIAISON_ET:
        # vingt et un … soixante et un, soixante et onze — « et » sans traits
        # d'union ; quatre-vingt-un / quatre-vingt-onze n'en prennent pas.
        return f'{mot} et {_UNITES[reste]}'
    return f'{mot}-{_UNITES[reste]}'


def _admin_moins_de_mille(n, termine=True):
    """0-999 en style administratif (espaces entre centaines et reste)."""
    centaine, reste = divmod(n, 100)
    parts = []
    if centaine == 1:
        parts.append('cent')
    elif centaine > 1:
        # « deux cents » seul ou devant un nom, « deux cent mille » devant un
        # adjectif numéral, « deux cent un » dès qu'un reste suit.
        suffixe = 's' if (reste == 0 and termine) else ''
        parts.append(f'{_UNITES[centaine]} cent{suffixe}')
    if reste > 0:
        parts.append(_admin_moins_de_cent(reste, termine=termine))
    return ' '.join(parts) if parts else 'zéro'


def _entier_administratif(n):
    """Entier positif → lettres, minuscules, style administratif."""
    if n == 0:
        return 'zéro'
    parts = []
    reste = n
    for valeur, mot in _TRANCHES:
        if reste >= valeur:
            quotient, reste = divmod(reste, valeur)
            if valeur == 1_000:
                # « mille » est un ADJECTIF : invariable, jamais précédé de
                # « un », et il ne déclenche pas le pluriel de vingt/cent.
                if quotient == 1:
                    parts.append(mot)
                else:
                    prefixe = _admin_moins_de_mille(quotient, termine=False)
                    parts.append(f'{prefixe} {mot}')
            else:
                # « million »/« milliard » sont des NOMS : ils s'accordent et
                # déclenchent le pluriel de vingt/cent qui les précède.
                prefixe = _admin_moins_de_mille(quotient, termine=True)
                suffixe = 's' if quotient > 1 else ''
                parts.append(f'{prefixe} {mot}{suffixe}')
    if reste > 0:
        parts.append(_admin_moins_de_mille(reste, termine=True))
    return ' '.join(parts)


def montant_en_lettres_administratif(montant, devise='dirhams',
                                     sous_unite=None, majuscules=True,
                                     liaison_de=True):
    """Montant → arrêté en lettres, orthographe administrative française.

    Ex. ``4999920`` → « QUATRE MILLIONS NEUF CENT QUATRE-VINGT-DIX-NEUF MILLE
    NEUF CENT VINGT DIRHAMS » — la forme attendue sur le bordereau des prix
    d'un appel d'offres.

    :param devise: clé de `_DEVISES_ADMINISTRATIF` ('dirhams', 'MAD', 'DH',
        'euros'…) ou n'importe quelle chaîne, alors utilisée telle quelle et
        traitée comme invariable.
    :param sous_unite: force le mot de la sous-unité (invariable) ; ``None``
        laisse la devise décider et accorde le singulier/pluriel.
    :param majuscules: rendu tout en capitales (accents conservés).
    :param liaison_de: « un million DE dirhams » sur un montant qui s'arrête
        pile sur un million/milliard.
    """
    montant = abs(Decimal(str(montant)).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP))
    entier = int(montant)
    centimes = int((montant - entier) * 100)

    cle = str(devise).strip().lower()
    if cle in _DEVISES_ADMINISTRATIF:
        d_sing, d_plur, s_sing, s_plur = _DEVISES_ADMINISTRATIF[cle]
    else:
        d_sing = d_plur = str(devise)
        s_sing, s_plur = 'centime', 'centimes'
    if sous_unite is not None:
        s_sing = s_plur = str(sous_unite)

    mot_devise = d_sing if entier < 2 else d_plur
    # « million »/« milliard » sont des noms : le nombre qui s'arrête sur eux
    # appelle la préposition (« deux millions de dirhams »).
    liaison = ''
    if liaison_de and entier and entier % 1_000_000 == 0:
        liaison = 'de '

    texte = f'{_entier_administratif(entier)} {liaison}{mot_devise}'
    if centimes:
        # Zéro centime ne s'écrit jamais dans un arrêté : la mention est omise.
        mot_sous = s_sing if centimes < 2 else s_plur
        texte += f' et {_entier_administratif(centimes)} {mot_sous}'
    if majuscules:
        return texte.upper()
    return texte[0].upper() + texte[1:]
