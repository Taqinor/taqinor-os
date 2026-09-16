"""STKCAT21 — LE VOCABULAIRE DE RÔLES DE DEVIS, DÉCLARÉ UNE SEULE FOIS.

POURQUOI CE MODULE EXISTE (audit L3 stock ↔ CRM ↔ devis du 16/09/2026)
----------------------------------------------------------------------
Le rôle d'un produit dans un devis (« panneau », « batterie », « structure »…)
n'était NULLE PART une donnée : il était RE-DEVINÉ à chaque lecture, à partir
de mots-clés du NOM, par quatre classifieurs séparés. Un produit réel nommé
« Pergola alu » n'était donc reconnu par aucun d'eux — le défaut fondateur
« Pergola introuvable ».

STKCAT21 ajoute la donnée manquante (``stock.Produit.role_devis``) et, avec
elle, un ORDRE DE LECTURE explicite :

    1. le rôle DÉCLARÉ sur la fiche produit   → source ``'declare'``
    2. la famille de sa CATÉGORIE, quand elle est sans ambiguïté
                                              → source ``'categorie'``
    3. les MOTS-CLÉS du nom (le classifieur historique, injecté)
                                              → source ``'nom'``
    4. rien                                   → ``(None, None)``

Les mots-clés ne DISPARAISSENT jamais : ils deviennent un REPLI PERMANENT.
C'est exactement la discipline de ``stock.selectors.specs_solaire_produit``
(champ déclaré d'abord — ``fiche.type_fiche`` —, mots-clés du nom ensuite).

POURQUOI DANS ``core`` ET PAS DANS ``apps/ventes``
-------------------------------------------------
Le même tuple de rôles doit être lu par ``apps.ventes.models``
(``ROLES_AUTO_COMPOSITION``, qui AUTORISE un rôle dans ``ParametresGammes``)
ET par ``apps.stock.models`` (les ``choices`` du nouveau champ). Or
``apps.stock`` n'a pas le droit d'importer ``apps.ventes`` (frontière
inter-app, CLAUDE.md, verrouillée par ``.importlinter``). Une COPIE de plus
serait un cinquième miroir à tenir à la main — la cause exacte du défaut
``onduleur_offgrid`` que ``scripts/check_roles_mirror.py`` a attrapé. Le tuple
vit donc ici : ``core`` est la couche de FONDATION que toutes les apps peuvent
importer vers le bas.

``core`` N'IMPORTE RIEN DE ``apps.*`` — ni Django, ni modèle, ni réglage. Le
classifieur par mots-clés, qui vit côté ``ventes``, est donc INJECTÉ en
paramètre (``classer_nom``), jamais importé. Ce module reste du Python pur :
il se teste et s'exécute sans base ni settings.

STKCAT22 y a ajouté la TABLE DE RECONNAISSANCE « PANNEAU » (voir plus bas) :
même motif, même raison — trois lecteurs répondaient trois choses différentes
sur la même désignation.
"""
from __future__ import annotations

import re

#: LE vocabulaire de rôles de composition/devis. Copie DÉPLACÉE (et non
#: dupliquée) de l'ancien littéral ``apps.ventes.models.ROLES_AUTO_COMPOSITION``
#: — MÊMES valeurs, MÊME ordre, au caractère près : ``ordonner_par_role`` et
#: ``ParametresGammes.ordre_lignes`` s'appuient sur ce rang.
#:
#: ``structure`` est le rôle GÉNÉRIQUE (STKCAT2) ; ``structure_acier`` et
#: ``structure_alu`` sont des ALIAS DÉPRÉCIÉS CONSERVÉS POUR TOUJOURS (un
#: réglage ``ParametresGammes`` enregistré hier reste accepté tel quel).
ROLES_DEVIS = (
    'onduleur_reseau', 'onduleur_hybride', 'onduleur_offgrid', 'panneau',
    'batterie',
    # ``structure`` d'abord (rôle générique), puis ses deux alias dépréciés —
    # rang EXPLICITE et voisin, jamais le rang « inconnu = dernier » de
    # ``ordonner_par_role``.
    'structure',
    'structure_acier',  # déprécié (alias conservé) — voir STKCAT2
    'structure_alu',    # déprécié (alias conservé) — voir STKCAT2
    'socle', 'cable_dc', 'cable_terre',
    'smart_meter', 'wifi_dongle', 'accessoires', 'tableau', 'installation',
    'transport', 'suivi',
)

#: Les sources possibles de :func:`role_effectif`, par rang de priorité.
SOURCES_ROLE = ('declare', 'categorie', 'nom')


