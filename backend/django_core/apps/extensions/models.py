"""NTEXT13 — registre de PACKAGES d'extension (marketplace interne).

Un ``ExtensionPackage`` est un GABARIT décrivant ce qu'une extension pose sur
un tenant (objets/champs personnalisés, règles d'automatisation, rapports,
gabarits de document) — décrit en JSON dans ``manifest``, jamais matérialisé
ici : la MATÉRIALISATION réelle (créer les objets dans une société donnée) et
l'installation/désinstallation par tenant sont une brique séparée (NTEXT14,
non construite dans ce lot).

Un package du CATALOGUE (``company=None``) est READ-ONLY et jamais lié à une
société — c'est le gabarit partagé que tout tenant peut parcourir avant de
l'installer. ``company`` reste néanmoins un FK nullable (et non un simple
booléen « global ») pour rester cohérent avec le reste de la plateforme et
laisser la porte ouverte à un futur package privé propre à un tenant, sans
migration supplémentaire.
"""
from django.db import models


class ExtensionPackage(models.Model):
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='extension_packages')
    code = models.SlugField(max_length=60)
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
        unique_together = [('company', 'code')]
        verbose_name = "Package d'extension"
        verbose_name_plural = "Packages d'extension"

    def __str__(self):
        return f'{self.code}@{self.version}'
