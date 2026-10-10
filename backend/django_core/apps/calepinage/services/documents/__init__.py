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
#: ``code du document -> SA fonction de mise en page`` : UNE seule fonction
#: HTML par document, que le rendu PDF et l'aperçu (CALX323) partagent. Les
#: pièces suivantes du lot AJOUTENT leur ligne ici. Une entrée est soit le
#: chemin ``'module:fonction'``, soit un appelable SANS argument qui rend la
#: fonction (import tardif : ce paquet n'importe rien au chargement).
MISES_EN_PAGE = {
    'rapport_etude': 'apps.calepinage.services.rapport:html_du_rapport',
}


def _piece(nom):
    """Le module de la pièce ``nom`` de ce paquet (import tardif)."""
    from importlib import import_module

    return import_module('%s.%s' % (__name__, nom))


def mise_en_page(code):
    """La fonction de mise en page HTML du document ``code`` (import tardif).

    Lève ``KeyError`` en nommant le code quand le document n'en a pas.
    """
    from importlib import import_module

    try:
        entree = MISES_EN_PAGE[code]
    except KeyError:
        raise KeyError('Document sans mise en page déclarée : « %s ».'
                       % code) from None
    if callable(entree):
        return entree()
    module, _, fonction = entree.partition(':')
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
    'ou_saisir': "Dessiner et enregistrer une conception dans l'atelier 3D.",
    'onglet': None,
}

#: Le champ manquant quand la conception existe mais qu'AUCUN résultat n'a
#: encore été calculé (état intermédiaire — hors des deux exemples du
#: contrat, mais couvert par le MÊME motif : « la conception ET le résultat »).
MANQUE_RESULTAT = {
    'champ': 'resultat',
    'libelle': 'Résultat de calcul enregistré (simulation)',
    'ou_saisir': "Lancer la simulation dans l'onglet Production avant "
                 "d'imprimer ce document.",
    'onglet': 'production',
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
        'ou_saisir': "Vérifier les températures dans l'onglet Équipements "
                     'électriques.',
        'onglet': 'equipements-electriques',
    },
}

#: ``rapport_ombrage`` — MOT POUR MOT l'exemple committé.
MANQUE_SOLAR_ACCESS = {
    'champ': 'roof_layout.zones[].geometry.solarAccess.values',
    'libelle': 'Accès solaire par module (matrice d’ombrage)',
    'ou_saisir': "Calculer l'ombrage dans l'atelier 3D avant d'imprimer ce "
                 'rapport.',
    'onglet': None,
}
MOTIF_SANS_OMBRAGE = (
    "Aucun accès solaire par module mesuré : le rapport d'ombrage ne se "
    "rend pas sans une trace d'ombre par module.")

#: ``plan_cablage`` — MOT POUR MOT l'exemple committé.
MANQUE_CHAINAGE = {
    'champ': 'electrique.chainage',
    'libelle': 'Schéma unifilaire (chaînage électrique)',
    'ou_saisir': "Désigner le module et l'onduleur dans l'onglet Équipements "
                 "électriques, puis chaîner dans l'onglet Affectation des "
                 "chaînes.",
    'onglet': 'affectation',
}
#: ACAL219 - le rendu du plan de cablage ne lit que ``electrique.affectation``
#: (jamais ``troncons``) : seul le chainage conditionne sa disponibilite.
MOTIF_SANS_CHAINAGE = (
    "Aucun chaînage électrique calculé : le plan de câblage dessine les "
    "chaînes affectées, et aucune n'existe encore.")

#: ``diagramme_pertes`` (CALX308) — rendu CÔTÉ SERVEUR depuis la cascade du
#: résultat SERVI : sans cascade, il se dit indisponible en la nommant.
MOTIF_SANS_DIAGRAMME = (
    "Aucune cascade de pertes calculée : le diagramme est rendu par le "
    "serveur depuis le résultat de simulation, et il n'existe pas encore.")
MANQUE_CASCADE_DIAGRAMME = {
    'champ': 'cascade',
    'libelle': 'Cascade de pertes du résultat de simulation',
    'ou_saisir': "Lancer la simulation dans l'onglet Production.",
    'onglet': 'production',
}

#: ``dossier_fin_chantier`` (ACAL220) — disponible dès qu'UNE pièce
#: fusionnable existe (plan de pose, as-built, plan de câblage, manuel).
MOTIF_SANS_PIECE_DOSSIER = (
    "Aucune pièce à fusionner : le dossier de fin de chantier assemble le "
    "plan de pose, le document as-built, le plan de câblage et le manuel, "
    "et aucune n'est disponible.")
MANQUE_PIECES_DOSSIER = {
    'champ': 'pieces',
    'libelle': 'Au moins une pièce fusionnable (plan de pose, as-built, '
               'plan de câblage, manuel)',
    'ou_saisir': "Enregistrer une conception dans l'atelier 3D, puis "
                 "ouvrir l'onglet Documents.",
    'onglet': 'documents',
}

