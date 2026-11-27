"""ACAL756 — la section « Synthèse » du rapport d'étude : une page de chiffres.

Placée juste après la page de garde, elle répond d'emblée à « combien
produit-on, est-ce conforme » avec les grandeurs que le résultat sert déjà :
puissance crête, modules, onduleurs, P50/P90, productible spécifique, PR,
pertes, contrôles électriques non conformes, écart PVGIS, couverture et
autoconsommation.

LU, jamais calculé : la seule conversion est fraction × 100 pour les deux taux
(``pourcentage``, par ``Decimal`` pour ne pas imprimer 57,99999). Une valeur
absente s'imprime « non calculée » avec son motif quand le résultat en sert
un — jamais 0. Aucun graphique, aucun montant : une pièce technique.
"""
from __future__ import annotations

from decimal import Decimal
from html import escape

from . import nombre_tel_que_servi, valeur_au_chemin
from .champs_lisibles import motif_lisible
from .production import mention_borne_haute, texte_non_publie

__all__ = ['CSS_SECTION', 'NON_CALCULEE', 'html_de_section', 'pourcentage']

NON_CALCULEE = 'non calculée'

CSS_SECTION = (
    '.synthese th{width:48%;text-align:left;}'
    '.synthese td{text-align:right;}'
    # ACAL1701 — la mention « borne haute » se lit : 9 pt, plus 7,5 pt gris.
    '.synthese .detail{display:block;font-size:9pt;color:#555;}'
)


def pourcentage(fraction):
    """Fraction servie × 100 (seule conversion de la section), ou ``None``."""
    if fraction is None or isinstance(fraction, bool):
        return None
    return float(Decimal(repr(fraction)) * 100)


def _present(resultat, chemin):
    present, valeur = valeur_au_chemin(resultat, chemin)
    return valeur if present else None


def _valeur(valeur, motif=None, *, unite=''):
    """La cellule : la valeur telle que servie, ou « non calculée » + motif."""
    if valeur is None:
        texte = NON_CALCULEE
        if motif:
            texte += ' — %s' % escape(motif_lisible(str(motif)))  # ACAL1928
        return texte
    return nombre_tel_que_servi(valeur) + unite


def _ligne(libelle_, cellule):
    return '<tr><th>%s</th><td>%s</td></tr>' % (escape(libelle_), cellule)


#: ACAL1677 — le motif d'une ligne électrique vide quand l'onduleur manque.
MOTIF_SANS_ONDULEUR = 'aucun onduleur désigné'
#: … et quand un onduleur est désigné sans chaîne (ni motif servi).
MOTIF_SANS_CHAINE = 'aucune chaîne calculée'


def _liste_onduleurs(resultat):
    return [o for o in (resultat.get('electrique') or {}).get('onduleurs')
            or () if isinstance(o, dict)]


#: T4-U2-014 — les débuts des phrases SERVIES (``electrique.resoudre_materiel``
#: ``absents`` et ``chaines.concevoir_par_pan`` ``manquantes``, toutes deux dans
#: ``resultat.avertissements``) qui disent pourquoi aucune chaîne n'est calculée.
_ONDULEUR_ABSENT = ('onduleur non désigné', 'onduleur introuvable')
_CAUSES_SANS_CHAINE = ('module PV non désigné', 'module PV introuvable',
                       'module : ', 'onduleur : ')


def _motif_sans_onduleur(resultat):
    """Pourquoi ``electrique.onduleurs`` est vide, LU dans les avertissements.

    Vide veut dire « aucune chaîne », pas « aucun onduleur » : l'onduleur
    choisi à l'étape Électrique (la même ``resoudre_materiel``) ne s'évalue
    qu'avec des chaînes. « aucun onduleur désigné » n'est dit que si
    l'absence de l'onduleur est SERVIE ; sinon la cause servie, sinon la
    chaîne absente seule."""
    servis = [str(a).strip() for a in resultat.get('avertissements') or ()]
    if any(a.startswith(_ONDULEUR_ABSENT) for a in servis):
        return MOTIF_SANS_ONDULEUR
    cause = next((a for a in servis if a.startswith(_CAUSES_SANS_CHAINE)), '')
    return '%s : %s' % (MOTIF_SANS_CHAINE, cause) if cause else MOTIF_SANS_CHAINE


