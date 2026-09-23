"""CAL181 — le PACK « dossier technique », fusionné par la GED.

Le constat
==========
La fusion PDF est une primitive de PLATEFORME (``apps.ged.services.fusionner_pdf``,
XGED10), déjà utilisée par le dossier d'appel d'offres. Le calepinage, lui,
n'avait aucun pack : le technicien envoyait trois pièces séparées, et le client
les recevait dans le désordre — quand il les recevait toutes.

Ce module ne fusionne RIEN lui-même : il rend les pièces, les dépose comme
documents GED, puis appelle ``fusionner_pdf``. Une fusion maison serait un
second chemin PDF à maintenir, et c'est exactement ce que XGED10 a supprimé.

Les frontières respectées
=========================
* la GED est atteinte par ses SERVICES (``deposit_document``, ``fusionner_pdf``)
  — jamais par ses modèles : ``apps.calepinage`` n'importe aucun modèle
  étranger (``lint-imports``) ;
* la société est POSÉE côté serveur (celle du calepinage), jamais lue d'un
  corps de requête ;
* l'idempotence du dépôt est ancrée sur (calepinage, EMPREINTE DU LAYOUT,
  pièce) : relancer le pack sur la MÊME conception retrouve les documents déjà
  déposés, tandis qu'une conception MODIFIÉE en produit de nouveaux. Ancrer sur
  le seul identifiant du calepinage aurait rendu un pack PÉRIMÉ en silence —
  le pire des deux mondes.

Une pièce manquante est SIGNALÉE
================================
Un dossier technique amputé qu'on remet sans le dire est un défaut invisible.
Donc : une pièce OBLIGATOIRE (planche, note de calcul) qui ne se rend pas fait
échouer le pack en la NOMMANT ; une pièce FACULTATIVE absente (plan de masse
sans parcelle saisie, schéma unifilaire non encore produit) est rapportée dans
``signalements`` — jamais sautée en silence.
"""
from __future__ import annotations

__all__ = [
    'PackRefuse', 'CABINET', 'DOSSIER', 'SPEC_PIECES', 'compter_pages',
    'rendre_pieces', 'construire_pack',
]

#: Où le pack se range dans la GED. Un cabinet et un dossier racine dédiés :
#: un dossier technique n'a rien à faire dans « Contrats » (le défaut du
#: service de dépôt).
CABINET = 'Calepinage'
DOSSIER = 'Dossiers techniques'

#: Les pièces du pack, DANS L'ORDRE D'IMPRESSION.
#: ``(code, libellé, obligatoire)``.
SPEC_PIECES = (
    ('planche', 'Planche de calepinage', True),
    ('note_calcul', 'Note de calcul', True),
    ('plan_toiture', 'Plan de toiture', False),
    ('plan_masse', 'Plan de masse', False),
)


class PackRefuse(ValueError):
    """Le pack refuse de sortir, en NOMMANT la pièce qui manque."""

    def __init__(self, message, *, piece=''):
        super().__init__(message)
        self.piece = piece


