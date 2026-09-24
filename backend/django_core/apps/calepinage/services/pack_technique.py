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
    # CALX319 — le dossier de fin de chantier.
    'DOSSIER_FIN_CHANTIER', 'DOSSIER_CHANTIER_GED',
    'MENTION_RECETTE_GARANTIES', 'construire_dossier_fin_chantier',
]

#: Où le pack se range dans la GED. Un cabinet et un dossier racine dédiés :
#: un dossier technique n'a rien à faire dans « Contrats » (le défaut du
#: service de dépôt).
CABINET = 'Calepinage'
DOSSIER = 'Dossiers techniques'

#: Les pièces du pack, DANS L'ORDRE D'IMPRESSION.
#: ``(code, libellé, obligatoire)``.
#: CALX326 — ``rapport_etude``/``plan_cablage``/``rapport_ombrage`` REJOIGNENT
#: le dossier technique : trois pièces FACULTATIVES (un calepinage non simulé,
#: ou sans chaîne/ombrage publiés, continue de produire le dossier d'avant la
#: tâche, ces trois-là sortant en signalement). L'ORDRE déclaré ICI est celui
#: d'impression — jamais réordonné par l'appelant.
SPEC_PIECES = (
    ('planche', 'Planche de calepinage', True),
    ('note_calcul', 'Note de calcul', True),
    ('plan_toiture', 'Plan de toiture', False),
    ('plan_masse', 'Plan de masse', False),
    ('rapport_etude', "Rapport d'étude", False),
    ('plan_cablage', 'Plan de câblage', False),
    ('rapport_ombrage', "Rapport d'ombrage", False),
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
    # CALX326 — le rapport d'étude, le plan de câblage et le rapport
    # d'ombrage REJOIGNENT le dossier technique. Chacun REND — jamais ne
    # recalcule — via SA propre mise en page (CALX297/CALX310/CALX317) ; un
    # calepinage non simulé, sans chaîne publiée ou sans matrice d'ombrage
    # lève son refus MOT POUR MOT (``RapportRefuse``/``PlanCablageRefuse``/
    # ``RapportOmbrageRefuse``), avalé par ``rendre_pieces`` en signalement
    # puisque les trois sont FACULTATIVES ci-dessus.
    from .documents.plan_cablage import rendre_plan_cablage_pdf
    from .rapport import rendre_rapport
    from .rapport_ombrage import rendre_rapport_ombrage

    return {
        'planche': lambda: rendre_planche_pdf(calepinage, company=company),
        'note_calcul': lambda: rendre_note_calcul(calepinage,
                                                  company=company),
        'plan_toiture': lambda: rendre_plan_pdf(
            calepinage, contenu=CONTENU_TOITURE, company=company),
        'plan_masse': lambda: rendre_plan_pdf(
            calepinage, contenu=CONTENU_MASSE, company=company),
        'rapport_etude': lambda: rendre_rapport(calepinage, company=company),
        'plan_cablage': lambda: rendre_plan_cablage_pdf(
            calepinage, company=company),
        'rapport_ombrage': lambda: rendre_rapport_ombrage(
            calepinage, company=company),
    }


def rendre_pieces(calepinage, *, company=None, rendus=None, spec=SPEC_PIECES):
    """``([(code, libelle, octets, pages)], [signalements])``.

    Une pièce OBLIGATOIRE qui ne se rend pas lève ``PackRefuse`` en la nommant.
    Une pièce FACULTATIVE qui ne se rend pas est SIGNALÉE, jamais sautée en
    silence.

    ``spec``/``rendus`` par défaut couvrent le dossier technique
    (``SPEC_PIECES``/``_rendus``) — CALX319 réutilise cette MÊME mécanique
    pour le dossier de fin de chantier en passant les siens
    (``DOSSIER_FIN_CHANTIER``/``_rendus_dossier_fin_chantier``).
    """
    company = company or getattr(calepinage, 'company', None)
    if rendus is None:
        rendus = _rendus(calepinage, company) if spec is SPEC_PIECES else {}
    pieces, signalements = [], []
    for code, libelle, obligatoire in spec:
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


# ── CALX319 — le dossier de fin de chantier ─────────────────────────────────
#
# Le pack de remise au CHANTIER existe déjà (``apps.installations.services
# .assemble_handover_pieces`` : as-built/schéma, fiches, garanties, recette
# IEC 62446-1, dossier 82-21, monitoring), et l'as-built de VENTES ne stocke
# que des RÉFÉRENCES (``apps.ventes.models_commissioning.AsBuiltPack.pieces``,
# JSON) : rien ne fusionne les pièces PRODUITES PAR LE CALEPINAGE en un seul
# document. Ce dossier-ci ne fabrique NI recette NI garantie — elles restent
# au chantier — il les NOMME plutôt que de les taire (``MENTION_RECETTE_
# GARANTIES``, toujours présente dans ``signalements``).
#
# LA MÊME mécanique que ``construire_pack`` ci-dessus : ``rendre_pieces``
# (contrôle de pages compris) et la fusion GED (``deposit_document`` +
# ``fusionner_pdf``, XGED10) — AUCUN second chemin de fusion, seulement un
# DOSSIER GED distinct (``DOSSIER_CHANTIER_GED``) et une ancre d'idempotence
# préfixée pour ne jamais collisionner avec le dossier technique.

#: Le dossier de fin de chantier ne partage PAS le dossier GED du dossier
#: technique : deux livrables distincts, deux rangements distincts.
DOSSIER_CHANTIER_GED = 'Dossiers de fin de chantier'

#: Les pièces du dossier de fin de chantier, DANS L'ORDRE D'IMPRESSION —
#: TOUTES facultatives : la recette et les garanties (produites par le
#: chantier, jamais ici) ne conditionnent aucune d'entre elles.
DOSSIER_FIN_CHANTIER = (
    ('plan_pose', 'Plan de pose', False),
    ('document_asbuilt', 'Document as-built', False),
    ('plan_cablage', 'Plan de câblage', False),
    ('nomenclature', 'Nomenclature', False),
    ('manuel_proprietaire', 'Manuel du propriétaire', False),
)

#: Toujours ajoutée à ``signalements`` du dossier de fin de chantier : la
#: recette et les garanties ne sont PAS des pièces absentes par erreur, elles
#: sont produites AILLEURS — le dire vaut mieux qu'un silence qui laisserait
#: croire à un dossier complet.
MENTION_RECETTE_GARANTIES = (
    "Recette IEC 62446-1 et garanties : produites par le chantier "
    "(apps.installations, assemblage de remise), non fabriquées par ce "
    "dossier — voir le pack de remise du chantier.")


def _rendus_dossier_fin_chantier(calepinage, company):
    """``code -> rendu`` du dossier de fin de chantier — CHAQUE pièce REND
    via SA mise en page déjà posée par le lot 6 ; la nomenclature emprunte
    celle du rapport d'étude, réduite à SA seule section
    (``sections=['garde', 'nomenclature']``), plutôt qu'une pièce autonome
    inventée pour l'occasion — la MÊME table que la note de calcul et le
    rapport d'étude impriment déjà (``resultat['nomenclature']``)."""
    from .documents.document_asbuilt import rendre_document_asbuilt
    from .documents.manuel_proprietaire import rendre_manuel
    from .documents.plan_cablage import rendre_plan_cablage_pdf
    from .planche import rendre_planche_pdf
    from .rapport import construire_rapport, html_de_rapport

    def _nomenclature():
        from core.pdf import render_pdf

        rapport = construire_rapport(calepinage,
                                     sections=['garde', 'nomenclature'])
        return render_pdf(html=html_de_rapport(rapport), company=company)

    return {
        'plan_pose': lambda: rendre_planche_pdf(calepinage, company=company),
        'document_asbuilt': lambda: rendre_document_asbuilt(
            calepinage, company=company),
        'plan_cablage': lambda: rendre_plan_cablage_pdf(
            calepinage, company=company),
        'nomenclature': _nomenclature,
        'manuel_proprietaire': lambda: rendre_manuel(
            calepinage, company=company),
    }


def construire_dossier_fin_chantier(calepinage, *, company=None,
                                    created_by=None, rendus=None):
    """Rend les cinq pièces, les dépose en GED et les fusionne en UN dossier.

    Renvoie la MÊME forme que ``construire_pack``
    (``{'document', 'pieces', 'pages_attendues', 'signalements'}``) —
    ``signalements`` porte TOUJOURS ``MENTION_RECETTE_GARANTIES`` en plus
    des pièces facultatives absentes, jamais en silence.
    """
    company = company or getattr(calepinage, 'company', None)
    if company is None:
        raise PackRefuse(
            "Un dossier de fin de chantier se produit toujours dans une "
            "société.", piece='company')

    if rendus is None:
        rendus = _rendus_dossier_fin_chantier(calepinage, company)
    pieces, signalements = rendre_pieces(
        calepinage, company=company, rendus=rendus, spec=DOSSIER_FIN_CHANTIER)
    if not pieces:
        raise PackRefuse(
            "Dossier de fin de chantier refusé : aucune pièce à fusionner.",
            piece='pieces')

    from apps.ged.services import deposit_document, fusionner_pdf

    documents, attendues = [], 0
    for code, libelle, octets, pages in pieces:
        document, _cree = deposit_document(
            company=company,
            nom='%s — %s' % (libelle, calepinage),
            source_type='calepinage.dossier_fin_chantier.%s' % code,
            source_id='dossier-fin-chantier:%s' % _ancre(calepinage, code),
            contenu_bytes=octets,
            mime='application/pdf',
            filename='%s.pdf' % code,
            cabinet_nom=CABINET, folder_nom=DOSSIER_CHANTIER_GED,
            created_by=created_by)
        documents.append(document)
        attendues += pages

    dossier = fusionner_pdf(
        documents, company=company, created_by=created_by,
        nom='Dossier de fin de chantier — %s' % calepinage)
    return {
        'document': dossier,
        'pieces': [(code, libelle, pages) for code, libelle, _o, pages
                   in pieces],
        'pages_attendues': attendues,
        'signalements': signalements + [MENTION_RECETTE_GARANTIES],
    }
