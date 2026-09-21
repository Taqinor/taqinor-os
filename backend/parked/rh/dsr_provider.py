"""XPLT23 — fournisseur DSR (loi 09-08) des Ressources Humaines.

Enregistré auprès du registre générique ``core.dsr`` (frontière déjà en place :
``core`` orchestre sans importer la RH ; la RH lit ses PROPRES modèles).

* **export** — renvoie le dossier employé de la personne concernée, identifiée
  par email (pro ou perso) OU téléphone ;
* **effacement** — REFUSÉ avec un motif légal : les obligations sociales et de
  paie imposent la conservation des dossiers employés (le refus est renvoyé
  dans le résultat, jamais une suppression silencieuse).

``subject_identifier`` = un email ou un téléphone. Tout est borné par
``company`` (multi-tenant).
"""
from __future__ import annotations

PROVIDER_NAME = 'rh'

MOTIF_REFUS = (
    "Effacement refusé : les dossiers employés sont conservés au titre des "
    "obligations sociales, fiscales et de paie (Code du travail, CNSS/AMO, "
    "administration fiscale). La donnée ne peut être effacée avant l'échéance "
    "des durées légales de conservation."
)


def _normalize(value):
    return (value or '').strip().lower()


def _matcher(company, subject_identifier):
    """Dossiers employés correspondant à ``subject_identifier`` (email/tel)."""
    from django.db.models import Q

    from .models import DossierEmploye

    ident = _normalize(subject_identifier)
    if not ident:
        return DossierEmploye.objects.none()

    # Téléphone : on ne garde que les chiffres pour un match tolérant.
    digits = ''.join(c for c in ident if c.isdigit())

    qs = DossierEmploye.objects.filter(company=company)
    cond = Q(email__iexact=ident) | Q(email_perso__iexact=ident)
    matches = list(qs.filter(cond))
    if digits:
        for d in qs:
            tel = ''.join(c for c in (d.telephone or '') if c.isdigit())
            telp = ''.join(
                c for c in (d.telephone_perso or '') if c.isdigit())
            if digits and digits in (tel, telp) and d not in matches:
                matches.append(d)
    return matches


def export_rh(company, subject_identifier):
    """Export du dossier employé de la personne concernée."""
    dossiers = _matcher(company, subject_identifier)
    return {
        'dossiers_employes': [
            {
                'id': d.pk,
                'matricule': d.matricule,
                'nom': d.nom,
                'prenom': d.prenom,
                'email': d.email,
                'email_perso': d.email_perso,
                'telephone': d.telephone,
                'telephone_perso': d.telephone_perso,
            }
            for d in dossiers
        ],
    }


def erase_rh(company, subject_identifier):
    """Effacement RH REFUSÉ (motif légal). Renvoie un compte-rendu, pas 0.

    Ne modifie AUCUNE donnée : renvoie un dict décrivant le refus et les
    dossiers concernés (comptés). ``core.dsr.effacer`` agrège ce résultat tel
    quel dans le compte-rendu de la demande.
    """
    dossiers = _matcher(company, subject_identifier)
    return {
        'refuse': True,
        'motif': MOTIF_REFUS,
        'dossiers_concernes': len(dossiers),
    }


def register():
    """Enregistre le fournisseur DSR RH (idempotent). Appelé en ready()."""
    from core import dsr
    dsr.register_dsr_provider(
        PROVIDER_NAME, export=export_rh, erase=erase_rh)