#: ``code -> (libellé, format, chemin sous le calepinage, produit_par)`` —
#: l'ORDRE et les LIBELLÉS sont ceux du contrat committé (ACAL220 : le
#: diagramme est un SVG rendu par le serveur ; le dossier se PRODUIT en POST).
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
     'Dossier de fin de chantier (pièces techniques fusionnées)',
     'pdf', 'dossier-fin-chantier/', 'serveur'),
    ('diagramme_pertes', 'Diagramme de pertes (cascade des pertes)',
     'svg', 'diagramme-pertes.svg/', 'serveur'),
    ('presentation_compacte', 'Présentation compacte (synthèse une page)',
     'pdf', 'presentation-compacte.pdf/', 'serveur'),
)


#: ACAL220 — la MÉTHODE de chaque document (le dossier de fin de chantier
#: CRÉE des documents GED : il se déclenche en POST, jamais en GET).
METHODES = {'dossier_fin_chantier': 'POST'}

#: ACAL220 — les langues RÉELLEMENT acceptées par la route du document
#: (``?langue=`` lu par ``views/documents.py``) ; toute autre pièce est servie
#: en français seulement.
LANGUES_PAR_DOCUMENT = {
    'rapport_etude': ['fr', 'en'],
    'rapport_ombrage': ['fr', 'en'],
    'diagramme_pertes': ['fr', 'en'],
}

#: ACAL220 — les formats annexes d'un document (même calepinage).
AUTRES_FORMATS = {
    'plan_cablage': (('dxf', 'plan-cablage.dxf/'),),
}


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
        'onglet': None,
    }


def _lecture_servie(calepinage):
    """``(servi, refus)`` - le resultat SERVI, lu UNE fois par appel.

    ACAL219 - la lecture STRICTE du rapport (``resultat_du_rapport``) sert a
    la fois la carte ``rapport_etude`` (son refus, MOT POUR MOT) et les huit
    autres cartes (le meme ``servi``) : une seule execution de
    ``resultat_calepinage`` par appel de ``documents/``. Seul un refus du
    lecteur strict (cle de cout, temperatures illisibles) declenche une
    seconde lecture, TOLERANTE, pour que les autres cartes restent evaluees.
    """
    from ... import selectors
    from ..rapport import RapportRefuse, resultat_du_rapport

    try:
        servi, _stocke = resultat_du_rapport(calepinage)
    except RapportRefuse as refus:
        return selectors.resultat_servi(calepinage), refus
    return servi, None


def _etat_du_document(code, calepinage, resultat, refus_rapport=None):
    """``(disponible, motif, manque)`` — la BASE (conception+résultat) est
    déjà acquise ici ; ``resultat`` est le résultat SERVI (ACAL219) ; chaque
    défaut supplémentaire est RÉELLEMENT levé par le service concerné,
    jamais un texte inventé pour l'occasion."""
    if code == 'rapport_etude':
        if refus_rapport is not None:
            return (False, str(refus_rapport),
                    [_manque_pour_champ(refus_rapport.champ)])
        return True, None, []

    if code == 'rapport_ombrage':
        present, _valeur = valeur_au_chemin(
            {'roof_layout': getattr(calepinage, 'roof_layout', None)},
            'roof_layout.zones[].geometry.solarAccess.values')
        if not present:
            return False, MOTIF_SANS_OMBRAGE, [MANQUE_SOLAR_ACCESS]
        return True, None, []

    if code == 'plan_cablage':
        # ACAL219 - le rendu ne lit que ``electrique.affectation`` (jamais
        # ``troncons``) : le chainage servi est la seule condition. Sans
        # chainage, la carte reste indisponible et le dit.
        if not valeur_au_chemin(resultat, 'electrique.chainage')[0]:
            return False, MOTIF_SANS_CHAINAGE, [MANQUE_CHAINAGE]
        return True, None, []

    if code == 'manuel_proprietaire':
        # ACAL220 - la disponibilite vient de la fonction declaree a cote du
        # rendu : sans gabarit « manuel » actif, le manuel ne se rend pas.
        from .manuel_proprietaire import disponibilite

        return disponibilite(calepinage)
    if code == 'document_asbuilt':
        # ACAL220 - le service ne refuse jamais : conception et resultat
        # (la base, deja acquise ici) suffisent.
        return True, None, []
    if code == 'diagramme_pertes':
        # CALX308 (clôture M4) — le diagramme est rendu CÔTÉ SERVEUR depuis
        # ``resultat['cascade']`` (route GET diagramme-pertes.svg/) : sa
        # disponibilité suit la cascade, plus une image déposée. L'image
        # navigateur (genre ``sankey``) reste une pièce jointe facultative.
        if valeur_au_chemin(resultat, 'cascade')[0]:
            return True, None, []
        return False, MOTIF_SANS_DIAGRAMME, [MANQUE_CASCADE_DIAGRAMME]

    # export_projet_json / presentation_compacte : la BASE
    # (conception+résultat) suffit — aucun défaut supplémentaire ne peut être
    # levé. ``dossier_fin_chantier`` se déduit des autres états (voir
    # ``inventaire_des_documents``).
    return True, None, []


