#!/usr/bin/env python3
"""ADEP108 (D-ACAL-97, « only one engine should be in my ERP ») — la garde « un seul moteur ».

Elle lit (AST, jamais par recherche de texte : une MENTION dans un commentaire ou une
docstring n'est pas un appel) chaque module Python de production de
``backend/django_core/apps`` et relève les APPELS des cinq noyaux qui calculent un chiffre
de conception solaire : ``recommander_taille``, ``etudier_ci``, ``etudier_pompage``,
``calculer_etude_horaire`` et ``simuler_calepinage``. Un appel n'est permis que :

* dans ``apps/ventes/conception/`` (le moteur unique, qui appelle les noyaux tels quels) ;
* dans un fichier de la LISTE FIGÉE :data:`APPELANTS_PERMIS` (appelants restants au
  25/11/2026, chacun avec la raison qui le garde), qui ne fait que RÉTRÉCIR.

Elle échoue (code 1) sur un NOUVEL appel hors liste — en nommant le fichier, la ligne et le
noyau — et sur une entrée PÉRIMÉE de la liste (le fichier n'appelle plus ce noyau : retirer
l'entrée, la liste ne regrossit jamais). Les tests (``tests/``, ``test*.py``) et les
migrations ne sont pas lus. Branchée au job ``stage-names`` par ``scripts/ci_guards.py``.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
APPS = RACINE / 'backend' / 'django_core' / 'apps'

#: Les cinq noyaux surveillés.
NOYAUX = ('recommander_taille', 'etudier_ci', 'etudier_pompage', 'calculer_etude_horaire',
          'simuler_calepinage')

#: Le moteur unique : seul endroit où un noyau s'appelle sans entrée dans la liste.
MOTEUR = 'apps/ventes/conception/'

#: La liste FIGÉE (25/11/2026) — ``(fichier relatif à django_core, noyau) -> pourquoi il reste``.
#: Elle ne fait que rétrécir : une entrée qui n'appelle plus son noyau fait échouer la garde.
APPELANTS_PERMIS = {
    # ── le calepinage : la simulation de LA POSE (PVGIS heure par heure), son seul calcul ──
    ('apps/calepinage/tasks.py', 'simuler_calepinage'):
        'la tâche de fond qui exécute la simulation (point d’entrée unique hors requête)',
    ('apps/calepinage/views/simulation.py', 'simuler_calepinage'):
        'POST simuler/ met la tâche en file (la simulation de la pose, jamais un chiffre du devis)',
    ('apps/calepinage/services/simulation.py', 'simuler_calepinage'):
        'recalculer_simulations_societe : relance en file des simulations de la société',
    ('apps/calepinage/services/simulation_auto.py', 'simuler_calepinage'):
        'la simulation qui part seule après un enregistrement de la pose (mise en file)',
    ('apps/calepinage/services/pose_pour_moteur.py', 'simuler_calepinage'):
        'le moteur unique lit la production de la pose par cette porte (pose souveraine, niveau 15)',
    ('apps/calepinage/services/plan_par_defaut.py', 'simuler_calepinage'):
        'le toit supposé d’un lead sans toit tracé (ACAL2026), simulé pour le moteur, sans écriture',
    ('apps/calepinage/services/balayage.py', 'simuler_calepinage'):
        'le balayage d’orientation / inclinaison / ratio d’une pose, hors lead, sans écriture',
    ('apps/calepinage/management/commands/semer_exemples_calepinage.py', 'simuler_calepinage'):
        'commande de démonstration : sème des calepinages d’exemple et les simule',
    # ── les cœurs du moteur eux-mêmes (appelés par apps/ventes/conception/) ──
    ('apps/ventes/etude_horaire.py', 'calculer_etude_horaire'):
        'cœur de l’étude horaire d’un devis (etude_horaire_pour_devis), le noyau résidentiel',
    ('apps/ventes/domain/entrees.py', 'calculer_etude_horaire'):
        'kwargs_moteur_ombre : entrées du noyau horaire avec l’ombrage, cœur du moteur',
    ('apps/ventes/dimensionnement_balayage.py', 'calculer_etude_horaire'):
        'balayage des tailles du dimensionnement (cœur de recommander_taille)',
    ('apps/ventes/domain/taille.py', 'recommander_taille'):
        'taille recommandée du devis automatique, cœur appelé par le moteur unique',
    ('apps/ventes/profils_comparatifs.py', 'recommander_taille'):
        'profils comparatifs (bloc de l’étude du moteur), une taille par silhouette',
    ('apps/ventes/offres_tailles.py', 'calculer_etude_horaire'):
        'cartes des tailles proposées (étude du moteur), deux variantes par taille',
    ('apps/ventes/economie_pompage.py', 'etudier_pompage'):
        'économie de pompage d’un devis agricole (bloc economie_pompage, contrat AGR3)',
    # ── les aperçus SANS lead ni devis (écran public, générateur avant enregistrement) ──
    ('apps/ventes/etude_horaire_view.py', 'calculer_etude_horaire'):
        'POST etude-horaire/preview/ : aperçu sans devis persisté (graphe du générateur)',
    ('apps/ventes/etude_horaire_view.py', 'recommander_taille'):
        'le tableau de dimensionnement du même aperçu sans devis persisté',
    ('apps/ventes/etude_ci_view.py', 'etudier_ci'):
        'POST etude-ci/preview/ : aperçu C&I, calcule, n’écrit rien',
    ('apps/ventes/etude_pompage_view.py', 'etudier_pompage'):
        'POST etude-pompage/preview/ : aperçu agricole, calcule, n’écrit rien',
    # ── les recompositions d’un devis C&I existant (après visite, après choix de batteries) ──
    ('apps/ventes/domain/revision_visite_ci.py', 'etudier_ci'):
        'recompose le devis C&I avec les mesures de la visite validée (CORC2)',
    ('apps/ventes/domain/recomposition_batteries_ci.py', 'etudier_ci'):
        'recompose l’étude C&I avec N batteries (mêmes entrées que la création)',
}


def _est_production(chemin, racine):
    parties = chemin.relative_to(racine).parts
    return not ('tests' in parties or 'migrations' in parties or chemin.name.startswith('test'))


def _alias(arbre):
    """``{nom local: noyau}`` : les noyaux eux-mêmes et leurs alias d'import
    (``from … import simuler_calepinage as tache_de_simulation``)."""
    noms = {noyau: noyau for noyau in NOYAUX}
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.ImportFrom):
            noms.update({a.asname: a.name for a in noeud.names if a.asname and a.name in NOYAUX})
    return noms


def appels(source, nom_fichier='<source>'):
    """``[(ligne, noyau)]`` des lectures d'un des :data:`NOYAUX` dans ``source`` (texte
    Python) : un appel, ou le noyau passé par référence (``partial``, rangé dans un nom),
    alias d'import compris. Les imports, définitions, commentaires et chaînes ne comptent pas."""
    arbre = ast.parse(source, filename=nom_fichier)
    noms = _alias(arbre)
    trouves = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Name) and isinstance(noeud.ctx, ast.Load) and noeud.id in noms:
            trouves.add((noeud.lineno, noms[noeud.id]))
        elif isinstance(noeud, ast.Attribute) and isinstance(noeud.ctx, ast.Load) and noeud.attr in NOYAUX:
            trouves.add((noeud.lineno, noeud.attr))
    return sorted(trouves)


