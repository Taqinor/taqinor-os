"""Services de conformité fiscale marocaine (NTMAR14/15/31/33)."""
import re
from datetime import date, timedelta

from django.utils import timezone

from .models import EcheanceFiscale, ObligationFiscale

# NTMAR14 — seed des obligations standard marocaines (idempotent, additif).
SEED_OBLIGATIONS = [
    (ObligationFiscale.Type.TVA, 'TVA (régime mensuel)',
     ObligationFiscale.Periodicite.MENSUELLE, '20 du mois suivant'),
    (ObligationFiscale.Type.ACOMPTE_IS, 'Acomptes IS',
     ObligationFiscale.Periodicite.TRIMESTRIELLE, 'fin de trimestre'),
    (ObligationFiscale.Type.IS, 'Impôt sur les sociétés (solde)',
     ObligationFiscale.Periodicite.ANNUELLE, '31 mars N+1'),
    (ObligationFiscale.Type.IR, "Impôt sur le revenu (retenue salariale)",
     ObligationFiscale.Periodicite.MENSUELLE, '20 du mois suivant'),
    (ObligationFiscale.Type.TIMBRE, 'Droit de timbre (quittances espèces)',
     ObligationFiscale.Periodicite.MENSUELLE, '20 du mois suivant'),
    (ObligationFiscale.Type.RAS, 'Retenue à la source (honoraires/loyers)',
     ObligationFiscale.Periodicite.MENSUELLE, '20 du mois suivant'),
    (ObligationFiscale.Type.CNSS_REF, 'Cotisations CNSS',
     ObligationFiscale.Periodicite.MENSUELLE, '10 du mois suivant'),
    (ObligationFiscale.Type.TAXE_PRO, 'Taxe professionnelle (patente)',
     ObligationFiscale.Periodicite.ANNUELLE, '31 janvier'),
    (ObligationFiscale.Type.DROIT_ENREGISTREMENT, "Droits d'enregistrement",
     ObligationFiscale.Periodicite.PONCTUELLE, 'à la signature de l\'acte'),
]


def seed_obligations_standard(company):
    """NTMAR14 — seed IDEMPOTENT (additif) des obligations standard
    marocaines pour ``company``. Ne touche jamais une obligation existante
    (ne réécrit pas ``periodicite``/``regle_echeance`` déjà personnalisées)."""
    created = []
    for type_obligation, libelle, periodicite, regle in SEED_OBLIGATIONS:
        obligation, was_created = ObligationFiscale.objects.get_or_create(
            company=company, type_obligation=type_obligation,
            defaults={
                'libelle': libelle, 'periodicite': periodicite,
                'regle_echeance': regle,
            })
        if was_created:
            created.append(obligation)
    return created


def _fin_mois(annee, mois):
    if mois == 12:
        return date(annee, 12, 31)
    return date(annee, mois + 1, 1) - timedelta(days=1)


def _decouper_annee(periodicite, annee):
    """Découpe l'année en périodes selon la périodicité. Une périodicité
    ``ponctuelle`` n'a pas de découpage automatique (saisie manuelle)."""
    if periodicite == ObligationFiscale.Periodicite.MENSUELLE:
        return [(date(annee, m, 1), _fin_mois(annee, m)) for m in range(1, 13)]
    if periodicite == ObligationFiscale.Periodicite.TRIMESTRIELLE:
        return [
            (date(annee, 1, 1), date(annee, 3, 31)),
            (date(annee, 4, 1), date(annee, 6, 30)),
            (date(annee, 7, 1), date(annee, 9, 30)),
            (date(annee, 10, 1), date(annee, 12, 31)),
        ]
    if periodicite == ObligationFiscale.Periodicite.ANNUELLE:
        return [(date(annee, 1, 1), date(annee, 12, 31))]
    return []


_REGLE_MOIS_SUIVANT_RE = re.compile(r'^\s*(\d{1,2})\s+du mois suivant\s*$', re.I)


def _date_limite(obligation, periode_fin):
    """Calcule la date limite selon ``regle_echeance`` (meilleur effort).

    Reconnaît ``« N du mois suivant »`` (le format des obligations seedées) ;
    tout autre libellé retombe sur un délai forfaitaire de 20 jours après la
    fin de période — jamais d'exception bloquante sur un libellé libre."""
    m = _REGLE_MOIS_SUIVANT_RE.match(obligation.regle_echeance or '')
    if m:
        jour = int(m.group(1))
        annee = periode_fin.year + (1 if periode_fin.month == 12 else 0)
        mois = 1 if periode_fin.month == 12 else periode_fin.month + 1
        import calendar
        jour = min(jour, calendar.monthrange(annee, mois)[1])
        return date(annee, mois, jour)
    return periode_fin + timedelta(days=20)


