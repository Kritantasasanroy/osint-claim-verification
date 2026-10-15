# Materiality rubric for ADVERSE (A7)

The verdict vocabulary is unchanged (`ADVERSE / NO_ADVERSE / UNVERIFIABLE`) so results stay comparable with
v1, but **ADVERSE now has an operational definition enforced in code**, not left to the model's judgement.

## Severity scale

The Evaluator tags every adverse fact about the subject with one severity (`investigation/evidence.py:Severity`),
most severe first:

| Severity | Examples | Material? |
|---|---|---|
| `criminal_conviction` | fraud conviction, guilty plea | yes |
| `criminal_charge` | indictment, criminal complaint by prosecutors | yes |
| `sanctions` | OFAC SDN listing, EU/UN/UK sanctions | yes |
| `insolvency` | bankruptcy, Chapter 11, administration, Insolvenzverfahren | yes |
| `regulator_ban_or_major_enforcement` | trading ban, licence revoked, consent order with large penalty | yes |
| `major_civil_judgment` | court finding of fraud or serious misconduct; damages large relative to the subject | yes |
| `routine_civil_or_minor_fine` | ordinary settlement without admission, class action settled as cost of business, small municipal / OSHA / minor environmental fine | **no** |

## The rule (code, not prompt)

* An evidence item with `points_to = ADVERSE` votes for ADVERSE **only if its severity is material**
  (`Evidence.direction`). An unrated or routine adverse item votes for nothing.
* Such items are still reported, in the report's **"Minor adverse items"** section, so an analyst sees them.
* The stopping gate will not close a case on ADVERSE without two independent publisher clusters pointing at
  ADVERSE with summed weight >= 1.0 **and** at least one official, major-news or reference source
  (`CaseFile.unmet_conditions`).
* NO_ADVERSE settles only with a confirmed identity (two independent publishers), at least one adverse-signal
  search, and no material adverse item of weight >= 0.5 on file.

## What is deliberately *not* modelled

* **Size relative to the entity** is not computed. "Large relative to the subject" is left to the Evaluator's
  severity tag; a $14M class-action settlement is routine for Costco and would be material for a ten-person
  firm. Making it numeric needs revenue data the toolbox cannot fetch reliably.
* **Patterns** (many minor items adding up to a material one) are not aggregated. A documented, testable rule
  (e.g. three or more regulator actions in five years) is future work; until then an analyst reads the
  "Minor adverse items" list.

## Why

C20 (Patagonia) and the held-out H2 (Costco) were called ADVERSE at 85–86% on routine settlements and small
fines. An analyst doing due diligence would not act on that. The review traced it to a verdict definition with
no materiality (§3 R1).
