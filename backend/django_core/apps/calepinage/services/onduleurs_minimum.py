"""ACAL632 — le plus petit nombre d'onduleurs qui tient le champ, SUGGÉRÉ.

Le noyau ne connaît que le plafond de dossier (« sans plafond, un seul
onduleur »). Quand les pans dépassent les entrées MPPT d'un onduleur sans
polystring, la conception le dit en alerte sans jamais proposer un second
onduleur. Ici, on relance la conception avec ``n_mppt × k`` entrées pour
k = 1, 2, … et on retient le plus petit k où les TROIS signaux réels sont au
vert : (a) aucun dépassement des entrées MPPT, (b) aucune surcharge de courant
d'entrée, (c) plus aucun module hors chaîne.

Aucun coût ici (l'argent reste dans ``apps/ventes``) ; le noyau n'est pas
modifié ; rien n'est écrit.
"""

#: Codes du noyau qui disent une surcharge de courant d'entrée (``core/
#: electrique/chaines.py`` : Isc cumulé hors spécification, Imp cumulé qui
#: écrête).
CODES_SURCHARGE_COURANT = ('CH_ISC_CUMULE_HORS_SPECIFICATION',
                           'CH_IMP_CUMULE_ECRETAGE')


def signaux(conception):
    """Les phrases des trois signaux de CETTE conception (vide = au vert)."""
    if conception.resultat is None or not conception.chaines:
        return []
    lignes = []
    if 'NON autorisé' in (conception.regle_mppt or ''):
        lignes.extend(alerte for alerte in conception.alertes
                      if 'entrée(s) MPPT pour' in alerte)
    lignes.extend(verdict.libelle for verdict in getattr(
        conception.resultat, 'verdicts', ()) or ()
        if verdict.code in CODES_SURCHARGE_COURANT)
    reste = int(getattr(conception.resultat, 'reste_total', 0) or 0)
    if reste > 0:
        lignes.append("%d module(s) restent hors chaîne" % reste)
    return lignes


def _avec_nombre(calepinage, materiel, entree, layout, nombre):
    """La conception relancée avec ``nombre`` onduleurs ACCEPTÉS (ACAL633 :
    ``nombre_onduleurs`` multiplie les entrées MPPT et le compte d'onduleurs)."""
    from .electrique import conception_du_calepinage

    return conception_du_calepinage(
        calepinage, entree={**(entree or {}), 'nombre_onduleurs': nombre},
        layout=layout, materiel=materiel)[0]


def onduleurs_suggeres(calepinage, conception, materiel, *, entree=None,
                       layout=None):
    """``{nombre, motif, signaux_avec_1}``, ou ``None`` si rien à juger.

    ``nombre`` vaut ``None`` quand aucun nombre d'onduleurs jusqu'au nombre de
    pans ne lève les signaux : le ``motif`` nomme alors l'obstacle.
    """
    if (conception.fiche_incomplete or conception.resultat is None
            or not conception.chaines):
        return None
    base = (conception if conception.nombre_onduleurs in (None, 1)
            else _avec_nombre(calepinage, materiel, entree, layout, 1))
    avec_un = signaux(base)
    if not avec_un:
        return {'nombre': 1, 'motif': '', 'signaux_avec_1': []}
    pans = [pan.label for pan in conception.pans]
    reste = avec_un
    for facteur in range(2, len(pans) + 1):
        reste = signaux(_avec_nombre(calepinage, materiel, entree, layout,
                                     facteur))
        if not reste:
            entrees = max(1, int(materiel['onduleur'].get('n_mppt') or 1))
            return {
                'nombre': facteur,
                'motif': "%d onduleurs sont nécessaires : %d pans pour %d "
                         "entrées par onduleur (pans : %s)"
                         % (facteur, len(pans), entrees, ', '.join(pans)),
                'signaux_avec_1': avec_un}
    return {'nombre': None,
            'motif': "aucun nombre d'onduleurs jusqu'à %d ne lève : %s"
                     % (max(len(pans), 1), ' ; '.join(reste)),
            'signaux_avec_1': avec_un}
