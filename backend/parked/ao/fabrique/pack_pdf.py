"""AOF152 — PDF unique « bon à tirer » : fusion ORDONNÉE pour l'impression.

Ce module ne fusionne pas
=========================
La fusion PDF existe déjà et n'a pas à être re-codée : ``apps.ged.services.
fusionner_pdf`` (XGED10) est le SEUL point d'assemblage du dépôt. Un second
usage de PyMuPDF ici créerait deux comportements de fusion qui divergeraient
au premier correctif.

Ce module apporte ce que la fusion ne sait pas : **l'ORDRE**. Il projette le
manifeste du pack en une séquence d'impression — pièces client seulement,
intercalaires entre sections, planches A3 intercalées dans un corps A4 — et
délègue l'assemblage. L'ordre du PDF « bon à tirer » est ainsi le même objet
que l'ordre du sommaire (AOF139) : ils ne peuvent pas diverger, puisqu'ils
sortent du même manifeste.

Mémoire bornée
--------------
La séquence est un GÉNÉRATEUR et ne lit jamais les octets d'une pièce : elle
ne manipule que des références de documents. Les octets ne sont touchés que
par la fusion incrémentale de GED. Matérialiser la liste des contenus pour
« simplifier » ferait tenir tout le pack en mémoire dans un worker Celery.
"""
from __future__ import annotations

__all__ = [
    'VISIBILITE_CLIENT',
    'FORMAT_CORPS',
    'FORMAT_PLANCHE',
    'MOTS_INTERDITS',
    'PackPdfRefuse',
    'sequence_impression',
    'plan_pagination',
    'intercalaire_html',
    'fusionner_pack',
]

VISIBILITE_CLIENT = 'client'
FORMAT_CORPS = 'A4'
FORMAT_PLANCHE = 'A3'

MOTS_INTERDITS = (
    "prix d'achat", 'coût de revient', 'cout de revient', 'marge',
    'bénéfice', 'benefice', 'rentabilité', 'rentabilite', 'maximum posable',
)


class PackPdfRefuse(Exception):
    """Levée quand le bon à tirer ne peut pas être assemblé."""


def _ordonnees(manifeste):
    return sorted(
        [piece for piece in (manifeste or [])
         if str(piece.get('visibilite') or VISIBILITE_CLIENT)
         == VISIBILITE_CLIENT],
        key=lambda p: (p.get('ordre') if p.get('ordre') is not None else 0,
                       str(p.get('code') or '')),
    )


def _verifier_etancheite(pieces):
    fautes = []
    for piece in pieces:
        texte = '{} {}'.format(piece.get('code') or '',
                               piece.get('libelle') or '').lower()
        for mot in MOTS_INTERDITS:
            if mot in texte:
                fautes.append('{} → « {} »'.format(piece.get('code'), mot))
    if fautes:
        raise PackPdfRefuse(
            "Bon à tirer : intitulés réservés au directeur — {}.".format(
                ' ; '.join(fautes)))


def sequence_impression(manifeste, *, avec_intercalaires=True):
    """GÉNÈRE la séquence d'impression : intercalaires + pièces, dans l'ordre.

    Chaque élément est ``{'type': 'intercalaire'|'piece', …}``. Générateur
    volontaire : rien n'est matérialisé, et surtout aucun octet de pièce n'est
    lu ici.
    """
    pieces = _ordonnees(manifeste)
    _verifier_etancheite(pieces)
    if not pieces:
        raise PackPdfRefuse(
            "Bon à tirer refusé : aucune pièce client dans le manifeste.")
    section_courante = object()
    for numero, piece in enumerate(pieces, start=1):
        section = piece.get('section') or piece.get('code')
        if avec_intercalaires and section != section_courante:
            section_courante = section
            yield {
                'type': 'intercalaire',
                'section': section,
                'libelle': piece.get('libelle') or '',
                'numero': numero,
                'format': FORMAT_CORPS,
            }
        yield {
            'type': 'piece',
            'numero': numero,
            'code': piece.get('code'),
            'libelle': piece.get('libelle') or '',
            'document': piece.get('document'),
            'format': (FORMAT_PLANCHE if str(piece.get('format_page') or '')
                       .upper() == FORMAT_PLANCHE else FORMAT_CORPS),
            'pages': piece.get('pages'),
        }


def plan_pagination(manifeste, *, avec_intercalaires=True):
    """Plages de pages attendues, pour que le sommaire et le PDF concordent.

    Renvoie ``[{'code', 'libelle', 'premiere_page', 'derniere_page',
    'format'}]``. Une pièce sans nombre de pages connu interrompt le plan :
    annoncer une pagination fausse est pire que ne pas en annoncer.
    """
    plan = []
    page = 1
    for element in sequence_impression(
            manifeste, avec_intercalaires=avec_intercalaires):
        if element['type'] == 'intercalaire':
            page += 1
            continue
        pages = element.get('pages')
        if pages is None:
            raise PackPdfRefuse(
                "Pièce « {} » sans nombre de pages : la pagination annoncée "
                "au sommaire serait fausse.".format(element.get('code')))
        plan.append({
            'code': element['code'],
            'libelle': element['libelle'],
            'premiere_page': page,
            'derniere_page': page + int(pages) - 1,
            'format': element['format'],
        })
        page += int(pages)
    return plan


def intercalaire_html(element):
    """HTML d'un intercalaire — une page de séparation, rien de plus."""
    from html import escape

    return (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<title>{titre}</title><style>'
        '@page{{size:A4;margin:0;}}'
        'body{{font-family:"DejaVu Sans",Arial,sans-serif;}}'
        '.i{{display:flex;height:100vh;align-items:center;'
        'justify-content:center;text-align:center;}}'
        '.t{{font-size:26pt;font-weight:bold;letter-spacing:1mm;}}'
        '</style></head><body><div class="i"><div class="t">{titre}</div>'
        '</div></body></html>'
    ).format(titre=escape(str(element.get('libelle') or '')))


def fusionner_pack(sequence, *, company, nom, created_by=None, cible=None):
    """Délègue l'assemblage à ``apps.ged.services.fusionner_pdf`` (XGED10).

    ``sequence`` est la sortie de ``sequence_impression`` ; on n'en extrait
    que les DOCUMENTS, dans l'ordre. Aucun octet ne transite par ce module.
    """
    from apps.ged.services import fusionner_pdf

    documents = []
    for element in sequence:
        document = element.get('document')
        if document is None:
            # Vaut aussi pour les INTERCALAIRES : un intercalaire sans document
            # disparaîtrait silencieusement du bon à tirer et la pagination
            # annoncée au sommaire deviendrait fausse. L'appelant les rend
            # (``intercalaire_html`` + ``core.pdf``) avant d'appeler ici.
            raise PackPdfRefuse(
                "Élément « {} » ({}) sans document GED : il ne peut pas "
                "entrer dans le bon à tirer.".format(
                    element.get('libelle') or element.get('code'),
                    element.get('type')))
        documents.append(document)
    if not documents:
        raise PackPdfRefuse("Bon à tirer refusé : aucun document à fusionner.")
    return fusionner_pdf(documents, cible=cible, company=company, nom=nom,
                         created_by=created_by)
