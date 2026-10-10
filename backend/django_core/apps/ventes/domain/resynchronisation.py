"""Resynchronisation — le devis suit le layout 3D qu'on vient de redessiner.

L'étape `reconcilier` — le MODE « réconcilier » du pipeline (QJR97) — et ce qui
l'entoure : le verrou de quantité manuelle et son avertissement, le
rafraîchissement de l'instance de l'appelant, l'erreur métier qu'un layout
impossible lève, et l'adaptateur historique `sync_devis_from_layout` qui DEMANDE
ce mode (il ne porte plus le geste : il n'y a pas deux implémentations).

IL RESTE ICI, PAS DANS `domain/lignes.py`. La base de
`check_override_registry` annonce que ses écritures de ligne « migreront vers
domain/lignes.py » — mais `lignes.py` est un module SANCTIONNÉ, exempté du
scan : l'y poser aujourd'hui ferait DISPARAÎTRE quatre sites de la garde sans
que rien ne les ait convertis au registre. Cette convergence est une BASCULE
(QJR84), pas un déplacement ; ici les quatre sites restent surveillés, leur
clé simplement re-clée sur ce fichier.

QJR76 (M3) — DÉPLACEMENT PUR depuis ``apps/ventes/services.py``, dernier de la
vague : après lui, ``services.py`` n'est plus qu'une façade de ré-exports. Les
corps sont recopiés à l'identique ; la seule retouche possible est mécanique
(`from .x` → `from ..x`, MÊME cible).

ORDRE DE CHARGEMENT : ``services.py`` importe ``domain/`` à la toute fin ; un
module de ``domain/`` importe en BAS de fichier les noms qu'il lit ailleurs, et
il vise TOUJOURS le module qui porte le corps — jamais la façade.

NOM DU LOGGER FIGÉ sur ``apps.ventes.services`` : des tests capturent ce nom.
"""
from decimal import Decimal
import logging

logger = logging.getLogger("apps.ventes.services")


# ── PV18 — RESYNCHRONISER un devis existant sur un nouveau calepinage ───────
#
# `build_devis_from_layout` CRÉE un devis. Ici on en MET À JOUR un qui existe
# déjà, et la différence est tout le sujet : un devis vivant porte des prix
# négociés, des remises, des sections, des notes, un ordre d'affichage et des
# groupes multi-villa que personne n'a le droit de perdre parce que la toiture a
# bougé de deux panneaux. La mise à jour est donc CHIRURGICALE — on touche les
# quantités de panneaux et la présence de la batterie, RIEN d'autre — et jamais,
# sous aucune condition, le STATUT (règle #4 : ce chemin LIT les statuts, il ne
# les écrit pas ; `save(update_fields=...)` ci-dessous le rend structurel).


class SyncLayoutError(Exception):
    """Le devis n'est pas dans un état où son calepinage peut être resynchronisé.

    ``revision_possible`` distingue les deux refus : un devis ENVOYÉ peut être
    révisé (une nouvelle version repart en brouillon), un devis
    accepté/refusé/expiré est clos.
    """

    def __init__(self, detail, *, revision_possible=False):
        super().__init__(detail)
        self.detail = detail
        self.revision_possible = revision_possible


def _refus_resynchro(devis):
    """QJR516 — le refus de statut d'une resynchro (geste ``CALEPINAGE``), ou
    ``None`` si le devis se resynchronise. ACAL96 — partagé par
    :func:`reconcilier` (sous verrou) et :func:`ecrire_conception_du_devis`
    (AVANT d'écrire le calepinage) : un refus n'écrit rien nulle part."""
    from apps.ventes.domain.modifiabilite import CALEPINAGE, verdict
    v = verdict(devis, CALEPINAGE)
    if v['modifiable']:
        return None
    if not devis.is_active:
        detail = v['raison_non_modifiable'] + '.'
    else:
        detail = (
            'Devis « %s » : son calepinage est figé, ce document est '
            'clos.' % devis.get_statut_display())
    return SyncLayoutError(detail, revision_possible=v['revision_possible'])


def _refuser_avant_ecriture(layout, *args, **kwargs):
    """ACAL353 (C-ACAL-VER-001) — les refus du document AVANT la première
    écriture : d'abord ceux que la création prononce déjà (surface pavée sans
    ``moduleWc``, pan au module absent de ``modules[]`` — même primitive
    ``refus_des_pans``, 409 nommé), puis le couple panneau/onduleur."""
    from apps.ventes.domain.geometrie import pans_du_document, refus_des_pans
    refus = refus_des_pans(pans_du_document(layout))
    if refus:
        raise SyncLayoutError(refus[0])
    _refuser_couple_panneau_onduleur_impossible(*args, **kwargs)


def _resynchroniser_instance_appelante(devis, verrou):
    """QJR20 (29/08/2026) — recale l'instance de l'APPELANT sur ce qui vient
    d'être écrit sous verrou.

    LE DÉFAUT CORRIGÉ. :func:`sync_devis_from_layout` recharge le devis sous
    ``select_for_update()`` et mute CETTE instance-là (``verrou``) ; l'objet que
    l'appelant tient est celui chargé en début de requête — et le viewset le
    charge avec ``prefetch_related('lignes', 'lignes__produit')``, si bien que
    ``devis.lignes.all()`` continue de servir la composition d'AVANT même après
    la resynchro. Les quatre études rafraîchies juste après
    (``rafraichir_etudes_du_devis``) repartaient donc de l'ancienne
    composition, et RÉÉCRIVAIENT ``etude_params`` par-dessus ce que la
    resynchro venait d'y poser. La conception électrique — seule des quatre à
    n'être jamais recalculée à la lecture, et pourtant lue par la page publique
    et l'annexe PDF depuis L-1V — pouvait ainsi PERSISTER un schéma faux
    jusqu'à ce qu'un humain rouvre l'onglet électrique.

    ``refresh_from_db()`` sans ``fields`` VIDE ``_prefetched_objects_cache``
    (Django) : la prochaine lecture de ``devis.lignes`` repart en base. Le vidage
    explicite qui suit n'est qu'une ceinture, pour que ce contrat ne dépende pas
    d'un détail d'implémentation du framework. Best-effort : un devis
    entre-temps supprimé ne doit pas transformer une resynchro RÉUSSIE en erreur.
    """
    if devis is None or devis is verrou:
        return
    try:
        devis.refresh_from_db()
    except Exception:  # noqa: BLE001 — la resynchro est déjà validée en base
        logger.warning('QJR20: instance appelante non rechargeable (devis %s)',
                       getattr(devis, 'pk', '?'), exc_info=True)
        return
    devis._prefetched_objects_cache = {}


def _quantite_verrouillee(ligne):
    """QJR60 / décision fondateur D12 — la quantité de cette ligne a-t-elle été
    TAPÉE par le commercial ?

    Lu par ``getattr`` : une ligne d'un autre modèle (ou d'un test qui n'en
    porte pas) répond ``False``, donc la resynchro garde exactement le
    comportement d'avant les marqueurs QJR59.
    """
    return bool(getattr(ligne, 'quantite_manuelle', False))


def _avertir_verrouillee(avertissements, lignes, ce_qui_n_a_pas_ete_applique):
    """L'AVERTISSEMENT FR NOMMÉ d'une resynchro qui refuse d'écraser une saisie.

    Le vendeur doit apprendre l'écart AU MOMENT de la resynchro : une quantité
    verrouillée qui ne suit pas le calepinage est une divergence réelle entre
    le dessin et le devis — la taire la ferait découvrir sur le PDF client.
    Les lignes sont NOMMÉES (leur désignation), jamais un « une ligne » anonyme.
    """
    noms = ', '.join(
        sorted({(getattr(li, 'designation', '') or '?') for li in lignes}))
    avertissements.append(
        'Quantité verrouillée par le vendeur sur : %s. %s n\'a pas été '
        'appliqué — corrigez la quantité à la main si le calepinage fait foi.'
        % (noms, ce_qui_n_a_pas_ete_applique.capitalize()))


def _ordre_suivant(devis):
    """PVORD / QJR226 — le prochain ``ordre`` LIBRE du devis (``max + 1``).

    LE DÉFAUT QUE CECI FERME. Les lignes PANNEAU et BATTERIE créées par la
    resynchro l'étaient SANS ``ordre`` : elles prenaient donc le défaut modèle
    ``0`` et, sous ``ordering = ['ordre', 'id']``, passaient DEVANT toute ligne
    d'ordre ≥ 1 — typiquement en tête d'un devis écrit à l'écran, dont les
    lignes sont numérotées 1..n. C'est le mode de défaillance PVORD que la
    justification de l'écrivain unique nomme explicitement. Les créateurs
    onduleur et kit calculaient déjà ``max(ordre) + 1`` : la règle est ici,
    UNE fois, et les quatre l'appellent.

    Passe par ``aggregate`` — donc par la BASE — plutôt que par
    ``devis.lignes.all()`` : un appelant qui a préchargé la relation
    (``prefetch_related``) verrait un cache PÉRIMÉ dès la première création, et
    deux lignes créées d'affilée se retrouveraient au MÊME ordre.
    """
    from django.db.models import Max

    valeur = devis.lignes.aggregate(_max=Max('ordre'))['_max']
    return int(valeur or 0) + 1


#: QJR219 / décision fondateur D12 — LE REFUS, NOMMÉ, DE PERMUTER UN ONDULEUR
#: DONT LE PRIX A ÉTÉ TAPÉ PAR LE VENDEUR.
#:
#: COMPORTEMENT RETENU : L'ABSTENTION. ``_permuter_onduleur`` écrasait
#: ``prix_unitaire`` avec le prix catalogue SANS consulter ``prix_manuel`` et
#: SANS effacer le drapeau : le prix tapé disparaissait pendant que la ligne
#: continuait d'affirmer qu'il avait été tapé — un état MENTEUR. Des deux
#: comportements admissibles (s'abstenir en le disant, ou permuter ET effacer
#: le drapeau dans la même écriture), on retient le premier, pour deux raisons
#: déjà écrites dans ce fichier : (1) D12 — « le prix tapé par le commercial
#: est souverain » (même abstention que ``lignes.retarifer_forfaits_par_panneau``)
#: et (2) le bloc « DEUX onduleurs » juste au-dessus CONSERVE déjà, avec un
#: avertissement, un onduleur intrus qui n'est pas au prix catalogue —
#: permuter celui-ci en silence contredirait la règle voisine.
MSG_PERMUTATION_PRIX_MANUEL = (
    'Prix saisi à la main sur « %s » : l\'onduleur n\'a PAS été permuté vers '
    '« %s » (le prix du vendeur fait foi, décision D12). Changez le produit à '
    'la main si le scénario exige l\'autre famille d\'onduleur.'
)


