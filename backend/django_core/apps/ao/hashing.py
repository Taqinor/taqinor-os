"""Empreinte canonique d'une ENTRÉE de calepinage (``apps.ao``) — AOF29.

Pourquoi une empreinte
======================
La note de synthèse d'un dossier réel annonçait encore 264 modules quand la
donnée en disait 314 : **la pièce la plus lue était la plus fausse.** Une
variante de calepinage doit donc savoir dire, seule, si l'entrée dont elle est
issue a bougé depuis. C'est le rôle de ``empreinte_entree`` : un SHA-256
DÉTERMINISTE de tout ce qui change le résultat, et de rien d'autre.

Ce qui entre dans l'empreinte
-----------------------------
* l'ENVELOPPE de la toiture (contour local métrique + azimut + paramètres
  d'arc) ;
* les obstacles ACTIFS, triés, avec leur emprise, leur provenance et le
  dégagement RÉELLEMENT appliqué ;
* les chaînes de cotes retenues (segments + statuts) ;
* les paramètres de calepinage, les kits autorisés et la version du moteur.

Ce qui n'y entre PAS : les identifiants techniques, les horodatages, les
libellés d'affichage, les obstacles écartés. Un simple renommage ne doit pas
périmer un plan — sinon le bandeau « périmé » se dévalue et l'utilisateur
apprend à l'ignorer.

Le patron (SHA-256 d'un JSON canonique trié, ``ensure_ascii=False``) est celui
de ``ventes.services.layout_hash`` : même idée d'idempotence, même famille de
bug évitée. Module PUR côté calcul (il ne fait que LIRE l'ORM).
"""
from __future__ import annotations

import hashlib
import json

__all__ = ['empreinte_entree', 'entree_canonique']


def _nombre(valeur):
    """Normalise un ``Decimal``/``float``/``None`` en flottant arrondi (mm)."""
    if valeur is None:
        return None
    return round(float(valeur), 4)


def _contour(points):
    return [[_nombre(p[0]), _nombre(p[1])] for p in (points or [])]


def entree_canonique(toiture, *, params=None, kits=None, version_moteur=''):
    """Dictionnaire CANONIQUE de l'entrée de calepinage d'une toiture.

    Trié et normalisé pour être stable d'une exécution à l'autre : c'est LUI
    qui est haché. L'exposer séparément rend l'empreinte débogable — sans quoi
    une divergence inexpliquée serait impossible à instruire.
    """
    obstacles = []
    if toiture.pk:
        for obstacle in toiture.obstacles.filter(actif=True).order_by(
                'repere', 'id'):
            obstacles.append({
                'repere': obstacle.repere or '',
                'nature': obstacle.nature,
                'provenance': obstacle.provenance,
                'rect': [
                    _nombre(obstacle.rect_x0_m), _nombre(obstacle.rect_x1_m),
                    _nombre(obstacle.rect_y0_m), _nombre(obstacle.rect_y1_m),
                ],
                'polygone': _contour(obstacle.polygone_local_m),
                'hauteur_m': _nombre(obstacle.hauteur_m),
                'degagement_m': _nombre(obstacle.degagement_m),
                'hors_zone_pv': bool(obstacle.hors_zone_pv),
            })

    chaines = []
    if toiture.pk:
        for chaine in toiture.chaines_cotes.order_by('libelle', 'id'):
            chaines.append({
                'libelle': chaine.libelle,
                'axe': chaine.axe,
                'segments': [
                    {
                        'libelle': s.get('libelle', ''),
                        'valeur_m': _nombre(s.get('valeur_m')),
                        'statut': s.get('statut', ''),
                    }
                    for s in (chaine.segments or [])
                ],
                'mesure_totale_m': _nombre(chaine.mesure_totale_m),
            })

    parametres = params if params is not None else (
        toiture.parametres_calepinage or {})
    return {
        'enveloppe': {
            'forme': toiture.forme,
            'contour_local_m': _contour(toiture.contour_local_m),
            'angle_nord_deg': _nombre(toiture.angle_nord_deg),
            'rayon_ext_m': _nombre(toiture.rayon_ext_m),
            'largeur_m': _nombre(toiture.largeur_m),
            'arc_segments': toiture.arc_segments or [],
            'murets': toiture.murets or [],
        },
        'obstacles': obstacles,
        'chaines': chaines,
        'params': parametres,
        'kits': sorted(kits or []),
        'version_moteur': version_moteur or '',
    }


def empreinte_entree(toiture, *, params=None, kits=None, version_moteur=''):
    """SHA-256 hexadécimal de l'entrée canonique (AOF29)."""
    canonique = entree_canonique(
        toiture, params=params, kits=kits, version_moteur=version_moteur)
    charge = json.dumps(canonique, sort_keys=True, ensure_ascii=False,
                        separators=(',', ':'))
    return hashlib.sha256(charge.encode('utf-8')).hexdigest()
