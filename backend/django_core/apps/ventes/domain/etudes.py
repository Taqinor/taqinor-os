"""Études — les rafraîchisseurs, et le cliché de marge.

Les quatre études d'un devis et ce qui les remet à jour : l'étude horaire
(calcul, prédicat de fraîcheur, écriture sur le devis), le bloc
`dimensionnement`, l'orchestrateur `rafraichir_etudes_du_devis`, et le
cliché de marge interne (`compute_marge_snapshot` /
`refresh_marge_snapshot`).

DEUX PRÉCISIONS SUR LE PÉRIMÈTRE DE QJR75 :

* `refresh_etude_consistency`, que la tâche cite encore, N'EXISTE PLUS —
  QJR48 l'a SUPPRIMÉE (avec ses deux récepteurs) le 29/08/2026, et
  `tests/test_qjr_coherence_etude.py` garde qu'elle ne revienne pas. Il n'y
  avait donc rien à déplacer ;
* `profil_reel_existe` a été SUPPRIMÉE par QJR107 le 30/08/2026 (sa
  suppression avait été extraite de QJR75 par R4-C.5 — une tâche déplace OU
  corrige, jamais les deux). Elle ne conditionnait plus AUCUN dimensionnement
  depuis l'ordre fondateur du 29/08 (« ALL sizing should go through the new
  sizing tool ») et un balayage du dépôt ne trouvait plus AUCUN appelant :
  ni production, ni test — seulement sa définition, son ré-export et le pin
  de surface. Voir la note de suppression plus bas.

QJR75 (M3) — DÉPLACEMENT PUR depuis ``apps/ventes/services.py``. Les corps
sont recopiés à l'identique ; la SEULE retouche est mécanique et obligatoire :
un corps descendu d'un cran (`apps/ventes/` → `apps/ventes/domain/`) voit son
point de départ relatif descendre avec lui, donc `from .x import y` devient
`from ..x import y` — MÊME cible (`apps.ventes.x`), au caractère près.

ORDRE DE CHARGEMENT (voir ``domain/bordereau.py``) : ``services.py`` importe
``domain/`` à la toute fin ; un module de ``domain/`` importe en BAS de fichier
les noms qu'il lit ailleurs. Quel que soit le module chargé le premier, chaque
attribut lu à l'import existe déjà.

NOM DU LOGGER FIGÉ sur ``apps.ventes.services`` : des tests capturent ce nom
précis (``assertLogs('apps.ventes.services')``). Un déplacement pur ne change
pas le nom sous lequel une ligne de journal est émise.
"""
import logging

logger = logging.getLogger("apps.ventes.services")


def rafraichir_etude_horaire(devis, *, kwc=None, batterie_kwh_utile=None):
    """CJ2a — (re)calcule ``etude_params['etude_horaire']`` et le RANGE.

    Point d'entrée unique pour poser le bloc canonique sur un devis. Écrit avec
    ``update_fields=['etude_params']`` UNIQUEMENT : ce chemin ne peut donc
    toucher NI le statut du devis, NI ses lignes, NI ses totaux (règle #4).

    Bloc non calculable (pas de facture, pas de localisation PVGIS, pas de
    puissance) ⇒ la clé est RETIRÉE plutôt que laissée périmée, et l'appelant
    retombe sur le forfait étiqueté (règle Z2). Ne lève jamais : une étude
    n'empêche pas d'enregistrer un devis.

    QJR44 — le bloc RANGÉ porte en plus ``_empreinte_entrees`` (l'estampille
    des entrées du moteur). La SORTIE du moteur
    (``etude_horaire_pour_devis``) reste byte-identique : l'estampille est
    posée ici, sur la copie persistée, jamais dans le moteur.

    QJR45 — les entrées sont lues UNE fois : le ``jour_reference`` qui part au
    moteur est EXACTEMENT celui que l'empreinte trace (une seconde lecture
    d'horloge pourrait tomber le lendemain et estampiller une date qui n'a pas
    servi).
    """
    from apps.ventes.domain.entrees import empreinte_entrees, entrees_depuis_devis
    from apps.ventes.domain.etude_schema import MOTEUR_HORAIRE, ecrire
    from apps.ventes.etude_horaire import etude_horaire_pour_devis
    try:
        entrees = entrees_depuis_devis(devis)
        bloc = etude_horaire_pour_devis(
            devis, kwc=kwc, batterie_kwh_utile=batterie_kwh_utile,
            jour_reference=(entrees.jour_reference if entrees else None))
        if bloc is None:
            if 'etude_horaire' not in (getattr(devis, 'etude_params', None)
                                       or {}):
                return None
        else:
            bloc = dict(bloc)
            bloc['_empreinte_entrees'] = (
                empreinte_entrees(entrees)
                if entrees is not None and entrees.conso_kwh_mensuelles
                else None)
        # QJR62 — ÉCRIVAIN UNIQUE : la fusion (et le retrait d'une clé posée à
        # ``None``, règle Z2) vit dans ``domain.etude_schema``, plus ici.
        ecrire(devis, proprietaire=MOTEUR_HORAIRE, etude_horaire=bloc)
        return bloc
    except Exception:  # noqa: BLE001 — jamais bloquant pour un devis
        logger.warning('etude_horaire non rafraîchie sur %s',
                       getattr(devis, 'reference', '?'), exc_info=True)
        return None