def reconcilier(devis, intention):
    """QJR97 — L'ÉTAPE « RÉCONCILIER » du pipeline (``MODE_RECONCILIER``).

    Le devis EXISTE et il est VIVANT : on l'aligne sur une nouvelle cible sans
    jamais le recomposer. C'est l'étape que ``pipeline.appliquer`` exécute — et
    la seule qu'il exécute — dans ce mode ; elle est appelée par les DEUX
    adaptateurs qui la demandent, la resynchronisation 3D
    (:func:`sync_devis_from_layout`) et le chemin apply-taille
    (``offres_tailles.appliquer_au_devis``, ``exact=True``).

    Elle lit son geste dans l'``IntentionDevis`` : ``layout`` (le calepinage à
    appliquer), ``user`` (qui le demande — journal seulement) et ``exact`` (la
    cible est un NOMBRE TAPÉ, pas une contenance de toit — voir plus bas).

    Le reste de cette docstring décrit la règle PV18, inchangée par la bascule.

    PV18 — aligne les LIGNES d'un devis brouillon sur un nouveau calepinage.

    Sous ``transaction.atomic()`` + ``select_for_update`` sur la ligne du devis
    (deux commerciaux sur le même devis ne peuvent pas s'écraser l'un l'autre).

    Comportement par statut — le statut est LU, JAMAIS écrit (règle #4) :

    * ``brouillon`` — mise à jour chirurgicale (voir plus bas) ;
    * ``envoye``    — ``SyncLayoutError(revision_possible=True)`` : le client a
      déjà cette version sous les yeux, le bon geste est « Réviser » ;
    * ``accepte`` / ``refuse`` / ``expire`` — ``SyncLayoutError`` : document
      clos, aucune révision de calepinage possible.

    Mise à jour chirurgicale, sur un brouillon :

    * les lignes PANNEAU sont portées au compte du layout ; quand il y en a
      plusieurs, l'écart va sur la PLUS GROSSE seule (les autres, souvent une
      seconde marque ou un second pan négocié, ne bougent pas) ;
    * aucune ligne panneau et un compte à poser → UNE ligne est créée depuis le
      catalogue au wattage du layout (``_pick_product``, catalogue société OU
      global, jamais un produit sans prix) ;
    * la BATTERIE suit le scénario : ajoutée si le layout en veut une et qu'il
      n'y en a pas, supprimée s'il n'en veut plus ;
    * l'ONDULEUR suit la batterie (PVSCE) : réseau → hybride quand une batterie
      entre, hybride → réseau quand elle sort, à quantité INCHANGÉE. Sans cette
      permutation la batterie serait « fantôme » — comptée dans le total du
      devis mais absente du PDF, que le moteur rendrait en « Sans batterie »
      faute d'onduleur hybride ;
    * un devis portant LES DEUX onduleurs (artefact d'anciens chemins) est
      ramené à celui du scénario — mais l'intrus n'est retiré que s'il est
      resté AU PRIX CATALOGUE, sans remise. Un prix modifié vaut prix négocié :
      la ligne est conservée et un avertissement le dit (PVHEAL) ;
    * L-2OPT — un devis DÉCLARÉ « Les deux (Sans + Avec) » (U2) échappe aux
      trois règles ci-dessus, qui ne connaissaient que les devis mono : ses
      DEUX onduleurs sont légitimes (aucun intrus, aucun avertissement), sa
      batterie n'est jamais retirée (elle EST l'option « avec »), l'onduleur
      qui manque est COMPLÉTÉ depuis le catalogue au lieu d'être permuté, et
      le scénario re-stocké reste « Les deux » — sauf si les lignes ne peuvent
      plus servir les deux côtés, auquel cas il dégrade au libellé mono ;
    * le KIT MANQUANT est COMPLÉTÉ (PVHEAL) : structures, socles, accessoires,
      tableau de protection AC/DC, installation, transport — et le duo Smart
      Meter + clé Wifi derrière un onduleur Huawei. Ces classes sont AJOUTÉES
      quand elles manquent, jamais re-tarifées quand elles sont là ; un
      composant introuvable ou non tarifé est sauté ET annoncé en français.
      Ni sur un devis agricole (pompage) ni sur un multi-villa : les deux
      demandent un kit qui ne se déduit pas d'une composition résidentielle ;
    * TOUT le reste est intact — prix unitaires, remises, TVA de ligne,
      sections, notes, ordre d'affichage, groupes multi-villa, et les produits
      des lignes non touchées ne sont JAMAIS re-choisis ;
    * ``roof_layout`` / ``layout_hash`` sont re-posés, et ``etude_params`` ne
      reçoit que ``puissance_kwc`` / ``production_annuelle`` /
      ``economies_annuelles`` / ``toiture`` / ``scenario`` — les champs d'étude
      du générateur (autoconsommation, payback, pompe…) ne sont jamais touchés.

    L-2OPT / RÈGLE TOIT — UN DEVIS À LIGNES VARIANTÉES (deux optimiseurs) SE
    RESYNCHRONISE PAR VARIANTE, ET LE CALEPINAGE N'Y EST QU'UN PLAFOND :

    * la ligne DOMINANTE se lit PAR VARIANTE — les lignes ``variante=''`` +
      ``'sans'`` pour l'option sans, ``''`` + ``'avec'`` pour l'option avec ;
    * le compte du calepinage est le nombre de panneaux PHYSIQUEMENT POSABLES.
      Une option dont le compte le DÉPASSE est ramenée à ce plafond (sur sa
      dominante) ; une option qui reste EN DESSOUS n'est JAMAIS augmentée —
      l'optimum économique a le droit de choisir moins que le toit, et une
      resynchro n'a pas à lui vendre des panneaux qu'il a refusés ;
    * les structures et les socles suivent le compte DE LEUR VARIANTE ;
    * QJR98 — une option SANS ligne de panneaux propre ne se corrige PAS sur
      une ligne COMMUNE : la commune sert les deux options, la bouger les
      bouge toutes les deux. Elle n'est mobilisable que si l'AUTRE option a
      besoin EXACTEMENT du même écart (le cas du plafond de toit, où les deux
      débordent du même toit) ; sinon l'écart est NOMMÉ et rien n'est écrit.

    Un devis SANS aucune ligne variantée (tous ceux d'hier) garde la règle
    historique mot pour mot : le compte est porté À LA CIBLE, à la hausse comme
    à la baisse.

    ``cible_exacte`` (défaut ``False`` — TOUS les appels d'hier, comportement
    byte-identique) RETOURNE cette règle du plafond, et uniquement pour les
    devis variantés : le compte du layout devient alors une CIBLE EXACTE que
    CHAQUE option est portée à, à la hausse comme à la baisse.

    POURQUOI CE COMMUTATEUR EXISTE (revue Fable, 29/08/2026). Le plafond est la
    bonne règle quand la cible vient d'un CALEPINAGE : le toit dit ce qui tient
    physiquement, et une option qui a délibérément choisi moins n'a pas à se
    voir vendre des panneaux qu'elle a écartés. Il est la MAUVAISE règle quand
    la cible vient d'un NOMBRE TAPÉ PAR LE VENDEUR sur la carte « Recommandé »
    (:func:`~apps.ventes.offres_tailles.appliquer_au_devis`) : là, le vendeur
    N'exprime PAS une contenance de toit, il exprime le devis qu'il veut. Sous
    la règle du plafond, taper un compte PLUS GRAND que celui du devis ne
    faisait STRICTEMENT RIEN — configuration consommée, message de succès,
    devis inchangé : très exactement le « les modifications ne changent rien au
    devis » que ce chemin existe pour clore.

    Re-soumettre le MÊME layout (même empreinte) ne fait AUCUNE écriture et
    renvoie ``inchange=True``.

    Renvoie toujours le même dict :
    ``{inchange, panneaux, kwc, scenario, batterie, lignes_modifiees,
    lignes_ajoutees, avertissements}`` — forme GELÉE, inchangée par L-2OPT ;
    sur un devis varianté ``panneaux`` est le compte de l'option SANS (l'option
    1), jamais la somme des deux (un nombre qui ne décrit aucune installation).
    ``lignes_modifiees`` compte ce que la logique chirurgicale a touché,
    ``lignes_ajoutees`` ce que la complétion du kit a ajouté.
    """
    from django.db import transaction

    from apps.ventes.models import Devis

    # QJR97 — LE GESTE EST LU DANS L'INTENTION, plus dans une liste
    # d'arguments propre à ce chemin : c'est ce qui fait de la resynchro un
    # MODE du pipeline et non plus un cinquième chemin parallèle.
    user = intention.user
    cible_exacte = bool(intention.exact)
    layout = intention.layout if isinstance(intention.layout, dict) else {}
    nouveau_hash = layout_hash(layout)
    toiture = extract_roof_config(layout)
    cible_panneaux = _cible_panneaux_du_layout(layout, toiture)
    watt = _watt_du_layout(layout, toiture, cible_panneaux)
    # ACAL63 (C-ACAL-042) — les modèles DÉSIGNÉS par le calepinage : la
    # resynchro porte CHAQUE ligne panneau au compte de SON modèle (plus de
    # « dominante » par quantité, plus de choix au wattage seul).
    modeles = modeles_designes(layout)

    # QJR556 — le scénario du layout est lu par son PROPRIÉTAIRE UNIQUE
    # (``geometrie.scenario_du_layout``), plus par une copie qui ignorait
    # ``'les_deux'`` (vocabulaire émis par le serveur et renvoyé par
    # ToitureDesign) : un layout « les deux » VEUT une batterie.
    veut_batterie = scenario_du_layout(layout) in (
        COMPOSITION_AVEC, COMPOSITION_LES_DEUX)

    with transaction.atomic():
        verrou = (Devis.objects.select_for_update()
                  .filter(pk=getattr(devis, 'pk', None)).first())
        if verrou is None:
            raise SyncLayoutError('Devis introuvable.')
        # ADEV30 — compte de panneaux AVANT toute écriture : un envoyé n'est
        # re-tarifé que si la resynchronisation le change.
        from .lignes import comptes_panneaux_du_devis
        comptes_avant = comptes_panneaux_du_devis(verrou)

        # PVMRQ — gamme RÉELLE de ce devis, calculée une fois et transmise à
        # chaque ``_pick_product``/``_pick_batterie`` de cette resynchro.
        gamme = gamme_nom(verrou)

        # ── L-2OPT — LE DEVIS « LES DEUX » EST LU AVANT LA PREMIÈRE ÉCRITURE ──
        #
        # Incident DEV-202608-0023 (production) : un devis né « Les deux (Sans +
        # Avec) » (U2) porte LÉGITIMEMENT les deux onduleurs — réseau pour
        # l'option « sans », hybride + batterie pour l'option « avec ». La
        # resynchro, elle, ne connaissait que les devis MONO : elle voyait dans
        # l'onduleur réseau l'« intrus » de l'artefact deux-onduleurs, retirait
        # la batterie dès qu'un layout n'en voulait pas, et réécrivait le
        # scénario avec un libellé mono. Le moteur PDF relisait alors une
        # déclaration mono (PV86/QF6) : ``nb_options`` retombait à 1 et la page
        # publique ne montrait plus qu'une option — celle que le commercial
        # n'avait jamais choisie seule. Une resynchronisation de calepinage n'a
        # jamais le droit de retirer au client une option qu'on lui a promise.
        #
        # C'est la DÉCLARATION STOCKÉE qui fait foi (la même que le moteur lit),
        # relue ici sous verrou, avant que quoi que ce soit n'ait bougé.
        devis_deux_options = (
            (verrou.etude_params or {}).get('scenario') == SCENARIO_LES_DEUX)

        # ── Garde de statut : LECTURE du statut, jamais une écriture ──
        # QJR516 — le prédicat UNIQUE (domain/modifiabilite, geste
        # CALEPINAGE). QJR557 (D-QJR5-5) — un ENVOYÉ se resynchronise SUR
        # PLACE (le refus PV21 « Créez une révision » tombe) ; la trace
        # « corrigé après envoi : calepinage » est posée par le pipeline
        # (``fin_de_geste_devis``). Textes des refus restants CONSERVÉS ;
        # ``revision_possible`` vient du prédicat (un accepté/refusé/expiré
        # est révisable, D-QJR5-2 ; un devis remplacé ne l'est pas).
        refus = _refus_resynchro(verrou)
        if refus is not None:
            raise refus

        lignes = _lignes_produit(verrou)
        lignes_panneau = [li for li in lignes
                          if _classe_ligne(li, _is_panel)]
        lignes_batterie = [li for li in lignes
                           if _classe_ligne(li, _is_battery)]
        a_batterie = bool(lignes_batterie)

        # ── L-2OPT — LES DEUX VUES DU CHAMP PV ─────────────────────────────
        # ``devis_variante`` est faux sur TOUS les devis d'hier (aucune ligne
        # variantée) : la resynchro reprend alors sa règle historique, mot pour
        # mot. Il n'est vrai que pour un devis composé par les deux
        # optimiseurs, et c'est là — et là seulement — que le calepinage
        # devient un PLAFOND plutôt qu'une cible.
        def _var(ligne):
            return getattr(ligne, 'variante', '') or ''

        def _lignes_de(variante):
            return [li for li in lignes_panneau
                    if _var(li) in ('', variante)]

        def _total_de(variante):
            return sum(int(li.quantite or 0) for li in _lignes_de(variante))

        devis_variante = any(_var(li) for li in lignes_panneau)
        total_panneaux = (_total_de(VARIANTE_SANS) if devis_variante
                          else sum(int(li.quantite or 0)
                                   for li in lignes_panneau))
        total_panneaux_avec = (_total_de(VARIANTE_AVEC) if devis_variante
                               else total_panneaux)

        avertissements = []
        # Cohérence avec PV17 : ces deux cas y sont déclarés NON modifiables.
        agricole = (
            verrou.mode_installation == Devis.ModeInstallation.AGRICOLE)
        if agricole:
            avertissements.append(
                'Devis agricole (pompage) — le calepinage de toiture ne '
                's\'applique pas.')
        multi_villa = verrou.lignes.filter(groupe_index__gte=1).exists()
        if multi_villa:
            avertissements.append(
                'Devis multi-villa : l\'écart de calepinage porte sur la ligne '
                'de panneaux la plus grosse, tous groupes confondus.')

        # ── Court-circuit : même géométrie → ZÉRO écriture ──
        # ACAL96 — accepté seulement si le layout STOCKÉ porte déjà
        # ``_pans_geometry`` quand le toit a des pans : un document stocké
        # brut (ancien chemin ``POST layout``) est rangé une fois, sinon la
        # 3D publique et l'annexe « paramètres du site » restent vides.
        stocke = verrou.roof_layout if isinstance(verrou.roof_layout,
                                                  dict) else {}
        range_ok = (not (toiture and toiture.get('pans'))
                    or bool(stocke.get('_pans_geometry')))
        if nouveau_hash and verrou.layout_hash == nouveau_hash and range_ok:
            return {
                'inchange': True,
                'panneaux': total_panneaux,
                'kwc': round(total_panneaux * watt / 1000.0, 3),
                # L-2OPT — un devis à deux options le DIT, même quand il n'y a
                # rien eu à écrire : l'écran ne doit jamais lire « réseau » sur
                # un document qui propose les deux.
                'scenario': ('les_deux' if devis_deux_options
                             else ('avec_batterie' if a_batterie
                                   else 'reseau')),
                'batterie': a_batterie,
                'lignes_modifiees': 0,
                'lignes_ajoutees': 0,
                'avertissements': avertissements,
            }

        lignes_modifiees = 0
        # F8 — vrai UNIQUEMENT quand le compte de panneaux a réellement bougé
        # (ligne créée, ou ligne dominante réajustée) : c'est ce qui déclenche
        # la resynchro des câbles plus bas, jamais un layout qui ne change
        # rien aux panneaux.
        panneaux_ont_change = False
        panneaux_avant = total_panneaux
        # ACAL100 (C-ACAL-110) — vrai dès qu'une ABSTENTION laisse un écart
        # de panneaux non appliqué (quantité tapée, ligne commune QJR98,
        # cible 0) : l'empreinte n'est alors PAS posée, le devis reste « à
        # resynchroniser » et le clic suivant ré-applique.
        ecart_residuel = False

        # ── DEV-202608-0016 — LE VERROU DE POSSIBILITÉ, AVANT LA PREMIÈRE
        # ÉCRITURE ──
        #
        # Placé ICI et pas plus haut : le court-circuit « même géométrie » est
        # déjà passé (re-poster un layout identique n'écrit rien, donc n'a rien
        # à refuser), et aucune ligne n'a encore bougé — un refus laisse la
        # transaction absolument intacte.
        _refuser_avant_ecriture(
            layout, verrou, lignes, lignes_panneau, cible_panneaux, watt,
            gamme, modeles=modeles)

        # ── Panneaux : porter le compte à la cible ──
        if modeles and not devis_variante and cible_panneaux > 0:
            # ── ACAL63 — LIGNE PAR LIGNE, MODÈLE PAR MODÈLE ────────────────
            modifiees, change, residuel = _reconcilier_panneaux_par_modele(
                verrou, lignes_panneau, modeles, avertissements)
            lignes_modifiees += modifiees
            panneaux_ont_change = panneaux_ont_change or change
            ecart_residuel = ecart_residuel or residuel
            total_panneaux = sum(
                int(li.quantite or 0)
                for li in _lignes_produit(verrou)
                if _classe_ligne(li, _is_panel))
            total_panneaux_avec = total_panneaux
        elif cible_panneaux > 0 and not lignes_panneau:
            panneau = _pick_product(verrou.company, _is_panel, watt=watt,
                                    role='panneau', gamme=gamme)
            if panneau is None:
                avertissements.append(
                    'Aucun panneau tarifé au catalogue : la ligne de panneaux '
                    'n\'a pas pu être créée. Ajoutez un panneau tarifé.')
            else:
                creer_ligne(
                    verrou, produit=panneau, designation=panneau.nom,
                    quantite=Decimal(str(cible_panneaux)),
                    prix_unitaire=Decimal(panneau.prix_vente),
                    # QJR226 — la ligne SUIT l'existant (PVORD) : sans
                    # ``ordre``, le défaut modèle 0 la faisait passer devant
                    # toutes les lignes du devis.
                    remise=Decimal('0'), ordre=_ordre_suivant(verrou))
                lignes_modifiees += 1
                # La ligne créée est COMMUNE (``variante=''`` par défaut) :
                # elle sert donc les deux vues à l'identique.
                total_panneaux = cible_panneaux
                total_panneaux_avec = cible_panneaux
                panneaux_ont_change = True
        elif cible_panneaux <= 0:
            # Un layout sans compte de panneaux ne DÉTRUIT pas les lignes en
            # place : « 0 » veut dire « inconnu », pas « enlève tout ».
            avertissements.append(
                'Ce calepinage ne porte aucun panneau : les lignes de '
                'panneaux du devis n\'ont pas été modifiées.')
            ecart_residuel = True
        elif lignes_panneau and devis_variante:
            # ── L-2OPT / RÈGLE TOIT — le calepinage est un PLAFOND ──────────
            # Chaque option a son propre compte, choisi par l'économie. Le
            # calepinage dit combien de panneaux TIENNENT sur le toit : une
            # option qui dépasse ce plafond est ramenée dessus (elle n'est
            # PHYSIQUEMENT pas posable), une option en dessous n'est jamais
            # augmentée — on ne rajoute pas au client des panneaux que
            # l'optimum a délibérément écartés.
            # ``cible_exacte`` — la cible vient d'un NOMBRE TAPÉ, pas d'un
            # toit : les DEUX options y sont portées, à la hausse comme à la
            # baisse. Sans lui, une augmentation était un NO-OP SILENCIEUX
            # (« une option qui reste EN DESSOUS n'est JAMAIS augmentée »),
            # configuration consommée et message de succès compris.
            for variante in (VARIANTE_SANS, VARIANTE_AVEC):
                vue = _lignes_de(variante)
                total_vue = sum(int(li.quantite or 0) for li in vue)
                if not vue:
                    continue
                if total_vue == cible_panneaux:
                    continue
                if not cible_exacte and total_vue < cible_panneaux:
                    continue
                # Rogner d'abord une ligne PROPRE à cette variante : toucher la
                # ligne commune rétrécirait AUSSI l'autre option, qui, elle,
                # tient peut-être sur le toit.
                propres = [li for li in vue if _var(li) == variante]
                # ── QJR98 — ET LE REPLI SUR LA COMMUNE EST CONDITIONNÉ ───────
                # Le vivier était ``propres or vue`` : sans ligne propre, la
                # boucle retombait sur ``vue``, qui contient les lignes
                # COMMUNES — et une commune sert LES DEUX options, donc la
                # bouger les bouge toutes les deux. C'est très exactement
                # l'issue que le commentaire ci-dessus dit d'éviter, et sur le
                # chemin apply-taille (``cible_exacte``) elle emportait une
                # option DÉJÀ au compte tapé quatre panneaux au-dessus.
                #
                # Une commune n'est donc mobilisable que si l'AUTRE option a
                # besoin EXACTEMENT du même écart : là, la bouger les sert à
                # l'identique et ne lèse personne (c'est le cas du plafond de
                # toit, où les deux options débordent du même toit). Sinon
                # l'écart est NOMMÉ et RIEN n'est écrit — même discipline que
                # pour une quantité verrouillée : on ne corrige pas une option
                # en cassant l'autre.
                vivier = propres
                if not vivier:
                    autre = (VARIANTE_AVEC if variante == VARIANTE_SANS
                             else VARIANTE_SANS)
                    if _total_de(autre) == total_vue:
                        vivier = vue
                    else:
                        avertissements.append(
                            'L\'option « %s » n\'a aucune ligne de panneaux '
                            'qui lui soit propre : l\'écart de %d panneau(x) '
                            'n\'a pas été appliqué, car il aurait fallu rogner '
                            'une ligne COMMUNE aux deux options — et l\'autre '
                            'option, elle, n\'a pas le même écart. Ajoutez une '
                            'ligne de panneaux propre à cette option, ou '
                            'corrigez les quantités à la main.'
                            % (variante, abs(total_vue - cible_panneaux)))
                        ecart_residuel = True
                        continue
                # QJR60 / D12 — une quantité TAPÉE par le vendeur n'est pas
                # réécrite : elle sort du vivier, et si tout le vivier est
                # verrouillé l'écart est NOMMÉ au lieu d'être appliqué.
                libres = [li for li in vivier
                          if not _quantite_verrouillee(li)]
                if not libres:
                    _avertir_verrouillee(
                        avertissements, vivier,
                        "l'écart de %d panneau(x) de l'option « %s »"
                        % (abs(total_vue - cible_panneaux), variante))
                    ecart_residuel = True
                    continue
                dominante = max(
                    libres,
                    key=lambda li: Decimal(str(li.quantite or 0)))
                nouvelle = int(dominante.quantite or 0) - (
                    total_vue - cible_panneaux)
                if nouvelle < 0:
                    # Même garde qu'en mono-option : jamais sous zéro, jamais
                    # une suppression silencieuse.
                    nouvelle = 0
                    avertissements.append(
                        'Le plafond du calepinage dépasse la plus grosse ligne '
                        'de panneaux de l\'option « %s » : elle a été ramenée '
                        'à 0, les autres lignes n\'ont pas été touchées.'
                        % variante)
                dominante.quantite = Decimal(str(nouvelle))
                dominante.save(update_fields=['quantite'])
                lignes_modifiees += 1
                panneaux_ont_change = True
            total_panneaux = _total_de(VARIANTE_SANS)
            total_panneaux_avec = _total_de(VARIANTE_AVEC)
        elif lignes_panneau and cible_panneaux != total_panneaux:
            # L'écart va sur la PLUS GROSSE ligne, elle seule : les autres
            # lignes panneau restent telles que le commercial les a posées.
            # QJR60 / D12 — et jamais sur une ligne dont la quantité a été
            # TAPÉE : elle sort du vivier.
            libres = [li for li in lignes_panneau
                      if not _quantite_verrouillee(li)]
            if not libres:
                _avertir_verrouillee(
                    avertissements, lignes_panneau,
                    "l'écart de %d panneau(x)"
                    % abs(cible_panneaux - total_panneaux))
                ecart_residuel = True
            else:
                dominante = max(libres,
                                key=lambda li: Decimal(str(li.quantite or 0)))
                ecart = cible_panneaux - total_panneaux
                nouvelle = int(dominante.quantite or 0) + ecart
                if nouvelle < 0:
                    # Un retrait plus grand que la ligne dominante : on ne
                    # descend jamais sous zéro (et le compte final est renvoyé
                    # tel quel).
                    nouvelle = 0
                    avertissements.append(
                        'Le retrait demandé dépasse la plus grosse ligne de '
                        'panneaux : elle a été ramenée à 0, les autres lignes '
                        'n\'ont pas été touchées.')
                dominante.quantite = Decimal(str(nouvelle))
                dominante.save(update_fields=['quantite'])
                lignes_modifiees += 1
                total_panneaux = sum(
                    int(li.quantite or 0) for li in lignes_panneau)
                total_panneaux_avec = total_panneaux
                panneaux_ont_change = True

        # DEV-202608-0016 — la resynchro DIT ce qu'elle a changé. Le compte de
        # panneaux est la décision commerciale la plus lourde de cet écran
        # (il porte le kWc, donc le prix) : qu'il bouge sous l'effet d'une
        # conception 3D ne doit pas se découvrir en relisant le devis.
        if panneaux_ont_change and total_panneaux != panneaux_avant:
            avertissements.append(
                'La conception 3D porte le devis de %d à %d panneaux.'
                % (panneaux_avant, total_panneaux))

        # ── Kilowattage RETENU — déplacé ICI (F8) : le kit (PVHEAL) ET les
        # câbles (PVCBL, juste en dessous) en ont tous les deux besoin, et le
        # panel count qui vient d'être arrêté ci-dessus est son unique
        # dépendance restante.
        result = dict(layout.get('result') or {})
        kwc = float(result.get('kwc') or toiture.get('kwc') or 0.0)
        if not kwc and total_panneaux:
            kwc = round(total_panneaux * watt / 1000.0, 3)

        # ── PVCBL — LES CÂBLES SUIVENT LA TAILLE DU CALEPINAGE (F8, fondateur
        # 18/08/2026) ──
        #
        # Le compte de panneaux, la batterie et l'onduleur se resynchronisaient
        # déjà ; les DEUX lignes de câble (DC solaire + terre AC), elles,
        # restaient au métrage du premier calepinage — un devis ramené de
        # 10 à 5 kWc gardait ses 120 m de câble DC (60 m/palier × 2 paliers)
        # alors que 5 kWc n'en réclame que 60. Mêmes métrés que ``solar.js``
        # (paliers = max(1, round(kWc / 5))).
        #
        # Ne touche QUE des lignes DÉJÀ PRÉSENTES, classées par le même
        # mot-clé que l'écran et rattachées à un PRODUIT catalogue (au mètre)
        # — jamais une note texte, et jamais une ligne INVENTÉE : un devis
        # sans câble hier n'en gagne pas un ici (ce trou reste à la charge de
        # PVHEAL/``composition_residentielle``, hors périmètre de cette
        # resynchro). Ne se déclenche QUE si le compte de panneaux a bougé —
        # un layout qui ne change rien aux panneaux ne touche pas aux câbles
        # non plus.
        def _resynchroniser_quantite(predicat, cible, variante=None):
            """Porte à ``cible`` la quantité de la famille ``predicat``.

            Ne touche QUE des lignes déjà présentes ET rattachées à un produit
            catalogue ; renvoie True quand une ligne a réellement bougé.

            L-2OPT — ``variante`` restreint la famille aux lignes de CETTE
            option-là (jamais les communes : une ligne commune sert les deux
            options, la porter au compte d'une seule fausserait l'autre).
            ``None`` (LE DÉFAUT, tous les appels d'hier) ⇒ aucune restriction.
            """
            candidats = [li for li in lignes
                         if getattr(li, 'produit', None) is not None
                         and _classe_ligne(li, predicat)
                         and (variante is None or _var(li) == variante)]
            if not candidats:
                return False
            # QJR60 / D12 — LA QUANTITÉ TAPÉE PAR LE VENDEUR EST UNE ENTRÉE.
            # C'est ce chemin qui réécrivait les mètres de câble DC/terre et
            # les comptes structure/socle : une ligne verrouillée en sort, et
            # si la famille entière est verrouillée l'écart est NOMMÉ dans les
            # avertissements plutôt qu'appliqué en silence.
            libres = [li for li in candidats
                      if not _quantite_verrouillee(li)]
            if not libres:
                _avertir_verrouillee(
                    avertissements, candidats,
                    'la quantité %s demandée par le calepinage' % cible)
                return False
            # Plusieurs lignes de la même famille (rare) : seule la PLUS
            # GROSSE bouge, même politique que les panneaux ci-dessus.
            dominante = max(libres,
                            key=lambda li: Decimal(str(li.quantite or 0)))
            nouvelle = Decimal(str(cible))
            if Decimal(str(dominante.quantite or 0)) == nouvelle:
                return False
            dominante.quantite = nouvelle
            dominante.save(update_fields=['quantite'])
            return True

        if panneaux_ont_change and kwc > 0:
            paliers = max(1, _arrondi_js(kwc / 5))
            # C4 (fondateur 19/08/2026) — garde AU MÈTRE : la cible est un
            # MÉTRAGE, elle ne s'applique qu'aux lignes dont le produit se
            # vend au mètre. Une ligne ROULEAU (« (100m) ») garde sa quantité.
            if _resynchroniser_quantite(
                    lambda n: _is_cable_dc(n) and _est_au_metre(n),
                    metre_cable_dc(paliers)):
                lignes_modifiees += 1
            if _resynchroniser_quantite(
                    lambda n: _is_cable_terre(n) and _est_au_metre(n),
                    metre_cable_terre(paliers)):
                lignes_modifiees += 1

        # ── PVSTR — LES STRUCTURES ET LES SOCLES SUIVENT LE COMPTE DE
        # PANNEAUX (fondateur, 18/08/2026) ──
        #
        # Les panneaux, la batterie, l'onduleur et les câbles se
        # resynchronisaient déjà ; la FERRURE, elle, restait au compte du
        # premier calepinage. Le devis de production DEV-202608-0007 en porte
        # la trace exacte : 9 panneaux, mais 8 structures et 16 socles — le
        # calepinage était passé de 8 à 9 panneaux et rien d'autre n'avait
        # suivi. Le client reçoit alors une installation sous-ferrée sur le
        # papier, et un total faux d'une structure et de deux socles.
        #
        # Mêmes garde-fous que les câbles, sans exception : ne touche QUE des
        # lignes DÉJÀ PRÉSENTES rattachées à un produit catalogue (jamais une
        # note, jamais une ligne INVENTÉE — une ferrure absente reste à la
        # charge de PVHEAL juste en dessous, qui l'ajoute au bon compte), et ne
        # se déclenche QUE si le compte de panneaux a réellement bougé.
        #
        # L-2OPT — sur un devis VARIANTÉ, la ferrure suit le compte DE SA
        # VARIANTE : les structures « sans » sur le champ « sans », les
        # « avec » sur le champ « avec ». Une ligne de ferrure restée COMMUNE
        # n'est PAS touchée — elle vaut pour les deux options, la porter au
        # compte d'une seule fausserait l'autre (et la fusion, elle, variante
        # toujours la ferrure quand les champs divergent : une commune ne peut
        # venir que d'une retouche manuelle, que PV18 ne réécrit jamais).
        if panneaux_ont_change and total_panneaux > 0:
            if devis_variante:
                for variante, total_vue in (
                        (VARIANTE_SANS, total_panneaux),
                        (VARIANTE_AVEC, total_panneaux_avec)):
                    if total_vue <= 0:
                        continue
                    if _resynchroniser_quantite(
                            _is_structure,
                            total_vue * STRUCTURES_PAR_PANNEAU,
                            variante=variante):
                        lignes_modifiees += 1
                    if _resynchroniser_quantite(
                            _is_socle, total_vue * SOCLES_PAR_PANNEAU,
                            variante=variante):
                        lignes_modifiees += 1
            else:
                if _resynchroniser_quantite(
                        _is_structure,
                        total_panneaux * STRUCTURES_PAR_PANNEAU):
                    lignes_modifiees += 1
                if _resynchroniser_quantite(
                        _is_socle, total_panneaux * SOCLES_PAR_PANNEAU):
                    lignes_modifiees += 1

        # ── Batterie : présente si (et seulement si) le layout en veut une ──
        if veut_batterie and not a_batterie:
            # PVOND — garde batterie data-driven : c'est l'onduleur HYBRIDE
            # RÉELLEMENT posé sur le devis qui décide de la fenêtre de tension
            # (et non celui que la composition aurait choisi — on ne remplace
            # jamais l'onduleur en place). À défaut d'hybride sur le devis, on
            # se rabat sur celui du catalogue, puis sur le mot-clé (PVG4).
            _hybride_du_devis = next(
                (li.produit for li in lignes
                 if _classe_ligne(li, _is_hybrid_inverter)
                 and getattr(li, 'produit', None) is not None), None)
            if _hybride_du_devis is None:
                _hybride_du_devis = _pick_product(
                    verrou.company, _is_hybrid_inverter,
                    role='onduleur_hybride', gamme=gamme)
            batterie = _pick_batterie(
                verrou.company, onduleur=_hybride_du_devis, gamme=gamme)
            if batterie is None:
                _plage_devis = _plage_batterie_de_l_onduleur(_hybride_du_devis)
                if _plage_devis and _plage_devis[1] > 0:
                    avertissements.append(
                        'Aucune batterie compatible tarifée pour cet onduleur '
                        '(plage %s-%s V) : la ligne batterie n\'a pas pu être '
                        'ajoutée.'
                        % (_v_txt(_plage_devis[0]), _v_txt(_plage_devis[1])))
                else:
                    avertissements.append(
                        'Aucune batterie tarifée au catalogue : la ligne '
                        'batterie n\'a pas pu être ajoutée. Ajoutez une '
                        'batterie tarifée.')
            else:
                creer_ligne(
                    verrou, produit=batterie, designation=batterie.nom,
                    quantite=Decimal('1'),
                    prix_unitaire=Decimal(batterie.prix_vente),
                    # QJR226 — même correction que la ligne panneau : la
                    # batterie créée par la resynchro SUIT l'existant.
                    remise=Decimal('0'), ordre=_ordre_suivant(verrou))
                lignes_modifiees += 1
                a_batterie = True
        elif not veut_batterie and a_batterie and not devis_deux_options:
            # L-2OPT — sur un devis « Les deux », la batterie EST l'option
            # « avec » : un calepinage qui n'en veut pas décrit l'option
            # « sans », il ne retire pas l'autre du document.
            #
            # QJR556 — même garde que PVHEAL (l'onduleur intrus) : une
            # batterie NÉGOCIÉE (``prix_negocie`` via ``_est_au_prix_catalogue``
            # — prix_manuel, remise, prix ≠ catalogue, pas de prix) ou à
            # QUANTITÉ FIGÉE (D12) n'est jamais supprimée en silence ; elle
            # reste, l'écran le dit, et elle ne compte pas comme modifiée.
            batteries_conservees = []
            for ligne in lignes_batterie:
                if (not _est_au_prix_catalogue(ligne)
                        or _quantite_verrouillee(ligne)):
                    batteries_conservees.append(ligne)
                    avertissements.append(
                        'Le calepinage ne prévoit plus de batterie, mais '
                        '« %s » porte un prix ou une quantité saisis à la '
                        'main : elle a été CONSERVÉE — retirez-la à la main '
                        's\'il n\'a rien à y faire.'
                        % (ligne.designation or 'ligne sans désignation'))
                    continue
                ligne.delete()
                lignes_modifiees += 1
            a_batterie = bool(batteries_conservees)

        # ── L'ONDULEUR DOIT S'ACCORDER AU SCÉNARIO (batterie fantôme) ──
        #
        # La resynchro n'a longtemps touché QUE les panneaux et la batterie —
        # « chirurgical ». Mais un devis réseau resynchronisé « avec batterie »
        # finissait avec un onduleur RÉSEAU face à une batterie, et le moteur
        # PDF n'accorde l'option « Avec » qu'à un devis portant onduleur
        # hybride ET batterie (builder.py : ``avec_ok = has_hybride and
        # has_batterie``). Le document retombait donc sur « Sans batterie »,
        # qui EXCLUT la ligne batterie : elle gonflait le total du devis sans
        # apparaître ni au PDF ni au total affiché. Une batterie fantôme —
        # facturée, invisible.
        #
        # La permutation est aussi chirurgicale que le reste : la ligne
        # d'onduleur garde sa QUANTITÉ, seuls le produit, la désignation et le
        # prix catalogue changent. Le sens inverse compte tout autant : sans
        # lui, retirer la batterie d'un devis hybride laisserait un document
        # SANS aucune option rendable (le moteur refuse alors le PDF).
        lignes_reseau = [li for li in lignes
                         if _classe_ligne(li, _is_reseau_inverter)]
        lignes_hybride = [li for li in lignes
                          if _classe_ligne(li, _is_hybrid_inverter)]

        # ── ARTEFACT « DEUX ONDULEURS » (PVHEAL) ──
        #
        # Des devis de production portent LES DEUX onduleurs — hybride ET
        # réseau — vestige d'anciens chemins qui composaient les deux options
        # côte à côte. Le scénario, lui, n'en veut qu'un : le second est
        # facturé pour rien. On retire donc l'intrus… mais SEULEMENT s'il est
        # resté au prix catalogue, sans remise. Un prix modifié vaut prix
        # négocié : la ligne est conservée et l'écran le dit. Supprimer en
        # silence une ligne que quelqu'un a retouchée serait exactement la
        # perte que PV18 s'interdit.
        #
        # L-2OPT — SAUF sur un devis « Les deux » : là, les DEUX onduleurs sont
        # la composition NORMALE (réseau pour l'option « sans », hybride pour
        # l'option « avec »). Il n'y a pas d'intrus à retirer, ni rien à
        # signaler — c'est ce bloc qui rétrécissait DEV-202608-0023.
        if lignes_reseau and lignes_hybride and not devis_deux_options:
            intrus = lignes_reseau if a_batterie else lignes_hybride
            conserves = []
            for ligne in intrus:
                if _est_au_prix_catalogue(ligne):
                    ligne.delete()
                    lignes_modifiees += 1
                else:
                    conserves.append(ligne)
                    avertissements.append(
                        'Ce devis porte DEUX onduleurs (réseau et hybride). '
                        '« %s » n\'est pas au prix catalogue : il a été '
                        'CONSERVÉ (prix probablement négocié) — retirez-le à '
                        'la main s\'il n\'a rien à y faire.'
                        % (ligne.designation or 'ligne sans désignation'))
            if a_batterie:
                lignes_reseau = conserves
            else:
                lignes_hybride = conserves

        def _phase_du_client(ligne):
            """ADEV29 — raccordement DÉCLARÉ du lead, sinon la phase de
            l'onduleur en place (le client a déjà ce raccordement)."""
            from apps.ventes.compatibilites import (
                PHASE_MONO, PHASE_TRI, est_triphase_produit)
            from apps.ventes.domain.taille import phase_et_isolement_du_lead
            lead = getattr(verrou, 'lead', None)
            phase = phase_et_isolement_du_lead(lead)[0] if lead else None
            if phase:
                return phase
            produit = getattr(ligne, 'produit', None)
            if produit is None:
                return None
            return PHASE_TRI if est_triphase_produit(produit) else PHASE_MONO

        def _permuter_onduleur(ligne, predicat, role, motif_absence):
            # ADEV29 (C-ADEV-039) — la règle du composeur (≥ 0,8 × kWc, phase
            # du client), plus jamais « le moins cher de la marque préférée ».
            from apps.ventes.domain.catalogue import (
                choisir_onduleur_permutation)
            phase = _phase_du_client(ligne)
            remplacant = choisir_onduleur_permutation(
                verrou.company, predicat, kwc=kwc, phase=phase, role=role,
                gamme=gamme)
            if remplacant is None:
                avertissements.append(
                    motif_absence + (
                        ' Aucun modèle %s ne convient à ce devis.' % phase
                        if phase else ''))
                return False
            # QJR219 / D12 — ABSTENTION DITE sur un prix SAISI À LA MAIN. Sans
            # cette garde, le prix tapé était écrasé par le prix catalogue et
            # ``prix_manuel`` restait à True : la ligne affirmait un prix
            # vendeur qui n'existait plus. Voir MSG_PERMUTATION_PRIX_MANUEL
            # pour le choix entre les deux comportements admissibles.
            if getattr(ligne, 'prix_manuel', False):
                avertissements.append(MSG_PERMUTATION_PRIX_MANUEL % (
                    ligne.designation or 'ligne sans désignation',
                    remplacant.nom))
                return False
            ligne.produit = remplacant
            ligne.designation = remplacant.nom
            ligne.prix_unitaire = Decimal(remplacant.prix_vente)
            ligne.save(update_fields=['produit', 'designation',
                                      'prix_unitaire'])
            return True

        def _poser_onduleur_manquant(predicat, role, motif_absence):
            """L-2OPT — POSE l'onduleur qui manque à un devis « Les deux ».

            Un devis à deux options a besoin des DEUX familles : permuter celle
            qui reste reviendrait à détruire l'option qu'elle sert. On complète
            donc depuis le catalogue, au prix catalogue et sans remise (aucun
            chiffre inventé) ; sans produit tarifé, on le DIT et on laisse le
            scénario stocké dégrader honnêtement plus bas.
            """
            produit = _pick_product(verrou.company, predicat, role=role,
                                    gamme=gamme)
            if produit is None:
                avertissements.append(motif_absence)
                return None
            # QJR226 — le calcul de l'ordre vit dans ``_ordre_suivant`` (une
            # seule définition, partagée avec les créateurs panneau/batterie).
            return creer_ligne(
                verrou, produit=produit, designation=produit.nom,
                quantite=Decimal('1'),
                prix_unitaire=Decimal(produit.prix_vente),
                remise=Decimal('0'), ordre=_ordre_suivant(verrou))

        if devis_deux_options:
            # Les deux familles sont légitimes : on COMPLÈTE ce qui manque, on
            # ne permute JAMAIS (une permutation retirerait au client l'option
            # que la ligne permutée servait).
            if lignes_hybride and not lignes_reseau:
                ligne = _poser_onduleur_manquant(
                    _is_reseau_inverter, 'onduleur_reseau',
                    'Aucun onduleur réseau tarifé au catalogue : ce devis à '
                    'deux options ne peut pas présenter l\'option sans '
                    'batterie. Ajoutez un onduleur réseau tarifé.')
                if ligne is not None:
                    lignes_reseau = [ligne]
                    lignes_modifiees += 1
            elif lignes_reseau and a_batterie and not lignes_hybride:
                ligne = _poser_onduleur_manquant(
                    _is_hybrid_inverter, 'onduleur_hybride',
                    'Aucun onduleur hybride tarifé au catalogue : ce devis à '
                    'deux options ne peut pas présenter l\'option avec '
                    'batterie. Ajoutez un onduleur hybride tarifé.')
                if ligne is not None:
                    lignes_hybride = [ligne]
                    lignes_modifiees += 1
        elif a_batterie and lignes_reseau and not lignes_hybride:
            if _permuter_onduleur(
                    lignes_reseau[0], _is_hybrid_inverter, 'onduleur_hybride',
                    'Aucun onduleur hybride tarifé au catalogue : l\'onduleur '
                    'réseau a été conservé. La proposition ne pourra pas '
                    'présenter l\'option avec batterie.'):
                lignes_hybride, lignes_reseau = [lignes_reseau[0]], []
                lignes_modifiees += 1
        elif not a_batterie and lignes_hybride and not lignes_reseau:
            if _permuter_onduleur(
                    lignes_hybride[0], _is_reseau_inverter, 'onduleur_reseau',
                    'Aucun onduleur réseau tarifé au catalogue : l\'onduleur '
                    'hybride a été conservé alors que la batterie a été '
                    'retirée.'):
                lignes_reseau, lignes_hybride = [lignes_hybride[0]], []
                lignes_modifiees += 1

        # ``result``/``kwc`` sont déjà résolus plus haut (F8, juste après le
        # bloc panneaux) — le kit ci-dessous et l'étude plus bas les
        # réutilisent tels quels.

        # ── PVHEAL — COMPLÉTER le kit manquant (structures, socles, tableau…) ──
        #
        # Le squelette des devis d'hier devient le kit réellement installé. La
        # complétion n'AJOUTE que : les lignes en place, leurs prix négociés et
        # leur ordre ne sont jamais touchés (voir le bloc PVHEAL plus haut).
        # Deux devis en sont écartés, parce qu'une composition RÉSIDENTIELLE ne
        # décrit pas leur kit : l'agricole (pompage — ni structure de toiture
        # ni socles) et le multi-villa (chaque villa a le sien, une série de
        # lignes hors groupe y serait fausse).
        lignes_ajoutees = 0
        if agricole or multi_villa:
            if multi_villa and not agricole:
                avertissements.append(
                    'Devis multi-villa : le kit manquant (structures, socles, '
                    'tableau de protection…) n\'a pas été complété '
                    'automatiquement — chaque villa a le sien.')
        else:
            lignes_ajoutees = _completer_kit_residentiel(
                verrou, kwc=kwc, watt=watt, nb_panneaux=total_panneaux,
                # L-2OPT — un devis à deux options doit porter le kit de
                # l'option la PLUS équipée : celle avec batterie. Le compléter
                # « sans » laisserait l'option « avec » incomplète au PDF.
                avec_batterie=True if devis_deux_options else a_batterie,
                avertissements=avertissements)

        # ── QJR220 — LES FORFAITS AU PANNEAU SUIVENT LE COMPTE RÉELLEMENT
        # ÉCRIT ──
        #
        # ``retarifer_forfaits_par_panneau`` (QJR83) n'avait qu'UN appelant dans
        # tout le dépôt : ``lignes.remplacer_lignes``. Or ``MODE_RECONCILIER``
        # n'appelle JAMAIS ``ecrire_lignes`` — et c'est précisément LE mode qui
        # change un compte de panneaux sur un devis EXISTANT (les trois sites
        # ``dominante.quantite = …`` ci-dessus). Une sync-layout 9 → 20
        # panneaux laissait donc la pose, les accessoires et le tableau au
        # barème de 9 : de l'argent faux sur un document client (l'incident
        # 9→20 que le fichier de test de QJR83 nomme lui-même).
        #
        # APPELÉE ICI, après TOUTES les écritures de lignes (quantités,
        # permutations, complétion du kit) : le barème s'applique au compte
        # RÉEL, jamais à celui que l'appelant croyait poser. Les abstentions
        # D12 (prix_manuel, forfait commun divergent) sont préservées et DITES
        # — elles rejoignent la même liste que les autres refus de resynchro,
        # celle que l'écran affiche déjà.
        retarifer_forfaits_par_panneau(verrou, avertissements=avertissements,
                                       comptes_avant=comptes_avant)

        # ── Étude : les clés géométriques + le scénario, jamais les champs
        # d'étude du générateur ──
        etude = dict(verrou.etude_params or {})
        # CIQ117 — commercial/industriel : le layout n'apporte que la
        # géométrie et le kWc, jamais production ni économies (le moteur C&I
        # les calcule) ; résidentiel/agricole inchangés.
        from apps.ventes.domain.etude_schema import cles_etude_du_layout
        etude.update(cles_etude_du_layout(
            getattr(verrou, 'mode_installation', None), result))
        # QJR63 — LE kWc VIENT DE SON PROPRIÉTAIRE, PLUS DU LAYOUT. Ce site
        # écrivait ``kwc`` — celui du CALEPINAGE — même quand la règle de
        # plafond de variante venait de faire atterrir le devis sur un AUTRE
        # compte de panneaux : le kWc stocké décrivait alors une installation
        # NON VENDUE, que ``Devis.save`` figeait ensuite dans ``prix_par_kwc``.
        # Les lignes sont déjà resynchronisées à ce point : le propriétaire lit
        # donc l'état RÉEL (registre de surcharges, sinon dérivation PVUNI).
        # QJR217 — l'AVERTISSEMENT R4-A remonte par la même liste que tous les
        # autres refus de resynchro : l'écran l'affiche déjà (réponse
        # ``sync-layout``), donc le désaccord « ligne verrouillée à N /
        # taille.nb_panneaux = M » cesse d'être silencieux.
        # QJR225 — LE REPLI SUR LE kWc DU CALEPINAGE A ÉTÉ RETIRÉ. Ce site
        # écrivait encore ``etude['puissance_kwc'] = kwc`` (le kWc du LAYOUT)
        # quand le propriétaire ne savait pas répondre : deux contradictions à
        # la fois — la règle « écrivain unique » de QJR63
        # (``domain.scenario.poser_puissance_kwc``, seul écrivain déclaré) et
        # la préférence Z2 de ce module lui-même (OMETTRE une valeur inconnue
        # plutôt que la fabriquer). Le calepinage modélise à watt constant :
        # ce n'est pas le panneau vendu. Sans kWc lisible, la clé est
        # ABSENTE — jamais un nombre de repli.
        # QJR306 — LE kWc PÉRIMÉ NE SURVIT PAS À UNE RESYNCHRO MUETTE. QJR225
        # avait retiré le REPLI sur le kWc du calepinage, mais pas la valeur
        # HÉRITÉE d'une exécution PRÉCÉDENTE : quand le propriétaire ne sait
        # plus répondre, la clé recopiée depuis ``verrou.etude_params`` à la
        # ligne ci-dessus restait en place — un devis qui a DÉJÀ eu la clé la
        # gardait, décrivant une installation qui n'est plus celle vendue. La
        # règle Z2 (OMETTRE plutôt que fabriquer) s'applique donc aussi au
        # RETRAIT d'une valeur devenue illisible, pas seulement à l'absence
        # d'écriture.
        _kwc_proprietaire = puissance_kwc_du_devis(
            verrou, avertissements=avertissements)
        if _kwc_proprietaire:
            etude['puissance_kwc'] = _kwc_proprietaire
        else:
            etude.pop('puissance_kwc', None)
        if toiture:
            etude['toiture'] = toiture
        # PVSCE — le scénario suit l'état RÉEL des lignes après resynchro : sans
        # lui, le moteur PDF garderait le choix stocké d'avant (ou déduirait
        # « Sans batterie » par repli) alors que l'équipement vient de changer.
        #
        # L-2OPT — un devis NÉ « Les deux » re-stocke « Les deux », jamais un
        # libellé mono : c'est cette déclaration que le moteur PDF lit pour
        # rendre la comparaison (PV86/QF6). Même garde anti-mensonge qu'à la
        # création (U2) : on ne le re-stocke que si les lignes peuvent
        # RÉELLEMENT servir les deux côtés (réseau d'un côté, hybride +
        # batterie de l'autre) — sinon on dégrade au libellé mono honnête.
        #
        # QJR97 — ET C'EST LA MÊME FONCTION QU'À LA CRÉATION. Cette garde était
        # écrite EN ENTIER ici ET dans ``pipeline.ecrire_etude_params``, sous
        # deux formulations des mêmes conditions. Les deux appellent désormais
        # ``domain.scenario`` : la règle qui décide de ce que le client voit sur
        # sa proposition n'a plus qu'un seul endroit où diverger — aucun.
        # QJR607 — le classifieur d'onduleur AUTONOME entre aussi : un site
        # isolé (autonome + batterie) sert l'option « avec ».
        from apps.ventes.domain.catalogue import _is_offgrid_inverter
        _faits = dict(a_reseau=bool(lignes_reseau),
                      a_hybride=bool(lignes_hybride),
                      a_batterie=bool(a_batterie),
                      a_offgrid=any(_classe_ligne(li, _is_offgrid_inverter)
                                    for li in _lignes_produit(verrou)))
        _scenario_auto = scenario_servable(devis_deux_options, **_faits)
        deux_options_servies = _scenario_auto == SCENARIO_LES_DEUX
        # QJR64 / décision fondateur D12 — UN SCÉNARIO DÉCLARÉ SURVIT À TOUT
        # RECALCUL. Ce site RE-DÉRIVAIT le scénario sans condition : un
        # « Les deux (Sans + Avec) » posé par un humain pouvait redevenir
        # « Avec batterie » à la première resynchro, et le PDF cessait de
        # rendre la comparaison. La dérivation ci-dessus reste le défaut ; elle
        # ne s'applique plus qu'en l'ABSENCE de surcharge au registre.
        etude['scenario'] = scenario_effectif(verrou, _scenario_auto)

        # QJ21 — le layout stocké porte la géométrie par pan DÉJÀ traitée, pour
        # que ses consommateurs n'aient pas à ré-extraire. Copie, jamais une
        # mutation du dict de l'appelant. L'empreinte, elle, est calculée sur
        # le layout D'ORIGINE (clés géométriques seules) : cet enrichissement
        # ne peut donc pas casser le court-circuit au prochain envoi.
        # ACAL96 — UN SEUL rangement : celui de la création
        # (``creation_calepinage._calepinage_range``), plus de copie inline.
        from apps.ventes.domain.creation_calepinage import _calepinage_range
        layout_stocke, _etude = _calepinage_range(layout, toiture, None)

        verrou.roof_layout = layout_stocke
        if ecart_residuel:
            # ACAL100 — l'écart n'a pas été ENTIÈREMENT appliqué : l'ancienne
            # empreinte reste, le devis est toujours « à resynchroniser ».
            avertissements.append(
                'Écart de calepinage non entièrement appliqué : le devis '
                'reste « à resynchroniser » — corrigez la cause ci-dessus '
                'puis resynchronisez.')
        else:
            verrou.layout_hash = nouveau_hash or verrou.layout_hash
        # QJR62 — la RÈGLE de fusion vient de l'écrivain unique
        # (``domain.etude_schema``) ; seule la PERSISTANCE diffère ici, parce
        # que ce chemin écrit ``roof_layout`` + ``layout_hash`` +
        # ``etude_params`` d'un SEUL ``save`` (le scinder ferait deux
        # allers-retour et deux fenêtres de course pour rien).
        # On ne soumet au validateur que les clés que CE chemin a réellement
        # CHANGÉES : une clé héritée d'un devis ancien (et pas encore déclarée
        # au schéma) ne doit pas faire échouer une resynchro qui ne la touche
        # même pas.
        from apps.ventes.domain.etude_schema import CALEPINAGE, fusionner
        _avant = dict(verrou.etude_params or {})
        _modifiees = {cle: valeur for cle, valeur in etude.items()
                      if cle not in _avant or _avant[cle] != valeur}
        # QJR306 — les RETRAITS voyagent aussi : ``etude`` est une copie
        # intégrale de ``_avant``, donc une clé présente AVANT et absente
        # d'``etude`` a été retirée PAR CE CHEMIN (le kWc périmé quand le
        # propriétaire ne répond plus). ``fusionner`` a déjà la sémantique du
        # retrait (``None`` = retirer la clé) ; sans cette ligne, le pop
        # d'amont était silencieusement perdu et la valeur périmée reconduite.
        _modifiees.update({cle: None for cle in _avant if cle not in etude})
        verrou.etude_params = fusionner(
            _avant, proprietaire=CALEPINAGE, **_modifiees)
        # `update_fields` EXCLUT `statut` : le statut ne peut pas partir d'ici,
        # même par accident (règle #4).
        verrou.save(update_fields=[
            'roof_layout', 'layout_hash', 'etude_params'])

        logger.info(
            'PV18: devis %s resynchronisé sur son calepinage (%d panneaux, '
            '%.2f kWc, %d ligne(s) touchée(s), %d ligne(s) de kit ajoutée(s), '
            'société %s, par %s)',
            verrou.reference, total_panneaux, kwc, lignes_modifiees,
            lignes_ajoutees, getattr(verrou.company, 'id', '?'),
            getattr(user, 'username', '?'))

        resultat = {
            'inchange': False,
            'panneaux': total_panneaux,
            'kwc': kwc,
            # L-2OPT — le champ dit l'état RÉEL du devis après resynchro :
            # « les_deux » (vocabulaire déjà en place, cf.
            # ``SCENARIOS_DEMANDABLES``) quand les deux options sont servies.
            'scenario': ('les_deux' if deux_options_servies
                         else ('avec_batterie' if a_batterie else 'reseau')),
            'batterie': a_batterie,
            'lignes_modifiees': lignes_modifiees,
            'lignes_ajoutees': lignes_ajoutees,
            'avertissements': avertissements,
        }

    # PV42 — la toiture a bougé : la conception ÉLECTRIQUE la suit, par pan.
    # HORS de la transaction, et en meilleur effort : une étude électrique en
    # panne ne doit ni annuler la resynchro déjà validée, ni salir sa
    # transaction. L'empreinte d'entrée (PV41) évite toute réécriture inutile.
    concevoir_electrique_du_devis(verrou, origine=ORIGINE_RESYNCHRONISATION)
    # QJR20 — l'appelant repart de CE QUI VIENT D'ÊTRE ÉCRIT (voir
    # ``_resynchroniser_instance_appelante`` : sans cela, les études
    # rafraîchies juste après décrivent la composition d'AVANT la resynchro).
    _resynchroniser_instance_appelante(devis, verrou)
    return resultat