def releve(racine=APPS):
    """``{(fichier relatif à django_core, noyau): [lignes]}`` des appels hors moteur."""
    base = racine.parent
    trouves = {}
    for chemin in sorted(racine.rglob('*.py')):
        if not _est_production(chemin, racine):
            continue
        relatif = chemin.relative_to(base).as_posix()
        if relatif.startswith(MOTEUR):
            continue
        source = chemin.read_text(encoding='utf-8')
        if not any(noyau in source for noyau in NOYAUX):  # pré-filtre : seul l'AST décide
            continue
        for ligne, noyau in appels(source, relatif):
            trouves.setdefault((relatif, noyau), []).append(ligne)
    return trouves


def verdict(trouves, permis):
    """``(nouveaux, perimes)`` : appels hors liste ``[(fichier, ligne, noyau)]`` et entrées
    de la liste qui n'appellent plus leur noyau ``[(fichier, noyau)]``."""
    nouveaux = [(fichier, ligne, noyau) for (fichier, noyau), lignes in sorted(trouves.items())
                if (fichier, noyau) not in permis for ligne in lignes]
    perimes = sorted(cle for cle in permis if cle not in trouves)
    return nouveaux, perimes


def main(racine=APPS, permis=None):
    permis = APPELANTS_PERMIS if permis is None else permis
    nouveaux, perimes = verdict(releve(racine), permis)
    for fichier, ligne, noyau in nouveaux:
        print(f'check_moteur_unique : NOUVEL appel de {noyau} hors du moteur unique — '
              f'{fichier}:{ligne} (lire la conception rangée, apps.ventes.selectors.conception_courante)')
    for fichier, noyau in perimes:
        print(f'check_moteur_unique : entrée PÉRIMÉE de la liste — {fichier} n\'appelle plus {noyau} : '
              'retirez-la de APPELANTS_PERMIS (la liste ne fait que rétrécir)')
    if nouveaux or perimes:
        return 1
    print(f'check_moteur_unique : OK — {len(permis)} appelant(s) restant(s) hors de {MOTEUR}, aucun nouveau.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
