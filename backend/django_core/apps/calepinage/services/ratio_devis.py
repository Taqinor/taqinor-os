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
    return (capacite / ac, None, SOURCE_BORNE_CAPACITE, '%s kWc' % fr(capacite, 0))


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


def detail_ratio(texte, conforme, bornes):
    """La phrase du verdict, qui dit D'OÙ vient la borne."""
    from core.electrique.types import fr

    borne, _alerte, source, detail = bornes
    if source == SOURCE_BORNE_CAPACITE:
        return '%s — %s la capacité publiée de l\'onduleur (%s)' % (
            texte, 'dans' if conforme else 'au-delà de', detail)
    return '%s pour %s au plus (%s)' % (texte, fr(borne, 2), source)
