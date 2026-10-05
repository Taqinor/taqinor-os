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

#: I7 — la clé du bloc horaire de l'option SANS. Posée UNIQUEMENT sur un devis
#: dont les deux options portent des champs PV DIFFÉRENTS (L-2OPT) ; le bloc
#: ``etude_horaire`` décrit alors l'option AVEC. Voir
#: :func:`puissances_etude_horaire`.
CLE_ETUDE_HORAIRE_SANS = 'etude_horaire_sans'


def rafraichir_etude_horaire(devis, *, kwc=None, batterie_kwh_utile=None,
                             kwc_sans=None):
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

    I7 — ``kwc_sans`` : la puissance de l'option SANS quand elle diffère de
    celle de l'option AVEC (``kwc``). Le même moteur, les mêmes entrées lues
    UNE fois, la même estampille, rangés sous ``etude_horaire_sans``. ``None``
    (tout devis non divergent) ⇒ cette clé est RETIRÉE si elle traînait :
    un bloc qui décrit une option disparue n'est jamais laissé en place.
    """
    from apps.ventes.domain.entrees import empreinte_entrees, entrees_depuis_devis
    from apps.ventes.domain.etude_schema import MOTEUR_HORAIRE, ecrire
    from apps.ventes.etude_horaire import etude_horaire_pour_devis
    try:
        entrees = entrees_depuis_devis(devis)
        empreinte = (empreinte_entrees(entrees)
                     if entrees is not None and entrees.conso_kwh_mensuelles
                     else None)

        def _calculer(puissance):
            bloc_calcule = etude_horaire_pour_devis(
                devis, kwc=puissance, batterie_kwh_utile=batterie_kwh_utile,
                jour_reference=(entrees.jour_reference if entrees else None))
            if bloc_calcule is None:
                return None
            bloc_calcule = dict(bloc_calcule)
            bloc_calcule['_empreinte_entrees'] = empreinte
            return bloc_calcule

        bloc = _calculer(kwc)
        bloc_sans = _calculer(kwc_sans) if kwc_sans else None
        existant = getattr(devis, 'etude_params', None) or {}
        if (bloc is None and bloc_sans is None
                and 'etude_horaire' not in existant
                and CLE_ETUDE_HORAIRE_SANS not in existant):
            return None
        # QJR62 — ÉCRIVAIN UNIQUE : la fusion (et le retrait d'une clé posée à
        # ``None``, règle Z2) vit dans ``domain.etude_schema``, plus ici. Les
        # deux blocs partent dans la MÊME écriture : jamais un état où l'un
        # décrit la nouvelle composition et l'autre l'ancienne.
        ecrire(devis, proprietaire=MOTEUR_HORAIRE, etude_horaire=bloc,
               **{CLE_ETUDE_HORAIRE_SANS: bloc_sans})
        return bloc
    except Exception:  # noqa: BLE001 — jamais bloquant pour un devis
        logger.warning('etude_horaire non rafraîchie sur %s',
                       getattr(devis, 'reference', '?'), exc_info=True)
        return None


def _bloc_horaire_deja_a_jour(devis, kwc, cle='etude_horaire'):
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

    I7 — ``cle`` : le bloc à contrôler (``etude_horaire``, ou
    ``etude_horaire_sans`` pour l'option SANS d'un devis divergent). Mêmes
    trois contrôles pour l'un et l'autre.
    """
    bloc = (getattr(devis, 'etude_params', None) or {}).get(cle)
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