# ═══════════════════════════════════════════════════════════════════════════
# LA CARTE FAMILLE (``stock.Categorie.TypeEquipement``) → RÔLE DE DEVIS
# ═══════════════════════════════════════════════════════════════════════════
#
# ARBITRAGES, ÉCRITS UNE FOIS POUR TOUTES. La règle de tranchage est celle que
# tout ce dépôt applique déjà au classement produit : ON PRÉFÈRE L'OMISSION AU
# FAUX POSITIF. Une famille qui recouvre PLUSIEURS rôles ne répond donc PAS
# (``None``) — le rôle retombe alors sur les mots-clés du nom, exactement comme
# aujourd'hui, et le fondateur peut toujours TRANCHER en déclarant le rôle sur
# la fiche produit (rang 1, qui passe devant tout).
#
#   · ``panneau`` → ``'panneau'`` — une seule correspondance possible.
#   · ``batterie`` → ``'batterie'`` — idem.
#   · ``structure`` → ``'structure'`` — le rôle GÉNÉRIQUE de STKCAT2, celui
#     qui existe précisément pour une structure dont le nom ne dit ni
#     « acier » ni « alu » (« Pergola alu » côté catégorie, c'est tout le sujet
#     de l'audit). Jamais un des deux ALIAS dépréciés : la catégorie ne connaît
#     pas le matériau.
#   · ``accessoire`` → ``'accessoires'`` (le rôle est au PLURIEL dans le
#     vocabulaire ; la famille au singulier — ce n'est pas une faute de frappe).
#
# LES FAMILLES QUI NE RÉPONDENT PAS, ET POURQUOI :
#
#   · ``onduleur`` → AMBIGU. Le TYPE dit la fonction de l'équipement, pas sa
#     topologie : les trois rôles ``onduleur_reseau``/``onduleur_hybride``/
#     ``onduleur_offgrid`` partagent cette unique famille (arbitrage écrit de
#     STKCAT3). Choisir l'un des trois composerait un onduleur hors réseau sur
#     un client raccordé.
#   · ``cable`` → AMBIGU : ``cable_dc`` (solaire) et ``cable_terre`` (AC) sont
#     deux rôles distincts, deux métrés distincts.
#   · ``service`` → AMBIGU : trois rôles de prestation (``installation``,
#     ``transport``, ``suivi``) tombent dans cette seule famille.
#   · ``protection`` → AMBIGU **et** FOURRE-TOUT : c'est la catégorie où
#     ``seed_catalogue.classify_categorie`` fait tomber TOUT l'inconnu. Lui
#     donner un rôle en ferait un rôle par défaut pour l'inconnu — l'inverse
#     exact de ce que cette table doit faire.
#   · ``pompe`` / ``variateur`` → PAS DE RÔLE DE DEVIS. Le pompage se compose
#     hors du vocabulaire résidentiel (aucun de ces deux mots n'est un rôle) ;
#     répondre quoi que ce soit ici inventerait une appartenance.
#   · ``compteur`` → NON TRANCHÉ. Le seul rôle « compteur » du vocabulaire est
#     ``smart_meter``, qui désigne l'accessoire de COMMUNICATION d'un onduleur
#     (règle QF9 : il est retiré d'un panier dont l'onduleur n'est pas Huawei).
#     Un compteur d'énergie ordinaire n'est pas cet accessoire-là : le promouvoir
#     automatiquement ferait entrer/sortir des accessoires d'un panier d'option
#     sur une simple catégorie. Le fondateur déclare ``smart_meter`` sur la
#     fiche quand c'en est un.
#
# La table est EXHAUSTIVE (les onze valeurs de ``TypeEquipement`` y figurent, y
# compris celles qui valent ``None``) : un test d'``apps/stock`` vérifie qu'il
# n'en manque aucune, pour qu'une famille ajoutée demain soit un arbitrage
# ÉCRIT et pas un oubli silencieux.
FAMILLE_VERS_ROLE = {
    'panneau': 'panneau',
    'batterie': 'batterie',
    'structure': 'structure',
    'accessoire': 'accessoires',
    # Ambiguës ou hors vocabulaire — voir les arbitrages ci-dessus.
    'onduleur': None,
    'cable': None,
    'protection': None,
    'pompe': None,
    'variateur': None,
    'compteur': None,
    'service': None,
}


def role_declare(role_devis):
    """Le rôle DÉCLARÉ, normalisé, ou ``None``.

    Une valeur hors :data:`ROLES_DEVIS` est IGNORÉE (on retombe sur les rangs
    suivants) plutôt que servie : le vocabulaire est la seule vérité, et un
    rôle inconnu ne doit jamais se propager dans un devis.
    """
    valeur = (role_devis or '').strip()
    return valeur if valeur in ROLES_DEVIS else None


