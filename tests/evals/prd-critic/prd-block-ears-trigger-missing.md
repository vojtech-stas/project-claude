# Eval Fixture: prd-block-ears-trigger-missing

## PRD Issue #9011

**Title:** PRD: add webhook notifications for hook failures

---

## PRD Body

### 1. Problem

When a hook fails silently, no one is notified. The failure only surfaces if someone
manually checks the log. We need proactive notification for hook failures.

### 2. Success criteria (EARS format)

- The system shall send a webhook POST to a configured URL.
- The payload shall include session_id, hook_name, exit_code, and timestamp.
- Delivery shall succeed within 5 seconds of the hook failure event.

### 3. Non-goals

- We will not implement retry logic for webhook delivery in this PRD.
- Email notifications are out of scope.

### 4. Appetite

3 slices, ~2 weeks.

### 5. Slice sketch

- Slice 1: webhook config + delivery
- Slice 2: retry + delivery status
- Slice 3: dashboard notification row

### 6. Rabbit-holes

- Do not attempt TLS certificate verification for webhook endpoints.

### 7. Production verification

qa-tester will verify webhook delivery by triggering a real hook failure and
confirming the POST reaches a test endpoint.

---

## Analysis notes

The EARS success-criteria statements are malformed. "The system shall send a webhook
POST to a configured URL" is missing the trigger/condition — it does not follow the
EARS pattern "WHEN <trigger>, the system shall <response>". A correct EARS statement
would be: "WHEN a hook exits with a non-zero code, the system shall POST a JSON
payload to the configured webhook URL within 5 seconds." The trigger is entirely
absent from all three criteria. PC-EARS violation — should BLOCK.
