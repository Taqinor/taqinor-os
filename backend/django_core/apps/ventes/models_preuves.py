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

    #: ADEV96 — v2 + les chiffres de l'étude C&I que la page et le PDF montrent
    #: (``domain.modifiabilite.figures_etude_scellees`` de la ``synthese_ci``).
    CONTENT_HASH_V3 = 3
    #: La version du payload dont sont scellées les NOUVELLES signatures
    #: (``DevisSignature.compute_content_hash`` ; v1 = QJ10, v2 = QJR144).
    CONTENT_HASH_VERSION = CONTENT_HASH_V3

    signataire_email = models.EmailField(
        max_length=254, blank=True, default='',
        verbose_name='E-mail du signataire (entreprise)')
    pouvoir_engager = models.BooleanField(
        default=False,
        verbose_name="Le signataire atteste du pouvoir d'engager la société")
    # ADEV96 — SHA-256 des OCTETS du PDF signé figé (``signed_pdf_key``), posé
    # une fois par ``cycle_vie._store_signed_pdf`` : le certificat dit quel
    # fichier exact a été remis. Vide sur les signatures antérieures.
    signed_pdf_sha256 = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='Empreinte SHA-256 du PDF signé')

    class Meta:
        abstract = True

    @classmethod
    def _suffixe_sceau_etude(cls, devis, version):
        """ADEV96 — la part ÉTUDE du payload v3 (``''`` avant v3 : les
        empreintes v1/v2 déjà posées se reproduisent à l'octet). Hors C&I, la
        part vaut ``etude=null`` sans aucune requête (le mode suffit)."""
        if (version or cls.CONTENT_HASH_VERSION) < cls.CONTENT_HASH_V3:
            return ''
        import json
        from apps.ventes.domain.modifiabilite import (
            figures_etude_scellees, synthese_ci_lue,
        )
        figures = figures_etude_scellees(synthese_ci_lue(devis))
        return (f"|v{cls.CONTENT_HASH_V3}|etude="
                f"{json.dumps(figures, sort_keys=True, ensure_ascii=False, default=str)}")


class SuiviLienPublic(models.Model):
    """ADEV98 — le signal d'ouverture FIABLE du lien public (``ShareLink``).

    Le rendu serveur de la page (``X-Proposition-Rendu: ssr``) n'est plus
    compté comme une lecture humaine : un scanner de messagerie (SafeLinks,
    Proofpoint, Mimecast…) qui pré-charge le lien déclenchait compteur, note
    et notification. Il est seulement daté ici, en APERÇU, sans chatter ni
    notification ; la lecture humaine vient du beacon de la page
    (``proposal/<token>/vu/``) après quelques secondes de visibilité."""

    apercu_le = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Dernier aperçu serveur (sans lecture humaine)')

    class Meta:
        abstract = True