def _onduleurs(resultat):
    liste = _liste_onduleurs(resultat)
    if not liste:
        return _valeur(None, _motif_sans_onduleur(resultat))
    return '<br>'.join(escape('%s × %s (%s kW)' % (
        o.get('reference') or '—', nombre_tel_que_servi(o.get('nombre')),
        nombre_tel_que_servi(o.get('taille_kw')))) for o in liste)


def _motif_sans_verdict(resultat):
    """Le motif servi sur l'onduleur, sinon ce qui manque (ACAL1677)."""
    liste = _liste_onduleurs(resultat)
    if not liste:
        return _motif_sans_onduleur(resultat)
    return next((str(o['motif']) for o in liste if o.get('motif')),
                MOTIF_SANS_CHAINE)


def _controles(resultat):
    verdicts = [v for v in (resultat.get('electrique') or {}).get('verdicts')
                or () if isinstance(v, dict)]
    if not verdicts:
        return _valeur(None, _motif_sans_verdict(resultat))
    faux = [str(v.get('libelle') or v.get('code') or '—') for v in verdicts
            if v.get('conforme') is False]
    if not faux:
        return 'aucun contrôle non conforme'
    return '<br>'.join(escape(libelle_) for libelle_ in faux)


def _p50(total, cle='p50_kwh', unite=' kWh'):
    """``cle`` servie + la mention « borne haute » d'un résultat incomplet —
    le P50 ET le productible spécifique (ACAL1701 : P50 ÷ kWc, la même borne
    haute)."""
    p50 = _present(total, cle)
    texte = _valeur(p50, unite=unite)
    mention = mention_borne_haute(total)
    if p50 is None or not mention:
        return texte
    return '%s<span class="detail">%s</span>' % (texte, escape(mention))


def _quantile(total, cle, unite):
    non_publie = texte_non_publie(total, cle)
    if non_publie is not None:
        return escape(non_publie)
    return _valeur(_present(total, cle), total.get('%s_motif' % cle),
                   unite=unite)


def _ecart(resultat):
    validation = resultat.get('validation') or {}
    ecart = validation.get('ecart_pct')
    if ecart is None:
        return _valeur(None, validation.get('avertissement'))
    texte = '%s %%' % nombre_tel_que_servi(ecart)
    verdict = validation.get('verdict')
    if verdict:
        texte += '<span class="detail">%s</span>' % escape(
            str(verdict).replace('_', ' '))
    return texte


def _taux(autoconsommation, cle):
    bloc = autoconsommation if isinstance(autoconsommation, dict) else {}
    return _valeur(pourcentage(bloc.get(cle)), bloc.get('motif_absence'),
                   unite=' %')


_RENVOI_VOLUMES = 'voir les volumes mensuels de la section Pompage'


def _ligne_volume(bloc, volumes, motif):
    """Revue 12 — ``m3_jour_plat`` est le calcul PLAT (débit × heures) : il
    ignore l'irradiation et le plafond du forage. La synthèse n'imprime donc
    jamais un autre chiffre que la section Pompage (qui imprime
    ``m3_mois_pvgis`` d'abord, ``m3_mois_plat`` à défaut) : série physique
    servie ou plafond atteint ⇒ renvoi à la section, sans chiffre ; seul le
    plat servi ⇒ le m³/jour plat, étiqueté comme tel (m3_mois_plat ÷ jours).
    """
    if not bloc or not volumes:
        return _ligne('Volume pompé par jour', _valeur(None, motif))
    if volumes.get('plafond_atteint'):
        return _ligne('Volume pompé par jour', NON_CALCULEE + ' — %s' % escape(
            'plafond du forage atteint : ' + _RENVOI_VOLUMES))
    if volumes.get('m3_mois_pvgis'):
        return _ligne('Volume pompé', escape(_RENVOI_VOLUMES))
    return _ligne(
        'Volume pompé par jour (calcul plat : débit × heures de pompage)',
        _valeur(volumes.get('m3_jour_plat'), unite=' m³/jour'))