def _bloc_horaire_deja_a_jour(devis, kwc):
    """CJ2b — le bloc rangé sur ce devis décrit-il DÉJÀ cette composition ?

    RAISON D'ÊTRE : ÉVITER UN RECALCUL INUTILE DANS UN HANDLER HTTP. Un calcul
    horaire résout la localisation PVGIS du chantier, ce qui peut coûter un
    appel réseau (cache système de 30 jours, mais un cache froid part sur le
    réseau). Le déclencher à CHAQUE ligne ajoutée/modifiée/retirée ferait payer
    cette latence à l'utilisateur pour un bloc qui n'aurait pas bougé d'un
    chiffre — c'est exactement le genre d'appel qu'on ne veut pas voir
    apparaître dans une boucle d'édition.

    LE CRITÈRE EST CELUI DU MOTEUR, PAS UN SECOND. La tolérance vient de
    ``pricing._HORAIRE_TOLERANCE_KWC`` : ce qui rend un bloc PÉRIMÉ pour le
    document est exactement ce qui le rend À RECALCULER ici. Deux seuils
    différents laisseraient une zone où le document refuse un bloc que ce
    garde-fou juge encore frais — donc un devis sans économies, sans raison
    visible.

    La capacité batterie compte AUSSI : elle change l'autoconsommation et donc
    toutes les économies, sans toucher au kWc (remplacer une batterie 5 kWh par
    une 10 kWh ne bouge pas la puissance PV).

    QJR44 — L'EMPREINTE DES ENTRÉES S'AJOUTE, ELLE NE REMPLACE RIEN. Les deux
    contrôles ci-dessus lisent la COMPOSITION (kWc, capacité batterie) ; ils
    ne voient PAS un changement de PROFIL (facture, localisation, occupation,
    équipements), qui change pourtant toutes les économies du bloc. Le bloc
    n'est donc à jour que si, EN PLUS, l'estampille ``_empreinte_entrees``
    qu'il porte égale l'empreinte des entrées d'aujourd'hui. Un bloc sans
    estampille (antérieur à QJR44) est PÉRIMÉ — un recalcul, une fois.
    La tolérance ``pricing._HORAIRE_TOLERANCE_KWC`` reste celle du moteur :
    deux seuils différents rouvriraient la zone où un devis se retrouve sans
    économies sans raison visible.

    Renvoie ``False`` au moindre doute — on préfère recalculer pour rien que
    servir un bloc qui ne décrit plus le devis.
    """
    bloc = (getattr(devis, 'etude_params', None) or {}).get('etude_horaire')
    if not isinstance(bloc, dict) or not kwc:
        return False
    try:
        from apps.ventes.quote_engine.pricing import _HORAIRE_TOLERANCE_KWC
        kwc_bloc = float(bloc.get('kwc') or 0)
        if kwc_bloc <= 0:
            return False
        if abs(kwc_bloc - float(kwc)) / float(kwc) > _HORAIRE_TOLERANCE_KWC:
            return False
        from apps.ventes.etude_horaire import capacite_batterie_du_devis
        actuelle = capacite_batterie_du_devis(devis)
        rangee = bloc.get('batterie_kwh_utile')
        if (actuelle is None) != (rangee is None):
            return False
        if actuelle is not None and abs(float(actuelle) - float(rangee)) > 0.05:
            return False
        from apps.ventes.domain.entrees import empreinte_entrees_du_devis
        empreinte = empreinte_entrees_du_devis(devis)
        if not empreinte or bloc.get('_empreinte_entrees') != empreinte:
            return False
        return True
    except Exception:  # noqa: BLE001 — au moindre doute, on recalcule
        return False


