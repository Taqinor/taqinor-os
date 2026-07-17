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