def _lignes_pompage(contexte, pose, pertes):
    """Décision fondateur 6 — la synthèse d'un calepinage de POMPAGE : ni
    production, ni autoconsommation, ni onduleur (une composition de pompage
    n'en a pas), ni écart PVGIS ; le débit, la HMT et le volume par jour du
    dernier dimensionnement enregistré (``pompage_dernier``), TELS QUE
    SERVIS. Le m³/jour n'est servi que pour une pompe à COURBE
    (``views/pompage.py``) : absent, il est « non calculée », jamais estimé."""
    bloc = (contexte.get('resultat_stocke') or {}).get('pompage_dernier') or {}
    pompe = bloc.get('pompe') if isinstance(bloc.get('pompe'), dict) else {}
    point = pompe.get('point_fonctionnement') or {}
    hmt = bloc.get('hmt') if isinstance(bloc.get('hmt'), dict) else {}
    volumes = (bloc.get('volumes') if isinstance(bloc.get('volumes'), dict)
               else {})
    motif = None if bloc else 'aucun dimensionnement de pompage enregistré'
    return [
        _ligne('Puissance crête', _valeur(pose.get('kwc'), unite=' kWc')),
        _ligne('Modules posés', _valeur(pose.get('total_modules'))),
        _ligne('Débit au point de fonctionnement',
               _valeur(point.get('debit_m3h'), motif, unite=' m³/h')),
        _ligne('Hauteur manométrique totale (HMT)',
               _valeur(hmt.get('hmt_m'), motif, unite=' m')),
        _ligne_volume(bloc, volumes, motif),
        _ligne('Pertes totales', _valeur(pertes, unite=' %')),
        _ligne('Contrôles électriques non conformes',
               _controles(contexte.get('resultat') or {})),
    ]


def html_de_section(contexte):
    """Le corps de la section ``synthese`` : au plus 12 lignes, une page."""
    resultat = contexte.get('resultat') or {}
    pose = resultat.get('pose') or {}
    if contexte.get('pompage'):
        lignes = _lignes_pompage(
            contexte, pose, (resultat.get('cascade') or {}).get('total_pct'))
        return '<table class="synthese generique">%s</table>' % ''.join(lignes)
    total = (resultat.get('production') or {}).get('total') or {}
    autoconso = resultat.get('autoconsommation')
    pertes = (resultat.get('cascade') or {}).get('total_pct')
    lignes = [
        _ligne('Puissance crête', _valeur(pose.get('kwc'), unite=' kWc')),
        _ligne('Modules posés', _valeur(pose.get('total_modules'))),
        _ligne('Onduleurs', _onduleurs(resultat)),
        _ligne('Production annuelle P50', _p50(total)),
        _ligne('Production annuelle P90', _quantile(total, 'p90_kwh', ' kWh')),
        _ligne('Productible spécifique',
               _p50(total, 'specific_yield_kwh_kwc', ' kWh/kWc')),
        _ligne('Ratio de performance (PR)',
               _quantile(total, 'performance_ratio', '')),
        _ligne('Pertes totales', _valeur(pertes, unite=' %')),
        _ligne('Contrôles électriques non conformes', _controles(resultat)),
        _ligne('Écart avec PVGIS', _ecart(resultat)),
        _ligne('Couverture des besoins', _taux(autoconso, 'taux_couverture')),
        _ligne('Autoconsommation',
               _taux(autoconso, 'taux_autoconsommation')),
    ]
    return '<table class="synthese generique">%s</table>' % ''.join(lignes)
