# PAB AI Triage Protocol v2

## Project JARMS — SCDF-Aligned Emergency Response

**Scope**: Elderly residents living alone in HDB rental flats.
**Input**: PAB-triggered audio transcript (from STT), paralinguistic evaluation, audio caption, and beneficiary context.
**Mode**: 24/7 operation. AI recommends to human operator. Human decides.
**Low-uncertainty default**: ESCALATE — never downgrade when uncertain.

---

## 1. Urgency Buckets

Five urgency buckets in queue priority order (highest to lowest):

| Bucket             | Description                                            | Max Wait     |
| ------------------ | ------------------------------------------------------ | ------------ |
| `life_threatening` | Imminent risk of death — act immediately               | 0 seconds    |
| `emergency`        | Serious condition — act within 1 minute                | 60 seconds   |
| `requires_review`  | Unclear, uncertain, or unreachable — human must review | 180 seconds  |
| `minor_emergency`  | Non-life-threatening but needs attention               | 600 seconds  |
| `non_emergency`    | Low-acuity, stable — redirect to GP/polyclinic         | 1800 seconds |

> **Queue order**: `life_threatening` → `emergency` → `requires_review` → `minor_emergency` → `non_emergency`

---

## 2. Triage Flags Schema

The AI must evaluate the transcript and emit the following boolean flags:

```json
{
  "airway_compromise": false,
  "not_breathing": false,
  "gasping_or_agonal_breathing": false,
  "severe_breathlessness": false,
  "unresponsive_or_unconscious": false,
  "confused_or_disoriented": false,
  "active_seizure": false,
  "stroke_keywords_present": false,
  "severe_chest_pain": false,
  "major_bleeding": false,
  "major_trauma": false,
  "fall_detected_or_suspected": false,
  "head_injury_suspected": false,
  "unable_to_get_up": false,
  "severe_pain_distress": false,
  "allergic_reaction_severe": false,
  "possible_asthma_exacerbation": false,
  "vomiting_or_diarrhoea_present": false,
  "cough_present": false,
  "fever_or_hot_to_touch": false,
  "silence_after_trigger": false,
  "calling_for_help_weak_voice": false,
  "multiple_voices_or_bystander_reports_collapse": false,
  "background_fall_impact_sound": false,
  "location_unverified": false
}
```

---

## 3. Keyword Lists (from SCDF Public Emergency Framework)

### 🔴 Life-Threatening Keywords

Any of these → immediately classify as `life_threatening`:

```
not breathing, cannot breathe, breathing difficulty, gasping, choking,
unconscious, not responding, collapsed, seizure, fits, stroke,
face drooping, slurred speech, one side weak, chest pain severe,
heavy chest, bleeding a lot, blood everywhere, hit head and not waking,
fell and cannot wake, major fall, head injury, very breathless
```

### 🟠 Emergency Keywords

Any of these → classify as `emergency` (unless already `life_threatening`):

```
fell down, cannot get up, fracture, broken bone, head hit,
dizzy and weak, wheezing, asthma attack, swollen tongue, allergy,
rash and breathless, confused, very weak, severe pain, bleeding,
persistent fever, vomiting many times
```

### 🟡 Minor Emergency Keywords

Any of these → classify as `minor_emergency` (unless higher flags present):

```
small cut, bleeding little, bruise, sprain, back pain, limb pain,
nose bleed, mild fever, diarrhoea, vomiting, headache
```

### 🟢 Non-Emergency Keywords

Only if NO higher flags are present:

```
constipation, chronic cough, skin rash, medical check up, minor sore eye
```

---

## 4. Classification Rules

Apply rules in strict order. Once a bucket is assigned at a higher level, do NOT downgrade.

### Rule 1 — Life-Threatening (HARD OVERRIDE)

**IF ANY of these flags are TRUE:**

- `airway_compromise`, `not_breathing`, `gasping_or_agonal_breathing`
- `severe_breathlessness`, `unresponsive_or_unconscious`
- `active_seizure`, `stroke_keywords_present`
- `severe_chest_pain`, `major_bleeding`, `major_trauma`

→ **Bucket = `life_threatening`** (cannot be overridden)

### Rule 2 — Emergency

**IF ANY of these flags are TRUE AND bucket is NOT already `life_threatening`:**

- `head_injury_suspected`, `fall_detected_or_suspected`, `unable_to_get_up`
- `confused_or_disoriented`, `allergic_reaction_severe`
- `possible_asthma_exacerbation`, `severe_pain_distress`
- `multiple_voices_or_bystander_reports_collapse`
- `calling_for_help_weak_voice`

→ **Bucket = `emergency`**

### Rule 3 — Requires Review

**IF ANY of these conditions are TRUE AND bucket is NOT `life_threatening` or `emergency`:**