def rafraichir_etude_horaire_devis(devis, *, force=False):
    """CJ2b — pose le bloc horaire canonique après une écriture SERVEUR d'un
    devis résidentiel (lignes ajoutées/modifiées/retirées, calepinage
    resynchronisé, devis mis à jour).

    Avant CJ2b, ``rafraichir_etude_horaire`` n'était appelé QUE par l'auto-devis
    (voir plus haut) : un devis résidentiel ÉDITÉ ensuite — panneau ajouté ou
    retiré, remplacement d'onduleur — gardait un bloc ``etude_horaire`` PÉRIMÉ
    ou ABSENT, et la page/le PDF retombaient alors sur le modèle « facture »/
    forfait alors qu'un calcul heure par heure exact restait possible. Ce point
    d'entrée unique referme la boucle depuis les chemins d'écriture du devis
    (``DevisViewSet.perform_update``, ``sync-layout``, ``LigneDevisViewSet``).

    RÉSIDENTIEL STRICT (``mode_installation == 'residentiel'``), volontairement
    PLUS STRICT que ``quote_engine.residential.renderer.is_residential`` (qui
    traite un mode VIDE comme résidentiel — un défaut d'AFFICHAGE PDF choisi
    pour ne jamais perdre le rendu d'un devis, pas une preuve que ce devis EST
    résidentiel). Poser un calcul horaire sur un devis dont le marché n'a
    simplement pas encore été choisi calculerait une étude sur une hypothèse
    non confirmée ; un devis dont le mode passe plus tard à 'residentiel'
    reçoit son bloc au prochain enregistrement — aucune perte, un calcul
    seulement différé.

    La puissance kWc vient EXCLUSIVEMENT de
    ``quote_engine.builder.panneaux_et_watt_lu``, sur le MÊME filtre de lignes
    que ``build_quote_data`` (lignes produit, non optionnelles) — jamais une
    seconde règle de dérivation (l'incident DEV-202608-0007 est précisément né
    de deux dérivations qui divergent). Sans panneau lisible, le rafraîchissement
    est appelé QUAND MÊME avec ``kwc=None`` : c'est ``rafraichir_etude_horaire``
    lui-même qui RETIRE alors le bloc devenu périmé plutôt que de le laisser
    décrire une installation qui n'existe plus (règle Z2 appliquée à la
    fraîcheur) — jamais un bloc laissé en place au hasard.

    ``force`` — recalculer MÊME si la composition n'a pas bougé. Les chemins
    « lignes » (ajout/modification/suppression, calepinage) ne touchent QUE la
    composition : quand celle-ci est inchangée, le bloc l'est aussi et
    ``_bloc_horaire_deja_a_jour`` court-circuite un calcul qui peut coûter un
    appel PVGIS. Les chemins « devis » (``perform_update``, ``replace-lines``)
    peuvent en revanche avoir changé les FACTURES ou le profil dans
    ``etude_params`` — grandeurs qu'aucune lecture de lignes ne verrait : ils
    passent ``force=True`` et acceptent le recalcul.

    Ne lève JAMAIS, ne touche NI le statut NI les lignes NI les totaux du devis
    (règle #4) : appelable en toute sécurité juste après une sauvegarde.
    """
    try:
        mode = (getattr(devis, 'mode_installation', None) or '').strip().lower()
        if mode != 'residentiel':
            return None
        from apps.ventes.quote_engine.builder import panneaux_et_watt_lu
        # Même filtre que build_quote_data : lignes PRODUIT non optionnelles
        # (les sections/notes n'ont pas de produit, les add-ons XSAL5 non
        # activés ne comptent pas encore dans la composition réelle).
        lignes = [
            li for li in devis.lignes.select_related(
                'produit', 'produit__fiche_technique').all()
            if getattr(li, 'type_ligne', 'produit') == 'produit'
            and not getattr(li, 'optionnelle', False)
        ]
        nb_panneaux, watt = panneaux_et_watt_lu(lignes)
        kwc = (round(nb_panneaux * watt / 1000, 2)
               if nb_panneaux > 0 and watt else None)
        if not force and _bloc_horaire_deja_a_jour(devis, kwc):
            return (devis.etude_params or {}).get('etude_horaire')
        return rafraichir_etude_horaire(devis, kwc=kwc)
    except Exception:  # noqa: BLE001 — un rafraîchissement raté n'empêche
        # jamais une sauvegarde de devis/ligne.
        logger.warning('rafraichir_etude_horaire_devis indisponible sur %s',
                       getattr(devis, 'reference', '?'), exc_info=True)
        return None


