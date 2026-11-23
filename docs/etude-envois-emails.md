# Envois d'e-mails — fiabilité

*16/11/2026. Audit de tous les envois, puis correctif (option A validée).*

## 1. État relevé

| E-mail | Règle | Échec avant correctif |
|---|---|---|
| Code de connexion / inscription | 1 code / 45 s / compte | Erreur affichée, l'utilisateur réessaie |
| Mot de passe oublié | seulement si le compte existe | Silencieux pour l'utilisateur (anti-énumération) |
| Invitation | voir `etude-invitations.md` | Envoi en tâche de fond : trace retirée, renvoi possible |
| Alertes admin (support, solde IA, journal) | comptes `admin`, repli `ADMIN_ALERT_EMAIL` | Simple avertissement console, perdu |
| Nouveautés | abonnés vérifiés, lots, reprise, désabonnement 1 clic | Arrêt, reprise à la relance |

Défauts communs : **un seul essai SMTP** (un raté d'une seconde perd l'e-mail) et
délai d'attente SMTP de 60 s. Alerte « erreurs à traiter » : délai anti-répétition
armé avant l'envoi, donc un échec la taisait une heure.

## 2. Options

| Option | Effet |
|---|---|
| **A. Reprise commune + échecs au journal** (retenue) | 2 nouveaux essais (2 s, 5 s) sur les erreurs passagères ; échec final visible dans `/admin/logs` |
| B. Reprise seule | Échecs d'alerte toujours invisibles |
| C. File d'attente persistante (worker, table d'envois) | Plus robuste, mais nouvelle infrastructure pour un faible volume |

## 3. Mise en œuvre

- `app/core/email.py` : `_envoyer` (reprise, délai 20 s par essai), `_passagere`
  (réseau et codes 4xx réessayés ; 5xx, destinataire refusé, identifiants faux non).
  `send_plain` renvoie `True`/`False` et journalise l'échec en `error`.
- `app/services/error_log.py` : alerte ratée → nouvel essai après 10 min.
- Tests : `tests/test_email_reprise.py` (8), `tests/test_error_logs.py` (+1).

## 4. Limites

- Un code de connexion peut attendre jusqu'à ~7 s de plus en cas de raté.
- Une coupure après acceptation par le serveur peut produire un doublon (rare, sans gravité).
- La mise en indésirables (Spacemail → Gmail) relève de la réputation du domaine, pas de ce correctif.
