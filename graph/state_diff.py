def diff_states(
    before: dict,
    after: dict,
) -> dict:

    before_values = before.get(
        "values",
        {},
    )

    after_values = after.get(
        "values",
        {},
    )

    added = {}

    removed = {}

    changed = {}

    for key, value in after_values.items():

        if key not in before_values:

            added[key] = value

        elif before_values[key] != value:

            changed[key] = {
                "before": before_values[key],
                "after": value,
            }

    for key, value in before_values.items():

        if key not in after_values:

            removed[key] = value

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
    }