def rafraichir_dimensionnement_devis(devis, *, force=False):
    """T5 (24/08/2026) — pose ``etude_params['dimensionnement']`` sur un devis
    RÉSIDENTIEL, même point d'entrée-esprit que
    :func:`rafraichir_etude_horaire_devis` (RÉSIDENTIEL STRICT, mêmes chemins
    d'écriture) mais pour le TABLEAU de dimensionnement
    (``apps.ventes.dimensionnement.recommander_taille``) plutôt que le bloc
    horaire d'UNE taille : c'est ce que lit désormais le moteur PDF
    (``ETUDE['dimensionnement']``) et le payload public (T4 — falaise,
    tranche visée, régime batterie).

    Contrairement à ``rafraichir_etude_horaire_devis``, aucune donnée de
    LIGNES n'entre dans ce calcul (le tableau balaye TOUTES les tailles
    candidates, il ne lit pas la composition posée).

    QJR43 — L'EMPREINTE DES ENTRÉES DÉCIDE, PLUS LA PRÉSENCE DE LA CLÉ. Le
    bloc rangé porte ``_empreinte`` (``domain.entrees.empreinte_entrees``) et
    n'est recalculé QUE si l'empreinte des entrées d'aujourd'hui en diffère.
    Avant, le test était ``'dimensionnement' in etude_params`` : corriger la
    facture d'hiver, l'occupation ou les équipements du lead ne périmait RIEN,
    et le tableau servi restait celui de la toute première lecture. Un bloc
    SANS ``_empreinte`` (tout devis antérieur à QJR43) est traité comme PÉRIMÉ
    — un recalcul, une seule fois, par devis existant.

    ``force`` reste accepté et signifie désormais « recalcule même si
    l'empreinte concorde » ; il devient inutile sur les chemins qui ne
    changeaient que la composition (QJR47 les retire un par un).

    Ne lève JAMAIS, ne touche NI le statut NI les lignes NI les totaux
    (règle #4). ``None`` (⇒ clé ABSENTE) quand le profil n'est pas
    exploitable (pas de facture, pas de société, catalogue incomplet,
    localisation non résolue) — jamais un tableau inventé.
    """
    try:
        from apps.ventes.domain.entrees import empreinte_entrees
        from apps.ventes.domain.etude_schema import (
            MOTEUR_DIMENSIONNEMENT, ecrire)

        # P2-A / QJR42 — LECTURE UNIQUE des entrées : l'échelle de paliers
        # batterie part exactement des mêmes. Elle est faite AVEC contexte
        # parce que l'empreinte a besoin de la localisation, de l'occupation
        # et des équipements — c'est le prix (une lecture, pas un balayage)
        # d'un cache qui se périme vraiment, et il remplace les DEUX lectures
        # que faisait l'ancien chemin quand il recalculait.
        entrees = entrees_dimensionnement_du_devis(devis)
        if entrees is None:
            return None
        etude_params = entrees['etude_params']
        conso = entrees['conso_kwh_mensuelles']
        if not conso:
            if not force and 'dimensionnement' not in etude_params:
                return None
            # QJR62 — ÉCRIVAIN UNIQUE : ``None`` RETIRE la clé (règle Z2).
            ecrire(devis, proprietaire=MOTEUR_DIMENSIONNEMENT,
                   dimensionnement=None)
            return None

        empreinte = empreinte_entrees(entrees)
        bloc = etude_params.get('dimensionnement')
        if (not force and isinstance(bloc, dict)
                and bloc.get('_empreinte') == empreinte):
            return bloc

        from apps.ventes.dimensionnement import recommander_taille
        resultat = recommander_taille(
            company=entrees['company'], conso_kwh_mensuelles=conso,
            ville=entrees['ville'], lat=entrees['lat'], lon=entrees['lon'],
            occupation=entrees['occupation'],
            equipements=entrees['equipements'],
            source_conso=entrees['source_conso'],
            jour_reference=entrees['jour_reference'],
            # QJR46 — le barème de la SOCIÉTÉ, celui que le devis appliquera.
            tranches=entrees['tranches'],
            charges_fixes_mad=entrees['charges_fixes_mad'])
        resultat['_empreinte'] = empreinte
        ecrire(devis, proprietaire=MOTEUR_DIMENSIONNEMENT,
               dimensionnement=resultat)
        return resultat
    except Exception:  # noqa: BLE001 — un rafraîchissement raté n'empêche
        # jamais une sauvegarde de devis/ligne.
        logger.warning('rafraichir_dimensionnement_devis indisponible sur %s',
                       getattr(devis, 'reference', '?'), exc_info=True)
        return None


