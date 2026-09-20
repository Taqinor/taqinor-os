"""CAL181 — le PACK « dossier technique » du calepinage.

Le constat
==========
Le calepinage n'avait aucun pack : le technicien envoyait trois pièces
séparées, et le client les recevait dans le désordre — quand il les recevait
toutes.

Ce module ne fusionne RIEN lui-même : il rend les pièces et appelle le SEUL
foyer de dépôt/fusion PDF du module (``services/depot_pdf.py``). Une fusion
écrite ici serait un second chemin PDF à maintenir.

SOLMVP15 — le dépôt et la fusion passaient par la GED (XGED10). La GED sort du
produit (elle revient en PHASE 2) ; le pack, lui, est une capacité de
l'atelier et reste. Les pièces se rangent désormais dans ``records`` (le
référentiel de pièces jointes que le module utilise déjà pour les photos de
site et pour les fichiers de gabarit) et la fusion se fait sur les octets,
avec la même bibliothèque PDF. Mêmes pièces, même ordre, même compte de
pages, mêmes refus.

Les frontières respectées
=========================
* le dépôt et la fusion passent par ``services/depot_pdf.py``, qui parle à
  ``records`` par son service de stockage — ``apps.calepinage`` n'importe
  aucune vue étrangère (``lint-imports``) ;
* la société est POSÉE côté serveur (celle du calepinage), jamais lue d'un
  corps de requête ;
* l'idempotence du dépôt est ancrée sur (calepinage, EMPREINTE DU LAYOUT,
  pièce) : relancer le pack sur la MÊME conception retrouve les pièces déjà
  déposées, tandis qu'une conception MODIFIÉE en produit de nouvelles. Ancrer
  sur le seul identifiant du calepinage aurait rendu un pack PÉRIMÉ en
  silence — le pire des deux mondes.

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

#: Comment le pack se NOMME. Ces deux libellés désignaient son emplacement dans
#: le référentiel documentaire (un cabinet et un dossier racine dédiés : un
#: dossier technique n'a rien à faire dans « Contrats »). Ce référentiel sort du
#: produit (SOLMVP15) ; les libellés restent PUBLIÉS pour que l'écran nomme le
#: pack comme avant, et pour que la recette de retour du module sache où les
#: pièces devront se ranger à nouveau.
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
    from .planche import rendre_planche_pdf

    # Les deux pièces FACULTATIVES (plan de toiture, plan de masse) ne sont
    # pas encore produites par le dépôt : elles restent DÉCLARÉES dans
    # ``SPEC_PIECES`` et sortent donc en SIGNALEMENT (« aucun rendu
    # disponible »), jamais sautées en silence. Le jour où leur rendu existe,
    # il s'ajoute ICI et le pack les emporte sans rien changer d'autre.
    return {
        'planche': lambda: rendre_planche_pdf(calepinage, company=company),
        'note_calcul': lambda: rendre_note_calcul(calepinage,
                                                  company=company),
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
    """L'ancre d'idempotence : calepinage + EMPREINTE du layout + pièce.

    Elle voyage dans le NOM DE FICHIER de la pièce déposée (SOLMVP15), donc
    elle ne porte que des caractères sûrs pour un nom de fichier — un ``:``
    rendrait le téléchargement impossible sous Windows.
    """
    empreinte = (getattr(calepinage, 'layout_hash', '') or 'sans-empreinte')
    return '%s-%s-%s' % (getattr(calepinage, 'pk', ''), empreinte[:12], code)


def construire_pack(calepinage, *, company=None, created_by=None,
                    rendus=None):
    """Rend les pièces, les dépose et les fusionne en UN document.

    Renvoie ``{'document', 'nom', 'pieces', 'pages_attendues',
    'signalements'}`` où le total de pages attendu est la somme des pages des
    pièces, faute de quoi le pack est refusé.
    """
    # La société AVANT tout dépôt : un refus de société doit être immédiat, et
    # il ne coûte pas le chargement d'un module lourd.
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

    from .depot_pdf import DepotRefuse, deposer_pdf, fusionner_pdf

    attendues = 0
    try:
        for code, libelle, octets, pages in pieces:
            deposer_pdf(
                calepinage, octets, company=company,
                filename='%s.pdf' % _ancre(calepinage, code),
                user=created_by)
            attendues += pages

        nom_pack = 'Dossier technique — %s' % calepinage
        fusionne = fusionner_pdf(
            [(libelle, octets) for _c, libelle, octets, _p in pieces])
        pack, _cree = deposer_pdf(
            calepinage, fusionne, company=company,
            filename='%s.pdf' % _ancre(calepinage, 'pack'),
            user=created_by)
    except DepotRefuse as refus:
        # Le motif du dépôt/de la fusion est rendu TEL QUEL — jamais un 500 et
        # jamais un texte réécrit par-dessus celui qui nomme la cause.
        raise PackRefuse(str(refus), piece='pieces') from refus

    return {
        'document': pack,
        'nom': nom_pack,
        'pieces': [(code, libelle, pages) for code, libelle, _o, pages
                   in pieces],
        'pages_attendues': attendues,
        'signalements': signalements,
    }
