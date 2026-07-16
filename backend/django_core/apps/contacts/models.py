"""NTCRM8 — Modèle Contact multi-rôles par client (organigramme d'achat).

Additif : ``crm.Client`` conserve ses champs contact historiques (nom/email/
téléphone…) pour compat — ils restent le contact PRINCIPAL implicite tant
qu'aucun ``ContactClient`` n'existe pour ce client. ``client`` est une FK
STRING vers ``crm.Client`` (jamais un import de ``apps.crm.models`` ici,
cette app reste découplée — cf. CLAUDE.md règle de frontière cross-app)."""
from django.core.exceptions import ValidationError
from django.db import models


class ContactClient(models.Model):
    class RoleAchat(models.TextChoices):
        DECIDEUR = 'decideur', 'Décideur'
        INFLUENCEUR = 'influenceur', 'Influenceur'
        UTILISATEUR = 'utilisateur', 'Utilisateur'
        GATEKEEPER = 'gatekeeper', 'Gatekeeper'
        SPONSOR = 'sponsor', 'Sponsor'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='contacts_client')
    client = models.ForeignKey(
        'crm.Client', on_delete=models.CASCADE, related_name='contacts_multi_roles')
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
        self.clean()
        super().save(*args, **kwargs)