def role_de_famille(type_equipement):
    """Le rôle d'une famille de catégorie, ou ``None`` si elle n'en dit rien.

    ``None`` couvre les DEUX cas volontairement confondus : famille ambiguë
    (plusieurs rôles possibles) et famille inconnue de la table. Les deux
    doivent laisser la main au rang suivant.
    """
    return FAMILLE_VERS_ROLE.get((type_equipement or '').strip() or None)


def role_effectif(role_devis=None, type_equipement=None, nom='',
                  classer_nom=None):
    """``(role, source)`` — le rôle RETENU et D'OÙ il vient.

    ``source`` vaut ``'declare'``, ``'categorie'``, ``'nom'``, ou ``None``
    quand aucun rang ne répond (le couple est alors ``(None, None)``).

    ``classer_nom`` est le classifieur par MOTS-CLÉS, INJECTÉ (``core`` ne peut
    pas importer ``apps.ventes.domain.catalogue``). Absent, le rang 3 est
    simplement sauté — la fonction reste utilisable dans un contexte qui n'a
    pas le domaine ventes sous la main.

    Ne lève jamais, n'écrit rien, ne requête rien.
    """
    declare = role_declare(role_devis)
    if declare:
        return declare, 'declare'
    famille = role_de_famille(type_equipement)
    if famille:
        return famille, 'categorie'
    if classer_nom is not None:
        par_mot_cle = (classer_nom(nom or '') or '').strip()
        if par_mot_cle in ROLES_DEVIS:
            return par_mot_cle, 'nom'
    return None, None


def contradiction_role_nom(role, role_mot_cle):
    """Le message FR d'une contradiction rôle déclaré ↔ désignation, ou ``None``.

    Jamais une décision : la ligne garde son rôle déclaré et reste EXACTEMENT
    où elle est. C'est la discipline « ceinture-bretelles, sans perte de ligne »
    de ``quote_engine.builder._repartir_options`` et de ``LigneDevis.variante``
    — une contradiction se JOURNALISE, elle n'écrase rien et ne fait jamais
    disparaître un dirham d'un document.
    """
    if not role or not role_mot_cle or role == role_mot_cle:
        return None
    return ("rôle déclaré « %s » en contradiction avec la désignation, que les "
            "mots-clés classent « %s » — le rôle déclaré est conservé"
            % (role, role_mot_cle))


# ═══════════════════════════════════════════════════════════════════════════
# STKCAT22 — LA TABLE DE RECONNAISSANCE « PANNEAU », PARTAGÉE
# ═══════════════════════════════════════════════════════════════════════════
#
# LE DÉFAUT MESURÉ. « Est-ce un panneau ? » avait TROIS réponses différentes
# dans ce dépôt, sur la MÊME désignation :
#
#   · ``apps.ventes.solar_design.is_panel`` (le moteur PDF, élargi le
#     19/08/2026) : « Module PV 550 W » → OUI ;
#   · ``seed_catalogue.classify_categorie`` : NON — le produit tombait dans la
#     catégorie fourre-tout « Protection & accessoires » ;
#   · ``seed_catalogue.is_panneau`` (le prédicat FISCAL) : NON — donc TVA 20 %
#     sur un panneau photovoltaïque, qui est à 10 % depuis la réforme.
#
# Les trois PROMETTAIENT en prose d'être alignés. Une prose ne se vérifie pas.
# La table vit désormais ICI, une fois, et les trois lecteurs l'IMPORTENT.
#
# CE QUE LA TABLE SAIT RECONNAÎTRE, ET DANS QUEL ORDRE (:func:`est_panneau`) :
#   1. le mot « panneau »/« panneaux » à FRONTIÈRE DE MOT ;
#   2. (si l'appelant fournit ``exclut``) une AUTRE famille de produit → NON ;
#   3. « module » + un qualifiant photovoltaïque ;
#   4. une MARQUE de panneau ET un wattage lisible — jamais la marque seule :
#      Canadian Solar, Huawei et consorts vendent aussi des onduleurs.
#
# L'ORDRE DE L'EXCLUSION EST LE CHOIX DE L'APPELANT, et c'est délibéré : le
# moteur PDF veut « panneau » écrit en toutes lettres qui l'emporte (il classe
# la ligne telle qu'elle est facturée), tandis que le prédicat FISCAL du seeder
# veut l'inverse (« Nettoyage panneaux » est une PRESTATION à 20 %, quel que
# soit le mot « panneaux » dans son nom). Les deux appellent donc la même
# table, chacun avec son ordre — au lieu d'avoir chacun sa table.

