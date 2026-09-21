"""Sélecteurs LECTURE SEULE de conformité fiscale marocaine (NTMAR16/28/29/30)."""
from datetime import timedelta
from decimal import Decimal

from django.db import models
from django.utils import timezone

from .models import (
    AttestationTenant, BeneficiaireEffectif, EcheanceFiscale, ObligationFiscale,
)

# NTMAR30 — seuil de complétude usuel de la déclaration UBO (25 % de détention
# cumulée couverte, seuil informatif — pas une règle légale figée).
SEUIL_COMPLETUDE_UBO_PCT = Decimal('25.00')


def tableau_conformite(company):
    """NTMAR16 — statut par obligation (à jour / échéance proche / en retard)
    + dernière déclaration liée. Basé sur l'échéance la plus récente
    (passée) et la plus proche (future) de chaque obligation active."""
    today = timezone.localdate()
    lignes = []
    obligations = ObligationFiscale.objects.filter(company=company, actif=True)
    for obligation in obligations:
        echeances = obligation.echeances.filter(company=company)
        derniere = echeances.filter(
            statut__in=[EcheanceFiscale.Statut.DEPOSEE, EcheanceFiscale.Statut.PAYEE]
        ).order_by('-periode_fin').first()
        prochaine = echeances.filter(
            statut=EcheanceFiscale.Statut.A_PREPARER
        ).order_by('date_limite').first()

        if prochaine is None:
            statut = 'a_jour' if derniere is not None else 'aucune_echeance'
        elif prochaine.date_limite < today:
            statut = 'en_retard'
        elif prochaine.date_limite <= today + timedelta(days=15):
            statut = 'echeance_proche'
        else:
            statut = 'a_jour'

        lignes.append({
            'obligation_id': obligation.id,
            'type_obligation': obligation.type_obligation,
            'libelle': obligation.libelle or obligation.get_type_obligation_display(),
            'statut': statut,
            'prochaine_echeance': prochaine.date_limite if prochaine else None,
            'derniere_declaration': {
                'type': derniere.declaration_type,
                'id': derniere.declaration_id,
                'periode_fin': derniere.periode_fin,
            } if derniere else None,
        })
    return lignes


def attestations_expirantes(company, *, within=30, today=None):
    """NTMAR28 — attestations expirant sous ``within`` jours (défaut 30)."""
    today = today or timezone.localdate()
    seuil = today + timedelta(days=within)
    return (AttestationTenant.objects
            .filter(company=company, date_expiration__isnull=False,
                    date_expiration__gte=today, date_expiration__lte=seuil)
            .order_by('date_expiration'))


def pieces_reutilisables_attestations(company, *, today=None):
    """NTMAR29 — attestations VALIDES (non expirées) réutilisables comme
    pièces administratives dans un dossier de soumission. Renvoie
    ``{type_attestation: {numero, date_expiration, fichier_key}}`` — le
    pré-remplissage du dossier lui-même vit dans ``apps.ao`` (hors périmètre
    de ce lot) : cette fonction n'est que la SOURCE réutilisable exposée."""
    today = today or timezone.localdate()
    qs = (AttestationTenant.objects
          .filter(company=company)
          .filter(models.Q(date_expiration__isnull=True)
                  | models.Q(date_expiration__gte=today))
          .order_by('type_attestation', '-date_emission'))
    resultat = {}
    for attestation in qs:
        if attestation.type_attestation in resultat:
            continue  # la plus récente valide déjà retenue (ordre ci-dessus)
        resultat[attestation.type_attestation] = {
            'numero': attestation.numero,
            'date_expiration': attestation.date_expiration,
            'fichier_key': attestation.fichier_key,
        }
    return resultat


def registre_ubo(company):
    """NTMAR30 — registre des bénéficiaires effectifs + alerte de
    complétude (Σ détention déclarée < seuil)."""
    qs = (BeneficiaireEffectif.objects.filter(company=company)
          .order_by('-pourcentage_detention', 'nom'))
    total = sum((ubo.pourcentage_detention for ubo in qs), Decimal('0'))
    return {
        'beneficiaires': list(qs),
        'total_pourcentage': total,
        'complet': total >= SEUIL_COMPLETUDE_UBO_PCT,
    }
