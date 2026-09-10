"""Native group hierarchy translation using GROUP.SUPERID."""


def _group_id(value, allow_root=False):
    try:
        number = int(str(value).removeprefix("sp5:group:"))
    except (TypeError, ValueError):
        raise ValueError("Gruppenhierarchie enthält eine ungültige ID.") from None
    if number < (0 if allow_root else 1):
        raise ValueError("Gruppenhierarchie enthält eine ungültige ID.")
    return number


def group_tree(groups):
    """Return a stable pre-order tree; missing visible parents form local roots.

    Missing parents can result from permission-filtered source lists. Duplicate IDs
    and cyclic parent links are rejected instead of silently dropping groups.
    """
    nodes = {}
    for group in groups:
        gid = _group_id(group["ID"])
        if gid in nodes:
            raise ValueError("Gruppenhierarchie enthält doppelte IDs.")
        nodes[gid] = {
            "id": str(gid),
            "name": group.get("NAME", ""),
            "parent_id": str(_group_id(group.get("SUPERID") or 0, allow_root=True)),
        }
    for gid in nodes:
        seen = set()
        current = gid
        while current in nodes:
            if current in seen:
                raise ValueError("Gruppenhierarchie enthält einen Zyklus.")
            seen.add(current)
            parent = int(nodes[current]["parent_id"])
            if parent == 0:
                break
            current = parent
    children = {}
    for gid, node in nodes.items():
        parent = int(node["parent_id"])
        children.setdefault(
            parent if parent in nodes and parent != 0 else None, []
        ).append(gid)
    result = []
    stack = [(gid, 0) for gid in reversed(children.get(None, []))]
    while stack:
        gid, depth = stack.pop()
        result.append({**nodes[gid], "depth": depth})
        stack.extend((child, depth + 1) for child in reversed(children.get(gid, [])))
    return result


def selected_group_ids(groups, root):
    tree = group_tree(groups)
    root = _group_id(root)
    if root not in {int(g["id"]) for g in tree}:
        raise ValueError("Gewählte Gruppe fehlt in den sichtbaren Stammdaten.")
    selected = {root}
    for group in tree:
        if int(group["parent_id"]) in selected:
            selected.add(int(group["id"]))
    return [int(g["id"]) for g in tree if int(g["id"]) in selected]


def resolve_group_selection(groups, team_id=None, team_ids=None):
    """Exact checkbox IDs, or legacy recursive single-team selection."""
    if team_ids is None:
        if team_id is None:
            raise ValueError("Mindestens eine sichtbare Gruppe auswählen.")
        return selected_group_ids(groups, team_id)
    if team_id is not None:
        raise ValueError("team_id und team_ids nicht gleichzeitig angeben.")
    tree = group_tree(groups)
    selected = {_group_id(g) for g in team_ids}
    if not selected or not selected <= {int(g["id"]) for g in tree}:
        raise ValueError("Mindestens eine sichtbare Gruppe auswählen; unbekannte IDs sind nicht erlaubt.")
    return [int(g["id"]) for g in tree if int(g["id"]) in selected]