- `silence_after_trigger`
- `location_unverified`
- Insufficient information to determine acuity
- Conflicting signals between transcript and audio analysis

→ **Bucket = `requires_review`** (treat as higher-risk than `minor_emergency`)

### Rule 4 — Minor Emergency

**IF ANY of these flags are TRUE AND NONE of the life-threatening or emergency flags are TRUE:**

- `vomiting_or_diarrhoea_present`, `cough_present`, `fever_or_hot_to_touch`

→ **Bucket = `minor_emergency`**

### Rule 5 — Non-Emergency

**ONLY IF ALL of the following are true:**

- Only low-acuity keywords present
- No red flags of any kind
- No uncertainty about the situation

→ **Bucket = `non_emergency`**

---

## 5. Patient History Modifiers

These promote the bucket **up one level** when the condition applies:

| Patient History                | Promotes when...                                          |
| ------------------------------ | --------------------------------------------------------- |
| Age ≥ 65                       | Any acute symptom and current bucket is below `emergency` |
| On anticoagulants              | Any fall or head injury detected                          |
| Cardiac or respiratory history | Chest pain, breathlessness, or confusion present          |
| Diabetes                       | Confusion, weakness, or reduced responsiveness            |
| Lives alone                    | Unreachable OR silence after trigger                      |

---

## 6. Hard Override Rules

These rules override ALL other logic:

1. **Life-threatening flags always win** — if any life-threatening flag is TRUE, bucket = `life_threatening`. No exceptions.
2. **Never classify as `non_emergency`** if there is uncertainty about the situation or conflicting signals between audio analysis and transcript.
3. **Deterioration escalates immediately** — if a new red flag is detected at any point during assessment, re-bucket upward immediately.
4. **Elderly alone + unreachable** → bucket must be at least `requires_review`.

---

## 7. Action Recommendations by Bucket

### `life_threatening`

- `call_patient_now`
- `call_995`
- `inform_emergency_contact`
- _(if available)_: `call_sgsecure_volunteers`, `notify_lift_lobby`

### `emergency`

- `call_patient_now`
- `inform_emergency_contact`
- _If no contact or symptoms worsen_: `call_995`
- _If transport needed but SCDF threshold not met_: `call_private_ambulance_1777`

### `requires_review`

- `call_patient_now`
- `inform_emergency_contact`
- _If unreachable and elderly alone_: `notify_lift_lobby`, `call_sgsecure_volunteers`
- _If red flag emerges_: `call_995`

### `minor_emergency`

- `call_patient_now`
- _If mobility issue or no safe transport_: `call_private_ambulance_1777`
- _Otherwise_: `call_ed_by_private_transport`

### `non_emergency`

- `call_patient_now`
- `inform_emergency_contact`

---

## 8. Allowed Actions (Enumerated)

The AI MUST only recommend from this list. No free-text actions:

- `call_patient_now`
- `inform_emergency_contact`
- `call_sgsecure_volunteers`
- `call_995`
- `call_private_ambulance_1777`
- `call_ed_by_private_transport`
- `call_999`
- `notify_lift_lobby`

---

## 9. Required Output Schema

The AI triage model MUST return a structured JSON object in exactly this format:

```json
{
  "urgency_bucket": "life_threatening | emergency | requires_review | minor_emergency | non_emergency",
  "triage_flags": {
    "airway_compromise": false,
    "not_breathing": false,
    "gasping_or_agonal_breathing": false,
    "severe_breathlessness": false,
    "unresponsive_or_unconscious": false,
    "confused_or_disoriented": false,
    "active_seizure": false,
    "stroke_keywords_present": false,
    "severe_chest_pain": false,
    "major_bleeding": false,
    "major_trauma": false,
    "fall_detected_or_suspected": false,
    "head_injury_suspected": false,
    "unable_to_get_up": false,
    "severe_pain_distress": false,
    "allergic_reaction_severe": false,
    "possible_asthma_exacerbation": false,
    "vomiting_or_diarrhoea_present": false,
    "cough_present": false,
    "fever_or_hot_to_touch": false,
    "silence_after_trigger": false,
    "calling_for_help_weak_voice": false,
    "multiple_voices_or_bystander_reports_collapse": false,
    "background_fall_impact_sound": false,
    "location_unverified": false
  },
  "reasoning": "Plain-language explanation of why this bucket was assigned, referencing specific transcript phrases and audio signals.",
  "recommended_actions": ["call_patient_now", "call_995"],
  "sbar": {
    "situation": "Brief description of what the patient reported or what was detected.",
    "background": "Relevant patient history, medical conditions, languages spoken, and context.",
    "assessment": "AI urgency assessment referencing specific triage flags and signals.",
    "recommendation": "Specific next steps for the human operator."
  }
}
```