def puissances_etude_horaire(devis):
    """I7 — ``(kwc du bloc principal, kwc du bloc « sans » ou None)``.

    LE DÉFAUT QUE CECI FERME (audit I7, 30/09/2026). Le kWc de l'étude horaire
    se lisait sur TOUTES les lignes produit, sans regarder
    ``LigneDevis.variante``. Sur un devis L-2OPT dont les options portent des
    champs PV différents (6 panneaux « sans », 8 « avec »), le bloc était
    calculé pour 6 + 8 = 14 panneaux : une installation qu'AUCUNE option ne
    vend. ``pricing._lire_etude_horaire`` le refusait pour les deux colonnes
    (garde 2 %) et le devis retombait en silence sur « factures » /
    « estimation » — 60 blocs sur 145 en prod.

    LA DÉCISION : UN BLOC PAR OPTION, JAMAIS UN SEUL « AU CHOIX ». Un bloc
    porte UNE puissance, donc ne peut servir qu'UNE colonne ; or la donut de
    couverture lit l'option AVEC (``residential.renderer.synthese_economies``)
    pendant que le lien public télécharge l'une OU l'autre variante (L-VAR).
    Sur un devis divergent :

    * le bloc principal décrit l'option AVEC — celle que portent les
      scalaires legacy du document (``builder._scalaires_par_option`` : « un
      scalaire unique doit décrire l'option que le client lit en premier »),
      et donc la puissance de tous les lecteurs à bloc unique (courbes de la
      page publique, régime batterie, carte « pointes », profils comparés) ;
    * le bloc « sans » décrit l'option SANS (lignes communes + « sans ») — le
      compte de panneaux que montre l'écran générateur
      (``r.variante !== 'avec'``).

    UNE SEULE DÉRIVATION : CELLE DU BUILDER. Pour un panneau, son panier est
    celui de ``builder._repartir_options`` — la variante LUE par
    ``_variante_de_ligne`` (normalisée : « Sans », « AVEC » et toute valeur
    inconnue sont lues comme lui les lit), commune ⇒ les deux paniers,
    variantée ⇒ la sienne ; la puissance et le verdict « divergents » sont
    ceux de ``_scalaires_par_option``. Le bloc décrit donc exactement le kWc
    que le document chiffre. Devis NON divergent (tout l'existant) : la
    lecture d'avant, sur toutes les lignes, au bit près, et aucun second bloc.

    Même filtre que ``build_quote_data`` : lignes PRODUIT non optionnelles
    (les sections/notes n'ont pas de produit, les add-ons XSAL5 non activés ne
    comptent pas encore dans la composition réelle).

    LIMITE ASSUMÉE (revue I7) : un devis mono-option « Z1 » (onduleur hybride
    ou autonome SANS batterie) qui porterait malgré tout des panneaux
    variantés est chiffré par le builder sur la SOMME des deux paniers — le
    « compte de personne » que sa propre doctrine L-2OPT refuse. Ce bloc n'est
    pas aligné sur ce chiffre-là : il ne légitime pas une puissance qu'aucune
    option ne vend (aucun devis de prod dans ce cas au 30/09/2026 sur 77 devis
    variantés). Le défaut est côté builder, pas ici.
    """
    from apps.ventes.quote_engine.builder import (
        _scalaires_par_option, _variante_de_ligne, panneaux_et_watt_lu)
    lignes = [
        li for li in devis.lignes.select_related(
            'produit', 'produit__fiche_technique').all()
        if getattr(li, 'type_ligne', 'produit') == 'produit'
        and not getattr(li, 'optionnelle', False)
    ]
    par_option = _scalaires_par_option(
        [li for li in lignes if _variante_de_ligne(li) in ('', 'sans')],
        [li for li in lignes if _variante_de_ligne(li) in ('', 'avec')])
    if par_option['divergents']:
        return par_option['kwc_avec'], par_option['kwc_sans']
    nb_panneaux, watt = panneaux_et_watt_lu(lignes)
    kwc = (round(nb_panneaux * watt / 1000, 2)
           if nb_panneaux > 0 and watt else None)
    return kwc, None


def _blocs_horaires_deja_a_jour(devis, kwc, kwc_sans):
    """I7 — les DEUX blocs décrivent-ils déjà cette composition ?

    Une puissance ABSENTE (pas de divergence pour le bloc « sans », ou des
    panneaux sans wattage lisible) ⇒ à jour seulement si AUCUN bloc ne traîne
    sous cette clé : un bloc qui ne décrit plus aucune puissance du devis doit
    partir (règle Z2), et à l'inverse l'absence d'un bloc impossible à
    calculer n'est pas une raison de relancer le moteur à chaque sauvegarde
    (revue I7 : une option AVEC aux panneaux illisibles le relançait sans
    fin). Un devis rangé AVANT I7 n'a pas de bloc « sans » ⇒ PÉRIMÉ, un
    recalcul, une fois.
    """
    etude_params = getattr(devis, 'etude_params', None) or {}
    for puissance, cle in ((kwc, 'etude_horaire'),
                           (kwc_sans, CLE_ETUDE_HORAIRE_SANS)):
        if not puissance:
            if cle in etude_params:
                return False
        elif not _bloc_horaire_deja_a_jour(devis, puissance, cle=cle):
            return False
    return True