def rafraichir_etudes_du_devis(devis, *, force=False):
    """L-1V (24/08/2026) — LES QUATRE ÉTUDES D'UN DEVIS, EN UN SEUL GESTE.

    LE TROU QUE CECI BOUCHE. Un devis porte quatre études dérivées de ses
    lignes : le bloc horaire, le tableau de dimensionnement, les profils
    comparatifs et la conception électrique. Trois chemins d'écriture les
    posaient — ``atomic`` et ``replace-lines`` en rafraîchissaient les QUATRE
    (deux listes recopiées à la main, donc deux occasions d'en oublier une),
    tandis que ``LigneDevisViewSet`` (ajout/modification/suppression d'UNE
    ligne) n'en rafraîchissait qu'UNE : le bloc horaire. Modifier une ligne
    depuis l'écran de devis faisait donc bouger le graphe horaire de la page
    client SANS toucher à la conception électrique — et le client voyait un
    schéma unifilaire décrivant une composition qui n'existait plus. Une seule
    fonction, appelée par TOUS les chemins : on ne peut plus en oublier une.

    Chacune est BEST-EFFORT et indépendante (chaque rafraîchisseur avale déjà
    ses propres erreurs) : une étude en échec n'empêche jamais les trois autres,
    et n'annule JAMAIS l'enregistrement du devis ou de la ligne qui l'a
    déclenchée. Aucun statut, aucune ligne, aucun prix n'est touché (règle #4).

    L'ORDRE COMPTE, et il est celui que ``replace-lines`` avait déjà : le
    dimensionnement après le bloc horaire, les profils comparatifs après le
    dimensionnement (le profil RÉEL réutilise alors le tableau qui vient d'être
    calculé au lieu d'en refaire un), la conception électrique en dernier.

    Rend le dict des quatre résultats (``None`` pour celles qui n'ont rien
    produit) — pour un appelant qui veut savoir, jamais pour décider.
    """
    from apps.ventes.profils_comparatifs import (
        rafraichir_profils_comparatifs_devis)
    from apps.ventes.electrical_service import (
        rafraichir_conception_electrique_devis)

    return {
        'etude_horaire': rafraichir_etude_horaire_devis(devis, force=force),
        'dimensionnement': rafraichir_dimensionnement_devis(devis,
                                                            force=force),
        'profils_comparatifs': rafraichir_profils_comparatifs_devis(
            devis, force=force),
        # Idempotente par empreinte : mêmes entrées ⇒ aucune écriture.
        'conception_electrique': rafraichir_conception_electrique_devis(devis),
    }