def _reconcilier_panneaux_par_modele(verrou, lignes_panneau, modeles,
                                     avertissements):
    """ACAL63 (C-ACAL-042) — porte CHAQUE ligne panneau au compte de SON
    modèle désigné par le calepinage. Rend ``(lignes_modifiees, a_change)``.

    * modèle à fiche désignée : la (plus grosse) ligne LIBRE de CE produit
      reçoit l'écart ; absente, une ligne de la fiche est créée au prix
      catalogue (une fiche non tarifée n'est jamais cotée : l'écart est DIT) ;
    * modèle sans fiche : la ligne panneau restante la plus grosse, à défaut
      le panneau du catalogue au wattage du modèle ;
    * une ligne panneau d'un produit qu'AUCUN modèle ne désigne est ramenée à
      0 et NOMMÉE (jamais une suppression silencieuse) ;
    * une quantité TAPÉE (QJR60 / D12) n'est jamais réécrite : l'écart est
      nommé.
    Jamais ``quantite_manuelle`` / ``prix_manuel`` posés.

    ACAL100 — rend ``(lignes_modifiees, a_change, ecart_residuel)`` :
    ``ecart_residuel`` est vrai quand un écart a été NOMMÉ au lieu d'être
    appliqué (quantité tapée, fiche non tarifée)."""
    from apps.ventes.domain.geometrie import _produit_designe

    modifiees = 0
    change = False
    residuel = False
    restantes = list(lignes_panneau)

    def _porter(lignes_m, cible, libelle):
        nonlocal modifiees, change, residuel
        total = sum(int(li.quantite or 0) for li in lignes_m)
        if total == cible:
            return
        libres = [li for li in lignes_m if not _quantite_verrouillee(li)]
        if not libres:
            _avertir_verrouillee(
                avertissements, lignes_m,
                "l'écart de %d panneau(x) « %s »" % (abs(total - cible),
                                                     libelle))
            residuel = True
            return
        dominante = max(libres, key=lambda li: Decimal(str(li.quantite or 0)))
        nouvelle = max(0, int(dominante.quantite or 0) + (cible - total))
        dominante.quantite = Decimal(str(nouvelle))
        dominante.save(update_fields=['quantite'])
        modifiees += 1
        change = True

    for modele in modeles:
        cible = int(modele.get('count') or 0)
        produit_id = modele.get('produit_id')
        if produit_id:
            try:
                cle = int(produit_id)
            except (TypeError, ValueError):
                cle = None
            lignes_m = [li for li in restantes if li.produit_id == cle]
            for li in lignes_m:
                restantes.remove(li)
            produit = (None if lignes_m
                       else _produit_designe(verrou.company, produit_id))
        else:
            lignes_m = ([max(restantes,
                             key=lambda li: Decimal(str(li.quantite or 0)))]
                        if restantes else [])
            for li in lignes_m:
                restantes.remove(li)
            produit = (None if lignes_m else _pick_product(
                verrou.company, _is_panel, watt=modele.get('watt'),
                role='panneau', gamme=gamme_nom(verrou)))
        if lignes_m:
            _porter(lignes_m, cible, getattr(lignes_m[0].produit, 'nom', '')
                    or lignes_m[0].designation)
            continue
        if produit is None:
            avertissements.append(
                'Le module désigné par le calepinage (fiche #%s) n\'est pas '
                'tarifé dans votre catalogue : sa ligne de %d panneau(x) n\'a '
                'pas été créée — tarifez la fiche puis resynchronisez.'
                % (produit_id or '?', cible))
            residuel = residuel or cible > 0
            continue
        if cible > 0:
            creer_ligne(
                verrou, produit=produit, designation=produit.nom,
                quantite=Decimal(str(cible)),
                prix_unitaire=Decimal(produit.prix_vente),
                remise=Decimal('0'), ordre=_ordre_suivant(verrou))
            modifiees += 1
            change = True

    for ligne in restantes:
        if int(ligne.quantite or 0) <= 0:
            continue
        if _quantite_verrouillee(ligne):
            _avertir_verrouillee(
                avertissements, [ligne],
                'la ligne « %s », hors des modules du calepinage'
                % ligne.designation)
            residuel = True
            continue
        avertissements.append(
            'La ligne de panneaux « %s » ne correspond à aucun module posé '
            'sur le calepinage : elle a été ramenée à 0.' % ligne.designation)
        ligne.quantite = Decimal('0')
        ligne.save(update_fields=['quantite'])
        modifiees += 1
        change = True
    return modifiees, change, residuel


