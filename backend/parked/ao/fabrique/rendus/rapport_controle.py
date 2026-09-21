"""AOF148 — rapport de contrôle horodaté et archivé : la PREUVE de vérification.

Pourquoi l'empreinte est le cœur de la pièce
============================================
Un rapport « tout vert » ne prouve rien s'il ne dit pas QUEL état du dossier il
a contrôlé : régénérez le pack après l'avoir édité, et le même papier certifie
un dossier qui n'existe plus. C'est la version documentaire du défaut n°1 de la
session — deux bordereaux homonymes divergents.

Le rapport porte donc l'**empreinte du pack contrôlé**, et
``est_perime(rapport, empreinte_courante)`` répond à la seule question qui
compte avant un dépôt : *ce rapport décrit-il encore le pack que je m'apprête
à remettre ?*

Reproductibilité
----------------
Aucun ``now()`` dans ce module : l'horodatage est FOURNI par l'appelant. Deux
rendus des mêmes entrées donnent le même HTML à l'octet près — sans quoi
« reproductible » ne voudrait rien dire et deux exécutions successives
produiraient deux preuves différentes du même contrôle.

Contrat d'entrée
----------------
``controles`` : ``[{'code', 'severite', 'message', 'objet', 'bloquant'}]`` —
la forme des lignes ``ControleCoherence`` (AOF146), consommée telle quelle ;
ce module ne rejoue AUCUN contrôle, il met en page un résultat.
"""
from __future__ import annotations

__all__ = [
    'SEVERITES',
    'GABARIT',
    'construire_rapport',
    'est_perime',
    'rendre_rapport_html',
    'rendre_rapport',
    'archiver_rapport',
]

GABARIT = 'ao/rapport_controle.html'

#: Ordre de gravité décroissante : un rapport se lit par le haut.
SEVERITES = ('bloquant', 'avertissement', 'information')


def construire_rapport(controles, *, empreinte_pack, horodatage,
                       reference_dossier='', pieces_hors_controle=()):
    """Compose le rapport. Ne rejoue aucun contrôle, ne décide de rien.

    ``pieces_hors_controle`` (AOF149) est repris ICI parce qu'un rapport qui
    tait les pièces non fabriquées annonce « tout vert » sur un dossier dont un
    tiers n'a jamais été vérifié — plus dangereux qu'un dossier orange.
    """
    if not empreinte_pack:
        raise ValueError(
            "Rapport de contrôle sans empreinte de pack : il ne prouverait "
            "rien, puisqu'il pourrait décrire un autre état du dossier.")
    if not horodatage:
        raise ValueError("Rapport de contrôle sans horodatage.")

    lignes = list(controles or [])
    par_severite = {severite: [] for severite in SEVERITES}
    for ligne in lignes:
        severite = str(ligne.get('severite') or 'information')
        if severite not in par_severite:
            par_severite[severite] = []
        par_severite[severite].append(ligne)

    bloquants = [ligne for ligne in lignes
                 if ligne.get('bloquant') or ligne.get('severite') == 'bloquant']
    hors_controle = list(pieces_hors_controle or ())
    return {
        'reference_dossier': reference_dossier,
        'empreinte_pack': empreinte_pack,
        'empreinte_courte': str(empreinte_pack)[:8],
        'horodatage': horodatage,
        'total': len(lignes),
        'par_severite': [
            {'severite': severite, 'lignes': par_severite.get(severite, []),
             'nombre': len(par_severite.get(severite, []))}
            for severite in SEVERITES
        ],
        'bloquants': bloquants,
        'nombre_bloquants': len(bloquants),
        'verdict': 'REFUSÉ' if bloquants else 'CONFORME',
        'pieces_hors_controle': hors_controle,
        'nombre_hors_controle': len(hors_controle),
    }


def est_perime(rapport, empreinte_pack_courante):
    """Vrai si le pack a bougé depuis l'établissement du rapport.

    Un rapport périmé n'est pas « un peu moins vert » : il ne décrit plus rien.
    """
    return str((rapport or {}).get('empreinte_pack') or '') != \
        str(empreinte_pack_courante or '')


def rendre_rapport_html(rapport):
    from django.template.loader import render_to_string

    return render_to_string(GABARIT, {'rapport': rapport})


def rendre_rapport(rapport, *, company=None, cle_objet=None):
    """PDF du rapport via ``core.pdf.render_pdf`` (ARC11).

    Avec ``cle_objet``, ``render_pdf`` téléverse aussi l'artefact sur MinIO et
    renvoie ``(octets, clé)`` — c'est la plomberie de stockage du noyau, jamais
    un second client objet.
    """
    from core.pdf import render_pdf

    html = rendre_rapport_html(rapport)
    if cle_objet:
        return render_pdf(html=html, company=company, upload_to=cle_objet)
    return render_pdf(html=html, company=company)


def archiver_rapport(cible, *, cle_objet, nom, taille=0, company=None,
                     user=None):
    """Rattache le rapport à son dossier via ``records.Attachment``.

    Aucun nouveau ``FileField`` : le garde ``apps/records/platform_guards.py``
    gèle ``apps/ao/models.py`` et tout artefact passe par la pièce jointe
    générique. La société est posée côté serveur, jamais lue d'une requête.
    """
    from django.contrib.contenttypes.models import ContentType

    from apps.records.models import Attachment

    return Attachment.objects.create(
        company=company if company is not None else getattr(
            cible, 'company', None),
        content_type=ContentType.objects.get_for_model(cible.__class__),
        object_id=cible.pk,
        file_key=cle_objet,
        filename=nom,
        size=taille,
        mime='application/pdf',
        uploaded_by=user,
    )
