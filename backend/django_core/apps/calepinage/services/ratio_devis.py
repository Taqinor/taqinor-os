"""ACAL1954 / D-ACAL-91 — LE verdict du ratio DC/AC du calepinage, jugé avec
la règle du MOTEUR DE DEVIS (demande du fondateur : « one engine, the CRM one »).

Décision D-ACAL-91 (orchestrateur, à confirmer par le fondateur ; elle remplace
le « Non jugé sans fourchette société » d'ACAL1538) — la borne qui juge est,
dans cet ordre :

* l'exigence de MARCHÉ (CPS du dossier) quand elle existe ;
* pour un onduleur HYBRIDE qui publie ``dc_max_kwc`` : sa capacité publiée
  (règle D-HYB-1, ``core.electrique.onduleurs.capacite_publiee_hybride``, la
  même que le moteur C&I) ;
* la FOURCHETTE DE LA SOCIÉTÉ quand elle est réglée ;
* sinon la RÈGLE DU DEVIS : la borne du moteur de devis, lue par
  ``apps.ventes.selectors_calepinage.borne_dc_ac_du_moteur_devis`` (jamais une
  copie du nombre).

Au-dessus ⇒ non conforme (« à régler »), jamais « Bon ». UNE fonction juge
(:func:`juger_ratio`) ; le bloc ``ratio_dc_ac``, le verdict CAL244 de l'étape
Électrique et « Prêt à envoyer ? » la lisent tous trois.
"""
from __future__ import annotations

from .valeurs import nombre as _nombre

SOURCE_BORNE_MARCHE = 'exigence de marché'
SOURCE_BORNE_SOCIETE = 'fourchette de la société'
SOURCE_BORNE_DEVIS = 'règle du devis'
SOURCE_BORNE_CAPACITE = "capacité publiée de l'onduleur"
#: D-HYB-1 — un HYBRIDE dont la fiche ne publie pas sa puissance PV maximale
#: (``dc_max_kwc``, libellé de la fiche technique du Stock) est jugé à la borne
#: de ratio, et la phrase le DIT avec le champ à remplir (lead 1742, 26/11/2026 :
#: « 1,72 pour 1,35 au plus » sans dire pourquoi la fiche n'a pas jugé).
MOTIF_HYBRIDE_SANS_CAPACITE = (
    "la fiche de l'onduleur hybride ne publie pas sa puissance PV maximale : "
    "compléter « Puissance PV maximale raccordable (kWc) » dans sa fiche technique (Stock)")


def bornes_ratio(*, exigence_marche=None, parametres_societe=None,
                 reglages=None):
    """``(borne_dc_ac, seuil_alerte, source, detail)`` — jamais une borne écrite ici.

    ``exigence_marche`` et ``parametres_societe`` portent ``ratio_dc_ac_max`` (et,
    optionnellement, ``ratio_dc_ac_alerte``) ; puis la borne usuelle SAISIE de la
    section « electrique_societe » (``reglages``) ; sinon la règle du devis."""
    from core.electrique.onduleurs import (
        SEUIL_ALERTE_DC_AC, SOURCE_CONVENTION_ATELIER, bornes_dc_ac,
    )
    from core.electrique.types import fr

    from .equipements import borne_dc_ac_devis

    for donnees, source in ((exigence_marche, SOURCE_BORNE_MARCHE),
                            (parametres_societe, SOURCE_BORNE_SOCIETE)):
        borne = _nombre((donnees or {}).get('ratio_dc_ac_max'))
        if borne is not None and borne > 0:
            alerte = _nombre((donnees or {}).get('ratio_dc_ac_alerte'))
            return (borne, alerte if alerte and alerte > 0 else None, source,
                    (donnees or {}).get('reference') or '')
    saisies = bornes_dc_ac(reglages)
    if saisies.borne_usuelle.source != SOURCE_CONVENTION_ATELIER:
        alerte = saisies.seuil_alerte
        return (saisies.borne_usuelle.valeur,
                (alerte.valeur if alerte.source != SOURCE_CONVENTION_ATELIER
                 else None), SOURCE_BORNE_SOCIETE, saisies.borne_usuelle.source)
    borne = borne_dc_ac_devis()
    return (borne, SEUIL_ALERTE_DC_AC, SOURCE_BORNE_DEVIS,
            'borne du moteur de devis : %s au plus' % fr(borne, 2))


def bornes_du_verdict(bornes, evaluation, conception):
    """Les bornes qui JUGENT : la capacité publiée d'un hybride (D-HYB-1) passe
    devant la fourchette de la société et la règle du devis — jamais devant une
    exigence de marché. Rendue sous la même forme ``(borne, alerte, source,
    detail)``, la borne exprimée en ratio (capacité ÷ puissance AC)."""
    from core.electrique.onduleurs import capacite_publiee_hybride
    from core.electrique.types import fr

    if bornes[2] == SOURCE_BORNE_MARCHE or evaluation is None or not evaluation.nombre:
        return bornes
    entree = getattr(conception, 'entree', None)
    capacite = capacite_publiee_hybride(getattr(entree, 'onduleur', None), evaluation.nombre)
    ac = evaluation.puissance_ac_kw
    if capacite is None or not ac:
        return bornes
    return (capacite / ac, None, SOURCE_BORNE_CAPACITE,
            'fiche constructeur : %s kWc au plus' % fr(capacite, 0))


