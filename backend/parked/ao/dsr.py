"""AOF168 — fournisseur DSR (loi 09-08) du module Appels d'offres.

Enregistré auprès du registre générique ``core.dsr``, sur le patron de
``apps/crm/dsr_provider.py`` : ``core`` orchestre sans importer ``ao``, et
``ao`` ne lit que SES propres modèles.

Où vivent les données personnelles d'un appel d'offres
------------------------------------------------------
Un dossier de marché public est majoritairement de la donnée d'ENTREPRISE
(acheteur, objet, montants). Les trois seules poches de données PERSONNELLES
qu'``apps.ao`` possède en propre sont :

* ``ReleveAO.participants`` — les personnes présentes à la visite de relevé,
  une par ligne ;
* ``SerieQuestions.destinataire`` — l'interlocuteur d'une série de questions ;
* ``AppelOffre.lead_id`` — un renvoi OPAQUE vers un lead CRM. Le lead lui-même
  appartient au fournisseur DSR ``crm`` : le dupliquer ici produirait deux
  effacements concurrents pour la même personne. On se contente donc de
  SIGNALER le rattachement dans l'export.

Effacement = ANONYMISATION, jamais suppression
----------------------------------------------
Un appel d'offres déposé est une pièce OPPOSABLE : la date d'une visite
contradictoire, le nombre de participants et l'existence d'une série de
questions font partie de ce qui rend un plan défendable. On vide donc les
IDENTITÉS et on garde les FAITS. Rien de géométrique, rien de chiffré, aucun
montant n'est touché — un DSR n'est pas un droit de réécrire une offre.
"""
from __future__ import annotations

PROVIDER_NAME = 'ao'


def _normaliser(valeur):
    return (valeur or '').strip().casefold()


def _correspond(valeur, sujet):
    """La ligne ``valeur`` désigne-t-elle ``sujet`` ?

    Comparaison sur la chaîne NORMALISÉE (espaces et casse), en égalité OU en
    inclusion : un ``destinataire`` réel s'écrit « M. Alami <a@x.ma> » aussi
    souvent que « a@x.ma ». Un sujet vide ne correspond à RIEN — un filtre
    absent ne doit jamais se muer en absence de filtre.
    """
    sujet = _normaliser(sujet)
    if not sujet:
        return False
    valeur = _normaliser(valeur)
    return bool(valeur) and (valeur == sujet or sujet in valeur)


def _releves_concernes(company, subject_identifier):
    from .models import ReleveAO

    trouves = []
    for releve in ReleveAO.objects.filter(company=company).select_related(
            'appel_offre'):
        lignes = [ligne for ligne in (releve.participants or '').splitlines()
                  if _correspond(ligne, subject_identifier)]
        if lignes:
            trouves.append((releve, lignes))
    return trouves


def _series_concernees(company, subject_identifier):
    from .models import SerieQuestions

    return [
        serie for serie in SerieQuestions.objects.filter(
            company=company).select_related('appel_offre')
        if _correspond(serie.destinataire, subject_identifier)
    ]


def export_ao(company, subject_identifier):
    """Export des données AO de la personne concernée (lecture seule)."""
    releves = _releves_concernes(company, subject_identifier)
    series = _series_concernees(company, subject_identifier)
    appels_lies = sorted({
        releve.appel_offre.reference for releve, _ in releves
    } | {serie.appel_offre.reference for serie in series})
    return {
        'participations_releve': [
            {
                'releve_id': releve.pk,
                'appel_offre': releve.appel_offre.reference,
                'date_visite': releve.date_visite.isoformat()
                if releve.date_visite else None,
                'contradictoire': releve.contradictoire,
                'lignes_participants': lignes,
            }
            for releve, lignes in releves
        ],
        'destinataire_de_series': [
            {
                'serie_id': serie.pk,
                'appel_offre': serie.appel_offre.reference,
                'numero': serie.numero,
                'canal': serie.canal,
                'destinataire': serie.destinataire,
                'date_envoi': serie.date_envoi.isoformat()
                if serie.date_envoi else None,
            }
            for serie in series
        ],
        'appels_offres_lies': appels_lies,
        # Le lead CRM appartient au fournisseur ``crm`` : on ne le duplique
        # pas ici, on signale seulement le rattachement.
        'note_lead': (
            "Les données du lead CRM éventuellement rattaché à ces appels "
            "d'offres sont servies par le fournisseur DSR « crm » — elles ne "
            'sont pas dupliquées ici.'
        ),
    }


def erase_ao(company, subject_identifier):
    """ANONYMISE les identités AO de la personne. Renvoie le compte traité.

    Ne supprime AUCUNE ligne : le relevé garde sa date et son caractère
    contradictoire, la série garde son numéro, son canal et ses questions. Ce
    sont les FAITS qui rendent un plan opposable ; seule l'IDENTITÉ part.
    """
    releves = _releves_concernes(company, subject_identifier)
    series = _series_concernees(company, subject_identifier)
    compte = 0

    for releve, lignes in releves:
        cibles = {_normaliser(ligne) for ligne in lignes}
        conservees = [
            'Anonymisé' if _normaliser(ligne) in cibles else ligne
            for ligne in (releve.participants or '').splitlines()
        ]
        releve.participants = '\n'.join(conservees)
        releve.save(update_fields=['participants'])
        compte += 1

    for serie in series:
        serie.destinataire = 'Anonymisé'
        serie.save(update_fields=['destinataire'])
        compte += 1

    return compte


def register():
    """Enregistre le fournisseur DSR AO (idempotent). Appelé en ``ready()``."""
    from core import dsr

    dsr.register_dsr_provider(PROVIDER_NAME, export=export_ao, erase=erase_ao)
