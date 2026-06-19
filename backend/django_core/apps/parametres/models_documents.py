"""Modèles de documents éditables — D2 / N60 / N67 / N26 / N59.

Une couche de RÉGLAGES par société pour les portions de TEXTE du devis premium
(en-têtes/pieds, mentions légales, conditions générales, validité, garanties,
libellé du tampon d'acceptation). Chaque champ est NULL/vide par défaut : tant
qu'il n'est pas renseigné, le moteur premium retombe sur le LITTÉRAL historique
codé en dur (``DEFAULT_DOC_TEXTS``), donc le PDF reste OCTET-POUR-OCTET identique
au devis d'aujourd'hui. C'est une couche purement éditoriale : elle ne touche ni
aux statuts du devis (brouillon/envoyé/accepté/refusé/expiré), ni au moteur de
prix, ni à l'entonnoir ``STAGES.py``.

``company`` est posée CÔTÉ SERVEUR (jamais lue du corps d'une requête). Un seul
enregistrement par société (singleton, comme ``CompanyProfile``). Le champ
``version`` versionne les textes : il s'incrémente à chaque sauvegarde modifiée
(N67) pour tracer quelle révision a servi à un envoi.

``app_label`` explicite : ce module n'est pas importé par ``models.py`` (gardé
séparé pour l'indépendance des lanes) ; il est chargé via ``apps.py`` ready().
La table reste ``parametres_documenttemplates`` (additif, une seule migration).
"""
from django.db import models


# Les CLÉS éditables connues, alignées sur ``DEFAULT_DOC_TEXTS`` du moteur.
# Toute autre clé du payload est ignorée côté serveur (pas de texte arbitraire
# injecté dans le PDF). Le moteur fournit le DÉFAUT de chaque clé.
DEVIS_TEXT_KEYS = (
    "validite_badge_p1",
    "validite_onepage",
    "cgv_titre",
    "cgv_bullets",
    "garantie_titre",
    "garantie_detail",
    "garantie_perf_label",
    "bpa_titre",
    "bpa_mention",
    "acceptance_stamp",
)


class DocumentTemplates(models.Model):
    """Textes éditables du devis premium, par société (singleton).

    Champs texte VIDES par défaut → repli moteur sur le littéral historique.
    ``cgv_bullets`` est une liste (JSON) ; vide/NULL → puces historiques.
    """

    company = models.OneToOneField(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='document_templates',
    )

    # ── D2 / N60 — validité de l'offre (deux emplacements distincts) ──
    validite_badge_p1 = models.CharField(max_length=120, blank=True, default='')
    validite_onepage = models.CharField(max_length=120, blank=True, default='')

    # ── D2 / N60 — conditions générales du devis (titre + puces) ──
    cgv_titre = models.CharField(max_length=120, blank=True, default='')
    # Liste de puces ; chaque élément peut porter {acompte}/{materiel}/{solde}/
    # {tva_note} substitués par le moteur. NULL/[] → puces historiques.
    cgv_bullets = models.JSONField(null=True, blank=True)

    # ── N67 — garanties (titre, détail, libellé de performance) ──
    garantie_titre = models.CharField(max_length=160, blank=True, default='')
    garantie_detail = models.TextField(blank=True, default='')
    garantie_perf_label = models.CharField(
        max_length=120, blank=True, default='')

    # ── D2 / N60 — bloc « Bon pour accord » (titre + mention manuscrite) ──
    bpa_titre = models.CharField(max_length=120, blank=True, default='')
    bpa_mention = models.TextField(blank=True, default='')

    # ── N26 — libellé du tampon d'acceptation (gabarit {date}/{nom}) ──
    # Le tampon lui-même n'apparaît QUE lorsque le devis est accepté (nom + date
    # posés). Vide ici → le moteur applique le libellé par défaut.
    acceptance_stamp = models.CharField(max_length=160, blank=True, default='')

    # ── N67 — versionnement des textes (incrémenté à chaque modification) ──
    version = models.PositiveIntegerField(default=1)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'parametres'
        verbose_name = 'Modèle de documents'
        verbose_name_plural = 'Modèles de documents'

    def __str__(self):
        return f'Modèles de documents (v{self.version})'

    @classmethod
    def get(cls, company=None):
        """Retourne (ou crée) l'enregistrement pour une société donnée.

        Sans société, retombe sur l'instance pk=1 (rétro-compat, comme
        ``CompanyProfile.get``)."""
        if company is not None:
            obj, _ = cls.objects.get_or_create(company=company)
            return obj
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def as_doc_texts(self):
        """Dict {clé: valeur} des SURCHARGES non vides (pour le builder).

        Une clé absente = pas de surcharge → le moteur applique son défaut
        (littéral historique). Donc tant que rien n'est édité, ce dict est vide
        et le PDF reste byte-identique.
        """
        out = {}
        for key in DEVIS_TEXT_KEYS:
            val = getattr(self, key, None)
            if key == 'cgv_bullets':
                # Liste non vide seulement (None/[] → défaut moteur).
                if isinstance(val, list) and val:
                    out[key] = [str(x) for x in val]
                continue
            if val:  # chaîne non vide uniquement
                out[key] = val
        return out
