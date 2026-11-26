"""Live agent-flow diagram: which agent is working, what it passed on, and where the plan stands.

Pure state + HTML so it can be tested without a browser. ``FlowState.apply`` takes the
same messages the orchestrator records (plus its display-only ``working`` notices);
``events_from_messages`` rebuilds that stream from a finished run so it can be replayed.
Display only: nothing here calls a model or changes a run.
"""
from __future__ import annotations

import base64
import html
import time

from project.ui.agent_view import STAGE_TEXT, feed_line, name

AGENT_NODES = {
    'network_investigator': 'investigator', 'field_resource_planner': 'planner',
    'service_priority_assessor': 'assessor', 'plan_reviewer': 'reviewer',
    'deterministic_scheduler': 'scheduler', 'template_baseline': 'parser',
}
LAYOUTS = {
    'multi': {
        'nodes': [('reports', 'Incident|reports', '📄', 80, 150), ('investigator', 'Network|Investigator', '🔎', 255, 150),
                  ('planner', 'Field Resource|Planner', '🧭', 440, 70), ('assessor', 'Service Priority|Assessor', '⚖️', 440, 230),
                  ('scheduler', 'CP-SAT|scheduler', '🗓️', 625, 150), ('reviewer', 'Plan|Reviewer', '✅', 800, 150),
                  ('operator', 'You|(operator)', '👤', 965, 150)],
        'edges': [('reports', 'investigator'), ('investigator', 'planner'), ('investigator', 'assessor'),
                  ('planner', 'scheduler'), ('assessor', 'scheduler'), ('scheduler', 'reviewer'),
                  ('reviewer', 'operator'), ('scheduler', 'operator')],
        'back': ('reviewer', 'investigator'),
    },
    'single': {
        'nodes': [('reports', 'Incident|reports', '📄', 80, 150), ('single', 'Single|agent', '🤖', 300, 150),
                  ('scheduler', 'CP-SAT|scheduler', '🗓️', 520, 150), ('selfreview', 'Self-|review', '✅', 740, 150),
                  ('operator', 'You|(operator)', '👤', 965, 150)],
        'edges': [('reports', 'single'), ('single', 'scheduler'), ('scheduler', 'selfreview'),
                  ('selfreview', 'operator')],
        'back': ('selfreview', 'single'),
    },
    'template': {
        'nodes': [('reports', 'Incident|reports', '📄', 80, 150), ('parser', 'Template|parser', '🧩', 380, 150),
                  ('scheduler', 'CP-SAT|scheduler', '🗓️', 680, 150), ('operator', 'You|(operator)', '👤', 965, 150)],
        'edges': [('reports', 'parser'), ('parser', 'scheduler'), ('scheduler', 'operator')],
        'back': None,
    },
}
STYLE = {  # stroke, fill, note colour
    'idle': ('#2a3647', '#111824', '#8D9EB3'), 'working': ('#F4C76B', '#2a2312', '#F4C76B'),
    'done': ('#54D6BB', '#0f2420', '#9fe9d6'), 'warn': ('#ff9f5a', '#2a1a10', '#ffc08f'),
    'failed': ('#FF7A85', '#2a1215', '#ff9ea4'),
}
W, H = 150, 76


def node_for(sender, stage=None):
    if sender == 'single_agent':
        return 'selfreview' if stage == 'review' else 'single'
    return AGENT_NODES.get(sender)


