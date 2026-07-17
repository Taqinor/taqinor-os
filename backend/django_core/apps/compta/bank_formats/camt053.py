"""Parseur de relevé bancaire au format camt.053 ISO 20022 (NTTRE3).

camt.053 (« Bank to Customer Statement ») est le relevé de compte XML normalisé
ISO 20022. Chaque opération est un élément ``<Ntry>`` portant :

  * ``<Amt Ccy="MAD">`` — montant (toujours positif dans le XML) ;
  * ``<CdtDbtInd>``     — sens ``CRDT`` (crédit) ou ``DBIT`` (débit) ;
  * ``<BookgDt><Dt>``   — date de comptabilisation ;
  * ``<NtryRef>``       — référence de l'écriture ;
  * ``<RmtInf><Ustrd>`` (ou ``<AddtlNtryInf>``) — libellé.

``parser_camt053(file_bytes) -> list[dict]`` renvoie une liste de dicts
``{date_operation, libelle, montant, reference}`` — un par ``<Ntry>`` — avec
``montant`` SIGNÉ (``CRDT`` positif, ``DBIT`` négatif). Le parsing est
insensible au namespace (``camt.053.001.02`` … ``.08``). Lève ``ValueError`` si
le XML est mal formé.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree as ET


def _local(tag):
    """Nom local d'un tag XML (retire le préfixe de namespace ``{...}``)."""
    return tag.rsplit('}', 1)[-1]


def _trouver(element, nom):
    """Premier descendant dont le nom local == ``nom`` (namespace-agnostique)."""
    for enfant in element.iter():
        if _local(enfant.tag) == nom:
            return enfant
    return None


def _texte(element, nom):
    trouve = _trouver(element, nom)
    if trouve is not None and trouve.text:
        return trouve.text.strip()
    return ''


def _date(brut):
    brut = (brut or '').strip()
    if not brut:
        return None
    # BookgDt peut être une Dt (AAAA-MM-JJ) ou un DtTm (ISO complet).
    for fmt in ('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S%z'):
        try:
            return datetime.strptime(brut[:len(fmt) + 6], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.strptime(brut[:10], '%Y-%m-%d').date()
    except ValueError:
        return None


def parser_camt053(file_bytes):
    """Parse un relevé camt.053 → liste de dicts de lignes de relevé (NTTRE3).

    ``file_bytes`` : ``bytes`` (ou ``str``) du XML. Un dict par ``<Ntry>`` ;
    ``montant`` signé selon ``<CdtDbtInd>``.
    """
    if isinstance(file_bytes, str):
        file_bytes = file_bytes.encode('utf-8')
    try:
        racine = ET.fromstring(file_bytes)
    except ET.ParseError as exc:
        raise ValueError("Fichier camt.053 mal formé : %s." % exc)

    resultats = []
    for element in racine.iter():
        if _local(element.tag) != 'Ntry':
            continue
        montant_brut = _texte(element, 'Amt')
        try:
            montant = Decimal(montant_brut or '0')
        except InvalidOperation:
            raise ValueError(
                "Montant camt.053 non numérique : « %s »." % montant_brut)
        sens = _texte(element, 'CdtDbtInd').upper()
        if sens == 'DBIT':
            montant = -montant

        bookg = _trouver(element, 'BookgDt')
        date_op = _date(_texte(bookg, 'Dt') or _texte(bookg, 'DtTm')) if bookg is not None else None

        libelle = _texte(element, 'Ustrd') or _texte(element, 'AddtlNtryInf')
        reference = _texte(element, 'NtryRef') or _texte(element, 'AcctSvcrRef')

        resultats.append({
            'date_operation': date_op,
            'libelle': (libelle or '').strip()[:255],
            'montant': montant,
            'reference': (reference or '').strip()[:80],
        })
    return resultats
