"""CAL98 — faire remonter l'ombrage AU NIVEAU DE LA CHAÎNE électrique.

LE CONSTAT
----------
Le noyau ne fait qu'un chaînage de modules par pan, sans AUCUNE notion
d'ombrage (``core/calepinage/electrique.py`` — le stringing détaillé est
documenté hors moteur), et l'accès solaire PAR MODULE est calculé CÔTÉ CLIENT
(``apps/web/src/lib/shadingEngine.ts`` : ``pointSolarAccess`` /
``cellsSolarAccess``). Le backend n'y a donc accès que si le document le
PERSISTE — ce que CAL248 a posé : ``zones[].geometry.solarAccess.values``,
« un facteur d'accès solaire par module, DANS LE MÊME ORDRE que ``panels`` ;
une entrée ``null`` = module non calculé (jamais 1) ».

Or la perte d'un module ombré se propage à TOUTE la chaîne (le courant d'une
série est celui de son module le plus faible —
https://www.trace-software.com/en/benefits-archelios-pro-photovoltaic-software/).
Une chaîne qui contient LE module le plus ombré du toit n'est donc pas une
chaîne comme les autres, et personne ne le voyait.

CE QUE CE MODULE FAIT — ET NE FAIT PAS
--------------------------------------
Il fournit la GÉOMÉTRIE et l'ACCÈS : pour chaque chaîne, la liste de ses
modules et leur accès solaire LU DANS LE DOCUMENT, plus le signalement des
chaînes dont un module est nettement plus ombré que les autres, avec l'écart
CHIFFRÉ. **Aucun kWh n'est calculé ici** : le calcul de production par chaîne
appartient à la partie production.

**AUCUN SIGNALEMENT INVENTÉ.** Accès solaire absent du document ⇒ silence
EXPLICITE (``mesure: False`` + motif), jamais un « tout va bien » ni un
module supposé à 100 % — un module sans accès calculé n'est pas un module non
ombré.

**AUCUN SEUIL DEVINÉ.** Le signalement de base ne repose sur aucun nombre
arbitraire : est signalée la chaîne qui contient LE module le plus ombré du
toit (une comparaison, pas un seuil). Un seuil d'écart supplémentaire existe,
mais il est SAISI (``ecart_signale``) — absent, il ne s'applique pas.

LE JOINT ENTRE LE DOCUMENT ET L'ÉLECTRIQUE
-------------------------------------------
L'affectation (CAL125, ``services/chaines.affectation``) repère ses modules
``« <pan>#<rang> »``, le rang comptant à partir de 1 dans l'ordre des modules
du pan — le MÊME ordre que ``panels`` et donc que ``solarAccess.values``.
C'est ce rang qui sert d'index ; quand le document porte moins de valeurs que
le pan n'a de modules, les modules au-delà sont publiés SANS accès (et
l'avertissement le dit), jamais complétés.
"""
from __future__ import annotations

__all__ = ['MOTIF_SANS_ACCES', 'acces_par_module', 'ombrage_des_chaines']

MOTIF_SANS_ACCES = (
    "Le document de toiture ne porte aucun accès solaire par module "
    "(« zones[].geometry.solarAccess ») : aucun écart d'ombrage n'est "
    'signalé. Le silence est explicite — un module sans accès calculé n’est '
    'pas un module non ombré.')


def _nombre(valeur):
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    if nombre != nombre:
        return None
    return nombre


def acces_par_module(layout):
    """``{repère du pan: [accès solaire, …]}`` LU dans le document.

    Les deux repères du pan (son ``label`` et son ``id``) mènent à la même
    liste : l'affectation nomme ses modules avec l'un ou l'autre selon la
    façon dont le pan a été étiqueté.
    """
    zones = ((layout or {}).get('zones')
             if isinstance(layout, dict) else None) or []
    par_pan = {}
    for zone in zones:
        if not isinstance(zone, dict):
            continue
        geometrie = zone.get('geometry')
        acces = (geometrie.get('solarAccess')
                 if isinstance(geometrie, dict) else None)
        valeurs = (acces.get('values') if isinstance(acces, dict) else None)
        if not isinstance(valeurs, list):
            continue
        lues = [_nombre(valeur) for valeur in valeurs]
        for repere in (zone.get('label'), zone.get('id')):
            if repere:
                par_pan[str(repere)] = lues
    return par_pan


def _rang(repere_module):
    """« PAN-SUD#7 » → 7, ou ``None`` si le repère ne porte pas de rang."""
    texte = str(repere_module or '')
    if '#' not in texte:
        return None
    suffixe = texte.rsplit('#', 1)[1]
    return int(suffixe) if suffixe.isdigit() else None