def _versions_pour(calepinage, code):
    """Les versions déjà produites de ``code`` (CALX322,
    ``services/documents/versions_document.py``) — SEULE cette ligne a
    changé depuis la section CALX321 ci-dessus."""
    from .versions_document import versions_du_document

    return versions_du_document(calepinage, code)


def _images_pour(calepinage):
    """Les images déposées par le navigateur (CALX302,
    ``services/images_document.py``) — MÊME GESTE que ``_versions_pour``
    ci-dessus (CALX322) : SEULE la ligne ``'images': ...`` de
    ``inventaire_des_documents`` a changé pour l'appeler."""
    from ..images_document import images_du_calepinage

    return images_du_calepinage(calepinage)


def _entree_document(code, libelle, format_, endpoint, produit_par,
                     disponible, motif, manque, versions, base=''):
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
        # ACAL220 — contrat v2 : méthode, langues, aperçu, autres formats.
        'methode': METHODES.get(code, 'GET'),
        'langues': list(LANGUES_PAR_DOCUMENT.get(code, ['fr'])),
        'apercu': code in MISES_EN_PAGE,
        'autres_formats': [
            {'format': extension, 'endpoint': base + chemin}
            for extension, chemin in AUTRES_FORMATS.get(code, ())],
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
    base_ok = a_conception and a_resultat
    # ACAL219 - le resultat SERVI, lu UNE fois pour les neuf cartes.
    resultat, refus_rapport = (_lecture_servie(calepinage) if base_ok
                               else ({}, None))

    etats = {}
    for code, _l, _f, _c, _p in _DEFINITIONS_DOCUMENTS:
        if not base_ok:
            manque_base = MANQUE_ROOF_LAYOUT if not a_conception \
                else MANQUE_RESULTAT
            etats[code] = (False, MOTIF_SANS_CONCEPTION_DOCUMENT,
                           [manque_base])
        elif code != 'dossier_fin_chantier':
            etats[code] = _etat_du_document(code, calepinage, resultat,
                                            refus_rapport)
    if base_ok:
        # ACAL220 - le dossier de fin de chantier est disponible des qu'une
        # piece fusionnable existe (plan de pose = la conception ; as-built,
        # plan de cablage, manuel = leur propre etat).
        fusionnables = ('document_asbuilt', 'plan_cablage',
                        'manuel_proprietaire')
        etats['dossier_fin_chantier'] = (
            (True, None, []) if any(etats[c][0] for c in fusionnables)
            else (False, MOTIF_SANS_PIECE_DOSSIER, [MANQUE_PIECES_DOSSIER]))

    documents = []
    for code, libelle, format_, chemin, produit_par in _DEFINITIONS_DOCUMENTS:
        disponible, motif, manque = etats[code]
        versions = _versions_pour(calepinage, code) if disponible else []
        documents.append(_entree_document(
            code, libelle, format_, base + chemin, produit_par,
            disponible, motif, manque, versions, base=base))

    langue = resolution_langue(calepinage)['langue'] if a_conception else None
    return {
        'calepinage': getattr(calepinage, 'pk', None),
        'layout_hash': getattr(calepinage, 'layout_hash', '') or None,
        'version_moteur': getattr(calepinage, 'version_moteur', '') or None,
        'langue': langue,
        'documents': documents,
        # CALX302 : la porte est posée (``POST image-document/``,
        # ``services/images_document.py``) — les images RÉELLEMENT déposées,
        # la plus récente d'abord.
        'images': _images_pour(calepinage),
    }


# ── CALX310 — le plan de câblage des chaînes ────────────────────────────────
#
# ENF18 — les quatre mises en page ci-dessous sont enregistrées par un
# appelable (``_piece(nom).fonction``) et non plus par un chemin-chaîne : la
# fonction est ainsi NOMMÉE dans le code qui la sert (``mise_en_page``,
# consommée par l'aperçu ``apercu-document/``), au lieu de n'exister que dans
# une chaîne que la garde ``check_services_appeles`` ne peut pas suivre.
MISES_EN_PAGE['plan_cablage'] = (
    lambda: _piece('plan_cablage').html_du_plan_cablage)


# ── CALX316 — le manuel du propriétaire, depuis le gabarit société ─────────
MISES_EN_PAGE['manuel_proprietaire'] = (
    lambda: _piece('manuel_proprietaire').html_du_manuel)


# ── CALX318 — le document as-built (prévu, posé, écarts, photos) ───────────
MISES_EN_PAGE['document_asbuilt'] = (
    lambda: _piece('document_asbuilt').html_du_document_asbuilt)


# ── CALX315 — la présentation compacte interne, deux pages, sans montant ───
MISES_EN_PAGE['presentation_compacte'] = (
    lambda: _piece('presentation_compacte').html_de_presentation_compacte)
