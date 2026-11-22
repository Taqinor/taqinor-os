"""ACAL887 — la production MESURÉE d'un calepinage et son écart au P50 servi.

Contrat ``contract_samples/calepinage_production_mesuree.json`` (ACAL886).
``PUT`` range jusqu'à douze valeurs mensuelles (le jeu REMPLACE le précédent :
une seule année par calepinage) ; ``GET`` rend, par mois, le ``p50_kwh`` du
résultat servi, le ``kwh_mesure`` et ``ecart_pct`` = (mesuré − P50) ÷ P50 × 100
au dixième. Un mois sans mesure vaut ``null`` (jamais 0). L'écart est publié,
jamais jugé : aucun seuil, aucune alerte. La société et l'auteur viennent du
serveur ; rien du corps de la requête ne désigne l'une ou l'autre.
"""
from __future__ import annotations

import datetime

from django.db import transaction

from . import valeurs

__all__ = ['MesureRefusee', 'enregistrer_mesures', 'etat_production_mesuree']

#: Les bornes de la COLONNE : ``annee`` est un PositiveSmallInteger (≤ 32767),
#: ``kwh_mesure`` un Decimal(12, 3) (< 1e9, trois décimales).
ANNEE_MINI, ANNEE_MAXI = 1900, 32767
#: Plafond de ``kwh_mesure`` : Decimal(12, 3) => strictement moins de 1e9 kWh.
KWH_MAXI = 999_999_999
MOTIF_VIDE = "Aucune production mesurée n'est saisie pour ce calepinage."
MOTIF_SANS_SIMULATION = ("Simulation absente ou périmée : le P50 mensuel n'est "
                         "pas servi, aucun écart n'est calculé.")


class MesureRefusee(ValueError):
    """Refus d'une saisie, en français, avec le CHAMP fautif nommé."""

    def __init__(self, message, champ='', statut=400):
        super().__init__(message)
        self.champ = champ
        # 409 = règle liant plusieurs lignes (mois saisi deux fois), que le
        # schéma ne dit pas (ENF11) ; 400 = forme invalide.
        self.statut = statut

    def corps(self):
        return {self.champ or 'detail': [str(self)]}


def _entier(valeur, champ, mini, maxi):
    if isinstance(valeur, bool) or not isinstance(valeur, int):
        raise MesureRefusee('Un entier est attendu.', champ)
    if not mini <= valeur <= maxi:
        raise MesureRefusee('Hors bornes : de %d à %d.' % (mini, maxi), champ)
    return valeur


def _valider(corps):
    """``(annee, [(mois, kwh)])`` ou un refus qui nomme le champ."""
    if not isinstance(corps, dict):
        raise MesureRefusee('Un objet {annee, mesures} est attendu.')
    annee = _entier(corps.get('annee'), 'annee', ANNEE_MINI, ANNEE_MAXI)
    lignes = corps.get('mesures')
    if not isinstance(lignes, list) or len(lignes) > 12:
        raise MesureRefusee('« mesures » est une liste de 12 lignes au plus.',
                            'mesures')
    vus, mesures = set(), []
    for rang, ligne in enumerate(lignes):
        base = 'mesures[%d]' % rang
        if not isinstance(ligne, dict):
            raise MesureRefusee('Une ligne {mois, kwh_mesure} est attendue.',
                                base)
        mois = _entier(ligne.get('mois'), base + '.mois', 1, 12)
        if mois in vus:
            raise MesureRefusee('Le mois %d est saisi deux fois.' % mois,
                                base + '.mois', statut=409)
        vus.add(mois)
        kwh = valeurs.nombre_fini(
            ligne.get('kwh_mesure'), base + '.kwh_mesure', mini=0,
            maxi=KWH_MAXI, decimales=3, obligatoire=True, erreur=MesureRefusee)
        mesures.append((mois, kwh))
    return annee, mesures


def enregistrer_mesures(calepinage, corps, *, user):
    """Range le jeu posté à la place du précédent. Société = celle du
    calepinage, auteur = l'utilisateur de la requête."""
    from ..models import ProductionMesuree

    annee, mesures = _valider(corps)
    with transaction.atomic():
        ProductionMesuree.objects.filter(calepinage=calepinage).delete()
        ProductionMesuree.objects.bulk_create([
            ProductionMesuree(
                company=calepinage.company, calepinage=calepinage,
                annee=annee, mois=mois, kwh_mesure=kwh, saisi_par=user)
            for mois, kwh in mesures])


def _pct(mesure, p50):
    """(mesuré − P50) ÷ P50 × 100 au dixième ; ``None`` sans l'un des deux."""
    if mesure is None or p50 is None or p50 <= 0:
        return None
    return round((mesure - p50) / p50 * 100.0, 1)


def _p50_mensuels(servi):
    """Les douze ``p50_kwh`` du résultat SERVI, ``None`` si la simulation est
    absente ou périmée."""
    if not (servi or {}).get('simule') or servi.get('simulation_perimee'):
        return [None] * 12
    mensuel = (servi.get('production') or {}).get('mensuel') or []
    lus = {ligne.get('mois'): valeurs.nombre(ligne.get('p50_kwh'))
           for ligne in mensuel if isinstance(ligne, dict)}
    return [lus.get(mois) for mois in range(1, 13)]


def _composer_etat(calepinage_id, annee, mesures, servi):
    """Le GET au contrat. ``mesures`` = ``[(mois, kwh, saisi_le_iso)]``."""
    if not mesures:
        return {'calepinage': calepinage_id, 'annee': None, 'mesures': [],
                'ecarts': [], 'ecart_annuel_pct': None, 'motif': MOTIF_VIDE}
    kwh = {mois: float(valeur) for mois, valeur, _le in mesures}
    p50 = _p50_mensuels(servi)
    ecarts = [{'mois': mois, 'p50_kwh': p50[mois - 1],
               'kwh_mesure': kwh.get(mois),
               'ecart_pct': _pct(kwh.get(mois), p50[mois - 1])}
              for mois in range(1, 13)]
    comparables = [ligne for ligne in ecarts if ligne['ecart_pct'] is not None]
    somme_p50 = sum(ligne['p50_kwh'] for ligne in comparables)
    ecart_annuel = _pct(sum(ligne['kwh_mesure'] for ligne in comparables),
                        somme_p50) if comparables else None
    sans = [m for m in range(1, 13) if m not in kwh]
    if all(valeur is None for valeur in p50):
        motif = (servi or {}).get('motif') or MOTIF_SANS_SIMULATION
    elif sans:
        motif = ("Écart annuel calculé sur les %d mois mesurés ; sans mesure : "
                 "mois %s." % (len(kwh), ', '.join(str(m) for m in sans)))
    else:
        motif = ''
    return {'calepinage': calepinage_id, 'annee': annee,
            'mesures': [{'mois': mois, 'kwh_mesure': float(valeur),
                         'saisi_le': saisi_le}
                        for mois, valeur, saisi_le in mesures],
            'ecarts': ecarts, 'ecart_annuel_pct': ecart_annuel,
            'motif': motif}


def etat_production_mesuree(calepinage):
    """Les mesures rangées du calepinage et leur écart au P50 servi."""
    from .. import selectors

    lignes = list(calepinage.productions_mesurees.order_by('annee', 'mois'))
    annee = max((ligne.annee for ligne in lignes), default=None)
    mesures = [(ligne.mois, ligne.kwh_mesure, ligne.saisi_le.astimezone(
                    datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
               for ligne in lignes if ligne.annee == annee]
    servi = selectors.resultat_servi(calepinage) if mesures else None
    return _composer_etat(calepinage.pk, annee, mesures, servi)
