"""ACAL403 — appliquer / retirer le PROFIL DE DÉPART sourcé (D-ACAL-31).

Le profil est un FICHIER du dépôt (``data/profil_depart.json``, forme du
contrat ACAL387 ``calepinage_profil_depart.json::exemple``), jamais une table :
chaque valeur y porte sa page lue (``reference``, ``url``, ``date_lecture``) ;
une clé sans page lue est dans ``sans_source`` et n'est JAMAIS écrite.

* ``appliquer_profil`` n'écrit que les clés VIDES du registre — une saisie
  n'est jamais écrasée (``ignorees`` / ``deja_saisie``) ;
* ``retirer_profil`` ne retire que les clés dont valeur, source ET référence
  sont encore celles du profil — une valeur retouchée est gardée.

Toute écriture passe par ``enregistrer_parametres`` (validation de type,
journal d'audit) ; l'empreinte de simulation porte les réglages, donc les
simulations stockées deviennent périmées d'elles-mêmes (D-ACAL-8).
"""
from __future__ import annotations

import json
from pathlib import Path

#: Chemin du dépôt, pas une mesure : ``parents[1]`` = le paquet ``apps/calepinage`` (ce
#: module vit dans ``services/``), où ``data/profil_depart.json`` est committé.
FICHIER_PROFIL = Path(__file__).resolve().parents[1] / 'data' / 'profil_depart.json'

#: La fin de toute référence écrite : la valeur est PUBLIÉE, pas mesurée.
SUFFIXE_REFERENCE = 'valeur publiée, non mesurée'

__all__ = ['FICHIER_PROFIL', 'appliquer_profil', 'charger_profil',
           'reference_ecrite', 'retirer_profil']


def charger_profil():
    """Le profil tel que le fichier le porte : ``{valeurs, sans_source}``."""
    return json.loads(FICHIER_PROFIL.read_text(encoding='utf-8'))


def reference_ecrite(ligne):
    """``<référence> — <url> — lu le <date> — valeur publiée, non mesurée``
    (la référence du fichier commence déjà par ``Profil de départ — ``)."""
    return (f"{ligne['reference']} — {ligne['url']} — lu le "
            f"{ligne['date_lecture']} — {SUFFIXE_REFERENCE}")


def _saisie_du_profil(ligne):
    return {'valeur': ligne['valeur'], 'source': ligne['source'],
            'reference': reference_ecrite(ligne)}


def _sections_verrouillees(company):
    """Les sections à registre de ``company``, ligne VERROUILLÉE (une saisie
    concurrente ne se glisse pas entre la lecture et l'écriture)."""
    from ..models import ParametresCalepinage
    from .parametres_cles import REGISTRES

    reglages = (ParametresCalepinage.objects.select_for_update()
                .filter(company=company).order_by('id').first())
    return {section: dict(getattr(reglages, section, None) or {})
            for section in REGISTRES}


def appliquer_profil(company, *, user, profil=None):
    """Remplit les SEULES clés vides ; rend ``{appliquees, ignorees}``."""
    from django.db import transaction

    from .parametres import enregistrer_parametres

    profil = charger_profil() if profil is None else profil
    appliquees, ignorees, donnees = [], [], {}
    with transaction.atomic():
        stockees = _sections_verrouillees(company)
        for ligne in profil.get('valeurs', []):
            section, cle = ligne['section'], ligne['cle']
            if cle in stockees.get(section, {}):
                ignorees.append({'cle': cle, 'section': section,
                                 'motif': 'deja_saisie'})
                continue
            donnees.setdefault(section, {})[cle] = _saisie_du_profil(ligne)
            appliquees.append({'cle': cle, 'section': section})
        if donnees:
            enregistrer_parametres(company, donnees, user=user)
    return {'appliquees': appliquees, 'ignorees': ignorees}


def retirer_profil(company, *, user, profil=None):
    """Retire ce que le profil a posé et qui n'a pas été retouché ; rend
    ``{retirees, gardees}`` (``gardees`` : présentes mais retouchées)."""
    from django.db import transaction

    from .parametres import _normaliser_cles_a_registre, enregistrer_parametres

    profil = charger_profil() if profil is None else profil
    retirees, gardees, donnees = [], [], {}
    with transaction.atomic():
        stockees = _sections_verrouillees(company)
        for ligne in profil.get('valeurs', []):
            section, cle = ligne['section'], ligne['cle']
            actuelle = stockees.get(section, {}).get(cle)
            if actuelle is None:
                continue
            posee = _normaliser_cles_a_registre(
                section, {cle: _saisie_du_profil(ligne)})[cle]
            if actuelle != posee:
                gardees.append({'cle': cle, 'section': section,
                                'motif': 'retouchee'})
                continue
            donnees.setdefault(section, {})[cle] = None
            retirees.append({'cle': cle, 'section': section})
        if donnees:
            enregistrer_parametres(company, donnees, user=user)
    return {'retirees': retirees, 'gardees': gardees}