def blocs_horaires_perimes(devis):
    """ERR-QAC-I7-BLOCS-PERIMES-REPARATION — les blocs horaires RANGÉS dont la
    PUISSANCE ne décrit plus le devis : ``[(clé, kWc du bloc, kWc attendu)]``.

    Le correctif de code I7 empêche d'en fabriquer de nouveaux ; il ne répare
    pas les blocs déjà stockés (59 devis en prod au 30/09/2026, calculés sur la
    somme des deux options). Ce prédicat est celui de la commande
    ``rafraichir_blocs_horaires`` : il ne regarde QUE le kWc (la garde de
    fraîcheur du moteur, ``pricing._HORAIRE_TOLERANCE_KWC``) — pas
    l'empreinte des entrées, qui marquerait périmé tout bloc antérieur à une
    montée de ``VERSION_MOTEUR_ENTREES`` et ferait d'une réparation ciblée un
    recalcul de toute la base.

    * ``etude_horaire`` présent et kWc à plus de 2 % de l'option qu'il décrit
      (l'option AVEC d'un devis divergent, sinon le devis) ⇒ périmé ;
    * ``etude_horaire_sans`` présent mais aucune option SANS distincte, ou
      kWc hors tolérance ⇒ périmé ;
    * devis divergent dont le bloc principal est présent mais le bloc
      « sans » ABSENT ⇒ périmé (kWc du bloc ``None``) : rangé avant I7.

    Un bloc ABSENT n'est jamais « périmé » ici : il n'est pas lu, rien à
    réparer. Lecture seule, ne lève pas (``[]`` au moindre doute).
    """
    try:
        from apps.ventes.quote_engine.pricing import _HORAIRE_TOLERANCE_KWC
        etude_params = getattr(devis, 'etude_params', None) or {}
        principal = etude_params.get('etude_horaire')
        if not isinstance(principal, dict):
            return []
        kwc, kwc_sans = puissances_etude_horaire(devis)
        perimes = []

        def _ecart(bloc, attendu):
            try:
                kwc_bloc = float(bloc.get('kwc') or 0)
            except (TypeError, ValueError):
                kwc_bloc = 0.0
            if not attendu or kwc_bloc <= 0:
                return kwc_bloc or None, True
            return kwc_bloc, (abs(kwc_bloc - float(attendu)) / float(attendu)
                              > _HORAIRE_TOLERANCE_KWC)

        kwc_bloc, perime = _ecart(principal, kwc)
        if perime and kwc:
            perimes.append(('etude_horaire', kwc_bloc, kwc))
        sans = etude_params.get(CLE_ETUDE_HORAIRE_SANS)
        if isinstance(sans, dict):
            kwc_bloc_sans, perime_sans = _ecart(sans, kwc_sans)
            if perime_sans:
                perimes.append((CLE_ETUDE_HORAIRE_SANS, kwc_bloc_sans,
                                kwc_sans))
        elif kwc_sans:
            perimes.append((CLE_ETUDE_HORAIRE_SANS, None, kwc_sans))
        return perimes
    except Exception:  # noqa: BLE001 — lecture de diagnostic, jamais bloquante
        logger.warning('blocs_horaires_perimes indisponible sur %s',
                       getattr(devis, 'reference', '?'), exc_info=True)
        return []


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

    La puissance kWc vient EXCLUSIVEMENT de :func:`puissances_etude_horaire`
    (I7) : ``quote_engine.builder.panneaux_et_watt_lu`` sur le MÊME filtre de
    lignes que ``build_quote_data`` (lignes produit, non optionnelles), OPTION
    PAR OPTION quand les deux champs PV divergent — jamais une seconde règle de
    dérivation (l'incident DEV-202608-0007 est précisément né de deux
    dérivations qui divergent ; I7, de la somme de deux options que personne ne
    vend). Sans panneau lisible, le rafraîchissement
    est appelé QUAND MÊME avec ``kwc=None`` : c'est ``rafraichir_etude_horaire``
    lui-même qui RETIRE alors le bloc devenu périmé plutôt que de le laisser
    décrire une installation qui n'existe plus (règle Z2 appliquée à la
    fraîcheur) — jamais un bloc laissé en place au hasard.

    ``force`` — recalculer MÊME si la composition n'a pas bougé. Quand elle est
    inchangée, ``_bloc_horaire_deja_a_jour`` court-circuite un calcul qui peut
    coûter un appel PVGIS.

    QJR243 (e) — CE PARAGRAPHE DOCUMENTAIT LE CONTRAT D'AVANT QJR47, ET IL
    ÉTAIT FAUX DES DEUX CÔTÉS. Il affirmait que les chemins « devis »
    (``perform_update``, ``replace-lines``) passent ``force=True`` pour couvrir
    un changement de FACTURES ou de profil : QJR47 a RETIRÉ ce ``force`` des
    deux — depuis QJR43/QJR44, c'est l'EMPREINTE DES ENTRÉES qui décide (le
    profil client entre dedans, donc un vrai changement recalcule tout seul et
    un faux ne coûte plus trois balayages). ``force=True`` ne subsiste que là
    où l'empreinte ne peut RIEN dire : les COPIES de devis (``creation``,
    ``cycle_vie``, ``gammes``, et ``/variante`` depuis QJR202), dont les clés
    dérivées viennent d'être purgées.

    Ne lève JAMAIS, ne touche NI le statut NI les lignes NI les totaux du devis
    (règle #4) : appelable en toute sécurité juste après une sauvegarde.
    """
    try:
        mode = (getattr(devis, 'mode_installation', None) or '').strip().lower()
        if mode != 'residentiel':
            return None
        kwc, kwc_sans = puissances_etude_horaire(devis)
        if not force and _blocs_horaires_deja_a_jour(devis, kwc, kwc_sans):
            return (devis.etude_params or {}).get('etude_horaire')
        return rafraichir_etude_horaire(devis, kwc=kwc, kwc_sans=kwc_sans)
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
            charges_fixes_mad=entrees['charges_fixes_mad'],
            # QJR606 — la phase et la gamme du devis, lues par l'adaptateur.
            phase=entrees['phase'],
            gamme_nom_devis=entrees['gamme_nom_devis'],
            # ERR-QJR605 — site isolé et paires MPPT du devis.
            hors_reseau=entrees['hors_reseau'],
            mppt_paires=entrees['mppt_paires'])
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
        # CIQ119 — commercial / industriel : l'étude suit les LIGNES facturées
        # (taille donnée, aucun redimensionnement) ; no-op sur tout autre marché.
        'etude_ci': _rafraichir_etude_ci(devis, force=force),
    }


def _rafraichir_etude_ci(devis, *, force=False):
    from apps.ventes.domain.etude_ci import rafraichir_etude_ci_devis
    return rafraichir_etude_ci_devis(devis, force=force)


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
#: I7 (30/09/2026) — SEPT clés depuis : le bloc horaire de l'option SANS suit
#: le bloc ``etude_horaire``, pour la même raison.
CLES_DERIVEES_NON_COPIEES = (
    'production_annuelle',
    'economies_annuelles',
    'payback',
    'etude_horaire',
    CLE_ETUDE_HORAIRE_SANS,
    'dimensionnement',
    'profils_comparatifs',
    # QJR591 — la ville de chiffrage figée : une copie se rechiffre sur la
    # ville de SON lead, jamais sur celle de la source.
    'ville_calcul',
    # CIQ117 — les dérivées exclusives du moteur C&I : une copie/V2 les
    # RECALCULE sur sa propre composition, jamais héritées du source.
    'etude_ci',
    'production_figee',
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

    QJR202 (31/08/2026) — QUATRE APPELANTS, PLUS TROIS. Le chemin de copie au
    niveau vue ``/variante`` (``views/devis.dupliquer_variante``) recopiait
    encore ``etude_params`` verbatim sur des devis dont il venait de multiplier
    les quantités : il passe désormais ici, suivi d'un
    :func:`rafraichir_etudes_du_devis` forcé, comme les trois autres.
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
