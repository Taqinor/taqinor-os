from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.utils.text import slugify


class Company(models.Model):
    nom = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Entreprise"
        verbose_name_plural = "Entreprises"

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.nom)
            self.slug = base or f"company-{Company.objects.count() + 1}"
        super().save(*args, **kwargs)


class CustomUser(AbstractUser):
    ROLE_ADMIN = 'admin'
    ROLE_RESPONSABLE = 'responsable'
    ROLE_NORMAL = 'normal'
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Administrateur'),
        (ROLE_RESPONSABLE, 'Utilisateur Responsable'),
        (ROLE_NORMAL, 'Utilisateur Normal'),
    ]

    # Legacy role field kept for backward compat and migration reference
    role_legacy = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_NORMAL,
    )
    # New FK to custom Role model (null until init_roles runs)
    role = models.ForeignKey(
        'roles.Role',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
    )
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
    )

    @property
    def is_admin_role(self):
        if self.is_superuser:
            return True
        if self.role:
            return 'roles_gerer' in (self.role.permissions or [])
        return self.role_legacy == self.ROLE_ADMIN

    @property
    def is_responsable(self):
        if self.is_superuser:
            return True
        if self.role:
            return True
        return self.role_legacy in (
            self.ROLE_RESPONSABLE, self.ROLE_ADMIN
        )

    def has_erp_permission(self, code):
        """Check if user has a specific ERP permission code."""
        if self.is_superuser:
            return True
        if self.role:
            return code in (self.role.permissions or [])
        return False

    groups = models.ManyToManyField(
        Group,
        verbose_name='groups',
        blank=True,
        related_name="customuser_set",
        related_query_name="customuser",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name='user permissions',
        blank=True,
        related_name="customuser_set",
        related_query_name="customuser",
    )

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

    def __str__(self):
        return self.username
