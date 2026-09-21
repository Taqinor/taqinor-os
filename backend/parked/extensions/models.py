"""NTEXT13 — registre de PACKAGES d'extension (marketplace interne).

Un ``ExtensionPackage`` est un GABARIT décrivant ce qu'une extension pose sur
un tenant (objets/champs personnalisés, règles d'automatisation, rapports,
gabarits de document) — décrit en JSON dans ``manifest``, jamais matérialisé
ici : la MATÉRIALISATION réelle (créer les objets dans une société donnée) et
l'installation/désinstallation par tenant sont une brique séparée (NTEXT14,
non construite dans ce lot).

Le CATALOGUE est un registre GLOBAL, partagé, en lecture seule — le gabarit
que tout tenant peut parcourir avant de l'installer. Ce n'est PAS de la donnée
métier scopée société (comme une table de référence système), donc il ne porte
volontairement aucune FK ``company`` : l'installation/matérialisation PAR tenant
(qui, elle, sera scopée société) est une brique séparée (NTEXT14, non construite
ici).
"""
from django.db import models

from core.models import TenantModel


class ExtensionPackage(models.Model):
    code = models.SlugField(max_length=60, unique=True)
    nom = models.CharField(max_length=150)
    version = models.CharField(max_length=20, default='1.0.0')
    description = models.TextField(blank=True, default='')
    categorie = models.CharField(max_length=60, blank=True, default='')
    # Manifest JSON décrivant ce que le package pose (structure documentée,
    # jamais exécutée ici) : clés attendues 'custom_object_defs' /
    # 'automation_rules' / 'rapport_definitions' / 'branded_templates', chacune
    # une liste de dicts décrivant les définitions à créer lors d'une future
    # installation (NTEXT14).
    manifest = models.JSONField(default=dict, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nom']
        verbose_name = "Package d'extension"
        verbose_name_plural = "Packages d'extension"

    def __str__(self):
        return f'{self.code}@{self.version}'


class ExtensionInstall(TenantModel):
    """NTEXT14 — INSTALLATION d'un package sur UNE société (par tenant).

    Le catalogue (``ExtensionPackage``) est un gabarit global ; l'installation
    est la trace, SCOPÉE SOCIÉTÉ, de la matérialisation de ce gabarit chez un
    tenant : quelle version a été posée, dans quel état, et surtout QUELS
    OBJETS l'installation a créés (``objets_crees``).

    ``objets_crees`` est une liste de RÉFÉRENCES ``'app_label.model:pk'`` —
    UNIQUEMENT les objets que CETTE installation a réellement créés (jamais un
    objet qui préexistait). C'est ce qui rend la désinstallation sûre : elle
    retire exactement ce que l'installation a posé, JAMAIS les données que
    l'utilisateur a saisies ensuite dans ces objets ni un objet homonyme qu'il
    avait déjà.

    Idempotence : ``unique_together (company, package)`` — ré-installer reprend
    la même ligne, et les matérialiseurs travaillent en ``get_or_create``, donc
    rien n'est dupliqué.
    """

    class Statut(models.TextChoices):
        INSTALLE = 'installe', 'Installé'
        DESINSTALLE = 'desinstalle', 'Désinstallé'
        ERREUR = 'erreur', 'Erreur'

    package = models.ForeignKey(
        ExtensionPackage, on_delete=models.PROTECT, related_name='installs',
        verbose_name='Package')
    version = models.CharField(
        'Version installée', max_length=20, blank=True, default='')
    statut = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.INSTALLE)
    installe_le = models.DateTimeField(
        'Installé le', null=True, blank=True)
    objets_crees = models.JSONField(
        "Objets posés", default=list, blank=True,
        help_text="Références 'app.model:pk' créées PAR l'installation.")

    class Meta:
        verbose_name = "Installation d'extension"
        verbose_name_plural = "Installations d'extension"
        ordering = ['-created_at', '-id']
        unique_together = [('company', 'package')]
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='ext_install_co_statut_idx'),
        ]

    def __str__(self):
        return f'{self.package_id}@{self.company_id} ({self.statut})'
