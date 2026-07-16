"""Modèles du registre des assurances & sinistres d'entreprise (Groupe NTASS).

Couvre les polices d'ENTREPRISE (RC pro, décennale, multirisque, cyber,
homme-clé) — distinctes des polices VÉHICULE qui restent dans
``flotte.AssuranceVehicule``/``flotte.Sinistre`` (jamais dupliquées ici,
référencées en string-FK via ``ActifCouvert``/``flotte_sinistre_id``) — et des
cautions bancaires marché (``compta.CautionBancaire``/``RetenueGarantie``).

Frontières (voir docs/plans/PLAN_FINANCE.md Groupe NTASS) :
  - ``flotte`` garde ses polices/sinistres véhicule ;
  - le futur NTGRC gardera le registre de risques ERM (string-FK ``risque_ref``) ;
  - ``qhse`` garde les accidents du travail ;
  - le futur NTJUR prendra le relais quand un sinistre devient contentieux
    (string-FK ``dossier_contentieux_ref``) ;
  - le futur NTPRO sera la cible string-FK pour les sites/biens immobiliers.
"""
from django.db import models


# ── NTASS1 — Registre des assureurs & courtiers ────────────────────────────

class Assureur(models.Model):
    """Compagnie d'assurance (NTASS1). Registre scopé société."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='assureurs', verbose_name='Société')
    raison_sociale = models.CharField(max_length=200, verbose_name='Raison sociale')
    ice = models.CharField(max_length=30, blank=True, default='', verbose_name='ICE')
    telephone = models.CharField(max_length=30, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    adresse = models.TextField(blank=True, default='')
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ['raison_sociale']
        verbose_name = 'Assureur'
        verbose_name_plural = 'Assureurs'

    def __str__(self):
        return self.raison_sociale


class Courtier(models.Model):
    """Courtier / intermédiaire d'assurance (NTASS1), distinct de l'assureur.

    Registre scopé société. Un courtier n'émet pas les polices lui-même (c'est
    l'assureur) mais intermédie ; ``numero_agrement`` est son numéro d'agrément
    professionnel (ACAPS au Maroc)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='courtiers', verbose_name='Société')
    raison_sociale = models.CharField(max_length=200, verbose_name='Raison sociale')
    numero_agrement = models.CharField(
        max_length=60, blank=True, default='', verbose_name="Numéro d'agrément")
    telephone = models.CharField(max_length=30, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ['raison_sociale']
        verbose_name = 'Courtier'
        verbose_name_plural = 'Courtiers'

    def __str__(self):
        return self.raison_sociale