class FlowState:
    def __init__(self, mode, report_count=0, clock=time.monotonic, stepwise=False):
        self.mode = mode if mode in LAYOUTS else 'multi'
        layout = LAYOUTS[self.mode]
        self.status = {n[0]: 'idle' for n in layout['nodes']}
        self.notes = {n[0]: 'waiting' for n in layout['nodes']}
        self.status['reports'], self.notes['reports'] = 'done', f'{report_count} reports'
        self.used, self.active = set(), None
        self.finished_order = ['reports']
        self.log, self.now = [], 'Starting…'
        self.messages = self.challenges = 0
        self.clock, self.started = clock, clock()
        self.finished = False
        self.stepwise = stepwise

    # ------------------------------------------------------------------ state
    def _arrive(self, node, back=False):
        layout = LAYOUTS[self.mode]
        if back and layout['back'] and layout['back'][1] == node:
            self.active = layout['back']
        else:
            sources = [a for a, b in layout['edges'] if b == node]
            done = [s for s in reversed(self.finished_order) if s in sources]
            self.active = (done[0], node) if done else None
        if self.active:
            self.used.add(self.active)

    def _done(self, node, note, status='done'):
        self.status[node], self.notes[node] = status, note
        if node in self.finished_order:
            self.finished_order.remove(node)
        self.finished_order.append(node)

    def apply(self, message):
        sender, recipient = message.get('sender', ''), message.get('recipient', '')
        content = message.get('finding') if isinstance(message.get('finding'), dict) else {}
        elapsed = self.clock() - self.started
        text, _ = feed_line(message)
        if recipient == 'working':
            node = node_for(sender, message.get('stage'))
            if node in self.status:
                reworking = self.status[node] != 'idle'
                self._arrive(node, back=reworking and message.get('stage') in ('reinvestigate', 'reanalyse'))
                self.status[node] = 'working'
                self.notes[node] = 'working…'
            self.now = f"{name(sender)} is {STAGE_TEXT.get(message.get('stage'), 'working')}…"
            return
        self.messages += 1
        self.log.append((elapsed, text))
        if 'fact_challenges' in content and recipient in ('network_investigator', 'single_agent'):
            self.challenges += len(content['fact_challenges'])
            back = LAYOUTS[self.mode]['back']
            if back:
                self._done(back[0], f"challenged {len(content['fact_challenges'])} fact(s)", 'warn')
                self.active = back
                self.used.add(back)
            return
        if sender == 'rejected_agent_output':
            node = node_for(content.get('role'), content.get('stage'))
            if node in self.status:
                self.status[node], self.notes[node] = 'warn', 'output rejected'
            return
        if sender == 'coordinator':
            node = AGENT_NODES.get(content.get('degraded_stage'))
            if node in self.status:
                self._done(node, 'skipped (degraded)', 'failed')
            if 'applied_action_ids' in content and 'scheduler' in self.status:
                self.notes['scheduler'] = f"hold on {', '.join(content['applied_action_ids'])}"
            return
        node = node_for(sender, content.get('stage'))
        if node not in self.status:
            return
        if sender == 'network_investigator' and content.get('shared') == 'facts':
            target = AGENT_NODES.get(recipient)
            if target:
                self.active = (node, target)
                self.used.add(self.active)
            return
        if node == 'scheduler':
            if self.status['scheduler'] != 'working':
                self._arrive('scheduler')
            n = len(content.get('actions', []))
            self._done('scheduler', f"{n} action{'' if n == 1 else 's'}, validated")
            return
        if node == 'parser':
            self._arrive('parser')
        self._done(node, self._note(content))

    @staticmethod
    def _note(content):
        if 'decision' in content:
            return f"decision: {content['decision']}"
        if 'facts' in content:
            ignored = content.get('ignored_reports', [])
            flagged = any(i.get('kind') == 'instruction_attempt' for i in ignored)
            return f"{len(content['facts'])} facts · {len(ignored)} set aside" + (' · ⚠' if flagged else '')
        parts = []
        for key, word in (('requests', 'hold'), ('questions', 'question'), ('priority_proposals', 'proposal')):
            if content.get(key):
                parts.append(f"{len(content[key])} {word}{'s' if len(content[key]) > 1 else ''}")
        return ' · '.join(parts) or 'finding sent'

    def finish(self, result):
        self.finished = True
        for node, status in self.status.items():
            if status == 'working':
                self.status[node], self.notes[node] = 'failed', 'stopped'
        layout = LAYOUTS[self.mode]
        sources = [a for a, b in layout['edges'] if b == 'operator' and self.status.get(a) in ('done', 'warn')]
        last = next((s for s in reversed(self.finished_order) if s in sources), None)
        if last:
            self.active = (last, 'operator')
            self.used.add(self.active)
        if result.status == 'awaiting_approval':
            self.status['operator'], self.notes['operator'] = 'done', 'plan ready to approve'
            self.now = 'Plan ready for your review. Open ② Inspect plan, then ③ Review & approve.'
        else:
            self.status['operator'], self.notes['operator'] = 'failed', 'escalated to you'
            self.now = 'Planning escalated: operator clarification needed.'

    # ------------------------------------------------------------------ render
    def svg(self):
        layout = LAYOUTS[self.mode]
        pos = {n[0]: (n[3], n[4]) for n in layout['nodes']}
        parts = ['<svg viewBox="0 0 1050 330" xmlns="http://www.w3.org/2000/svg" role="img" '
                 'aria-label="Agent workflow" font-family="Source Sans Pro, Helvetica, Arial, sans-serif">',
                 SVG_CSS, '<defs>' + ''.join(
                     f'<marker id="ah-{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
                     f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>'
                     for k, c in (('idle', '#2f3d50'), ('used', '#4f8f82'), ('active', '#54D6BB'), ('back', '#ff9f5a')))
                 + '</defs>']
        for a, b in layout['edges']:
            (x1, y1), (x2, y2) = pos[a], pos[b]
            x1, x2 = x1 + W / 2, x2 - W / 2
            mid = (x1 + x2) / 2
            parts.append(self._edge(f'M{x1},{y1} C{mid},{y1} {mid},{y2} {x2 - 2},{y2}', (a, b)))
        if layout['back']:
            a, b = layout['back']
            (x1, y1), (x2, y2) = pos[a], pos[b]
            parts.append(self._edge(f'M{x1},{y1 + H / 2} C{x1},322 {x2},322 {x2},{y2 + H / 2 + 2}', (a, b), back=True))
            parts.append(f'<text x="{(x1 + x2) / 2}" y="300" text-anchor="middle" font-size="11" '
                         f'fill="{"#ffc08f" if self.challenges else "#8D9EB3"}">fact challenges go back'
                         f'{f" ({self.challenges})" if self.challenges else ""}</text>')
        for node, title, icon, x, y in layout['nodes']:
            stroke, fill, note_colour = STYLE[self.status[node]]
            cls = ' class="rl-pulse"' if self.status[node] == 'working' else ''
            first, second = title.split('|')
            parts.append(f'<g><rect{cls} x="{x - W / 2}" y="{y - H / 2}" width="{W}" height="{H}" rx="12" '
                         f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
                         f'<text x="{x - W / 2 + 12}" y="{y - 4}" font-size="20">{icon}</text>'
                         f'<text x="{x - W / 2 + 42}" y="{y - 14}" font-size="12.5" font-weight="600" fill="#EAF1F8">'
                         f'{html.escape(first)}</text>'
                         f'<text x="{x - W / 2 + 42}" y="{y + 2}" font-size="12.5" font-weight="600" fill="#EAF1F8">'
                         f'{html.escape(second)}</text>'
                         f'<text x="{x}" y="{y + 26}" font-size="10.5" text-anchor="middle" fill="{note_colour}">'
                         f'{html.escape(self.notes[node][:30])}</text></g>')
        parts.append('</svg>')
        return ''.join(parts)

    def _edge(self, d, key, back=False):
        if key == self.active:
            colour, marker, cls = ('#ff9f5a', 'back', ' class="rl-flow"') if back else ('#54D6BB', 'active', ' class="rl-flow"')
            width = 3
        elif key in self.used:
            colour, marker, cls, width = ('#a8683a', 'back', '', 2) if back else ('#4f8f82', 'used', '', 2)
        else:
            colour, marker, cls, width = '#2f3d50', 'idle', '', 1.5
        dash = ' stroke-dasharray="5 5"' if back and key != self.active else ''
        return (f'<path{cls} d="{d}" fill="none" stroke="{colour}" stroke-width="{width}"{dash} '
                f'marker-end="url(#ah-{marker})"/>')

    def html(self, log_lines=6):
        elapsed = self.clock() - self.started
        dot = '#54D6BB' if self.finished else '#F4C76B'
        header = (f'<div class="rl-flow-head"><span class="rl-dot" style="background:{dot}"></span>'
                  f'<b>{html.escape(self.now)}</b><span class="rl-meta">{self.messages} messages · '
                  f'{self.challenges} challenges · {elapsed:.1f} s</span></div>')
        first = max(0, len(self.log) - log_lines)
        rows = ''.join(f'<div class="rl-log-row"><span>{f"#{first + i + 1}" if self.stepwise else f"{t:5.1f}s"}</span>'
                       f'{_md(text)}</div>' for i, (t, text) in reversed(list(enumerate(self.log[first:]))))
        if self.stepwise:
            header = header.replace(f' · {elapsed:.1f} s', ' · recorded run')
        log = f'<div class="rl-log">{rows or "<div class=rl-log-row>Waiting for the first agent…</div>"}</div>'
        image = base64.b64encode(self.svg().encode()).decode()
        diagram = (f'<img class="rl-diagram" alt="Agent workflow: {html.escape(self.now)}" '
                   f'src="data:image/svg+xml;base64,{image}"/>')
        return f'<div class="rl-flow">{FLOW_CSS}{header}{diagram}{log}</div>'


