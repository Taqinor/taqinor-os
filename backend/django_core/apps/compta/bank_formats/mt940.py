"""Parseur de relevé bancaire au format MT940 SWIFT (NTTRE2).

Le MT940 est le relevé de compte SWIFT (texte), émis par la plupart des banques
marocaines (BMCE, Attijari…). Il s'articule autour de tags :

  * ``:20:``  référence du relevé ;
  * ``:60F:`` solde d'ouverture (``C``/``D`` + devise + date + montant) ;
  * ``:61:``  LIGNE de mouvement (date valeur, sens débit/crédit, montant, code) ;
  * ``:86:``  libellé détaillé du mouvement ``:61:`` qui précède ;
  * ``:62F:`` solde de clôture.

``parser_mt940(file_bytes) -> list[dict]`` renvoie une liste de dicts
``{date_operation, libelle, montant, reference}`` — un par tag ``:61:`` — avec
``montant`` SIGNÉ (crédit ``C`` = positif, débit ``D`` = négatif). Par
construction, la somme des montants signés égale ``solde_clôture − solde_ouverture``
(tags ``:62F:``/``:60F:``).
"""

import re
from datetime import datetime
from decimal import Decimal

# :61: value-date(YYMMDD) [entry-date MMDD] mark(R?[CD]) [funds 1 alpha]
#      amount(digits & comma) [type Nxxx] reference...
_RE_61 = re.compile(
    r'^(?P<vdate>\d{6})'
    r'(?P<edate>\d{4})?'
    r'(?P<mark>R?[DC])'
    r'(?P<funds>[A-Z])?'
    r'(?P<amount>[\d,]+)'
    r'(?P<rest>.*)$'
)


def _montant(brut):
    """Convertit un montant MT940 (virgule décimale) en Decimal (positif)."""
    return Decimal((brut or '0').replace(',', '.'))


def _date_valeur(yymmdd):
    try:
        return datetime.strptime(yymmdd, '%y%m%d').date()
    except (ValueError, TypeError):
        return None


def _reference(rest):
    """Extrait la référence client d'un ``:61:`` (avant « // » banque)."""
    rest = (rest or '').strip()
    if not rest:
        return ''
    # Code type opération : 4 car type « Nxxx/Fxxx/Sxxx » en tête, à retirer.
    rest = re.sub(r'^[NFS][A-Z0-9]{3}', '', rest)
    ref = rest.split('//', 1)[0]
    return ref.strip()[:80]


def _iter_tags(texte):
    """Itère (tag, valeur) en recollant les lignes de continuation (sans ``:``)."""
    tag, buffer = None, []
    for ligne in texte.splitlines():
        ligne = ligne.rstrip('\r\n')
        if ligne.strip() in ('', '-'):
            continue
        m = re.match(r'^:(\w+):(.*)$', ligne)
        if m:
            if tag is not None:
                yield tag, '\n'.join(buffer)
            tag, buffer = m.group(1), [m.group(2)]
        elif tag is not None:
            buffer.append(ligne)
    if tag is not None:
        yield tag, '\n'.join(buffer)


def parser_mt940(file_bytes):
    """Parse un relevé MT940 → liste de dicts de lignes de relevé (NTTRE2).

    ``file_bytes`` : ``bytes`` (ou ``str``). Un dict par tag ``:61:`` ; le
    ``:86:`` qui suit alimente le libellé. ``montant`` signé (crédit +, débit −).
    """
    if isinstance(file_bytes, bytes):
        texte = file_bytes.decode('latin-1')
    else:
        texte = file_bytes or ''

    resultats = []
    for tag, valeur in _iter_tags(texte):
        if tag == '61':
            m = _RE_61.match(valeur.split('\n', 1)[0].strip())
            if not m:
                raise ValueError(
                    "Ligne :61: MT940 illisible : « %s »." % valeur[:40])
            signe = Decimal('-1') if m.group('mark').endswith('D') else Decimal('1')
            resultats.append({
                'date_operation': _date_valeur(m.group('vdate')),
                'libelle': '',
                'montant': signe * _montant(m.group('amount')),
                'reference': _reference(m.group('rest')),
            })
        elif tag == '86' and resultats:
            libelle = ' '.join(part.strip() for part in valeur.splitlines())
            resultats[-1]['libelle'] = libelle.strip()[:255]
    return resultats
