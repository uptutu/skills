#!/usr/bin/env python3
"""design_audit.py — 对照 modern-front-design 规范审计前端项目。

用法:
  python3 design_audit.py [root]                       # markdown 审计报告
  python3 design_audit.py [root] --format json         # 原始 JSON
  python3 design_audit.py [root] --snapshot out.json   # 保存进度快照
  python3 design_audit.py --compare old.json new.json  # 进度对比报告
  python3 design_audit.py --selfcheck
"""
import argparse
import colorsys
import json
import os
import re
import sys
from collections import Counter
from datetime import date

EXTS = ('.css', '.scss', '.less', '.tsx', '.jsx', '.vue', '.html', '.svelte')
SKIP_DIRS = {'node_modules', '.git', 'dist', 'build', '.next', 'out', 'coverage', 'vendor'}
MAX_REPORT_FINDINGS = 50

HEX_RE = re.compile(r'#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b')
RADIUS_RE = re.compile(r'border-radius\s*:\s*([\d.]+)\s*(px|rem|em)?', re.I)
SHADOW_RE = re.compile(r'box-shadow\s*:([^;}]+)', re.I)
FONTSIZE_RE = re.compile(r'font-size\s*:\s*([\d.]+)\s*(px|rem|em)', re.I)
RGBA_RE = re.compile(r'rgba?\(([^)]+)\)')
COLOR_FN_RE = re.compile(r'rgba?\([^)]*\)|#[0-9a-fA-F]{3,8}\b')

# 规范调色板（SKILL.md 第 3 节 + Hero/饱和面）
PALETTE = {
    '#ffffff', '#f7f8fa', '#f5f7fa', '#eef2f7', '#f4f8fd', '#f2f4f7',
    '#0f172a', '#1e293b', '#64748b', '#94a3b8',
    '#b1cbea', '#8fb3e0', '#bfd8f2', '#d9e9f8', '#c9bfff', '#b9a7ff',
    '#86e39b', '#e7f9ec', '#ff8a8a', '#ffeded', '#ffd166', '#ffb4a2',
    '#1fa2a6', '#2bc0d4',
}

ADVICE = {
    'no-dark-mode': '移除 dark mode 媒体查询——本规范只支持浅色',
    'no-dark-bg': '深色背景替换为 #FFFFFF / #F7F8FA',
    'low-saturation-only': '高饱和色降饱和处理；全屏只保留一处饱和面',
    'no-square-corners': '方角改为 18–24px 圆角',
    'soft-shadows-only': '硬阴影改为多层柔和阴影，如 0 12px 32px rgba(23,43,77,0.06)',
    'no-lorem': '可读 lorem 文本替换为 greeked 灰色圆角横条',
    'no-candlestick': '蜡烛图替换为 1–2px 细线/面积图',
    'label-floor': '小于 10px 的字号提升到 10–11px 标签档',
}


def norm_hex(h):
    h = h.lower()
    if len(h) == 4:
        h = '#' + ''.join(c * 2 for c in h[1:])
    return h


def to_px(v, unit):
    return float(v) * 16 if unit in ('rem', 'em') else float(v)


def sat_val(h):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    _, s, v = colorsys.rgb_to_hsv(r, g, b)
    return s, v


def _selfcheck():
    assert norm_hex('#FFF') == '#ffffff'
    assert norm_hex('#86E39B') == '#86e39b'
    assert to_px('1.5', 'rem') == 24.0
    s, v = sat_val('#86e39b')
    assert 0.2 < s < 0.6 and v > 0.8
    assert sat_val('#ff0000')[0] == 1.0
    print('selfcheck ok')