def motif_capacite_non_publiee(conception, source=None):
    """D-HYB-1 — :data:`MOTIF_HYBRIDE_SANS_CAPACITE` quand l'onduleur de la
    ``conception`` est un hybride dont la fiche ne publie pas ``dc_max_kwc`` (la
    borne de ratio le juge alors), ``''`` sinon — et ``''`` quand la borne qui
    juge (``source``, si donnée) est une exigence de marché. Fonction PURE."""
    from core.electrique.onduleurs import dc_max_publie_kwc, onduleur_est_hybride

    if source is not None and source not in (SOURCE_BORNE_DEVIS, SOURCE_BORNE_SOCIETE):
        return ''
    onduleur = getattr(getattr(conception, 'entree', None), 'onduleur', None)
    if onduleur is None or not onduleur_est_hybride(onduleur):
        return ''
    publie = dc_max_publie_kwc(getattr(onduleur, 'dc_max_kwc', None)) is not None
    return '' if publie else MOTIF_HYBRIDE_SANS_CAPACITE


def famille_de_l_onduleur(produit):
    """D-HYB-1 (fondateur 24/11/2026 : « un produit se reconnaît à son rôle et à sa fiche
    avant son nom ») — ``(role, famille_par_nom)`` d'un produit DÉJÀ LU (aucune requête) :

    * ``role`` : le rôle de devis DÉCLARÉ (``core.product_roles.role_declare``), ``''``
      sinon — la famille de catégorie « onduleur » est ambiguë (``FAMILLE_VERS_ROLE``) et
      ne donne jamais de rôle d'onduleur ;
    * ``famille_par_nom`` : la famille d'onduleur AUTRE qu'hybride que le classifieur du
      catalogue lit dans son nom (``ventes.selectors_calepinage.autre_famille_d_onduleur_par_nom``).

    Rangés sur le ``SpecOnduleur`` (``role``, ``famille_par_nom``), lus par
    ``core.electrique.onduleurs.onduleur_est_hybride``."""
    from apps.ventes.selectors_calepinage import autre_famille_d_onduleur_par_nom
    from core.product_roles import role_declare

    if produit is None:
        return ('', '')
    return (role_declare(getattr(produit, 'role_devis', None)) or '',
            autre_famille_d_onduleur_par_nom(getattr(produit, 'nom', '') or ''))


def juger_ratio(valeur, bornes, reglages=None):
    """LE verdict du ratio DC/AC : ``True`` / ``False``, ``None`` sans ratio.

    Au-dessus de la borne qui juge ⇒ ``False`` ; sous le seuil BAS saisi par la
    société ⇒ ``False``. Aucune borne ne « publie sans juger »."""
    from core.electrique.onduleurs import bornes_dc_ac

    if valeur is None:
        return None
    bas = bornes_dc_ac(reglages).seuil_bas
    dans = valeur <= bornes[0] + 1e-9
    return dans and (not bas.controlee or valeur >= bas.valeur - 1e-9)


def detail_ratio(texte, conforme, bornes, *, valeur=None, reglages=None, conception=None):
    """La phrase du verdict, qui dit D'OÙ vient la borne — et, sous le seuil BAS
    réglé par la société, LA borne franchie : la règle du devis
    (``borne_dc_ac_du_moteur_devis``) ne fixe qu'un plafond, jamais de borne
    basse ; seul le seuil bas de la société (``seuil_bas_dc_ac``) peut juger un
    ratio trop faible (rejeu T3-VAGUEC2 : « 0,99 pour 1,35 au plus » à régler
    sans raison dite). D-HYB-1 : refusé par la borne de ratio parce que la fiche
    d'un hybride (``conception``) ne publie rien, la phrase le dit et nomme le champ."""
    from core.electrique.onduleurs import bornes_dc_ac
    from core.electrique.types import fr

    borne, _alerte, source, detail = bornes
    bas = bornes_dc_ac(reglages).seuil_bas
    if (not conforme and valeur is not None and bas.controlee
            and valeur < bas.valeur - 1e-9):
        plafond = ("la règle du devis n'a pas de borne basse, %s au plus" % fr(borne, 2)
                   if source == SOURCE_BORNE_DEVIS else '%s au plus, %s' % (fr(borne, 2), source))
        return '%s : sous le seuil bas de %s réglé par la société (%s)' % (
            texte, fr(bas.valeur, 2), plafond)
    if source == SOURCE_BORNE_CAPACITE:
        return '%s — %s la capacité publiée de l\'onduleur (%s)' % (
            texte, 'dans' if conforme else 'au-delà de', detail)
    phrase = '%s pour %s au plus (%s)' % (texte, fr(borne, 2), source)
    manque = '' if conforme else motif_capacite_non_publiee(conception, source)
    return '%s — %s' % (phrase, manque) if manque else phrase
