"""
Lead → Client resolution (approach approved by the founder, 2026-06-12).

A quote always carries a Client; when it starts from a Lead the client is
resolved automatically, without ever creating duplicates:

  1. the lead is already linked to a client  → reuse that client;
  2. the lead has an email matching an existing client of the SAME company
     (case-insensitive)                      → link and reuse that client;
  3. otherwise                               → create a client from the lead's
     contact details and link it.

The resolved link is persisted on the lead, so every later quote from the
same lead reuses the same client. Everything stays tenant-scoped.
"""
from . import stages
from .models import Client, Lead, LeadActivity

# Mouvement automatique du funnel à partir des statuts DOCUMENT du devis
# (couche séparée et permanente — CLAUDE.md règles #2/#4) :
#   devis « envoye »  → étape QUOTE_SENT (Devis envoyé)
#   devis « accepte » → étape SIGNED (Signé)
# Clés scalaires uniquement — jamais de nouvelle liste d'étapes (STAGES.py).
_STATUT_VERS_STAGE = {
    'envoye': ('QUOTE_SENT', 'envoyé'),
    'accepte': ('SIGNED', 'accepté'),
}


def _rang_funnel(stage_key: str) -> int:
    """Rang d'avancement dans le funnel, depuis l'ordre canonique de STAGES.

    COLD est un état de PARKING, pas « plus avancé » : il est classé sous
    QUOTE_SENT pour qu'un lead froid soit RÉACTIVÉ par les deux mouvements
    automatiques (devis envoyé / accepté).
    """
    if stage_key == 'COLD':
        return stages.STAGES.index('QUOTE_SENT') - 1
    return stages.STAGES.index(stage_key)


def avancer_stage_pour_devis(devis, ancien_statut, nouveau_statut, user):
    """Avance l'étape du lead quand le STATUT d'un devis change.

    Ne recule jamais, ignore les leads perdus (drapeau `perdu`), n'agit que sur
    les transitions envoye/accepte. Écrit UNE entrée d'historique marquée
    automatique (« auto — devis … »).
    """
    if nouveau_statut == ancien_statut:
        return
    cible = _STATUT_VERS_STAGE.get(nouveau_statut)
    if cible is None:
        return
    lead = devis.lead
    if lead is None:
        return
    if lead.perdu:
        return  # lead perdu (drapeau) — le funnel ne bouge plus automatiquement.

    stage_cible, suffixe = cible
    if _rang_funnel(lead.stage) >= _rang_funnel(stage_cible):
        return  # jamais en arrière (ni sur-place).

    ancien_stage = lead.stage
    lead.stage = stage_cible
    lead.save(update_fields=['stage'])

    if stage_cible == 'SIGNED':
        # SIGNED_QUOTE_CAPI_HOOK: fire on transition INTO SIGNED — entering Signé here
        # (auto via devis accepté) est équivalent à une entrée manuelle.
        pass

    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.MODIFICATION,
        field='stage', field_label='Étape',
        old_value=stages.STAGE_LABELS[ancien_stage],
        new_value=stages.STAGE_LABELS[stage_cible],
        body=f"auto — devis {devis.reference} {suffixe}",
    )


def default_responsable_for(company):
    """Responsable assigné par défaut aux nouveaux leads d'une société.

    Source unique : le profil entreprise (Paramètres → « Responsable par
    défaut des nouveaux leads »). None si non configuré ou pas de société.
    """
    if company is None:
        return None
    from apps.parametres.models import CompanyProfile
    profile = CompanyProfile.objects.filter(company=company).first()
    return profile.responsable_defaut_leads if profile else None


def resolve_client_for_lead(lead: Lead) -> Client:
    if lead.client_id:
        return lead.client

    client = None
    if lead.email:
        client = Client.objects.filter(
            company=lead.company, email__iexact=lead.email,
        ).first()

    if client is None:
        # Séparateur VISIBLE entre rue et ville : un \n disparaît dans les
        # champs <input> et collait l'adresse à la ville (« …AuditCasablanca »).
        adresse = lead.adresse or ''
        if lead.ville:
            adresse = ', '.join(p for p in (adresse, lead.ville) if p)
        client = Client.objects.create(
            company=lead.company,
            nom=lead.nom,
            prenom=lead.prenom,
            email=lead.email,
            telephone=(lead.telephone or '')[:20] or None,
            adresse=adresse or None,
        )

    lead.client = client
    lead.save(update_fields=['client'])
    return client
