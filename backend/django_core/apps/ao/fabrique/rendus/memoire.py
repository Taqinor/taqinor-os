"""AOF133 — mémoire technique par SECTIONS COMPOSABLES, pas un texte libre.

Le constat qui commande ce module : sans composition, une bascule d'équipement
redevient un chercher-remplacer sur ~90 paragraphes. Les douze remplacements de
désignation de la bascule batterie réelle ne sont fiables que si la désignation
n'existe qu'à UN endroit — le snapshot de l'équipement (AOF118). Les sections
ne portent donc que des ``{{ placeholders }}``, jamais une désignation ni un
chiffre écrit à la main.

Trois briques :

* :func:`contexte_memoire` — le contexte UNIQUE, dérivé du dossier
  (équipements actifs, résultats de calepinage, références) ;
* :func:`sections_a_inclure` — filtre déclaratif de la bibliothèque
  ``SectionMemoire`` par ``conditions_inclusion`` (jamais du code évalué) ;
* :func:`assembler_memoire` / :func:`rendre_memoire_html` — l'assemblage, rendu
  par ``core.templating`` puis par le gabarit Django ``ao/memoire.html``.

La section « géométries » n'est pas rédigée : elle est CALCULÉE depuis les
variantes retenues et injectée dans le contexte.
"""
from __future__ import annotations

from decimal import Decimal

from ..gabarits import rendre_gabarit, valider_gabarit
from ..identite import identite_client

__all__ = [
    'CODE_SECTION_GEOMETRIES',
    'assembler_memoire',
    'contexte_memoire',
    'rendre_memoire_html',
    'sections_a_inclure',
]

#: Code réservé de la section CALCULÉE (jamais seedée : son corps vient du
#: calepinage, pas d'un rédacteur).
CODE_SECTION_GEOMETRIES = 'GEOMETRIES'


def _equipements_par_role(appel_offre):
    """``{role: {designation, marque, reference, quantite, …}}`` — snapshot.

    La désignation vient du snapshot FIGÉ de l'équipement : c'est l'UNIQUE
    source. Aucune section ne la recopie.
    """
    from ...models import EquipementAO

    par_role = {}
    for equipement in EquipementAO.objects.filter(
            company=appel_offre.company, appel_offre=appel_offre, actif=True):
        par_role[equipement.role] = {
            'designation': equipement.designation,
            'marque': equipement.marque,
            'reference': equipement.reference_constructeur,
            'quantite': str(equipement.quantite),
            'unite': equipement.unite,
            'caracteristiques': equipement.caracteristiques or {},
        }
    return par_role


def _geometries(appel_offre):
    """Résultats de calepinage des variantes RETENUES, par toiture.

    Renvoie ``{'lignes': [...], 'total_modules': n, 'puissance_kwc': x}``.
    Rien n'est arrondi ni « estimé » : ce sont les résultats du moteur.
    """
    from ...models import VarianteCalepinage

    lignes = []
    total_modules = 0
    puissance = Decimal('0.000')
    retenues = VarianteCalepinage.objects.filter(
        company=appel_offre.company, appel_offre=appel_offre,
        est_retenue=True).select_related('toiture', 'toiture__batiment')
    for variante in retenues:
        modules = int(variante.total_modules or 0)
        kwc = Decimal(str(variante.puissance_kwc or 0))
        total_modules += modules
        puissance += kwc
        toiture = variante.toiture
        lignes.append({
            'batiment': getattr(toiture.batiment, 'code', '') if toiture else '',
            'toiture': getattr(toiture, 'code_document', '') if toiture else '',
            'variante': variante.nom,
            'modules': modules,
            'puissance_kwc': str(kwc),
            'methode': (variante.preuve or {}).get('methode', ''),
        })
    return {
        'lignes': lignes,
        'total_modules': total_modules,
        'puissance_kwc': str(puissance),
    }


def _references(appel_offre):
    """Tableau de références : les AO GAGNÉS de la société, jamais inventés."""
    from ...models import ResultatAO

    tableau = []
    gagnes = ResultatAO.objects.filter(
        company=appel_offre.company, issue=ResultatAO.Issue.GAGNE
    ).select_related('appel_offre').exclude(appel_offre=appel_offre)
    for resultat in gagnes:
        tableau.append({
            'objet': resultat.appel_offre.objet,
            'maitre_ouvrage': resultat.appel_offre.maitre_ouvrage
            or resultat.appel_offre.acheteur,
            'annee': resultat.date_resultat.year
            if resultat.date_resultat else '',
        })
    return tableau


