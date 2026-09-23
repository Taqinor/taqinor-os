"""Les DOCUMENTS imprimables du module calepinage (lot 6 — CALX291-CALX330).

Un paquet, pas un module : le gabarit société (``gabarit_document``), les
libellés FR/EN (``libelles_document``) et chaque pièce du lot 6 y posent LEUR
fichier, et ce ``__init__`` reste une surface APPEND-ONLY (une section par
tâche, ajoutée EN FIN, jamais réordonnée) — deux lanes du même lot ne se
disputent ainsi jamais le même fichier.

AUCUN IMPORT AU CHARGEMENT : importer ``services.documents.gabarit_document``
exécute d'abord ce fichier ; un import lourd ici (WeasyPrint, modèles) se
paierait à chaque lecture d'un libellé. Les sections ci-dessous importent
FONCTION-LOCALEMENT.

Rien ici n'est un devis client : ``/proposal`` reste le seul PDF de devis
(règle #4) et aucune pièce du module ne porte de montant (D5).
"""
from __future__ import annotations


# ── CALX297 — le rapport d'étude ────────────────────────────────────────────
#: ``code du document -> chemin de SA fonction de mise en page`` : UNE seule
#: fonction HTML par document, que le rendu PDF et l'aperçu (CALX323)
#: partagent. Les pièces suivantes du lot AJOUTENT leur ligne ici.
MISES_EN_PAGE = {
    'rapport_etude': 'apps.calepinage.services.rapport:html_du_rapport',
}


def mise_en_page(code):
    """La fonction de mise en page HTML du document ``code`` (import tardif).

    Lève ``KeyError`` en nommant le code quand le document n'en a pas.
    """
    from importlib import import_module

    try:
        chemin = MISES_EN_PAGE[code]
    except KeyError:
        raise KeyError('Document sans mise en page déclarée : « %s ».'
                       % code) from None
    module, _, fonction = chemin.partition(':')
    return getattr(import_module(module), fonction)


# ── CALX321 — nommer, donnée par donnée, ce qui manque à chaque document ───
#
# CE QUE CETTE SECTION PUBLIE, ET COMMENT ELLE SE DISTINGUE DE ``sorties/``
# ---------------------------------------------------------------------------
# ``inventaire_des_documents`` sert le contrat POSÉ SEUL (PACT10, CALX291)
# ``contract_samples/calepinage_documents.json`` — les NEUF pièces du lot 6,
# un inventaire DISTINCT de ``inventaire_des_sorties`` (CAL175, les douze
# sorties TECHNIQUES existantes, inchangé). Chaque pièce indisponible NOMME
# le ou les champs qui manquent (``manque: [{champ, libelle, ou_saisir}]``),
# jamais une phrase libre — la discipline que ``sorties/`` n'a pas
# (``motif_indisponible`` y reste un texte, CAL175).
#
# LA BASE COMMUNE AUX NEUF PIÈCES : une conception ENREGISTRÉE
# (``roof_layout``) ET un résultat de calcul ENREGISTRÉ (``resultat``) —
# aucun document du lot 6 ne se compose d'un calcul reconstitué. Sans l'un
# des deux, LES NEUF sortent indisponibles avec le MÊME motif ; le champ
# publié distingue lequel manque (``roof_layout`` en premier, puisque sans
# lui il n'y a jamais de résultat non plus).
#
# CHAQUE CHAMP AU-DELÀ DE LA BASE EST RÉELLEMENT LEVÉ PAR UN SERVICE :
# ``rapport_etude`` rejoue ``services.rapport.resultat_du_rapport`` (le
# MÊME appel que le PDF, CALX297) — un défaut y est donc IDENTIQUE, jamais
# un second texte inventé ici ; ``rapport_ombrage``/``plan_cablage`` relisent
# les chemins réels du résultat/de la conception avec la MÊME grammaire que
# le contrat des sections (``services.rapport.valeur_au_chemin``) ; les
# pièces qui dépendent d'une preuve terrain déposée (``document_asbuilt``,
# ``dossier_fin_chantier``, ``diagramme_pertes``) restent TOUJOURS
# indisponibles aujourd'hui — le dépôt d'image (``POST image-document/``,
# CALX302) n'existe pas encore dans ce dépôt, et un calepinage ne peut
# honnêtement avoir aucune preuve déposée tant que la porte n'existe pas.
#
# ``versions[]`` reste ``[]`` (CALX322 la branche, une ligne dans
# ``_versions_pour`` ci-dessous — aucune autre ligne de cette section ne
# bouge) ; ``images[]`` reste ``[]`` pour la même raison que ci-dessus.
from ..rapport import valeur_au_chemin  # noqa: E402 — après la section CALX297

