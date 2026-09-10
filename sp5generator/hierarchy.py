"""Native group hierarchy translation using GROUP.SUPERID."""


def group_tree(groups):
    """Return a stable pre-order tree; missing visible parents form local roots.

    Missing parents can result from permission-filtered source lists. Duplicate IDs
    and cyclic parent links are rejected instead of silently dropping groups.
    """
    nodes = {}
    for group in groups:
        gid = int(group["ID"])
        if gid in nodes:
            raise ValueError("Gruppenhierarchie enthält doppelte IDs.")
        nodes[gid] = {
            "id": str(gid),
            "name": group.get("NAME", ""),
            "parent_id": str(int(group.get("SUPERID") or 0)),
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
    root = int(str(root).removeprefix("sp5:group:"))
    if root not in {int(g["id"]) for g in tree}:
        raise ValueError("Gewählte Gruppe fehlt in den sichtbaren Stammdaten.")
    selected = {root}
    for group in tree:
        if int(group["parent_id"]) in selected:
            selected.add(int(group["id"]))
    return [int(g["id"]) for g in tree if int(g["id"]) in selected]