# ── QJR117 — UNE COPIE DE DEVIS NE SERT PAS LES CHIFFRES DU SOURCE ──────────
#
# Constats CS4 / CS5 / CS6 (audit du 30/08/2026), vérifiés en code : les trois
# chemins de copie recopiaient ``etude_params`` TEL QUEL et n'appelaient AUCUN
# des quatre rafraîchisseurs.
#
#   · CS4 — ``dupliquer_devis`` ne copie PAS ``roof_layout``, donc le recalage
#     par layout (``quote_engine/builder``, ``_recalage = puissance_kwc /
#     _kwc_layout``) ne s'exécute pas sur la copie : le moteur prenait
#     ``production_annuelle``/``economies_annuelles`` VERBATIM et écrasait le
#     ROI qu'il venait de calculer sur les lignes réelles de la copie.
#   · CS5 — la gamme sœur recevait le bloc chiffré du FRÈRE alors que sa
#     docstring annonce « chaque gamme a sa composition et ses prix PROPRES ».
#   · CS6 — le renouvellement RE-TARIFE les lignes au catalogue courant et
#     gardait un payback calculé sur les ANCIENS prix.
#
# Et rien ne rattrapait : l'édition de ligne appelle ``rafraichir_etudes_du_
# devis`` SANS ``force``, or le dimensionnement se court-circuite sur empreinte
# concordante.
#
# CE QUI EST PURGÉ, ET CE QUI NE L'EST PAS. On retire les six clés DÉRIVÉES qui
# mêlent la PRODUCTION ou l'ARGENT à une composition qui peut diverger — celles
# que la copie ne peut pas garantir. On garde toute la CONFIGURATION (ce que le
# commercial a saisi : factures réelles, toiture, scénario, gamme, entrées
# agricoles / industrielles), qu'aucun serveur ne saurait reconstruire.
#
# Les autres clés DÉRIVÉES du schéma restent délibérément :
#   · ``puissance_kwc`` décrit la composition, qui est clonée à l'identique ;
#   · les dérivées POMPAGE (``debit_hmt_m3h``, ``m3_jour``, ``champ_kwc``) et
#     les taux industriels (``taux_autoconso``, ``taux_couverture``,
#     ``injection_*``) décrivent le SITE du client et n'ont AUCUN rafraîchisseur
#     serveur : les purger supprimerait l'étude sans la remplacer. Seule celle
#     qui dépend du PRIX — ``payback`` — part avec les cinq autres, parce que
#     c'est précisément le prix que le renouvellement change.
#
# Aucune de ces six clés absentes ne fabrique un chiffre en aval : le moteur
# recalcule depuis les lignes (``calculate_savings_roi``) ou OMET la carte
# (``_card_if``, ``ind_masquer_economies``). C'est la règle « zéro chiffre
# inventé » appliquée à la copie : mieux vaut recalculer, ou taire.

#: QJR117 — les clés DÉRIVÉES qu'une COPIE de devis ne reprend jamais.
#: Chacune est déclarée ``DERIVEE`` dans ``domain/etude_schema.SCHEMA`` (un
#: test le vérifie : une clé renommée au schéma ne peut plus être purgée « à
#: côté » en silence).
CLES_DERIVEES_NON_COPIEES = (
    'production_annuelle',
    'economies_annuelles',
    'payback',
    'etude_horaire',
    'dimensionnement',
    'profils_comparatifs',
)

