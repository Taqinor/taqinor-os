"""ARC24 — Référentiel des conditions de paiement, par société.

Constat : trois représentations sans lien —
  - ``parametres.CompanyProfile.payment_terms`` (JSON, échéancier client) ;
  - ``ventes.Facture.conditions_paiement`` (TextField libre, mention N11) ;
  - ``stock.Fournisseur.delai_paiement_jours`` / ``fin_de_mois`` /
    ``escompte_pct`` (XPUR6).

Ce modèle DÉCLARE, par société, des conditions de paiement nommées (libellé FR +
délai jours + fin de mois + escompte %). Il devient la SOURCE du libellé par
défaut d'une facture (le TextField libre reste surchargeable) et le MIROIR des
trois champs numériques d'un fournisseur — les champs existants sont CONSERVÉS
(additif). Sans condition référencée, tout se comporte comme avant.

Gardé dans un fichier dédié (indépendance de lane) ; enregistré via
``apps.ready()``.
"""
from django.db import models

from core.models import TenantModel


class ConditionPaiement(TenantModel):
    """Une condition de paiement nommée par société (délai + escompte)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='conditions_paiement_referentiel')
    libelle = models.CharField(
        max_length=120,
        help_text='Libellé FR (ex. « 30 jours fin de mois », « Comptant »).')
    # Délai en jours (0 = comptant, comportement historique). ``fin_de_mois``
    # arrondit l'échéance à la fin du mois calendaire suivant l'ajout du délai.
    delai_jours = models.PositiveIntegerField(default=0)
    fin_de_mois = models.BooleanField(default=False)
    # Escompte paiement anticipé (type 2/10 net 30). 0 = pas d'escompte.
    escompte_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=0)
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Condition de paiement'
        verbose_name_plural = 'Conditions de paiement'
        ordering = ['delai_jours', 'libelle']
        # Un triplet (délai, fin de mois, escompte) unique par société : garantit
        # l'idempotence du backfill fournisseur (une entrée par condition
        # distincte, jamais de doublon).
        unique_together = [
            ('company', 'delai_jours', 'fin_de_mois', 'escompte_pct'),
        ]
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='param_condpaie_idx'),
        ]

    def __str__(self):
        return f'{self.company_id}:{self.libelle}'

    @staticmethod
    def libelle_pour(delai_jours, fin_de_mois, escompte_pct):
        """Libellé FR canonique pour un triplet de conditions (backfill/défaut)."""
        from decimal import Decimal
        if delai_jours == 0 and not fin_de_mois:
            base = 'Comptant'
        else:
            base = f'{delai_jours} jours'
            if fin_de_mois:
                base += ' fin de mois'
        try:
            esc = Decimal(str(escompte_pct or 0))
        except Exception:
            esc = Decimal('0')
        if esc > 0:
            base += f' — escompte {esc.normalize()} %'
        return base

    @classmethod
    def from_triplet(cls, company, delai_jours, fin_de_mois, escompte_pct):
        """Retourne (crée si besoin) la condition référentielle d'un triplet.

        Idempotent : la contrainte d'unicité garantit une seule entrée par
        (société, délai, fin de mois, escompte). Utilisé par le backfill des
        conditions distinctes des fournisseurs."""
        from decimal import Decimal
        try:
            esc = Decimal(str(escompte_pct or 0))
        except Exception:
            esc = Decimal('0')
        obj, _ = cls.objects.get_or_create(
            company=company,
            delai_jours=delai_jours or 0,
            fin_de_mois=bool(fin_de_mois),
            escompte_pct=esc,
            defaults={'libelle': cls.libelle_pour(
                delai_jours or 0, fin_de_mois, esc)})
        return obj