#: Le champ manquant quand AUCUNE conception n'est enregistrée — copié MOT
#: POUR MOT de l'exemple committé (``calepinage_documents.json::exemple_vide``).
MANQUE_ROOF_LAYOUT = {
    'champ': 'roof_layout',
    'libelle': 'Conception enregistrée (toiture et modules)',
    'ou_saisir': "Dessiner et enregistrer une conception sur l'onglet "
                 "Toiture.",
}

#: Le champ manquant quand la conception existe mais qu'AUCUN résultat n'a
#: encore été calculé (état intermédiaire — hors des deux exemples du
#: contrat, mais couvert par le MÊME motif : « la conception ET le résultat »).
MANQUE_RESULTAT = {
    'champ': 'resultat',
    'libelle': 'Résultat de calcul enregistré (simulation)',
    'ou_saisir': 'Lancez le calcul de simulation avant d’imprimer ce '
                 'document.',
}

#: Motif commun aux deux manques ci-dessus — MOT POUR MOT l'exemple committé.
MOTIF_SANS_CONCEPTION_DOCUMENT = (
    "Aucune conception enregistrée : ce document se compose de la "
    "conception et du résultat enregistrés, jamais d'un calcul "
    "reconstitué.")

#: Le champ manquant quand ``resultat_du_rapport`` refuse sans donner de
#: ``champ`` reconnu ici (défensif — un service qui gagnerait un nouveau
#: refus n'a pas besoin de revenir modifier cette table).
_MANQUE_CHAMPS_CONNUS = {
    'resultat': MANQUE_RESULTAT,
    'temperatures': {
        'champ': 'temperatures',
        'libelle': 'Températures de site lisibles',
        'ou_saisir': "Vérifiez les températures sur l'onglet Équipements "
                     'électriques.',
    },
}

#: ``rapport_ombrage`` — MOT POUR MOT l'exemple committé.
MANQUE_SOLAR_ACCESS = {
    'champ': 'roof_layout.zones[].geometry.solarAccess.values',
    'libelle': 'Accès solaire par module (matrice d’ombrage)',
    'ou_saisir': "Calculer l'ombrage sur l'onglet Toiture avant d'imprimer "
                 'ce rapport.',
}
MOTIF_SANS_OMBRAGE = (
    "Aucun accès solaire par module mesuré : le rapport d'ombrage ne se "
    "rend pas sans une trace d'ombre par module.")

#: ``plan_cablage`` — MOT POUR MOT l'exemple committé.
MANQUE_CHAINAGE = {
    'champ': 'electrique.chainage',
    'libelle': 'Schéma unifilaire (chaînage électrique)',
    'ou_saisir': "Chaîner l'électrique sur l'onglet Électrique.",
}
MANQUE_TRONCONS = {
    'champ': 'troncons',
    'libelle': 'Cheminements mesurés',
    'ou_saisir': "Tracer au moins un cheminement sur le plan avant "
                 "d'imprimer.",
}
MOTIF_SANS_CABLAGE = (
    "Aucun schéma unifilaire tracé et aucun cheminement mesuré : le plan "
    "de câblage assemble les deux, et aucun des deux n'existe encore.")

#: ``document_asbuilt`` / ``dossier_fin_chantier`` / ``diagramme_pertes`` —
#: MOT POUR MOT l'exemple committé.
MANQUE_IMAGES_ASBUILT = {
    'champ': 'images',
    'libelle': 'Preuve terrain (photo déposée depuis le chantier)',
    'ou_saisir': "Déposer au moins une photo depuis l'onglet Documents.",
}
MOTIF_SANS_ASBUILT = (
    "Aucune preuve terrain déposée : le document as-built compare "
    "l'implantation posée à la conception, et rien ne l'atteste encore.")