def contexte_memoire(appel_offre):
    """Le contexte UNIQUE du mémoire — dérivé, jamais saisi (AOF133).

    Toute grandeur citée dans une section vient d'ici. Un changement
    d'équipement ou de calepinage change donc le mémoire SANS intervention.
    """
    geometries = _geometries(appel_offre)
    equipements = _equipements_par_role(appel_offre)
    return {
        'appel_offre': {
            'reference': appel_offre.reference,
            'reference_acheteur': appel_offre.reference_acheteur,
            'objet': appel_offre.objet,
            'acheteur': appel_offre.acheteur,
            'maitre_ouvrage': appel_offre.maitre_ouvrage,
            'delai_execution_jours': appel_offre.delai_execution_jours or '',
            'validite_offre_jours': appel_offre.validite_offre_jours,
            'nombre_exemplaires': appel_offre.nombre_exemplaires,
            'date_limite': appel_offre.date_limite or '',
        },
        # AOF144 — un rendu CLIENT n'utilise QUE le soumissionnaire : le
        # bureau d'exécution n'entre jamais dans ce contexte.
        'soumissionnaire': identite_client(appel_offre),
        'equipements': equipements,
        'geometries': geometries,
        'etude': {
            'puissance_kwc': geometries['puissance_kwc'],
            'nombre_modules': geometries['total_modules'],
            'nombre_batiments': appel_offre.batiments.count(),
        },
        'references': {'tableau': _references(appel_offre)},
    }


def _condition_satisfaite(conditions, contexte):
    """Évalue des conditions DÉCLARATIVES ``{"chemin.variable": valeur}``.

    Aucune exécution de code : on résout le chemin dans le contexte et on
    compare la représentation textuelle. Une condition dont la variable est
    absente n'est PAS satisfaite (une section conditionnelle ne s'invite pas
    par défaut).
    """
    for chemin, attendu in (conditions or {}).items():
        courant = contexte
        for partie in str(chemin).split('.'):
            if isinstance(courant, dict):
                courant = courant.get(partie)
            else:
                courant = getattr(courant, partie, None)
            if courant is None:
                break
        if attendu is True:
            if not courant:
                return False
            continue
        if attendu is False:
            if courant:
                return False
            continue
        if str(courant) != str(attendu):
            return False
    return True


def sections_a_inclure(company, contexte):
    """Les sections ACTIVES dont les conditions d'inclusion sont satisfaites."""
    from ...models import SectionMemoire

    retenues = []
    for section in SectionMemoire.objects.filter(company=company, actif=True):
        if _condition_satisfaite(section.conditions_inclusion, contexte):
            retenues.append(section)
    return retenues


def _corps_geometries(geometries):
    """Corps de la section « géométries » — ASSEMBLÉ, jamais rédigé."""
    if not geometries['lignes']:
        return ("Aucun calepinage retenu n'est encore publiable : la section "
                "sera renseignée dès qu'une variante sera retenue.")
    phrases = []
    for ligne in geometries['lignes']:
        phrases.append(
            f"Bâtiment {ligne['batiment']} (planche {ligne['toiture']}) : "
            f"{ligne['modules']} modules pour {ligne['puissance_kwc']} kWc, "
            f"calepinage « {ligne['variante']} »."
        )
    phrases.append(
        f"Total du projet : {geometries['total_modules']} modules, "
        f"{geometries['puissance_kwc']} kWc."
    )
    return ' '.join(phrases)


def assembler_memoire(appel_offre, *, contexte=None):
    """Assemble le mémoire : liste ordonnée de ``{code, titre, corps}`` rendus.

    Chaque corps est VALIDÉ (aucun littéral chiffré) puis rendu par
    ``core.templating.rendre`` via ``fabrique.gabarits``. La section
    « géométries » est ajoutée à la fin, CALCULÉE depuis le contexte.
    """
    contexte = contexte or contexte_memoire(appel_offre)
    blocs = []
    for section in sections_a_inclure(appel_offre.company, contexte):
        valider_gabarit(section.corps, origine=section.titre)
        blocs.append({
            'code': section.code,
            'titre': section.titre,
            'corps': rendre_gabarit(section.corps, contexte, valider=False),
        })
    blocs.append({
        'code': CODE_SECTION_GEOMETRIES,
        'titre': 'Géométries d\'implantation retenues',
        'corps': _corps_geometries(contexte['geometries']),
    })
    return blocs


def rendre_memoire_html(appel_offre, *, contexte=None):
    """Rend le mémoire assemblé dans le gabarit Django ``ao/memoire.html``."""
    from django.template.loader import render_to_string

    contexte = contexte or contexte_memoire(appel_offre)
    return render_to_string('ao/memoire.html', {
        'appel_offre': appel_offre,
        'contexte': contexte,
        'sections': assembler_memoire(appel_offre, contexte=contexte),
    })
