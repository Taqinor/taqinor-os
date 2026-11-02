/**
 * ENF19 — types et format de date communs aux pages SSR /status et /status/<incident>
 * (NTOBS1/NTOBS2) : le récit d'un incident vient tel quel du backend, jamais reformulé.
 */
export interface IncidentUpdatePublic {
  statut: string;
  message: string;
  horodatage: string;
}

export interface IncidentPublicItem {
  id: number;
  titre: string;
  severite: string;
  statut: string;
  region: string;
  composants: string[];
  debute_le: string;
  resolu_le: string | null;
  updates: IncidentUpdatePublic[];
  postmortem_markdown: string;
  postmortem_publie_le: string | null;
}

export function formatDate(iso: string | null): string {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString('fr-FR', {
      day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}