def sync_devis_from_layout(devis, layout, user=None, *, cible_exacte=False):
    """PV18 — ADAPTATEUR (QJR97, bascule 5/5a).

    Cette fonction ne PORTE plus le geste : elle le DEMANDE. Elle traduit ses
    arguments historiques en ``IntentionDevis`` et laisse ``pipeline.appliquer``
    ordonner le mode « réconcilier », dont l'étape unique est
    :func:`reconcilier` (juste au-dessus, où la règle PV18 est documentée).
    Son ancien corps — le geste chirurgical lui-même — n'existe plus ici : il
    n'y a pas deux implémentations, il y en a une, appelée par un pipeline.

    La SIGNATURE et le RÉSULTAT sont INCHANGÉS À L'OCTET : le viewset PV18, le
    chemin apply-taille et la commande de réparation lisent exactement le même
    dict ``{inchange, panneaux, kwc, scenario, batterie, lignes_modifiees,
    lignes_ajoutees, avertissements}``, et ``SyncLayoutError`` remonte telle
    quelle à travers le pipeline (aucune étape ne l'intercepte).
    """
    resultat = appliquer(devis, IntentionDevis(
        origine=ORIGINE_RESYNCHRONISATION,
        company=getattr(devis, 'company', None),
        user=user,
        layout=layout if isinstance(layout, dict) else {},
        # La cible vient-elle d'un NOMBRE TAPÉ (apply-taille) plutôt que d'un
        # toit ? C'est le seul choix que cet adaptateur transmet.
        exact=bool(cible_exacte),
        mode=MODE_RECONCILIER))
    return resultat['resynchro']