#: QJR136 / ES13 — L'ATTRIBUTION PUBLICITAIRE NE SE RECOPIE PAS NON PLUS.
#: ``etude_params['attribution']`` est le snapshot first-touch (fbclid/UTM) que
#: ``_persist_attribution`` pose à l'ACCEPTATION, et il SORT immédiatement si
#: la clé existe déjà. Un devis renouvelé qui hérite du snapshot de sa source
#: recrédite donc le MÊME clic publicitaire une seconde fois — et la
#: déduplication Meta ne rattrape rien, l'``event_id`` portant la référence,
#: qui a changé. C'est le patron « double application ».
#: Elle est listée à part des six clés d'étude (QJR117) parce que ce n'est pas
#: une valeur d'étude : c'est une trace de provenance, et le motif est le
#: comptage publicitaire, pas la fraîcheur d'un chiffre.
#: PORTÉE EXACTE, sans exagérer : la copie repart SANS snapshot hérité. Si elle
#: est acceptée à son tour, ``_persist_attribution`` en reposera un, relu du
#: LEAD À CE MOMENT-LÀ — une valeur d'aujourd'hui plutôt qu'un héritage figé.
#: Une déduplication publicitaire complète demanderait en plus une DATE DE CLIC
#: conservée (constat ES10), qui exige un champ neuf : hors de ce lot.
CLES_ATTRIBUTION_NON_COPIEES = ('attribution',)

#: Ce qu'une copie de devis ne reprend JAMAIS, toutes raisons confondues.
CLES_NON_COPIEES = (
    CLES_DERIVEES_NON_COPIEES + CLES_ATTRIBUTION_NON_COPIEES)


def etude_params_pour_copie(etude_params):
    """QJR117 / QJR136 — le bloc d'étude qu'une COPIE de devis reçoit.

    La CONFIGURATION du source, jamais ses chiffres dérivés
    (:data:`CLES_DERIVEES_NON_COPIEES`) ni son snapshot d'attribution
    publicitaire (:data:`CLES_ATTRIBUTION_NON_COPIEES`). Rend ``None`` quand il
    ne reste rien — ``Devis.etude_params`` est ``null=True`` et une clé absente
    vaut « pas calculable » (règle Z2), donc un devis sans étude reste sans
    étude.

    Rend TOUJOURS un dict NEUF : ``etude_params=devis.etude_params`` partageait
    la même référence entre source et copie, et une mutation de l'un fuyait sur
    l'autre (le dépôt nomme ce piège dans ``dupliquer_variante``).
    """
    bloc = {cle: valeur for cle, valeur in dict(etude_params or {}).items()
            if cle not in CLES_NON_COPIEES}
    return bloc or None


# ════════════════════════════════════════════════════════════════════════════
# QJR48 (29/08/2026) — ``refresh_etude_consistency`` A ÉTÉ SUPPRIMÉE
# ════════════════════════════════════════════════════════════════════════════
# Elle écrivait ``etude_params['payback_annees']`` (TTC canonique ÷ économies
# annuelles stockées) à CHAQUE sauvegarde et à CHAQUE suppression de
# ``LigneDevis``, plus à chaque changement de remise globale — soit un
# ``Devis.save()`` par ligne PLUS une recomputation complète d'``option_totaux``.
#
# CETTE CLÉ N'AVAIT AUCUN LECTEUR. Le balayage du dépôt (joint au commit, et
# rejoué par ``tests/test_qjr_coherence_etude.py`` pour qu'il ne puisse pas
# repartir en silence) ne trouve ``payback_annees`` QUE dans des blocs qui
# portent leur PROPRE payback et le calculent eux-mêmes : les cartes
# ``offres_tailles``, les paliers de ``dimensionnement``, les comparateurs
# ``compta``/``parametres``. Le PDF et la page publique lisent, eux, la clé
# ``payback`` (industriel/commercial), recalculée par ``quote_engine/builder``
# — jamais ``payback_annees``.
#
# Les deux récepteurs QX24 (``apps/ventes/receivers.py``) ont été retirés dans
# le même commit : aucun chemin ne subsiste. Aucun chiffre rendu au client ne
# change.


