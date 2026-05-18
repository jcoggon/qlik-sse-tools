# Association Rules

This page documents the association-rule function exposed by the Qlik Python SSE.
It is intended as an operational reference for agents generating Qlik load script
or checking an existing integration.

## Capability

`Association_Rules` builds transactions from grouped items and returns Apriori
association rules sorted by lift. It uses the `efficient-apriori` implementation.

Use this function from the Qlik load script. The result has a different row
count from the input, so it is not suitable for ordinary chart-expression use.

## Function

```qlik
LOAD
    rule,
    rule_lhs,
    rule_rhs,
    support,
    confidence,
    lift
EXTENSION PythonSSE.Association_Rules(group, item, args);
```

Input fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `group` | string | Transaction, basket, document, session, or other grouping key. |
| `item` | string | One item belonging to the group. Each input row represents one group-item pair. |
| `args` | string | Optional keyword arguments. Use an empty string when no options are needed. |

Output fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `rule` | string | Human-readable rule in the form `lhs -> rhs`. |
| `rule_lhs` | string | Comma-separated left-hand-side items. |
| `rule_rhs` | string | Comma-separated right-hand-side items. |
| `support` | numeric | Rule support. |
| `confidence` | numeric | Rule confidence. |
| `lift` | numeric | Rule lift. |

## Argument Format

Arguments are passed as a single string:

```text
min_support=0.2|float, min_confidence=0.5|float, max_length=3|int
```

The SSE parses `keyword=value` pairs. For values that must be converted before
being passed to `efficient-apriori`, append `|type`, for example `|float`,
`|int`, or `|bool`.

Common arguments:

| Argument | Purpose |
| --- | --- |
| `min_support` | Lower values return more rules and increase runtime. |
| `min_confidence` | Filters weak rules. |
| `max_length` | Limits rule/itemset length. |
| `debug` | Set `debug=true` to write request and response details to logs. |

Additional `efficient-apriori` keyword arguments can be passed with the same
syntax when supported by the installed library version.

## Script Pattern

Prepare one row per item in each group, then call the extension:

```qlik
RuleInput:
LOAD
    TransactionId as group,
    ProductName as item,
    'min_support=0.02|float, min_confidence=0.3|float' as args
RESIDENT SourceItems;

Rules:
LOAD
    rule,
    rule_lhs,
    rule_rhs,
    support,
    confidence,
    lift
EXTENSION PythonSSE.Association_Rules(RuleInput{group, item, args});

DROP TABLE RuleInput;
```

## Operational Notes

- Use stable group keys. The function builds one transaction per distinct
  `group` value.
- De-duplicate upstream if repeated group-item rows should not increase item
  presence within a transaction.
- If no rules are returned, lower `min_support` or `min_confidence`, or check
  that groups contain multiple meaningful items.
- Very low thresholds can create a large rule set. Start conservative, inspect
  row counts, then tune.
- The function returns numeric rule metrics only. Any downstream filtering,
  ranking, or categorisation should happen in Qlik after the extension call.