def calendrier(company, annee):
    """NTMAR14 — matérialise (idempotent) les ``EcheanceFiscale`` datées de
    ``annee`` pour toutes les obligations ACTIVES de ``company``. Renvoie la
    liste des échéances (créées ou déjà existantes), triée par date limite."""
    obligations = ObligationFiscale.objects.filter(company=company, actif=True)
    resultats = []
    for obligation in obligations:
        for periode_debut, periode_fin in _decouper_annee(
                obligation.periodicite, annee):
            date_limite = _date_limite(obligation, periode_fin)
            echeance, _created = EcheanceFiscale.objects.get_or_create(
                company=company, obligation=obligation,
                periode_debut=periode_debut, periode_fin=periode_fin,
                defaults={'date_limite': date_limite})
            resultats.append(echeance)
    resultats.sort(key=lambda e: (e.date_limite, e.id))
    return resultats


def envoyer_rappels_fiscaux(company=None, *, jours_avant=7, today=None):
    """NTMAR15 — rappel in-app N jours avant chaque ``EcheanceFiscale`` à
    préparer (best-effort, jamais bloquant). IDEMPOTENT via
    ``rappel_envoye_le``. Diffuse vers Admin/Responsable de la société
    (patron ``compta.envoyer_rappels_j7``)."""
    today = today or timezone.localdate()
    seuil = today + timedelta(days=jours_avant)
    qs = EcheanceFiscale.objects.filter(
        statut=EcheanceFiscale.Statut.A_PREPARER,
        date_limite__lte=seuil, date_limite__gte=today,
        rappel_envoye_le__isnull=True,
    ).select_related('obligation', 'company')
    if company is not None:
        qs = qs.filter(company=company)

    notifiees = []
    for echeance in qs:
        _notifier_echeance(echeance)
        echeance.rappel_envoye_le = timezone.now()
        echeance.save(update_fields=['rappel_envoye_le'])
        notifiees.append(echeance)
    return notifiees


def _notifier_echeance(echeance):
    """Notification best-effort (jamais d'exception remontée à l'appelant)."""
    try:
        from authentication.models import CustomUser
        from apps.notifications.models import EventType
        from apps.notifications.services import notify_many

        destinataires = CustomUser.objects.filter(
            company=echeance.company, is_active=True,
            role_legacy__in=[CustomUser.ROLE_ADMIN, CustomUser.ROLE_RESPONSABLE])
        if not destinataires.exists():
            return
        libelle = echeance.obligation.libelle or (
            echeance.obligation.get_type_obligation_display())
        notify_many(
            list(destinataires), EventType.DIGEST,
            f'Échéance fiscale à venir : {libelle}',
            body=f'{libelle} — date limite {echeance.date_limite}.',
            company=echeance.company,
        )
    except Exception:  # pragma: no cover - best-effort, jamais bloquant
        pass


def export_declaration_ubo(company):
    """NTMAR31 — formulaire de déclaration des bénéficiaires effectifs
    (structure OMPIC), prêt à déposer manuellement. Renvoie une liste de
    dicts (une ligne par UBO) — le rendu CSV/PDF reste côté vue."""
    from .models import BeneficiaireEffectif

    lignes = []
    qs = (BeneficiaireEffectif.objects.filter(company=company)
          .order_by('-pourcentage_detention', 'nom'))
    for ubo in qs:
        lignes.append({
            'nom': ubo.nom,
            'cin_passeport': ubo.cin_passeport,
            'nationalite': ubo.nationalite,
            'pourcentage_detention': str(ubo.pourcentage_detention),
            'type_controle': ubo.get_type_controle_display(),
            'date_declaration': (
                ubo.date_declaration.isoformat() if ubo.date_declaration else ''),
        })
    return lignes


def marquer_impact_veille_traite(veille):
    """NTMAR33 — marque l'impact d'une ``VeilleReglementaire`` comme traité
    (une fois le réglage cible vérifié par le founder/admin)."""
    if veille.impact_traite:
        return veille
    veille.impact_traite = True
    veille.save(update_fields=['impact_traite'])
    return veille