MANQUE_IMAGES_DOSSIER = {
    'champ': 'images',
    'libelle': 'Preuves terrain (photos)',
    'ou_saisir': "Déposer au moins une photo de fin de chantier depuis "
                 "l'onglet Documents.",
}
MOTIF_SANS_DOSSIER = (
    "Aucune preuve terrain déposée : le dossier de fin de chantier "
    "fusionne les pièces techniques et les preuves terrain, et la seconde "
    "manque encore.")

MANQUE_IMAGES_DIAGRAMME = {
    'champ': 'images',
    'libelle': 'Diagramme de pertes (image déposée par le navigateur)',
    'ou_saisir': "Ouvrir le panneau Pertes et déposer l'image du "
                 "diagramme.",
}
MOTIF_SANS_DIAGRAMME = (
    "Aucune image déposée : le diagramme de pertes est capturé par le "
    "navigateur puis déposé par POST image-document, et rien n'a encore "
    "été joint.")

#: ``code -> (libellé, format, chemin sous le calepinage, produit_par)`` —
#: l'ORDRE et les LIBELLÉS sont ceux du contrat committé.
_DEFINITIONS_DOCUMENTS = (
    ('rapport_etude',
     "Rapport d'étude (site, système, pertes, production, électrique)",
     'pdf', 'rapport-etude.pdf/', 'serveur'),
    ('rapport_ombrage',
     "Rapport d'ombrage (cartes de chaleur et TOF/TSRF)",
     'pdf', 'rapport-ombrage.pdf/', 'serveur'),
    ('export_projet_json', 'Export JSON projet + résultats', 'json',
     'export-projet.json/', 'serveur'),
    ('plan_cablage', 'Plan de câblage (schéma unifilaire + cheminements)',
     'pdf', 'plan-cablage.pdf/', 'serveur'),
    ('manuel_proprietaire',
     'Manuel propriétaire (mise en service et entretien)',
     'pdf', 'manuel-proprietaire.pdf/', 'serveur'),
    ('document_asbuilt', "Document as-built (conforme à l'exécution)",
     'pdf', 'document-asbuilt.pdf/', 'serveur'),
    ('dossier_fin_chantier',
     'Dossier de fin de chantier (pièces fusionnées + preuves terrain)',
     'pdf', 'dossier-fin-chantier.pdf/', 'serveur'),
    ('diagramme_pertes',
     'Diagramme de pertes (cascade, capturé par le navigateur)',
     'png', 'documents/', 'navigateur'),
    ('presentation_compacte', 'Présentation compacte (synthèse une page)',
     'pdf', 'presentation-compacte.pdf/', 'serveur'),
)


def _base_documents(calepinage):
    return '/api/django/calepinage/calepinages/%s/' % calepinage.pk


def _manque_pour_champ(champ):
    """Le ``{champ, libelle, ou_saisir}`` d'un champ RÉELLEMENT levé.

    Un champ que la table ne connaît pas encore obtient une entrée
    DÉFENSIVE plutôt qu'une exception — un service qui gagne un nouveau
    refus ne doit jamais faire tomber l'inventaire, seulement publier un
    ``ou_saisir`` moins précis, en attendant d'être ajouté ici.
    """
    connu = _MANQUE_CHAMPS_CONNUS.get(champ)
    if connu is not None:
        return connu
    lisible = (champ or 'donnée').replace('.', ' ').replace('_', ' ').strip()
    return {
        'champ': champ or '',
        'libelle': lisible[:1].upper() + lisible[1:] if lisible else 'Donnée',
        'ou_saisir': 'Corrigez « %s » avant d’imprimer ce document.'
                     % (champ or 'cette donnée'),
    }


