"""NTCRM8 — Modèle Contact multi-rôles par client (organigramme d'achat).

Additif : ``crm.Client`` conserve ses champs contact historiques (nom/email/
téléphone…) pour compat — ils restent le contact PRINCIPAL implicite tant
qu'aucun ``ContactClient`` n'existe pour ce client. ``client`` est une FK
STRING vers ``crm.Client`` (jamais un import de ``apps.crm.models`` ici,
cette app reste découplée — cf. CLAUDE.md règle de frontière cross-app)."""
from django.core.exceptions import ValidationError
from django.db import models, transaction

from core.models import TenantModel


class ContactClient(TenantModel):
    """ARC1 — hérite de ``core.models.TenantModel``; ``company`` redéclaré à
    l'identique (related_name historique)."""

    class RoleAchat(models.TextChoices):
        DECIDEUR = 'decideur', 'Décideur'
        INFLUENCEUR = 'influenceur', 'Influenceur'
        UTILISATEUR = 'utilisateur', 'Utilisateur'
        GATEKEEPER = 'gatekeeper', 'Gatekeeper'
        SPONSOR = 'sponsor', 'Sponsor'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='contacts_client')
    client = models.ForeignKey(
        'crm.Client', on_delete=models.CASCADE,  # on_delete: contact sans objet si client supprimé
        related_name='contacts_multi_roles')
    nom = models.CharField(max_length=255)
    prenom = models.CharField(max_length=255, blank=True, default='')
    poste = models.CharField(max_length=150, blank=True, default='')
    email = models.EmailField(blank=True, null=True)
    telephone = models.CharField(max_length=50, blank=True, null=True)
    whatsapp = models.CharField(max_length=50, blank=True, null=True)
    role_achat = models.CharField(
        max_length=15, choices=RoleAchat.choices, default=RoleAchat.AUTRE,
        verbose_name="Rôle d'achat")
    contact_principal = models.BooleanField(
        default=False, verbose_name='Contact principal')
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-contact_principal', 'nom']
        verbose_name = 'Contact client'
        verbose_name_plural = 'Contacts client'
        constraints = [
            # AUD608 — l'unicité du contact PRINCIPAL était vérifiée en Python
            # (`clean()`), donc uniquement lisible : deux écritures simultanées
            # passaient toutes les deux le contrôle et le client se retrouvait
            # avec DEUX contacts principaux — c'est-à-dire deux destinataires
            # « officiels » pour un devis. La base la refuse désormais, ce que
            # `clean()` ne pouvait pas garantir seul.
            models.UniqueConstraint(
                fields=['client'],
                condition=models.Q(contact_principal=True),
                name='uniq_contact_principal_par_client'),
        ]

    def __str__(self):
        return f'{self.nom} {self.prenom} ({self.client_id})'.strip()

    def clean(self):
        super().clean()
        if self.contact_principal:
            qs = ContactClient.objects.filter(
                client_id=self.client_id, contact_principal=True)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({
                    'contact_principal':
                        'Un seul contact principal est autorisé par client '
                        '— un autre contact est déjà marqué principal.',
                })

    def save(self, *args, **kwargs):
        # Toujours revalider « un seul principal par client » à l'écriture,
        # y compris pour les créations/mises à jour ORM directes (management
        # commands, fixtures) qui ne passent pas par le serializer.
        #
        # AUD608 — la revalidation vit désormais DANS une transaction, les
        # contacts principaux du client VERROUILLÉS : sans cela, `clean()` et
        # `save()` étaient deux instants distincts et deux écritures
        # concurrentes se croisaient entre les deux. Le message français reste
        # rendu par `clean()` (l'API garde son 400 lisible) ; la contrainte
        # d'unicité partielle de `Meta` est le filet de dernier recours, qui
        # lève une IntegrityError si un chemin oubliait ce `save()`.
        with transaction.atomic():
            if self.contact_principal and self.client_id:
                list(ContactClient.objects.select_for_update().filter(
                    client_id=self.client_id, contact_principal=True)
                    .values_list('pk', flat=True))
            self.clean()
            super().save(*args, **kwargs)