def scan(root):
    d = {
        'date': date.today().isoformat(), 'root': os.path.abspath(root),
        'files_scanned': 0, 'colors': Counter(), 'saturated_colors': Counter(),
        'radii': [], 'fonts': Counter(), 'shadow_soft': 0, 'shadow_hard': 0,
        'findings': [],
    }
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [x for x in dirnames if x not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith(EXTS):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, root)
            try:
                text = open(path, encoding='utf-8', errors='ignore').read()
            except OSError:
                continue
            d['files_scanned'] += 1
            if re.search(r'prefers-color-scheme\s*:\s*dark', text):
                d['findings'].append(dict(rule='no-dark-mode', severity='critical', file=rel, detail='prefers-color-scheme: dark'))
            if re.search(r'lorem ipsum', text, re.I):
                d['findings'].append(dict(rule='no-lorem', severity='high', file=rel, detail='readable lorem ipsum'))
            if re.search(r'candlestick', text, re.I):
                d['findings'].append(dict(rule='no-candlestick', severity='high', file=rel, detail='candlestick chart'))
            for ln, line in enumerate(text.splitlines(), 1):
                low = line.lower()
                for m in HEX_RE.finditer(line):
                    h = norm_hex(m.group(0))
                    d['colors'][h] += 1
                    s, v = sat_val(h)
                    # 只在 hex 所属声明段（; 或 { 之后）里判 background，避免同行其他属性误报
                    seg_start = max(line.rfind(';', 0, m.start()), line.rfind('{', 0, m.start())) + 1
                    is_bg = 'background' in line[seg_start:m.start()].lower()
                    if is_bg and v < 0.35:
                        d['findings'].append(dict(rule='no-dark-bg', severity='critical', file=rel, line=ln, detail=f'dark background {h}'))
                    elif s > 0.75 and v > 0.75 and h not in PALETTE:
                        d['saturated_colors'][h] += 1
                        d['findings'].append(dict(rule='low-saturation-only', severity='medium', file=rel, line=ln, detail=f'saturated color {h}'))
                for m in RADIUS_RE.finditer(line):
                    px = to_px(m.group(1), m.group(2) or 'px')
                    d['radii'].append(px)
                    if px == 0:
                        d['findings'].append(dict(rule='no-square-corners', severity='high', file=rel, line=ln, detail='border-radius: 0'))
                for m in SHADOW_RE.finditer(line):
                    spec = m.group(1)
                    # 去掉颜色函数后按序取长度值：x y blur spread（px/rem 混合按原值比较，足够判断 blur 阈值）
                    bare = COLOR_FN_RE.sub('', spec)
                    lengths = [float(n) for n in re.findall(r'-?[\d.]+', bare)]
                    blur = lengths[2] if len(lengths) >= 3 else 0
                    strong_dark = False
                    for rm in RGBA_RE.finditer(spec):
                        parts = [p.strip() for p in rm.group(1).split(',')]
                        if len(parts) != 4:
                            continue
                        try:
                            alpha = float(parts[3])
                            rgb = [float(parts[i]) for i in range(3)]
                        except ValueError:
                            continue
                        if alpha > 0.15 and sum(rgb) / 3 < 80:
                            strong_dark = True
                    if strong_dark or (blur and blur < 6 and 'rgba' not in spec):
                        d['shadow_hard'] += 1
                        d['findings'].append(dict(rule='soft-shadows-only', severity='medium', file=rel, line=ln, detail=spec.strip()[:60]))
                    else:
                        d['shadow_soft'] += 1
                for m in FONTSIZE_RE.finditer(line):
                    px = to_px(*m.groups())
                    d['fonts'][px] += 1
                    if px < 10:
                        d['findings'].append(dict(rule='label-floor', severity='low', file=rel, line=ln, detail=f'font-size {px}px < 10px'))
    return d


def score(d):
    distinct = len(d['colors']) or 1
    palette_hits = sum(1 for c in d['colors'] if c in PALETTE)
    color = max(0, round(100 * palette_hits / distinct - 2 * len(d['saturated_colors'])))
    if d['radii']:
        full = sum(1 for r in d['radii'] if 18 <= r <= 24)
        half = sum(1 for r in d['radii'] if 8 <= r < 18 or 24 < r <= 32)
        radius = round(100 * (full + 0.5 * half) / len(d['radii']))
    else:
        radius = None
    total_shadow = d['shadow_soft'] + d['shadow_hard']
    shadow = round(100 * d['shadow_soft'] / total_shadow) if total_shadow else None
    total_fonts = sum(d['fonts'].values())
    font = round(100 * sum(v for k, v in d['fonts'].items() if k >= 10) / total_fonts) if total_fonts else None
    negatives = max(0, 100 - 5 * len(d['findings']))
    parts = {'硬性禁忌': negatives, '调色板': color, '圆角': radius, '阴影': shadow, '字体': font}
    valid = [v for v in parts.values() if v is not None]
    return parts, round(sum(valid) / len(valid)) if valid else 0