def ombrage_des_chaines(layout, affectation, *, ecart_signale=None):
    """L'accès solaire, chaîne par chaîne, et les chaînes à regarder.

    Args:
        layout: le document ``roof_layout`` v2.
        affectation: la table ``[{module, pan, chaine, onduleur, mppt}]`` de
            ``services/chaines.affectation`` — la partition RÉELLEMENT
            dimensionnée, jamais une partition recalculée ici.
        ecart_signale: écart d'accès solaire (0 à 1) à partir duquel une
            chaîne est signalée, SAISI. ``None`` ⇒ aucun seuil n'est appliqué
            (seule la chaîne du module le plus ombré est signalée).

    Returns:
        dict — ``mesure`` (le document porte-t-il des accès ?), ``motif``,
        ``chaines`` (``[{chaine, pan, mppt, modules, acces_min, acces_max,
        acces_moyen, ecart_interne, module_le_plus_ombre}]``),
        ``signalements`` (``[{chaine, pan, module, acces, ecart, raison}]``),
        ``modules_sans_acces``, ``avertissements``.
        AUCUN kWh, aucune perte : ce service publie de la géométrie.
    """
    par_pan = acces_par_module(layout)
    lignes = [ligne for ligne in (affectation or [])
              if isinstance(ligne, dict)]

    if not par_pan:
        return {
            'mesure': False, 'motif': MOTIF_SANS_ACCES, 'chaines': [],
            'signalements': [], 'modules_sans_acces': [],
            'avertissements': [],
        }

    chaines = {}
    sans_acces = []
    avertissements = []
    for ligne in lignes:
        chaine = ligne.get('chaine')
        if chaine is None:
            # Module posé mais câblé à rien (réserve d'appoint du noyau) : il
            # n'appartient à aucune chaîne, donc il n'en ombre aucune.
            continue
        pan = str(ligne.get('pan') or '')
        rang = _rang(ligne.get('module'))
        valeurs = par_pan.get(pan)
        acces = None
        if valeurs is not None and rang is not None and 1 <= rang <= len(valeurs):
            acces = valeurs[rang - 1]
        if acces is None:
            sans_acces.append(str(ligne.get('module') or ''))
        cle = (pan, chaine)
        entree = chaines.setdefault(cle, {
            'chaine': chaine, 'pan': pan, 'mppt': ligne.get('mppt'),
            'modules': [],
        })
        entree['modules'].append({'module': ligne.get('module'),
                                  'acces': acces})

    if sans_acces:
        avertissements.append(
            f'{len(sans_acces)} module(s) affecté(s) n’ont pas d’accès '
            'solaire dans le document : ils sont publiés SANS accès et '
            'n’entrent dans aucun écart (aucune valeur n’est supposée).')

    publiees = []
    for cle in sorted(chaines, key=lambda c: (c[0], c[1])):
        entree = chaines[cle]
        mesures = [m['acces'] for m in entree['modules']
                   if m['acces'] is not None]
        if mesures:
            acces_min = min(mesures)
            acces_max = max(mesures)
            le_plus_ombre = min(
                (m for m in entree['modules'] if m['acces'] is not None),
                key=lambda m: m['acces'])['module']
            publiees.append(dict(
                entree,
                acces_min=acces_min, acces_max=acces_max,
                acces_moyen=round(sum(mesures) / len(mesures), 4),
                ecart_interne=round(acces_max - acces_min, 4),
                module_le_plus_ombre=le_plus_ombre,
                modules_mesures=len(mesures)))
        else:
            publiees.append(dict(
                entree, acces_min=None, acces_max=None, acces_moyen=None,
                ecart_interne=None, module_le_plus_ombre=None,
                modules_mesures=0))

    mesurees = [c for c in publiees if c['acces_min'] is not None]
    signalements = []
    if mesurees:
        # (1) LA chaîne qui contient le module le plus ombré du toit. Aucun
        # seuil : une comparaison. C'est la garantie exigée par la tâche.
        pire = min(mesurees, key=lambda c: c['acces_min'])
        reference = max(c['acces_max'] for c in mesurees)
        signalements.append({
            'chaine': pire['chaine'], 'pan': pire['pan'],
            'module': pire['module_le_plus_ombre'],
            'acces': pire['acces_min'],
            'ecart': round(reference - pire['acces_min'], 4),
            'raison': (
                'Cette chaîne contient le module le plus ombré du toit : son '
                f'accès solaire est de {round(pire["acces_min"] * 100, 1)} % '
                f'contre {round(reference * 100, 1)} % pour le module le '
                'mieux exposé. Le courant d’une chaîne est celui de son '
                'module le plus faible.'),
        })
        # (2) Le seuil SAISI, s'il l'est : écart INTERNE à une chaîne.
        seuil = _nombre(ecart_signale)
        if seuil is not None and seuil >= 0:
            for chaine in mesurees:
                if chaine['ecart_interne'] < seuil:
                    continue
                if (chaine['chaine'], chaine['pan']) == (pire['chaine'],
                                                         pire['pan']):
                    continue
                signalements.append({
                    'chaine': chaine['chaine'], 'pan': chaine['pan'],
                    'module': chaine['module_le_plus_ombre'],
                    'acces': chaine['acces_min'],
                    'ecart': chaine['ecart_interne'],
                    'raison': (
                        'Écart interne à la chaîne de '
                        f'{round(chaine["ecart_interne"] * 100, 1)} points, '
                        f'au-delà du seuil saisi '
                        f'({round(seuil * 100, 1)} points).'),
                })

    return {
        'mesure': True,
        'motif': '',
        'chaines': publiees,
        'signalements': signalements,
        'modules_sans_acces': sans_acces,
        'avertissements': avertissements,
    }
