"""La SEULE porte du moteur unique vers ``apps/calepinage`` (D-ACAL-97).

Le moteur (``apps/ventes/conception/``) lit le calepinage par ses portes
``selectors`` / ``services`` seulement, et toujours depuis ce module (un seul
fichier de ``ventes`` en plus au cliquet ACAL1009) :

* ACAL2016 — les VERDICTS électriques d'une option, jugés par LA règle
  existante du ratio (``calepinage/services/ratio_devis.py::juger_ratio``,
  ACAL1954, D-ACAL-91) et la règle D-HYB-1 de la capacité publiée d'un hybride
  (``core.electrique.onduleurs.capacite_publiee_hybride``) : aucune seconde
  règle ici, le moteur RANGE le verdict et « Prêt à envoyer ? » le relit.

Lecture pure : rien n'est écrit.
"""
from types import SimpleNamespace


def _nombre(valeur):
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _fiche_onduleur(company, produit_id):
    """La fiche (bloc plat) de l'onduleur ``produit_id`` de ``company``, ``{}`` sinon."""
    from apps.stock.selectors import get_produit_scoped, specs_for_produit

    produit = get_produit_scoped(company, produit_id) if company is not None and produit_id else None
    return (specs_for_produit(produit) or {}) if produit is not None else {}


def _reglages_electriques(company):
    """La section « electrique_societe » des réglages calepinage (seuils DC/AC saisis)."""
    from apps.calepinage.selectors import parametres_de_societe
    from apps.calepinage.services.parametres_cles import SECTION_ELECTRIQUE_SOCIETE

    return parametres_de_societe(company).get(SECTION_ELECTRIQUE_SOCIETE) or {}


def _verdict_ratio(ratio, evaluation, conception, reglages):
    from apps.calepinage.services.ratio_devis import bornes_du_verdict, bornes_ratio, detail_ratio, juger_ratio
    from core.electrique.types import fr

    bornes = bornes_du_verdict(bornes_ratio(reglages=reglages), evaluation, conception)
    conforme = juger_ratio(ratio, bornes, reglages)
    return {'conforme': conforme, 'valeur': ratio, 'borne': bornes[0], 'borne_source': bornes[2],
            'detail': detail_ratio(fr(ratio, 2), conforme, bornes, valeur=ratio, reglages=reglages)}


def _verdict_capacite(onduleur, nombre, puissance_kwc):
    from core.electrique.onduleurs import capacite_publiee_hybride
    from core.electrique.types import fr

    capacite = capacite_publiee_hybride(onduleur, nombre)
    if capacite is None or puissance_kwc is None:
        return None
    conforme = puissance_kwc <= capacite + 1e-9
    return {'conforme': conforme, 'capacite_kwc': capacite, 'puissance_kwc': puissance_kwc,
            'detail': '%s kWc %s la capacité publiée de l\'onduleur hybride (%s kWc)' % (
                fr(puissance_kwc, 2), 'dans' if conforme else 'au-delà de', fr(capacite, 0))}


def _verdict_longueur(chaines):
    longueurs = [c.get('nb_modules') for c in chaines if c.get('nb_modules')]
    if not longueurs:
        return None
    conforme = all(c.get('conforme') is not False for c in chaines)
    return {'conforme': conforme, 'longueurs': longueurs, 'longueur': max(longueurs),
            'detail': 'chaînes de %s modules %s dans la fenêtre de tension de l\'onduleur' % (
                '/'.join(str(n) for n in sorted(set(longueurs))), 'toutes' if conforme else 'pas toutes')}


def verdicts_electriques(company, design, onduleurs, puissance_kwc):
    """ACAL2016 — ``{ratio_dc_ac, capacite_hybride, longueur_chaine}`` de l'option dont la
    conception électrique ``design`` porte l'onduleur (``onduleurs`` : ses lignes, forme
    ``valeurs.onduleurs``), ``None`` sans conception électrique. Chaque verdict =
    ``{conforme, …, detail}`` ou ``None`` quand il ne s'applique pas (onduleur réseau ou
    capacité non publiée pour la capacité ; aucune chaîne pour la longueur)."""
    if not design or not onduleurs:
        return None
    fiche = _fiche_onduleur(company, onduleurs[0].get('produit'))
    materiel = (design.get('materiel') or {}).get('onduleur') or {}
    nombre = sum(int(o.get('quantite') or 0) for o in onduleurs) or 1
    onduleur = SimpleNamespace(designation=materiel.get('designation') or onduleurs[0].get('designation'),
                               dc_max_kwc=fiche.get('dc_max_kwc'))
    ac_kw = _nombre(materiel.get('ac_kw')) or _nombre(fiche.get('ac_kw')) or 0.0
    evaluation = SimpleNamespace(nombre=nombre, puissance_ac_kw=nombre * ac_kw)
    ratio = _nombre(design.get('ratio_dc_ac'))
    return {
        'ratio_dc_ac': (_verdict_ratio(ratio, evaluation, SimpleNamespace(entree=SimpleNamespace(onduleur=onduleur)),
                                       _reglages_electriques(company)) if ratio is not None else None),
        'capacite_hybride': _verdict_capacite(onduleur, nombre, _nombre(puissance_kwc)),
        'longueur_chaine': _verdict_longueur(design.get('chaines') or []),
    }
