"""CPU-only plan validation and frame-exact duration allocation."""
import json
import math
import re

VERSION = '2.0.0'
FPS = 24
SYSTEM = '''You are a film director planning an edited sequence for MiniMax H3.
Return ONE JSON object only: {"title":"short title", "shots":[{"title":"short beat", "seconds":6, "description":"camera framing, one achievable action, explicit starting and ending state", "sound":"ambience and any short spoken line"}]}.
Choose the number of shots needed for the brief, within the supplied limits. Choose DIFFERENT durations when appropriate: quiet establishing shots can be shorter than dialogue or action. Durations must sum to the requested total. Each shot is 5 to 15 seconds. Separate camera setups and story beats into separate shots. No cuts inside a shot. State cause and effect clearly; do not invent unrelated twists or change relationships. Keep identity, clothes, location geography, light and prop ownership consistent. Describe the start and end of each action. Keep dialogue short enough to speak comfortably (roughly 2 words/second with pauses). Reference the supplied <Subject N> labels; do not invent reference pictures. For a character sheet, show one person, never the grid. No extra JSON keys, markdown or explanation.'''


def parse_json(text):
    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text)
    return json.loads(text)


def allocate_frames(weights, total):
    """Bounded weighted allocation; exactly total frames, 120..360 per shot."""
    n = len(weights)
    if not n or not 120*n <= total <= 360*n:
        raise ValueError(f'{n} shots cannot cover {total/FPS:g}s at 5–15s each.')
    if any(not math.isfinite(w) or w <= 0 for w in weights):
        raise ValueError('Shot durations must be finite positive numbers.')
    values = [0.0]*n
    remaining, free = float(total), set(range(n))
    while free:
        scale = remaining/sum(weights[i] for i in free)
        low = [i for i in free if weights[i]*scale < 120]
        high = [i for i in free if weights[i]*scale > 360]
        if not low and not high:
            for i in free: values[i] = weights[i]*scale
            break
        # Fix only the violated side warranted by the total clipped sum.
        clipped_sum = sum(min(360, max(120, weights[i]*scale)) for i in free)
        fix, bound = (low, 120) if clipped_sum > remaining else (high, 360)
        for i in fix:
            values[i] = bound
            remaining -= bound
            free.remove(i)
    result = [int(math.floor(v+1e-8)) for v in values]
    for i in sorted(range(n), key=lambda i: (values[i]-result[i], -i), reverse=True):
        if sum(result) == total: break
        if result[i] < 360: result[i] += 1
    assert sum(result) == total
    return result


def validate_plan(data, target_seconds=None, max_shots=12, automatic=False):
    if not isinstance(data, dict) or not isinstance(data.get('shots'), list):
        raise ValueError('Plan must contain a shots array.')
    shots = data['shots']
    if not 1 <= len(shots) <= max_shots:
        raise ValueError(f'Plan must have 1–{max_shots} shots.')
    weights = []
    for i, s in enumerate(shots):
        if not isinstance(s, dict): raise ValueError(f'Shot {i+1} must be an object.')
        for key in ('title', 'description', 'sound'):
            if not isinstance(s.get(key), str) or not s[key].strip():
                raise ValueError(f'Shot {i+1} needs {key}.')
        value = s.get('seconds')
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f'Shot {i+1} needs a finite positive seconds value.')
        if not automatic and not 5 <= value <= 15:
            raise ValueError(f'Shot {i+1}: seconds must be between 5 and 15.')
        take = s.get('take', 0)
        if isinstance(take, bool) or not isinstance(take, int) or not 0 <= take <= 100000:
            raise ValueError('take must be an integer between 0 and 100000.')
        weights.append(value)
    frames = (allocate_frames(weights, round(target_seconds*FPS)) if automatic
              else [round(v*FPS) for v in weights])
    clean = {'version': VERSION, 'title': str(data.get('title', 'My film'))[:150], 'shots': []}
    cursor = 0
    for i, (s, f) in enumerate(zip(shots, frames)):
        clean['shots'].append({'title': s['title'].strip(), 'seconds': f/FPS,
          'description': s['description'].strip(), 'sound': s['sound'].strip(),
          'take': s.get('take', 0), 'export_frames': f, 'generation_frames': max(124, 5+17*math.ceil((f-5)/17)),
          'start_seconds': cursor/FPS, 'end_seconds': (cursor+f)/FPS})
        for key in ('id','selected','approved_file','mode','first_frame','last_frame','reference_notes','media_state'):
            if key in s: clean['shots'][-1][key]=s[key]
        clean['shots'][-1].setdefault('id', f'shot_{i+1:02}')
        cursor += f
    ids=[s['id'] for s in clean['shots']]
    if len(set(ids))!=len(ids) or any(not isinstance(x,str) or not x for x in ids): raise ValueError('Shot IDs must be unique strings')
    clean['total_seconds'] = cursor/FPS
    return clean


def shot_prompt(shot, reference_notes, style):
    labels = sorted(set(re.findall(r'<Subject \d+>', reference_notes)))
    retention = '\n'.join(f'{label} (this shot): fully_preserved - Preserve the described identity, wardrobe, architecture and lighting; use the camera framing below.' for label in labels)
    return (f'subject_definitions:\n{reference_notes}\n\nsummary:\n[reference generation] {shot["title"]}\n\n'
      f'retention_analysis:\n{retention}\n\ndetailed_description:\n{style}\n[Shot 1] {shot["description"]}\n\n'
      f'overall_soundscape:\n{shot["sound"]}\n\nnon_diegetic_music:\nN/A')


def timeline(plan):
    rows = [f'{plan["title"]} — {len(plan["shots"])} clips, {plan["total_seconds"]:g} seconds, 24 fps']
    for i,s in enumerate(plan['shots'],1):
        rows.append(f'{i:02}. {s["start_seconds"]:g}–{s["end_seconds"]:g}s | {s["seconds"]:g}s | {s["title"]}\n{s["description"]}\nSound: {s["sound"]}')
    return '\n\n'.join(rows)
