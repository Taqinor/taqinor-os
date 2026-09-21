"""CAD-B — CAD35 : lecture des périodes d'absence déclarées.

Une seule question, posée une seule fois par calcul de cockpit : « ce jour-là,
la personne qui devait faire cette touche était-elle déclarée absente ? ».

Pourquoi un module à part : `selectors.kpi_adherence` appelle `_a_lheure` des
centaines de fois par requête ; la couverture des absences se charge donc UNE
fois (deux requêtes bornées) et se relit ensuite en mémoire. Aucun calcul de
date n'est réinventé ici — une absence est un intervalle de dates LOCALES,
bornes comprises, exactement comme le modèle le déclare.

Garde-fou de CAD35, rappelé ici parce que c'est ce module qu'on lira pour
vérifier : une absence ne SUPPRIME, n'AVANCE ni ne DÉCALE aucune touche. Elle
neutralise une MESURE d'adhérence, rien d'autre.
"""
from __future__ import annotations


# ── CAD-B ── CAD35 ──────────────────────────────────────────────────────────

class CouvertureAbsences:
    """Les absences d'une société sur une fenêtre, prêtes à être interrogées.

    ``couvre(user_id, jour)`` répond vrai quand ``jour`` tombe dans une
    absence de CETTE personne, ou dans une fermeture de toute la société
    (période sans ``utilisateur``). Une absence déclarée pour quelqu'un
    d'autre n'excuse évidemment personne.
    """

    __slots__ = ('_par_user', '_societe', '_periodes')

    def __init__(self, periodes=()):
        self._periodes = list(periodes)
        self._par_user = {}
        self._societe = []
        for periode in self._periodes:
            if periode.utilisateur_id is None:
                self._societe.append(periode)
            else:
                self._par_user.setdefault(
                    periode.utilisateur_id, []).append(periode)

    def __bool__(self):
        return bool(self._periodes)

    def couvre(self, user_id, jour):
        if jour is None:
            return False
        for periode in self._societe:
            if periode.couvre(jour):
                return True
        if user_id is None:
            return False
        for periode in self._par_user.get(user_id, ()):
            if periode.couvre(jour):
                return True
        return False

    def resume(self):
        """Ce que le cockpit AFFICHE : une ligne par période déclarée, sans
        prénom en dur — l'identifiant de la personne et son remplaçant, que
        l'écran résout en nom."""
        return [
            {
                'id': periode.pk,
                'utilisateur_id': periode.utilisateur_id,
                'remplacant_id': periode.remplacant_id,
                'motif': periode.motif,
                'date_debut': periode.date_debut.isoformat(),
                'date_fin': periode.date_fin.isoformat(),
            }
            for periode in sorted(
                self._periodes,
                key=lambda p: (p.date_debut, p.utilisateur_id or 0))
        ]


def couverture(company, debut, fin, *, utilisateurs=None):
    """Charge les absences de ``company`` qui CHEVAUCHENT [debut, fin].

    ``utilisateurs`` restreint aux absences de ces personnes (plus les
    fermetures de société, qui concernent tout le monde) : les tuiles
    personnelles n'ont pas à lire les congés de l'équipe.
    """
    from django.db.models import Q

    from .models import PeriodeAbsence

    qs = PeriodeAbsence.objects.filter(
        company=company, date_debut__lte=fin, date_fin__gte=debut)
    if utilisateurs is not None:
        qs = qs.filter(
            Q(utilisateur_id__isnull=True)
            | Q(utilisateur_id__in=list(utilisateurs)))
    return CouvertureAbsences(
        qs.only('id', 'utilisateur_id', 'remplacant_id', 'motif',
                'date_debut', 'date_fin'))
