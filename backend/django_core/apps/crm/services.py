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
from .models import Client, Lead


def resolve_client_for_lead(lead: Lead) -> Client:
    if lead.client_id:
        return lead.client

    client = None
    if lead.email:
        client = Client.objects.filter(
            company=lead.company, email__iexact=lead.email,
        ).first()

    if client is None:
        adresse = lead.adresse or ''
        if lead.ville:
            adresse = f"{adresse}\n{lead.ville}".strip()
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
