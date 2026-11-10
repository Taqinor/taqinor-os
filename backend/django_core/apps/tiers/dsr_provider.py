"""ASOC67 — DSR des Tiers, export seul ; fondation : SES champs, jamais le CRM."""
import re


def _cle_tel(valeur):
    chiffres = re.sub(r'\D', '', str(valeur or ''))
    return chiffres[-9:] if len(chiffres) >= 9 else ''


def export_tiers(company, subject_identifier):
    from .models import Tiers
    ident = (subject_identifier or '').strip()
    cle = '' if '@' in ident else _cle_tel(ident)
    qs = Tiers.objects.filter(company=company).order_by('pk')
    if not cle:  # e-mail (ou identifiant vide → aucun tiers)
        trouves = list(qs.filter(email__iexact=ident)) if '@' in ident else []
    else:  # téléphone stocké libre (espaces, +212) : rapprochement en Python
        trouves = [t for t in qs.exclude(telephone='', whatsapp='')
                   if cle in (_cle_tel(t.telephone), _cle_tel(t.whatsapp))]
    return {'tiers': [{'id': t.pk, 'nom': t.nom, 'prenom': t.prenom, 'email': t.email,
                       'telephone': t.telephone, 'adresse': t.adresse, 'ville': t.ville}
                      for t in trouves]}


def register():
    from core import dsr
    dsr.register_dsr_provider('tiers', export=export_tiers)