def emettre_layout_finalise(devis, user):
    """PV79 — annonce que la conception 3D d'un devis est finalisée.

    Passe par le bus ``core.events`` (M6) plutôt que par un appel direct à
    ``crm`` : les deux apps restent découplées. Ne change AUCUN statut et
    n'écrit rien lui-même (règle #4). Jamais bloquant : un abonné en échec ne
    fait pas échouer la finalisation d'un calepinage déjà enregistré.

    ACAL34 — déplacé ici depuis la vue (qui y délègue) pour que l'enveloppe
    :func:`resynchroniser_conception` l'émette elle-même ; le littéral
    ``sender`` est INCHANGÉ (aucun récepteur ne filtre dessus).
    """
    from core.events import layout_finalise
    try:
        layout_finalise.send(sender='ventes.views.devis', devis=devis,
                             user=user)
    except Exception:  # noqa: BLE001 — un abonné cassé ne casse pas le devis
        logging.getLogger(__name__).exception(
            'PV79 : abonné en échec sur layout_finalise (devis %s)', devis.pk)


def resynchroniser_conception(devis, layout, user=None, *, emettre=True,
                              roof_image=None):
    """ACAL34 (C-ACAL-109) — L'ENVELOPPE UNIQUE d'une resynchronisation de
    conception : ``sync-layout`` (ventes) ET « Resynchroniser le devis »
    (module calepinage) l'appellent, plus aucune suite recopiée.

    1. :func:`sync_devis_from_layout` — le geste chirurgical (PV18), tracé
       « corrigé après envoi » sur un ENVOYÉ (QJR557) ;
    2. si quelque chose a changé (pas ``inchange``) : les QUATRE études
       repartent de la composition COURANTE
       (``etudes.rafraichir_etudes_du_devis`` — étude horaire, profils,
       dimensionnement, électrique) ; sur un envoyé, ce rafraîchissement a lieu
       DANS ce geste explicite, jamais hors geste ;
    3. si ``emettre`` : l'annonce ``layout_finalise`` (PV79).

    ACAL98 (C-ACAL-107) — ``roof_image`` (la clé de l'affiche du calepinage,
    passée par la resynchro du MODULE) : quand quelque chose a changé, ses
    octets sont COPIÉS sous la clé du devis
    (``stockage_toiture.poser_affiche_depuis``) ; ``None`` (défaut, la route
    ``sync-layout``) ne touche pas l'affiche. Best-effort : un magasin
    injoignable n'annule pas la resynchro déjà validée.

    Rend le dict de :func:`sync_devis_from_layout`, INCHANGÉ ; ``SyncLayoutError``
    remonte telle quelle. Aucun statut écrit (règle #4).
    """
    resultat = sync_devis_from_layout(devis, layout, user)
    if isinstance(resultat, dict) and resultat.get('inchange'):
        return resultat
    if roof_image:
        from apps.ventes.domain.stockage_toiture import poser_affiche_depuis
        try:
            poser_affiche_depuis(devis, roof_image)
        except Exception:  # noqa: BLE001 — cf. docstring : jamais bloquant
            logger.warning(
                'ACAL98 : affiche du calepinage non copiée sur le devis %s',
                getattr(devis, 'pk', None), exc_info=True)
    if emettre:
        emettre_layout_finalise(devis, user)
    # QJR20 — ``sync_devis_from_layout`` a recalé l'instance passée sur la
    # ligne verrouillée et écrite : les études se calculent sur la
    # composition d'APRÈS la resynchro.
    from apps.ventes.domain.etudes import rafraichir_etudes_du_devis
    rafraichir_etudes_du_devis(devis)
    return resultat


