"""Escaped, local SVG dependency schematic; deliberately not a coverage map."""
from html import escape
from .incident_data import local_site_status, observed_label

COLORS = {'OK': '#69e3c6', 'Fault': '#ff8c91', 'Unknown': '#f1cb78'}


def schematic_positions(scenario):
    children = {scenario.core_id: []}
    for site in scenario.sites:
        children[site.site_id] = []
    for link in scenario.links:
        children[link.parent].append(link.child)
    for items in children.values():
        items.sort()
    depth = {scenario.core_id: 0}
    leaves = []
    stack = [scenario.core_id]
    order = []
    while stack:
        node = stack.pop();order.append(node)
        if not children[node]:
            leaves.append(node)
        for child in reversed(children[node]):
            depth[child] = depth[node] + 1
            stack.append(child)
    width = max(960, 160 * (max(depth.values()) + 1))
    height = max(440, len(leaves) * 62 + 150)
    ys = {node: 65 + index * (height - 190) / max(1, len(leaves) - 1)
          for index, node in enumerate(leaves)}
    for node in reversed(order):
        if children[node]:
            ys[node] = sum(ys[child] for child in children[node]) / len(children[node])
    positions = {node: (65 + depth[node] * (width - 190) / max(depth.values()), ys[node]) for node in order}
    positions[scenario.depot_id] = (65, height - 55)
    return positions, width, height


def render_topology_svg(scenario, selected_site=None, show_roads=False):
    if selected_site is not None and selected_site not in scenario.observed_state.sites:
        raise ValueError('Select a known site')
    positions, width, height = schematic_positions(scenario)
    def text(value):
        return escape(str(value), quote=True)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
             'role="img" aria-labelledby="relink-topology-title relink-topology-desc" '
             'style="width:100%;height:auto;display:block;background:#0e1722;border-radius:12px">',
             '<title id="relink-topology-title">Synthetic backhaul dependencies and observed asset states</title>',
             '<desc id="relink-topology-desc">Arrows point from upstream parent to downstream site. '
             'Local observations OK does not mean service is restored. Layout is schematic, not geographic.</desc>',
             '<defs><marker id="relink-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" '
             'markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="context-stroke"/></marker></defs>']
    if show_roads:
        for road in scenario.roads:
            start, end = positions[road.origin], positions[road.to]
            label = observed_label(scenario.observed_state.roads[road.road_id], 'Open', 'Closed')
            color = COLORS[observed_label(scenario.observed_state.roads[road.road_id])]
            parts.append(f'<line data-road-id="{text(road.road_id)}" x1="{start[0]}" y1="{start[1]}" '
                         f'x2="{end[0]}" y2="{end[1]}" stroke="{color}" stroke-width="2" stroke-dasharray="3 7" opacity=".5">'
                         f'<title>{text(road.road_id)} · {label} · {road.travel_minutes} min · undirected road</title></line>')
    for link in scenario.links:
        sx, sy = positions[link.parent];tx, ty = positions[link.child]
        status = observed_label(scenario.observed_state.links[link.link_id]);color = COLORS[status]
        opacity = '1' if selected_site is None or selected_site in (link.parent, link.child) else '.3'
        dash = ' stroke-dasharray="8 6"' if status != 'OK' else ''
        distance = (tx - sx) * .48
        parts.append(f'<path data-link-id="{text(link.link_id)}" d="M {sx+24} {sy} C {sx+distance} {sy}, '
                     f'{tx-distance} {ty}, {tx-28} {ty}" fill="none" stroke="{color}" stroke-width="2.5" '
                     f'marker-end="url(#relink-arrow)" opacity="{opacity}"{dash}>'
                     f'<title>{text(link.link_id)} · {text(link.parent)} → {text(link.child)} · {status}</title></path>')
        parts.append(f'<text x="{(sx+tx)/2}" y="{(sy+ty)/2-9}" text-anchor="middle" '
                     f'fill="{color}" font-size="15" font-family="system-ui,sans-serif" opacity="{opacity}">{text(link.link_id)}</text>')
    critical = {service.site_id for service in scenario.services if service.critical}
    for site in scenario.sites:
        x, y = positions[site.site_id]
        local = local_site_status(scenario, site.site_id)
        status = 'Fault' if local == 'Local fault' else 'Unknown' if local == 'Unknown' else 'OK'
        opacity = '1' if selected_site in (None, site.site_id) else '.4'
        parts.append(f'<g data-site-id="{text(site.site_id)}" data-local-status="{text(local)}" opacity="{opacity}"><title>'
                     f'{text(site.site_id)} · {text(site.label)} · {local} · '
                     f'equipment: {observed_label(scenario.observed_state.sites[site.site_id].equipment_ok)} · '
                     f'grid: {observed_label(scenario.observed_state.sites[site.site_id].grid_power_ok, "Available", "Unavailable")}'
                     '</title>')
        if site.site_id in critical:
            symbol = '!' if status == 'Fault' else '?' if status == 'Unknown' else '✓'
        parts.append(f'<circle cx="{x}" cy="{y}" r="30" fill="none" stroke="#d7b66c" stroke-width="1.5" stroke-dasharray="3 4"/>')
        symbol = '!' if status == 'Fault' else '?' if status == 'Unknown' else '✓'
        parts.append(f'<circle cx="{x}" cy="{y}" r="22" fill="#162532" stroke="{COLORS[status]}" stroke-width="3"/>'
                     f'<text x="{x}" y="{y+5}" text-anchor="middle" fill="#e8eef5" font-size="16" '
                     f'font-family="system-ui,sans-serif">{text(site.site_id)}</text>'
                     f'<circle cx="{x+18}" cy="{y-19}" r="9" fill="#0e1722" stroke="{COLORS[status]}"/>'
                     f'<text x="{x+18}" y="{y-15}" text-anchor="middle" fill="{COLORS[status]}" font-size="12" '
                     f'font-family="system-ui,sans-serif">{symbol}</text></g>')
    x, y = positions[scenario.core_id]
    parts.append(f'<g><title>Core reference node; health is not separately observed in this schema</title>'
                 f'<rect x="{x-23}" y="{y-23}" width="46" height="46" rx="10" fill="#172d42" stroke="#8ec3f5" stroke-width="2"/>'
                 f'<text x="{x}" y="{y+5}" text-anchor="middle" fill="#b5dafb" font-size="12" font-family="system-ui,sans-serif">{text(scenario.core_id)}</text>'
                 f'<text x="{x}" y="{y+46}" text-anchor="middle" fill="#9baec2" font-size="11" font-family="system-ui,sans-serif">Core reference</text></g>')
    x, y = positions[scenario.depot_id]
    parts.append(f'<g><title>Depot reference; schematic location, not a real coordinate</title>'
                 f'<path d="M {x} {y-21} L {x+24} {y} L {x} {y+21} L {x-24} {y} Z" fill="#252435" stroke="#b7a5e6" stroke-width="2"/>'
                 f'<text x="{x+36}" y="{y+5}" fill="#cbbbec" font-size="12" font-family="system-ui,sans-serif">{text(scenario.depot_id)} · depot</text></g>')
    parts.append('</svg>')
    return ''.join(parts)