def _md(text):
    """Escape, then render the **bold** markers used by feed lines."""
    out, bold = [], False
    for i, piece in enumerate(html.escape(text).split('**')):
        out.append(('<b>' if bold else '') + piece + ('</b>' if bold else '') if i else piece)
        bold = not bold
    return ''.join(out)


SVG_CSS = ('<style>.rl-pulse{animation:rlpulse 1.1s ease-in-out infinite}'
           'path.rl-flow{stroke-dasharray:9 6;animation:rldash .7s linear infinite}'
           '@keyframes rlpulse{0%,100%{stroke-opacity:1}50%{stroke-opacity:.25}}'
           '@keyframes rldash{to{stroke-dashoffset:-15}}</style>')
FLOW_CSS = """<style>
.rl-flow{border:1px solid #22303F;border-radius:14px;padding:12px 14px;background:#0D141F;margin-bottom:8px}
.rl-diagram{width:100%;height:auto;display:block;margin:4px 0}
.rl-flow-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-size:14px;margin-bottom:4px;color:#EAF1F8}
.rl-dot{width:10px;height:10px;border-radius:50%;display:inline-block;animation:rlblink 1.2s infinite}
.rl-meta{margin-left:auto;color:#8D9EB3;font-size:12px}
.rl-log{border-top:1px solid #182334;margin-top:6px;padding-top:6px;font-size:12.5px;color:#B8C6D6;max-height:170px;overflow:auto}
.rl-log-row{padding:2px 0}.rl-log-row span{color:#8D9EB3;display:inline-block;width:52px;font-variant-numeric:tabular-nums}
@keyframes rlblink{0%,100%{opacity:1}50%{opacity:.35}}
</style>"""