class ConceptionRefusee(Exception):
    """ACAL96 — refus du CALEPINAGE lié (jeton périmé, document invalide,
    verrou, devis introuvable) : ``statut`` HTTP et ``corps`` tels que le
    module les rend, propagés mot pour mot par la vue."""

    def __init__(self, statut, corps):
        super().__init__(str(corps))
        self.statut = statut
        self.corps = corps


def _sans_cles_privees(layout):
    """Le document de conception sans les clés PRIVÉES du devis (racine
    préfixée ``_`` : ``_pans_geometry``…) — même règle que l'adoption
    (``apps.calepinage.services.creation``) : jamais recopiées dans la
    conception ; l'empreinte imprimée ne les lit pas."""
    return {cle: valeur for cle, valeur in (layout or {}).items()
            if not str(cle).startswith('_')}


def ecrire_conception_du_devis(devis, layout, user=None, *,
                               base_empreinte=None):
    """ACAL96 (D-ACAL-1, C-ACAL-102) — ``sync-layout`` et ``POST layout`` du
    devis écrivent LE CALEPINAGE lié, puis resynchronisent le devis.

    1. refus de statut (prédicat ventes ``CALEPINAGE``) AVANT toute écriture
       → :class:`SyncLayoutError` (409 existant) ;
    2. le calepinage du devis : lié, sinon adopté/créé par la porte unique
       ``apps.calepinage.services.adopter_ou_creer_pour_devis`` ;
    3. ``enregistrer_layout`` — SEUL écrivain du document (version seulement
       si changé ; jeton ``If-Match`` comparé s'il est fourni) ;
    4. :func:`resynchroniser_conception` sur ``calepinage.roof_layout`` —
       seule à écrire ``Devis.roof_layout`` (rangé par ``_calepinage_range``,
       avec ``_pans_geometry``). Plus aucune écriture de ``Devis.roof_layout``
       depuis un corps arbitraire.

    Rend le dict de la resynchro, INCHANGÉ. Aucun statut écrit (règle #4).

    Raises:
        SyncLayoutError: devis figé (accepté, refusé, expiré, remplacé).
        ConceptionRefusee: refus du calepinage (statut + corps du module).
    """
    refus = _refus_resynchro(devis)
    if refus is not None:
        raise refus
    from apps.calepinage import services as calepinage_services

    try:
        calepinage, _origine = calepinage_services.adopter_ou_creer_pour_devis(
            devis.pk, devis.company, user=user)
        calepinage_services.enregistrer_layout(
            calepinage, _sans_cles_privees(layout), user=user,
            base_empreinte=base_empreinte)
    except calepinage_services.DocumentModifie as conflit:
        raise ConceptionRefusee(409, conflit.corps()) from None
    except (calepinage_services.LayoutRefuse,
            calepinage_services.CreationRefusee) as erreur:
        champ = getattr(erreur, 'champ', '') or 'roof_layout'
        raise ConceptionRefusee(400, {champ: str(erreur)}) from None
    # Lot 2 critique #28 — la resynchro passe par LA porte du module
    # (``resynchroniser_devis``) : approbation / feu vert à jour (ACAL116) et
    # garde électrique (ACAL170) s'appliquent ici comme à « Resynchroniser le
    # devis » du calepinage, avec les MÊMES corps de refus (400 nommé, 422
    # ``{detail, electrique}``, 409 ``{detail, revision_possible}``). La
    # conception reste enregistrée ; le devis n'est pas touché sur refus.
    from rest_framework.exceptions import ValidationError

    try:
        return calepinage_services.resynchroniser_devis(calepinage, user=user)
    except calepinage_services.DevisRefuse as refus:
        raise ConceptionRefusee(
            refus.statut,
            refus.donnees or {refus.champ or 'detail': str(refus)}) from None
    except ValidationError as refus:
        raise ConceptionRefusee(400, refus.detail) from None


