"""NTGRC1 — fournisseur DSR (loi 09-08 / RGPD) des Achats/Stock.

Enregistré auprès du registre générique ``core.dsr`` (``core`` orchestre sans
importer le Stock ; le Stock lit ses PROPRES modèles). La personne concernée
côté Stock est le CONTACT d'un fournisseur : une personne physique nommée dans
la fiche (``contact_personne``) avec son email et son téléphone.

* **export** — les fiches fournisseur où la personne apparaît (raison sociale,
  contact, email, téléphone). Jamais de prix d'achat ni de marge.
* **effacement** — PSEUDONYMISE le CONTACT (nom de la personne, email,
  téléphone) et CONSERVE la personne morale : raison sociale, identifiants
  légaux (ICE/IF/RC/RIB) et tout l'historique d'achat restent intacts — ce
  sont des données d'entreprise et des pièces comptables, pas des données
  personnelles. Aucune ligne n'est supprimée : les agrégats restent cohérents.

``subject_identifier`` = un email ou un téléphone. Tout est borné par
``company`` (multi-tenant).
"""
from __future__ import annotations

PROVIDER_NAME = 'stock'

ANONYME = 'Contact anonymisé'

MOTIF_CONSERVATION = (
    "La personne morale fournisseur (raison sociale, ICE/IF/RC/RIB) et "
    "l'historique d'achat sont conservés : ce ne sont pas des données "
    "personnelles et ils relèvent d'obligations comptables et fiscales. Seul "
    "le contact physique a été pseudonymisé."
)


def _digits(valeur):
    return ''.join(c for c in (valeur or '') if c.isdigit())


def _matcher(company, subject_identifier):
    """Fiches fournisseur où la personne apparaît (email OU téléphone)."""
    from .models import Fournisseur

    ident = (subject_identifier or '').strip()
    if not ident:
        return Fournisseur.objects.none()

    qs = Fournisseur.objects.filter(company=company)
    if '@' in ident:
        return qs.filter(email__iexact=ident)

    digits = _digits(ident)
    if not digits:
        return Fournisseur.objects.none()
    ids = [
        pk for pk, tel in qs.values_list('id', 'telephone')
        if _digits(tel) == digits
    ]
    return qs.filter(id__in=ids)


def export_stock(company, subject_identifier):
    """Export des fiches fournisseur portant le contact (jamais de prix)."""
    fournisseurs = _matcher(company, subject_identifier)
    return {
        'fournisseurs': [
            {
                'id': f.pk,
                'raison_sociale': f.nom,
                'contact_personne': f.contact_personne,
                'email': f.email,
                'telephone': f.telephone,
            }
            for f in fournisseurs
        ],
    }


def erase_stock(company, subject_identifier):
    """Pseudonymise le CONTACT des fiches fournisseur de la personne.

    Renvoie ``{'pseudonymises', 'motif_conservation'}``. Aucune ligne n'est
    supprimée ; la personne morale et l'historique d'achat sont conservés.
    """
    from apps.grc.services import empreinte_avant, journaliser_destruction

    fournisseurs = _matcher(company, subject_identifier)
    count = 0
    for f in fournisseurs:
        empreinte = empreinte_avant({
            'contact_personne': f.contact_personne,
            'email': f.email,
            'telephone': f.telephone,
        })
        f.contact_personne = ANONYME
        f.email = None
        f.telephone = None
        f.save(update_fields=['contact_personne', 'email', 'telephone'])
        journaliser_destruction(
            company, type_objet='stock_fournisseur', objet_ref=f.pk,
            action='anonymise', demande_droit_ref=subject_identifier,
            motif='Effacement DSR (loi 09-08) — contact fournisseur',
            empreinte=empreinte)
        count += 1

    return {
        'pseudonymises': count,
        'motif_conservation': MOTIF_CONSERVATION,
    }


def register():
    """Enregistre le fournisseur DSR Stock (idempotent). Appelé en ready()."""
    from core import dsr
    dsr.register_dsr_provider(
        PROVIDER_NAME, export=export_stock, erase=erase_stock)