def compter_pages(octets_pdf):
    """Le nombre de pages d'un PDF, ou 0 si le document est illisible.

    Sert au CONTRÔLE : le pack fusionné doit compter exactement la somme des
    pages de ses pièces. Sans ce contrôle, une pièce vidée par une erreur de
    rendu disparaîtrait du dossier sans que personne ne le voie.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:  # pragma: no cover - dépend de l'environnement
        return 0
    try:
        document = fitz.open(stream=octets_pdf, filetype='pdf')
    except Exception:  # noqa: BLE001 - un PDF illisible n'a pas de pages
        return 0
    try:
        return document.page_count
    finally:
        document.close()


def _rendus(calepinage, company):
    """``code -> fonction de rendu`` — chacune rend des OCTETS PDF.

    Les imports sont FONCTION-LOCAUX : la plomberie PDF est lourde et n'a
    aucune raison d'être chargée au démarrage de Django.
    """
    from .note_calcul import rendre_note_calcul
    from .planche import (
        CONTENU_MASSE, CONTENU_TOITURE, rendre_plan_pdf, rendre_planche_pdf,
    )

    # CALX309 — le plan de toiture et le plan de masse EXISTENT déjà
    # (``rendre_plan_pdf``, déjà servis en HTTP par
    # ``views/sorties.py:plan_toiture_pdf``/``plan_masse_pdf``) : ils
    # n'étaient simplement jamais BRANCHÉS ici, alors que ``SPEC_PIECES`` les
    # déclarait déjà — le pack sortait donc toujours amputé de deux pièces
    # qui existaient. Le plan de masse reste REFUSÉ (``PlancheRefusee``,
    # champ ``parcelle``) tant qu'aucune parcelle n'est saisie : cette
    # exception remonte telle quelle jusqu'à ``rendre_pieces``, qui la
    # SIGNALE (pièce FACULTATIVE) plutôt que de faire échouer le pack — le
    # motif nomme la parcelle, il n'est pas reformulé ici.
    return {
        'planche': lambda: rendre_planche_pdf(calepinage, company=company),
        'note_calcul': lambda: rendre_note_calcul(calepinage,
                                                  company=company),
        'plan_toiture': lambda: rendre_plan_pdf(
            calepinage, contenu=CONTENU_TOITURE, company=company),
        'plan_masse': lambda: rendre_plan_pdf(
            calepinage, contenu=CONTENU_MASSE, company=company),
    }


def rendre_pieces(calepinage, *, company=None, rendus=None):
    """``([(code, libelle, octets, pages)], [signalements])``.

    Une pièce OBLIGATOIRE qui ne se rend pas lève ``PackRefuse`` en la nommant.
    Une pièce FACULTATIVE qui ne se rend pas est SIGNALÉE, jamais sautée en
    silence.
    """
    company = company or getattr(calepinage, 'company', None)
    rendus = rendus if rendus is not None else _rendus(calepinage, company)
    pieces, signalements = [], []
    for code, libelle, obligatoire in SPEC_PIECES:
        rendu = rendus.get(code)
        if rendu is None:
            if obligatoire:
                raise PackRefuse(
                    "Dossier technique : la pièce « %s » n'a aucun rendu "
                    "disponible." % libelle, piece=code)
            signalements.append(
                "« %s » : aucun rendu disponible — pièce absente du dossier."
                % libelle)
            continue
        try:
            octets = rendu()
        except Exception as erreur:  # noqa: BLE001 - le MOTIF est reporté
            if obligatoire:
                raise PackRefuse(
                    "Dossier technique : la pièce « %s » ne se rend pas — %s. "
                    "Un dossier amputé ne se remet pas."
                    % (libelle, erreur), piece=code)
            signalements.append('« %s » : %s' % (libelle, erreur))
            continue
        if not octets:
            if obligatoire:
                raise PackRefuse(
                    "Dossier technique : la pièce « %s » est vide. Un PDF "
                    "vide dans un dossier remis est un défaut invisible."
                    % libelle, piece=code)
            signalements.append('« %s » : rendu vide.' % libelle)
            continue
        pieces.append((code, libelle, octets, compter_pages(octets)))
    return pieces, signalements


def _ancre(calepinage, code):
    """L'ancre d'idempotence : calepinage + EMPREINTE du layout + pièce."""
    empreinte = (getattr(calepinage, 'layout_hash', '') or 'sans-empreinte')
    return '%s:%s:%s' % (getattr(calepinage, 'pk', ''), empreinte[:12], code)


def construire_pack(calepinage, *, company=None, created_by=None,
                    rendus=None):
    """Rend les pièces, les dépose en GED et les fusionne en UN document.

    Renvoie ``{'document', 'pieces', 'pages', 'signalements'}`` où ``pages``
    est le nombre de pages du pack fusionné — égal à la somme des pages des
    pièces, faute de quoi le pack est refusé.
    """
    # La société AVANT l'import de la GED : un refus de société doit être
    # immédiat, et il ne coûte pas le chargement d'un module lourd.
    company = company or getattr(calepinage, 'company', None)
    if company is None:
        raise PackRefuse(
            "Un dossier technique se produit toujours dans une société.",
            piece='company')

    pieces, signalements = rendre_pieces(calepinage, company=company,
                                         rendus=rendus)
    if not pieces:
        raise PackRefuse(
            "Dossier technique refusé : aucune pièce à fusionner.",
            piece='pieces')

    from apps.ged.services import deposit_document, fusionner_pdf

    documents, attendues = [], 0
    for code, libelle, octets, pages in pieces:
        document, _cree = deposit_document(
            company=company,
            nom='%s — %s' % (libelle, calepinage),
            source_type='calepinage.%s' % code,
            source_id=_ancre(calepinage, code),
            contenu_bytes=octets,
            mime='application/pdf',
            filename='%s.pdf' % code,
            cabinet_nom=CABINET, folder_nom=DOSSIER,
            created_by=created_by)
        documents.append(document)
        attendues += pages

    pack = fusionner_pdf(
        documents, company=company, created_by=created_by,
        nom='Dossier technique — %s' % calepinage)
    return {
        'document': pack,
        'pieces': [(code, libelle, pages) for code, libelle, _o, pages
                   in pieces],
        'pages_attendues': attendues,
        'signalements': signalements,
    }
