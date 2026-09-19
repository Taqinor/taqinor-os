"""Générateurs et parseurs EDI de l'API publique (NTAPI33/34/35).

Chaque format vit dans son propre module (``x12.py`` pour ANSI X12 810/850).
Tous sont GATED : sans le drapeau ``PUBLICAPI_EDI_ACTIF``, les points d'entrée
sont des NO-OP propres qui renvoient ``None`` — jamais une exception, jamais un
fichier écrit, jamais une transmission. Aucun module de ce paquet n'ouvre de
connexion sortante : ils produisent ou lisent du TEXTE, l'acheminement (AS2,
SFTP, VAN) reste une étape fondateur.
"""