#: Le mot « panneau »/« panneaux » à FRONTIÈRE DE MOT (jamais une sous-chaîne
#: nue — même garde-fou que ``seed_catalogue.is_offgrid``).
PANNEAU_RE = re.compile(r'\bpanneau(x)?\b')

#: Qualifiants qui font d'un « module » un module PHOTOVOLTAÏQUE. Sans eux,
#: « module » seul désignerait aussi un module de batterie ou de coffret.
PANNEAU_MODULE_QUALIFIERS = ('pv', 'photovolta', 'solaire', 'solar')

#: Marques de panneaux. Elles ne suffisent JAMAIS seules — il faut un wattage
#: lisible à côté. On préfère l'omission au faux positif.
PANNEAU_MARQUES = (
    'canadian solar', 'canadien solar', 'jinko', 'longi', 'trina',
    'ja solar', 'risen', 'sunpower', 'qcells', 'q cells', 'astronergy',
    'znshine',
)

#: Un wattage lisible : « 550 W », « 710Wc ». MÊME expression que celle dont
#: ``apps.ventes.solar_design`` se sert pour LIRE la puissance — ce module en
#: est la source, ``solar_design._WATT_RE`` en est l'alias (une seule regex).
WATT_RE = re.compile(r'(\d{3,4})\s*(?:wc|w)\b', re.IGNORECASE)


def est_panneau(nom, exclut=None):
    """Le texte ``nom`` désigne-t-il un PANNEAU photovoltaïque ?

    ``exclut`` — prédicat OPTIONNEL ``(texte minusculé) -> bool`` qui dit
    « ce texte appartient à une AUTRE famille de produit ». Il est consulté
    APRÈS le mot « panneau » et AVANT les deux reconnaissances élargies
    (module+qualifiant, marque+watt) : un onduleur ou une batterie portant une
    marque de panneau n'est jamais un panneau. Absent ⇒ aucune exclusion
    (l'appelant a déjà filtré lui-même, comme le fait le seeder).

    Fonction PURE : ni Django, ni base, ni I/O.
    """
    d = (nom or '').lower()
    if PANNEAU_RE.search(d):
        return True
    if exclut is not None and exclut(d):
        return False
    if 'module' in d and any(q in d for q in PANNEAU_MODULE_QUALIFIERS):
        return True
    return bool(any(m in d for m in PANNEAU_MARQUES) and WATT_RE.search(d))


# ═══════════════════════════════════════════════════════════════════════════
# STKCAT23 — LE RÔLE DIT À QUELLE OPTION UNE LIGNE APPARTIENT
# ═══════════════════════════════════════════════════════════════════════════
#
# Un devis résidentiel « Les deux » propose DEUX kits : « sans batterie » et
# « avec batterie ». L'appartenance d'une ligne à l'un ou à l'autre était
# décidée par MOTS-CLÉS sur sa désignation
# (``apps.ventes.utils.options.blob_va_dans_sans`` / ``...avec``) — une
# désignation qu'un commercial peut éditer à la main après coup.
#
# Les deux tuples ci-dessous sont la MÊME règle exprimée sur le RÔLE, à
# l'identique : « sans batterie » exclut la batterie, l'onduleur hybride et
# l'onduleur AUTONOME (une option sans batterie sur un site isolé n'existe
# pas) ; « avec batterie » exclut l'onduleur RÉSEAU. Les panneaux, la
# structure et la pose restent dans les DEUX paniers — invariant du moteur.
#
# Les fonctions rendent ``None`` — « le rôle n'en dit rien » — quand la ligne
# n'en porte pas ou porte une valeur hors vocabulaire. L'appelant retombe alors
# sur ses mots-clés, ce qui rend toute ligne historique (rôle NULL) byte-
# identique à hier.

#: Rôles JAMAIS servis par l'option « sans batterie ».
ROLES_EXCLUS_DU_PANIER_SANS = ('batterie', 'onduleur_hybride',
                               'onduleur_offgrid')

#: Rôles JAMAIS servis par l'option « avec batterie ».
ROLES_EXCLUS_DU_PANIER_AVEC = ('onduleur_reseau',)


def role_va_dans_sans(role):
    """La ligne de rôle ``role`` entre-t-elle dans le panier « sans » ?

    ``None`` = le rôle n'en dit rien (absent ou hors vocabulaire) : l'appelant
    garde ses mots-clés, qui restent le REPLI PERMANENT.
    """
    role = role_declare(role)
    if role is None:
        return None
    return role not in ROLES_EXCLUS_DU_PANIER_SANS


def role_va_dans_avec(role):
    """Miroir de :func:`role_va_dans_sans` pour le panier « avec »."""
    role = role_declare(role)
    if role is None:
        return None
    return role not in ROLES_EXCLUS_DU_PANIER_AVEC
