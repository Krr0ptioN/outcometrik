## Status table

| Situation (eligible = weight > 0)                    | Status       | Value |
| ---------------------------------------------------- | ------------ | ----- |
| No eligible entries                                  | UNMAPPED     | null  |
| Any eligible entry MISSING                           | INCOMPLETE   | null  |
| All eligible entries EXEMPT                          | ALL_EXEMPT   | null  |
| Nothing scorable left (zero denominator / not graded) | NOT_ASSESSED | null  |
| Otherwise                                            | OK           | mean  |

Policy: 40-digit precision, ROUND_HALF_EVEN internally. Display/export only: 1 decimal,
ROUND_HALF_UP (PRD §12, pending DEC-01). Entries are processed in `key` order.
