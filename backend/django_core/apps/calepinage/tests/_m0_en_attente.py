"""Clés posées par les M0 ACAL (PACT10) AVANT que leur producteur ne les serve.

Les contrats ACAL1-21 sont arrivés SEULS sur main (le contrat d'abord) : leurs
échantillons portent déjà des clés que le serveur d'aujourd'hui n'émet pas.
Les tests qui comparent ce que le serveur SERT à l'échantillon retirent ces
clés-là — et SEULEMENT elles — via :func:`sans`, chacune nommant la tâche qui
la livre. La tâche nommée retire son entrée dans le même commit que son
producteur : la comparaison d'égalité rougit d'elle-même dès qu'une clé « en
attente » est réellement servie (la valeur servie ne correspond plus à
l'échantillon amputé), ou via :func:`affirmer_non_servies`.

Syntaxe des chemins : ``'a.b.c'`` (clés de dictionnaires), ``'a[].b'``
(chaque élément d'une liste). Un chemin absent est ignoré.
"""
from __future__ import annotations

import copy


def _retirer(noeud, segments):
    if not segments or noeud is None:
        return
    tete, reste = segments[0], segments[1:]
    if tete.endswith('[]'):
        liste = noeud.get(tete[:-2]) if isinstance(noeud, dict) else None
        if isinstance(liste, list) and reste:
            for element in liste:
                _retirer(element, reste)
        return
    if not isinstance(noeud, dict):
        return
    if not reste:
        noeud.pop(tete, None)
        return
    _retirer(noeud.get(tete), reste)


def sans(valeur, chemins):
    """Copie profonde de ``valeur`` privée des clés désignées par ``chemins``.

    ``chemins`` : itérable de chemins, ou dictionnaire ``chemin -> tâche``.
    """
    copie = copy.deepcopy(valeur)
    for chemin in chemins:
        _retirer(copie, chemin.split('.'))
    return copie


def _present(noeud, segments):
    if not segments or noeud is None:
        return False
    tete, reste = segments[0], segments[1:]
    if tete.endswith('[]'):
        liste = noeud.get(tete[:-2]) if isinstance(noeud, dict) else None
        return isinstance(liste, list) and any(
            _present(element, reste) for element in liste)
    if not isinstance(noeud, dict) or tete not in noeud:
        return False
    return True if not reste else _present(noeud[tete], reste)


def affirmer_non_servies(test, servi, en_attente):
    """Rougit dès qu'une clé « en attente » est servie : retirer son entrée."""
    servies = sorted(chemin for chemin in en_attente
                     if _present(servi, chemin.split('.')))
    test.assertEqual(
        servies, [],
        f'Le serveur sert désormais {servies} : retirer ces clés de la table '
        'des clés en attente (tâche livrée : '
        f'{sorted({en_attente[c] for c in servies})}).')


#: ``calepinage_detail.json`` (ACAL6, forme_serveur ``partielle``) : la
#: première moitié back de chaque clé la sert, retire son entrée et remet
#: ``complete`` quand la table est vide.
EN_ATTENTE_DETAIL = {
    'custom_data': 'ACAL6 moitié back (D09-T33)',
    'permissions.peut_deroger': 'ACAL6 moitié back (D-ACAL-9)',
    'lead.supprime': 'ACAL178',
}

#: Clés du bloc de simulation posées par ACAL8 (M0) — chemins relatifs à
#: un état de ``calepinage_simulation.json`` OU de ``calepinage_resultat.json``
#: (les deux échantillons publient les mêmes blocs).
EN_ATTENTE_SIMULATION = {
    'simulation.version_simulation': 'ACAL48',
    'simulation.reglages_utilises': 'ACAL48',
    'simulation.meteo_fichier': 'ACAL146',
    'cascade.etapes_omises': 'ACAL49',
    'cascade.irradiation_incidente_kwh_m2': 'ACAL128',
    'meteo.fichier': 'ACAL146',
    'meteo.heure.provenance_fuseau': 'ACAL129',
    'ombrage.par_pan[].perte_ombrage_pct': 'ACAL53',
    'ombrage.par_pan[].cascade': 'ACAL53',
    'production.total.complete': 'ACAL49',
    'production.total.socle_manquant': 'ACAL49',
    'production.total.mention': 'ACAL49',
    'production.total.performance_ratio_motif': 'ACAL49',
    'production.total.p75_kwh_motif': 'ACAL49',
    'production.total.p90_kwh_motif': 'ACAL49',
    'production.total.p95_kwh_motif': 'ACAL49',
    'production.total.p95_kwh': 'ACAL49',
    'production.total.portee': 'ACAL54',
    'production.total.annees_fenetre': 'ACAL54',
    'production.annees[].observe': 'ACAL54',
}

#: Clés propres à ``calepinage_resultat.json`` posées par ACAL8 (M0), en plus
#: des blocs de simulation ci-dessus.
EN_ATTENTE_RESULTAT = {
    **EN_ATTENTE_SIMULATION,
    'production.annees': 'ACAL54',
    'simulation': 'ACAL48',
    'ecart_devis': 'ACAL104',
    'derogations': 'ACAL283',
    'ecarts_longueur': 'ACAL283',
    'pose.pans[].cle': 'ACAL265',
    'pose.pans[].module_id': 'ACAL264',
    'electrique.affectation[].couleur_chaine': 'ACAL285',
    'electrique.affectation[].couleur_mppt': 'ACAL285',
    'electrique.affectation_obsolete': 'ACAL265',
}


# ═══════════════════════════════════════════════════════════════════════════
# Export / import de projet v3 (ACAL17, M0) — producteur : ACAL243.
# Le serveur exporte et relit le format 2 tant qu'ACAL243 n'a pas livré le
# bloc ``saisies`` ; ces deux fonctions ramènent un état du contrat v3 à ce
# que le serveur v2 sert. ACAL243 les supprime avec ses appelants.
# ═══════════════════════════════════════════════════════════════════════════

TACHE_EXPORT_V3 = 'ACAL243'


def export_projet_v2(document):
    """Un fichier ``export_projet.json`` v3 ramené au format 2 servi."""
    servi = sans(document, {'saisies': TACHE_EXPORT_V3})
    servi['format_version'] = 2
    return servi


def import_projet_v2(reponse):
    """Une réponse ``calepinage_projet_json.json`` v3 ramenée à celle du
    serveur v2 : ni ``saisies`` reprises, ni produits ignorés, ni ``ouvrir``.
    """
    servi = sans(reponse, {'ouvrir': TACHE_EXPORT_V3})
    if 'format_version' in servi:
        servi['format_version'] = 2
    if 'repris' in servi:
        servi['repris'] = [bloc for bloc in servi['repris']
                           if bloc != 'saisies']
    if 'ignores' in servi:
        servi['ignores'] = [ligne for ligne in servi['ignores']
                            if ligne.get('bloc') != 'saisies.produits']
    return servi


def refus_version_v2(refus):
    """Le refus de version v3 (« versions lues : 1, 2, 3 ») ramené au v2."""
    return {champ: message.replace('1, 2, 3)', '1, 2)')
            for champ, message in refus.items()}
