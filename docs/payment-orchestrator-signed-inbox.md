# Précis — Signed Payment Orchestrator inbox (disabled)

This change consumes the version-1 signed protocol from
[Trigenys/payment-orchestrator PR #44](https://github.com/Trigenys/payment-orchestrator/pull/44).
**It does NOT grant pages, mark a purchase paid or enable Fapshi collection.**

The private route is:
`POST /api/payments/orchestrator/events`, exactly matching the dispatcher
allowlisted path. It returns **404 unless explicitly enabled**. A valid request
must include one each of:

- `x-trigenys-event-id`
- `x-trigenys-key-id`
- `x-trigenys-timestamp`
- `x-trigenys-signature`: `v1=<sha256 hex>`

Expected digest: HMAC-SHA256(secret, UTF8(`v1\n<unix seconds>\n<event id>\n`)
+ **exact raw JSON body**). Compare in constant time, reject older than 300
seconds and accept **only** the configured environment/project and matching
embedded payment evidence. There is an 8 KB request cap. No raw body, customer
email or phone is persisted.

The receiver uses PostgreSQL unique constraints on `event_id` and
`(project_id,environment,effect_key)`. An exact replay is safe; different
signed evidence for the same business effect is rejected with 409.
**HTTP 204 + x-trigenys-event-ack=event_id** is sent only after commit.
Transport-level retries are expected.

## Environment (do NOT configure yet)

```ini
PRECIS_ORCHESTRATOR_EVENTS_ENABLED=true
PRECIS_ORCHESTRATOR_EVENTS_ENVIRONMENT=sandbox
PRECIS_ORCHESTRATOR_EVENTS_PROJECT_ID=<sandbox orchestrator project ID>
PRECIS_ORCHESTRATOR_EVENTS_KEY_ID=<matching sender key ID>
PRECIS_ORCHESTRATOR_EVENTS_HMAC_SECRET=<matching 32+ character HMAC secret>
```

Live is additionally gated by `PRECIS_ORCHESTRATOR_LIVE_APPROVED=true`,
and must use different secrets, DB separation, projects and rollout review.
**Do not turn on the route until sandbox business binding has been validated.**
Rotate the key by coordinating both services, and only retire an old key
once in-flight events have been drained. An unrelated Fapshi shared
`x-wh-secret` is NEVER used as the HMAC key.

## Mandatory next business gate

The record is saved in `payment_orchestrator_events` with
`state=pending_purchase_match`, **not** immediately credited.

Before awarding any benefit, Précis must:
1. Identify a **server-created and frozen** purchase/quote by
   `external_reference` (and link to the stored payment intent).
2. Require exact project, environment, currency, amount and owned user /
   document, including purchase expiry and price/version rules.
3. Under one SQL transaction, serialize the purchase, change its status,
   award the correct pages/plan only once and mark the receipt consumed.
4. Test replay, late event, cross-user purchase, lost-ACK, concurrent
   inbox/legacy provider callbacks, account changes and refund-due cases.

The existing Campay and Fapshi routes are unmodified. No PSP credential is
shared with this receiver. No new server/container, paid subscription or
payment is activated by this PR.