def events_from_messages(messages):
    """Recorded messages plus the 'working' notices that preceded each agent's answer."""
    events = []
    for message in messages:
        sender = message.get('sender', '')
        content = message.get('finding') if isinstance(message.get('finding'), dict) else {}
        is_answer = message.get('recipient') == 'coordinator' and sender in (*AGENT_NODES, 'single_agent')
        if is_answer and sender != 'template_baseline':
            stage = 'schedule' if sender == 'deterministic_scheduler' else content.get('stage')
            events.append({'sender': sender, 'recipient': 'working', 'stage': stage, 'finding': None})
        events.append(message)
    return events


def final_state(result):
    state = FlowState(result.mode, len(result.state.scenario.reports), clock=lambda: 0.0, stepwise=True)
    for event in events_from_messages(result.messages):
        state.apply(event)
    state.finish(result)
    return state


class LiveFlow:
    """Orchestrator observer that redraws the flow diagram in a Streamlit placeholder."""

    def __init__(self, slot, mode, report_count, status=None):
        self.slot, self.status = slot, status
        self.state = FlowState(mode, report_count)
        self.count = 0
        self.draw()

    def draw(self):
        self.slot.html(self.state.html())

    def __call__(self, message):
        self.state.apply(message)
        if message.get('recipient') != 'working':
            self.count += 1
        elif self.status is not None:
            self.status.update(label=self.state.now)
        self.draw()

    def finish(self, result):
        if result is not None:
            self.state.finish(result)
        self.draw()


def replay(slot, result, delay=0.7):
    state = FlowState(result.mode, len(result.state.scenario.reports), clock=lambda: 0.0, stepwise=True)
    slot.html(state.html())
    for event in events_from_messages(result.messages):
        state.apply(event)
        slot.html(state.html())
        time.sleep(delay)
    state.finish(result)
    slot.html(state.html())
    return state


__all__ = ['FlowState', 'LiveFlow', 'events_from_messages', 'final_state', 'replay', 'name']