def report(d, scores, overall):
    L = [f"# 现代化审计报告 — {d['root']}", f"日期: {d['date']} · 扫描文件: {d['files_scanned']}", '']
    L.append(f"## 总分: {overall}/100\n")
    L.append('| 维度 | 得分 |')
    L.append('|---|---|')
    for k, v in scores.items():
        L.append(f"| {k} | {'n/a' if v is None else str(v)} |")
    L.append('')
    fs = d['findings']
    L.append(f"## 硬性禁忌与规范违规（{len(fs)} 条，展示前 {MAX_REPORT_FINDINGS} 条）\n")
    L.append('| 级别 | 规则 | 位置 | 详情 |')
    L.append('|---|---|---|---|')
    order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    for f in sorted(fs, key=lambda x: order.get(x['severity'], 9))[:MAX_REPORT_FINDINGS]:
        loc = f['file'] + (f":{f['line']}" if f.get('line') else '')
        L.append(f"| {f['severity']} | {f['rule']} | {loc} | {f['detail']} |")
    L.append('')
    distinct = len(d['colors'])
    hits = sum(1 for c in d['colors'] if c in PALETTE)
    L.append(f"## 调色板：命中规范 {hits}/{distinct} 种\n")
    L.append('Top 10 颜色: ' + ' '.join(f"`{c}`×{n}" for c, n in d['colors'].most_common(10)))
    if d['saturated_colors']:
        L.append('\n高饱和颜色（需降饱和）: ' + ' '.join(f"`{c}`" for c in d['saturated_colors']))
    by_rule = Counter(f['rule'] for f in fs)
    if by_rule:
        L.append('\n## 修复建议（按出现频次排序）\n')
        for rule, n in by_rule.most_common():
            L.append(f"- **{rule}**（{n} 处）: {ADVICE.get(rule, '见 SKILL.md 第 9 节')}")
    return '\n'.join(L)


def _fkey(f):
    return (f['rule'], f['file'], f.get('detail', '')[:40])


def compare(old, new):
    so, oo = old.get('scores', {}), old.get('overall', 0)
    sn, on = new.get('scores', {}), new.get('overall', 0)
    L = ["# 迁移进度报告", f"基线: {old.get('date', '?')} → 当前: {new.get('date', '?')}", '']
    L.append(f"## 总分: {oo} → {on}（{on - oo:+d}）\n")
    L.append('| 维度 | 基线 | 当前 | Δ |')
    L.append('|---|---|---|---|')
    for k in sn:
        a, b = so.get(k), sn.get(k)
        if a is None or b is None:
            L.append(f"| {k} | n/a | n/a | - |")
        else:
            L.append(f"| {k} | {a} | {b} | {b - a:+d} |")
    old_keys = {_fkey(f) for f in old.get('findings', [])}
    new_keys = {_fkey(f) for f in new.get('findings', [])}
    resolved = old_keys - new_keys
    added = new_keys - old_keys
    L.append(f"\n## Findings：已解决 {len(resolved)} · 新增 {len(added)} · 剩余 {len(new_keys)}\n")
    if added:
        L.append('### 新增问题')
        for rule, f, detail in sorted(added)[:20]:
            L.append(f"- `{rule}` {f} — {detail}")
    if new_keys:
        L.append('\n### 剩余 Top 问题')
        for rule, n in Counter(k[0] for k in new_keys).most_common(10):
            L.append(f"- **{rule}**（{n} 处）: {ADVICE.get(rule, '')}")
    return '\n'.join(L)


def snapshot(d, scores, overall):
    return {
        'date': d['date'], 'root': d['root'], 'files_scanned': d['files_scanned'],
        'overall': overall, 'scores': scores,
        'colors': d['colors'].most_common(50),
        'findings': d['findings'],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('root', nargs='?', default='.')
    p.add_argument('--format', choices=['markdown', 'json'], default='markdown')
    p.add_argument('--snapshot', metavar='OUT.json')
    p.add_argument('--compare', nargs=2, metavar=('OLD.json', 'NEW.json'))
    p.add_argument('--selfcheck', action='store_true')
    a = p.parse_args()

    if a.selfcheck:
        _selfcheck()
        return
    if a.compare:
        old, new = (json.load(open(f, encoding='utf-8')) for f in a.compare)
        print(compare(old, new))
        return

    d = scan(a.root)
    scores, overall = score(d)
    if a.snapshot:
        with open(a.snapshot, 'w', encoding='utf-8') as f:
            json.dump(snapshot(d, scores, overall), f, ensure_ascii=False, indent=2)
        print(f"snapshot -> {a.snapshot}（总分 {overall}/100，findings {len(d['findings'])} 条）", file=sys.stderr)
    if a.format == 'json':
        print(json.dumps(snapshot(d, scores, overall), ensure_ascii=False, indent=2))
    else:
        print(report(d, scores, overall))


if __name__ == '__main__':
    main()