# ── PONTS M3 : noms hébergés ailleurs ────────────────────────────────────────
# Imports EN BAS DE FICHIER, visant le module qui PORTE chaque corps.
from apps.ventes.domain.bordereau import concevoir_electrique_du_devis  # noqa: E402,F401
from apps.ventes.domain.catalogue import (  # noqa: E402,F401
    SOCLES_PAR_PANNEAU,
    STRUCTURES_PAR_PANNEAU,
    _arrondi_js,
    _est_au_metre,
    _is_battery,
    _is_cable_dc,
    _is_cable_terre,
    _is_hybrid_inverter,
    _is_panel,
    _is_reseau_inverter,
    _is_socle,
    _is_structure,
    _pick_batterie,
    _pick_product,
    _plage_batterie_de_l_onduleur,
    metre_cable_dc,
    metre_cable_terre,
)
from apps.ventes.domain.composition import (  # noqa: E402,F401
    VARIANTE_AVEC,
    VARIANTE_SANS,
    _completer_kit_residentiel,
    _est_au_prix_catalogue,
    _refuser_couple_panneau_onduleur_impossible,
    _v_txt,
)
from apps.ventes.domain.gammes import gamme_nom  # noqa: E402,F401
from apps.ventes.domain.geometrie import (  # noqa: E402,F401
    _cible_panneaux_du_layout,
    _watt_du_layout,
    extract_roof_config,
    layout_hash,
    modeles_designes,
    scenario_du_layout,
)
from apps.ventes.domain.lignes import (  # noqa: E402,F401
    _classe_ligne,
    _lignes_produit,
    creer_ligne,
    retarifer_forfaits_par_panneau,
)
# QJR97 — le pipeline est importé EN BAS, comme tout pont de ce paquet. Il n'y
# a pas de cycle : ``pipeline`` n'importe CE module que depuis l'intérieur de
# son étape ``reconcilier`` (import fonction-local, délibéré), donc il est
# toujours complètement chargé quand cette ligne s'exécute.
from apps.ventes.domain.pipeline import (  # noqa: E402,F401
    MODE_RECONCILIER,
    ORIGINE_RESYNCHRONISATION,
    IntentionDevis,
    appliquer,
)
from apps.ventes.domain.etape_composer import (  # noqa: E402,F401
    COMPOSITION_AVEC,
    COMPOSITION_LES_DEUX,
)
from apps.ventes.domain.scenario import (  # noqa: E402,F401
    SCENARIO_LES_DEUX,
    puissance_kwc_du_devis,
    scenario_effectif,
    scenario_servable,
)
