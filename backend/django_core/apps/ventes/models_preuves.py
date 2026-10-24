"""Champs de PREUVE du lien public (L3 lien, 24/10/2026) — mixins ABSTRAITS.

``DevisSignature`` (``models.py``) hérite de :class:`PreuveSignatureB2B` :
tout ce que l'acceptation en ligne d'un devis commercial / industriel doit
garder en plus du nom tapé — l'e-mail du signataire et son attestation de
pouvoir (ADEV95). Champs ADDITIFS : vides sur toute signature antérieure et
hors C&I (comportement inchangé). Aucun statut nouveau (règle #4).

Module séparé parce que ``models.py`` est un fichier-mur (≥ 2 000 lignes, garde
C20) : les champs vivent ici, la table reste celle de ``DevisSignature``.
"""
from django.db import models


class PreuveSignatureB2B(models.Model):
    """ADEV95 — identité et pouvoir du SIGNATAIRE d'une entreprise.

    * ``signataire_email`` — l'adresse du signataire déclarée à l'acceptation
      (destinataire de la confirmation, ADEV99) ;
    * ``pouvoir_engager`` — le signataire a coché « j'agis en la qualité
      indiquée et j'ai le pouvoir d'engager la société ».
    """

    #: La version du payload dont sont scellées les NOUVELLES signatures
    #: (``DevisSignature.compute_content_hash`` ; v1 = QJ10, v2 = QJR144).
    CONTENT_HASH_VERSION = 2

    signataire_email = models.EmailField(
        max_length=254, blank=True, default='',
        verbose_name='E-mail du signataire (entreprise)')
    pouvoir_engager = models.BooleanField(
        default=False,
        verbose_name="Le signataire atteste du pouvoir d'engager la société")

    class Meta:
        abstract = True
