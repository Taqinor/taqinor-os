"""API planning Gantt d'un projet — PROJ10.

Assemble une représentation prête à dessiner un diagramme de Gantt : une BARRE
par tâche feuille (début/fin en jours relatifs ET, si le projet a une
``date_debut``, en dates calendaires), l'avancement, le drapeau CRITIQUE et les
marges issus du CPM (PROJ8), plus la liste des LIENS de dépendance
(prédécesseur → successeur, type + lag) pour tracer les flèches.

Lecture seule : aucune donnée n'est modifiée. Les dates calendaires sont une
projection NAÏVE en jours calendaires à partir de ``projet.date_debut`` (le
calendrier ouvré/fériés de PROJ12 viendra raffiner cette projection) ; sans
``date_debut`` les barres restent en jours relatifs (dates ``None``).
"""
from datetime import timedelta

from . import cpm
from .models import DependanceTache, Tache


def _dates_calendaires(date_origine, es, ef):
    """(début, fin) calendaires d'une barre, ou (None, None) sans origine.

    Convention : ``debut = origine + es jours`` ; ``fin = origine + ef jours``
    (borne de fin EXCLUSIVE en jours relatifs ; on rend la dernière journée
    travaillée en soustrayant 1 jour pour l'affichage d'une barre inclusive).
    """
    if date_origine is None:
        return None, None
    debut = date_origine + timedelta(days=es)
    fin = date_origine + timedelta(days=max(es, ef - 1))
    return debut, fin


def construire_planning(projet):
    """Construit le planning Gantt du projet. Renvoie un dict prêt à sérialiser.

    Structure ::

        {
          'date_origine': 'YYYY-MM-DD' | None,   # projet.date_debut
          'duree_projet': int,                   # jours (chemin critique)
          'has_cycle': bool,
          'taches': [
             {'tache', 'libelle', 'code_wbs', 'statut', 'avancement_pct',
              'duree', 'es', 'ef', 'ls', 'lf', 'marge_totale', 'marge_libre',
              'critique', 'date_debut', 'date_fin'},  # dates None sans origine
             ...
          ],
          'liens': [
             {'id', 'source', 'cible', 'type', 'lag'},  # source=préd, cible=succ
             ...
          ],
        }

    Quand un cycle empêche le CPM (``has_cycle=True``), ``taches`` est vide mais
    ``liens`` reste fourni (pour diagnostiquer le cycle côté UI).
    """
    resultat_cpm = cpm.calculer_cpm(projet)
    date_origine = projet.date_debut

    # Statut/avancement frais des tâches (le CPM ne les porte pas).
    meta = {
        t.id: (t.statut, int(t.avancement_pct))
        for t in Tache.objects.filter(projet=projet, company=projet.company)
    }

    taches = []
    for row in resultat_cpm['taches']:
        statut, avancement = meta.get(row['tache'], ('', 0))
        debut, fin = _dates_calendaires(date_origine, row['es'], row['ef'])
        taches.append({
            'tache': row['tache'],
            'libelle': row['libelle'],
            'code_wbs': row['code_wbs'],
            'statut': statut,
            'avancement_pct': avancement,
            'duree': row['duree'],
            'es': row['es'],
            'ef': row['ef'],
            'ls': row['ls'],
            'lf': row['lf'],
            'marge_totale': row['marge_totale'],
            'marge_libre': row['marge_libre'],
            'critique': row['critique'],
            'date_debut': debut.isoformat() if debut else None,
            'date_fin': fin.isoformat() if fin else None,
        })

    liens = []
    deps = DependanceTache.objects.filter(
        predecesseur__projet=projet, company=projet.company).order_by('id')
    for dep in deps:
        liens.append({
            'id': dep.id,
            'source': dep.predecesseur_id,
            'cible': dep.successeur_id,
            'type': dep.type_dependance,
            'lag': dep.lag,
        })

    return {
        'date_origine': date_origine.isoformat() if date_origine else None,
        'duree_projet': resultat_cpm['duree_projet'],
        'has_cycle': resultat_cpm['has_cycle'],
        'taches': taches,
        'liens': liens,
    }