def compute_marge_snapshot(devis):
    """QX23be — marge HT interne figée d'un devis (usage MANAGER UNIQUEMENT).

    marge = Σ(HT ligne, option acceptée si applicable) − Σ(qté × prix_achat).
    Renvoie un Decimal, ou None si AUCUN produit lié ne porte de prix_achat
    exploitable (on ne veut pas figer une fausse marge = 100 % du CA). Best-
    effort : jamais d'exception remontée.

    RÈGLE #4 : ``prix_achat`` ne quitte JAMAIS cette fonction interne — le
    résultat (une marge) n'est exposé qu'au responsable dans la vue liste,
    jamais dans un PDF/une sortie client.
    """
    from decimal import Decimal
    try:
        from apps.ventes.utils.options import option_lines
        lignes = option_lines(devis)
    except Exception:  # noqa: BLE001
        try:
            lignes = list(devis.lignes.select_related('produit').all())
        except Exception:  # noqa: BLE001
            return None
    ht = Decimal('0')
    cout = Decimal('0')
    a_un_cout = False
    for li in lignes:
        try:
            ht += Decimal(str(li.total_ht))
        except Exception:  # noqa: BLE001
            continue
        produit = getattr(li, 'produit', None)
        prix_achat = getattr(produit, 'prix_achat', None) if produit else None
        if prix_achat is not None and Decimal(str(prix_achat)) > 0:
            a_un_cout = True
            cout += Decimal(str(li.quantite)) * Decimal(str(prix_achat))
    if not a_un_cout:
        return None
    return (ht - cout).quantize(Decimal('0.01'))


def refresh_marge_snapshot(devis):
    """QX23be — recalcule et persiste ``marge_snapshot`` (best-effort)."""
    try:
        marge = compute_marge_snapshot(devis)
        if devis.marge_snapshot != marge:
            devis.marge_snapshot = marge
            devis.save(update_fields=['marge_snapshot'])
    except Exception as exc:  # noqa: BLE001 — jamais bloquant
        logger.warning('QX23: marge_snapshot échoué pour devis %s : %s',
                       getattr(devis, 'reference', '?'), exc)


# ── QJR76 : les ENTRÉES des études ──────────────────────────────────────────
# `entrees_dimensionnement_du_devis` alimente `rafraichir_dimensionnement_devis`
# (plus haut) : il vivait dans `services.py`, ce module l'importait par un pont.
#
# QJR107 (30/08/2026) — `profil_reel_existe` A ÉTÉ SUPPRIMÉE D'ICI. Elle
# répondait « ce lead porte-t-il autre chose qu'une facture ? » (présence en
# journée, équipement déclaré avec sa grandeur, douze factures réelles) et
# gardait autrefois l'entrée du chemin horaire dans `build_devis_auto`. Depuis
# l'ordre fondateur du 29/08/2026 — « ALL sizing should go through the new
# sizing tool » — TOUT lead se dimensionne par le moteur (facture d'hiver
# inversée au barème ONEE + `courbes_journalieres.DEFAUT_RESIDENTIEL`,
# QJR10/D4), donc elle ne conditionnait plus rien. Un balayage du dépôt au
# moment de la suppression ne trouvait AUCUN appelant : ni production, ni
# test — seulement sa définition, son ré-export dans `services.py` et
# l'entrée du pin de surface, tous trois retirés dans le même commit.
#
# NE PAS LA RÉINTRODUIRE POUR DÉCIDER D'UNE TAILLE : un prédicat « ce lead
# a-t-il un vrai profil ? » redeviendrait immédiatement une porte de
# dimensionnement, c'est-à-dire un second dimensionneur — exactement ce que
# l'ordre du 29/08 interdit. Une lecture de QUALITÉ DE FICHE (score du lead,
# complétude du questionnaire) appartient à `apps/crm`, pas ici.


def entrees_dimensionnement_du_devis(devis, *, contexte=True):
    """RÉ-EXPORT (QJR42) de ``apps.ventes.domain.entrees.entrees_depuis_devis``.

    Le corps a été DÉPLACÉ TEL QUEL dans ``domain/entrees.py``, où il partage
    désormais sa forme (:class:`~apps.ventes.domain.entrees.EntreesMoteur`)
    avec l'adaptateur LEAD du chemin auto-devis / tunnel. Ce nom reste ici
    parce que trois modules l'importent depuis ``services``
    (``dimensionnement``, ``offres_tailles``, et ce module) — le pin
    ``tests/test_services_surface.py`` le vérifie.

    ``contexte=False`` est CONSERVÉ : il saute les lectures de localisation /
    occupation / équipements pour l'appelant qui n'a besoin que de la GARDE
    (voir la docstring de l'original).
    """
    from apps.ventes.domain.entrees import entrees_depuis_devis
    return entrees_depuis_devis(devis, contexte=contexte)