def _etat_du_document(code, calepinage, resultat):
    """``(disponible, motif, manque)`` — la BASE (conception+résultat) est
    déjà acquise ici ; chaque défaut supplémentaire est RÉELLEMENT levé par
    le service concerné, jamais un texte inventé pour l'occasion."""
    if code == 'rapport_etude':
        from ..rapport import RapportRefuse, resultat_du_rapport

        try:
            resultat_du_rapport(calepinage)
        except RapportRefuse as refus:
            return False, str(refus), [_manque_pour_champ(refus.champ)]
        return True, None, []

    if code == 'rapport_ombrage':
        present, _valeur = valeur_au_chemin(
            {'roof_layout': getattr(calepinage, 'roof_layout', None)},
            'roof_layout.zones[].geometry.solarAccess.values')
        if not present:
            return False, MOTIF_SANS_OMBRAGE, [MANQUE_SOLAR_ACCESS]
        return True, None, []

    if code == 'plan_cablage':
        # ``resultat['troncons']`` est un DICT (``{troncons[], totaux,
        # omissions[], verdicts[]}``, contrat ``calepinage_resultat.json``)
        # OU ``null`` tant qu'aucun cheminement n'est tracé — JAMAIS une
        # liste vide (« mesuré, et il n'y a rien » serait faux). La
        # grammaire ``[]`` ne s'applique donc pas ici : présence du dict.
        manque = []
        if not valeur_au_chemin(resultat, 'electrique.chainage')[0]:
            manque.append(MANQUE_CHAINAGE)
        if not valeur_au_chemin(resultat, 'troncons')[0]:
            manque.append(MANQUE_TRONCONS)
        if manque:
            return False, MOTIF_SANS_CABLAGE, manque
        return True, None, []

    if code == 'document_asbuilt':
        return False, MOTIF_SANS_ASBUILT, [MANQUE_IMAGES_ASBUILT]
    if code == 'dossier_fin_chantier':
        return False, MOTIF_SANS_DOSSIER, [MANQUE_IMAGES_DOSSIER]
    if code == 'diagramme_pertes':
        return False, MOTIF_SANS_DIAGRAMME, [MANQUE_IMAGES_DIAGRAMME]

    # export_projet_json / manuel_proprietaire / presentation_compacte : la
    # BASE (conception+résultat) suffit — aucun service dédié n'existe
    # encore pour eux, aucun défaut supplémentaire ne peut donc être levé.
    return True, None, []


def _versions_pour(calepinage, code):
    """Les versions déjà produites de ``code`` (CALX322,
    ``services/documents/versions_document.py``) — SEULE cette ligne a
    changé depuis la section CALX321 ci-dessus."""
    from .versions_document import versions_du_document

    return versions_du_document(calepinage, code)


def _entree_document(code, libelle, format_, endpoint, produit_par,
                     disponible, motif, manque, versions):
    return {
        'code': code,
        'libelle': libelle,
        'format': format_,
        'endpoint': endpoint,
        'produit_par': produit_par,
        'disponible': bool(disponible),
        'motif_indisponible': None if disponible else motif,
        'manque': [] if disponible else list(manque or ()),
        'versions': list(versions or ()),
    }


def inventaire_des_documents(calepinage):
    """CALX321 — l'inventaire des NEUF documents du lot 6, DISTINCT de
    ``inventaire_des_sorties`` (CAL175). Forme = ``calepinage_documents.json``.

    Une pièce indisponible reste LISTÉE (jamais masquée) et porte AU MOINS
    une entrée ``manque`` qui NOMME le champ — jamais une phrase générique.
    """
    from .libelles_document import resolution_langue

    base = _base_documents(calepinage)
    a_conception = bool(getattr(calepinage, 'roof_layout', None))
    resultat_brut = getattr(calepinage, 'resultat', None)
    a_resultat = isinstance(resultat_brut, dict) and bool(resultat_brut)
    resultat = resultat_brut if isinstance(resultat_brut, dict) else {}
    base_ok = a_conception and a_resultat

    documents = []
    for code, libelle, format_, chemin, produit_par in _DEFINITIONS_DOCUMENTS:
        if not base_ok:
            manque_base = MANQUE_ROOF_LAYOUT if not a_conception \
                else MANQUE_RESULTAT
            disponible, motif, manque = (False, MOTIF_SANS_CONCEPTION_DOCUMENT,
                                         [manque_base])
        else:
            disponible, motif, manque = _etat_du_document(
                code, calepinage, resultat)
        versions = _versions_pour(calepinage, code) if disponible else []
        documents.append(_entree_document(
            code, libelle, format_, base + chemin, produit_par,
            disponible, motif, manque, versions))

    langue = resolution_langue(calepinage)['langue'] if a_conception else None
    return {
        'calepinage': getattr(calepinage, 'pk', None),
        'layout_hash': getattr(calepinage, 'layout_hash', '') or None,
        'version_moteur': getattr(calepinage, 'version_moteur', '') or None,
        'langue': langue,
        'documents': documents,
        # CALX291 : le dépôt d'image (POST image-document/, CALX302) est
        # hors périmètre de CALX321 — aucune image ne peut exister tant que
        # cette porte n'a pas été posée.
        'images': [],
    }
