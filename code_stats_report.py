# -*- coding: utf-8 -*-
"""
代码量统计工具 - 自动生成可视化 HTML 报告
运行后选择文件夹，自动统计代码量并生成 report 网页（含柱状图、表格、函数分布）

使用方式：
    python code_stats_report.py
"""
import os
import re
import csv
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox
from collections import defaultdict
from statistics import mean, median
from datetime import datetime

# ============ 配置 ============
LANG_EXT = {
    'C':      ['.c', '.h'],
    'C++':    ['.cpp', '.hpp', '.cc', '.cxx', '.hh'],
    'JAVA':   ['.java'],
    'Python': ['.py'],
    'C#':     ['.cs'],
}
LINE_COMMENT = {'C': '//', 'C++': '//', 'JAVA': '//', 'C#': '//', 'Python': '#'}
BLOCK_COMMENT = {'C': ('/*', '*/'), 'C++': ('/*', '*/'), 'JAVA': ('/*', '*/'),
                 'C#': ('/*', '*/'), 'Python': ('"""', '"""')}


def detect_lang(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    for lang, exts in LANG_EXT.items():
        if ext in exts:
            return lang
    return None


def analyze_file(filepath, lang):
    """一次遍历统计：代码行/空行/注释行 + 函数个数与长度"""
    code = blank = comment = 0
    func_count = 0
    func_lengths = []
    in_block = False
    cur_func = 0
    in_func = False
    block_start, block_end = BLOCK_COMMENT[lang]
    line_comment = LINE_COMMENT[lang]

    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            s = line.strip()

            # --- 行数统计 ---
            if in_block:
                comment += 1
                if block_end in s:
                    in_block = False
                if in_func:
                    cur_func += 1
                continue
            if s == '':
                blank += 1
                if in_func:
                    cur_func += 1
                continue
            if s.startswith(line_comment):
                comment += 1
                if in_func:
                    cur_func += 1
                continue
            if s.startswith(block_start):
                comment += 1
                if block_end not in s:
                    in_block = True
                if in_func:
                    cur_func += 1
                continue
            code += 1

            # --- 函数统计 ---
            if lang == 'Python':
                match = re.match(r'def\s+\w+\s*\(', s)
            else:
                match = re.match(
                    r'^(?:static\s+|public\s+|private\s+|protected\s+|virtual\s+|override\s+)*'
                    r'(?:void|int|char|float|double|bool|long|short|string|auto|\w+::\w+)\s+'
                    r'\w+\s*\([^;]*\)\s*[{:]?$', s)
            if match:
                if in_func:
                    func_lengths.append(cur_func)
                func_count += 1
                in_func = True
                cur_func = 1
            elif in_func:
                cur_func += 1

    if in_func:
        func_lengths.append(cur_func)
    return code, blank, comment, func_count, func_lengths


def scan_directory(root_dir):
    """扫描目录，返回汇总 stats 和文件明细 details"""
    stats = defaultdict(lambda: {'files': 0, 'code': 0, 'blank': 0, 'comment': 0,
                                 'funcs': 0, 'lengths': []})
    details = defaultdict(list)  # lang -> [(相对路径, code, blank, comment, funcs)]
    for dirpath, _, filenames in os.walk(root_dir):
        for fn in filenames:
            fp = os.path.join(dirpath, fn)
            lang = detect_lang(fp)
            if not lang:
                continue
            c, b, cm, fc, fl = analyze_file(fp, lang)
            s = stats[lang]
            s['files'] += 1
            s['code'] += c
            s['blank'] += b
            s['comment'] += cm
            s['funcs'] += fc
            s['lengths'].extend(fl)
            rel = os.path.relpath(fp, root_dir)
            details[lang].append((rel, c, b, cm, fc))
    return stats, details


def build_report_html(stats, details, root_dir, csv_names=None):
    """生成可视化 HTML 报告
    csv_names: (汇总csv文件名, 明细csv文件名)，用于报告内下载链接"""
    langs = ['C', 'C++', 'JAVA', 'Python', 'C#']
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    # CSV 下载链接（如果有）
    csv_links = ''
    if csv_names:
        sum_name, det_name = csv_names
        csv_links = f'''
    <div style="margin-bottom:20px;">
      <a class="btn" href="{sum_name}" download>📥 下载汇总表 (CSV)</a>
      <a class="btn" href="{det_name}" download>📥 下载文件明细 (CSV)</a>
    </div>'''

    # 汇总数字
    total_files = sum(s['files'] for s in stats.values())
    total_code = sum(s['code'] for s in stats.values())
    total_comment = sum(s['comment'] for s in stats.values())
    total_funcs = sum(s['funcs'] for s in stats.values())

    # --- 柱状图数据（各语言代码行数）---
    max_code = max((s['code'] for s in stats.values()), default=1)
    bars = ''
    for lang in langs:
        s = stats.get(lang)
        if not s:
            continue
        w = round(s['code'] / max_code * 100, 1)
        bars += f'''
        <div class="bar-row">
          <div class="bar-label">{lang}</div>
          <div class="bar-track">
            <div class="bar-fill" style="width:{w}%"></div>
          </div>
          <div class="bar-value">{s["code"]}</div>
        </div>'''

    # --- 详细表格 ---
    rows = ''
    for lang in langs:
        s = stats.get(lang)
        if not s:
            rows += f'<tr><td>{lang}</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td><td>-</td><td>-</td><td>-</td><td>-</td></tr>'
            continue
        lengths = s['lengths']
        mx = max(lengths) if lengths else '-'
        mn = min(lengths) if lengths else '-'
        avg = round(mean(lengths), 1) if lengths else '-'
        med = median(lengths) if lengths else '-'
        rows += (f'<tr><td><b>{lang}</b></td><td>{s["files"]}</td><td>{s["code"]}</td>'
                 f'<td>{s["blank"]}</td><td>{s["comment"]}</td><td>{s["funcs"]}</td>'
                 f'<td>{mx}</td><td>{mn}</td><td>{avg}</td><td>{med}</td></tr>')

    # --- 函数长度分布（分桶）---
    buckets = [(1, 10), (11, 20), (21, 30), (31, 40), (41, 10 ** 9)]
    bucket_names = ['1~10', '11~20', '21~30', '31~40', '40+']
    func_dist = ''
    for lang in langs:
        s = stats.get(lang)
        if not s or not s['lengths']:
            continue
        counts = [0] * len(buckets)
        for L in s['lengths']:
            for i, (lo, hi) in enumerate(buckets):
                if lo <= L <= hi:
                    counts[i] += 1
                    break
        max_c = max(counts) or 1
        dist_bars = ''
        for i, name in enumerate(bucket_names):
            w = round(counts[i] / max_c * 100, 1)
            dist_bars += f'''
            <div class="dist-row">
              <span class="dist-name">{name}行</span>
              <div class="bar-track"><div class="bar-fill alt" style="width:{w}%"></div></div>
              <span class="dist-val">{counts[i]}</span>
            </div>'''
        func_dist += f'''
        <div class="dist-card">
          <h3>{lang} · 函数长度分布（共 {s["funcs"]} 个函数）</h3>
          {dist_bars}
        </div>'''

    # --- 文件级明细（折叠）---
    detail_html = ''
    for lang in langs:
        if lang not in details:
            continue
        file_rows = ''
        for rel, c, b, cm, fc in sorted(details[lang]):
            file_rows += (f'<tr><td class="fname">{rel}</td><td>{c}</td><td>{b}</td>'
                          f'<td>{cm}</td><td>{fc}</td></tr>')
        detail_html += f'''
        <details class="detail-block">
          <summary>{lang} · {len(details[lang])} 个文件</summary>
          <table>
            <thead><tr><th class="fname">文件</th><th>代码行</th><th>空行</th><th>注释</th><th>函数</th></tr></thead>
            <tbody>{file_rows}</tbody>
          </table>
        </details>'''

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>代码量统计报告</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
         background: #f5f0e6; padding: 30px 20px; }}
  .container {{ max-width: 960px; margin: 0 auto; }}
  h1 {{ color: #2d5a3d; font-size: 26px; margin-bottom: 6px; }}
  .meta {{ color: #888; font-size: 13px; margin-bottom: 24px; }}
  .card {{ background: #fff; border-radius: 12px; padding: 24px;
          box-shadow: 0 4px 16px rgba(0,0,0,0.06); margin-bottom: 20px; }}
  .card h2 {{ color: #2d5a3d; font-size: 18px; margin-bottom: 16px;
             border-left: 4px solid #2d5a3d; padding-left: 10px; }}
  .overview {{ display: flex; gap: 14px; flex-wrap: wrap; }}
  .ov-item {{ flex: 1; min-width: 150px; background: #eef5ee; border-radius: 10px;
             padding: 16px; text-align: center; }}
  .ov-item .num {{ font-size: 30px; font-weight: 800; color: #2d5a3d; }}
  .ov-item .lab {{ font-size: 13px; color: #666; margin-top: 4px; }}

  .bar-row {{ display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }}
  .bar-label {{ width: 64px; font-weight: 700; color: #444; text-align: right; }}
  .bar-track {{ flex: 1; background: #f0ead8; border-radius: 6px; height: 26px; overflow: hidden; }}
  .bar-fill {{ height: 100%; background: linear-gradient(90deg, #3a7050, #2d5a3d);
              border-radius: 6px; min-width: 2px; }}
  .bar-fill.alt {{ background: linear-gradient(90deg, #8aa98a, #5f8a5f); }}
  .bar-value {{ width: 56px; font-weight: 700; color: #2d5a3d; }}

  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th, td {{ padding: 9px 8px; text-align: center; border-bottom: 1px solid #eee; }}
  th {{ background: #2d5a3d; color: #fff; font-weight: 600; }}
  tr:nth-child(even) {{ background: #f9f7f2; }}
  tr:hover {{ background: #eef5ee; }}

  .dist-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  .dist-card {{ background: #faf8f2; border-radius: 10px; padding: 16px; }}
  .dist-card h3 {{ font-size: 14px; color: #444; margin-bottom: 12px; }}
  .dist-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }}
  .dist-name {{ width: 52px; font-size: 12px; color: #888; text-align: right; }}
  .dist-val {{ width: 30px; font-size: 12px; font-weight: 700; color: #444; }}

  .detail-block {{ margin-bottom: 10px; }}
  .detail-block summary {{ cursor: pointer; font-weight: 700; color: #2d5a3d;
                          padding: 8px; background: #eef5ee; border-radius: 8px; }}
  .detail-block table {{ margin-top: 10px; }}
  .fname {{ text-align: left; font-family: Consolas, monospace; font-size: 13px; }}

  .note {{ font-size: 13px; color: #777; line-height: 1.8; }}
  .note li {{ margin-left: 18px; }}
  .btn {{ display: inline-block; padding: 9px 16px; background: #2d5a3d; color: #fff;
          border-radius: 8px; text-decoration: none; font-size: 14px; margin-right: 10px; }}
  .btn:hover {{ background: #3a7050; }}
  @media (max-width: 700px) {{ .dist-grid {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<div class="container">
  <h1>📊 代码量统计报告</h1>
  <div class="meta">统计时间：{now} ｜ 统计目录：{root_dir}</div>
  {csv_links}

  <div class="card">
    <h2>总体概览</h2>
    <div class="overview">
      <div class="ov-item"><div class="num">{total_files}</div><div class="lab">源文件总数</div></div>
      <div class="ov-item"><div class="num">{total_code}</div><div class="lab">代码行总数</div></div>
      <div class="ov-item"><div class="num">{total_comment}</div><div class="lab">注释行总数</div></div>
      <div class="ov-item"><div class="num">{total_funcs}</div><div class="lab">函数总数</div></div>
    </div>
  </div>

  <div class="card">
    <h2>各语言代码量</h2>
    {bars}
  </div>

  <div class="card">
    <h2>详细统计表</h2>
    <table>
      <thead><tr><th>语言</th><th>源文件数</th><th>代码行数</th><th>空行数</th><th>注释行数</th>
      <th>函数个数</th><th>最大值</th><th>最小值</th><th>均值</th><th>中位数</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>

  <div class="card">
    <h2>函数长度分布</h2>
    <div class="dist-grid">{func_dist}</div>
  </div>

  <div class="card">
    <h2>文件级明细</h2>
    {detail_html}
  </div>

  <div class="card">
    <h2>统计口径说明</h2>
    <ul class="note">
      <li>代码行数：去掉空行、纯注释行后的有效代码行。</li>
      <li>空行数：空白行（无任何字符）。</li>
      <li>注释行数：单行注释（//、#）及块注释（/* */、三引号 docstring）覆盖的行。</li>
      <li>函数个数：按常见函数定义形式识别（Python 的 def；C 系语言的返回类型 + 函数名 + 括号）。</li>
      <li>最大值/最小值/均值/中位数：统计每个函数的<strong>行数</strong>。</li>
    </ul>
  </div>
</div>
</body>
</html>'''
    return html


def export_csv(stats, details, base_dir):
    """导出两个 CSV：汇总表 + 文件明细表。返回 (汇总文件名, 明细文件名)。
    使用 utf-8-sig 编码，Excel 打开中文不乱码。"""
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    langs = ['C', 'C++', 'JAVA', 'Python', 'C#']

    # 1) 汇总表
    sum_name = f'代码统计汇总_{ts}.csv'
    with open(os.path.join(base_dir, sum_name), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['语言', '源文件数', '代码行数', '空行数', '注释行数',
                    '函数个数', '最大值', '最小值', '均值', '中位数'])
        for lang in langs:
            s = stats.get(lang)
            if not s:
                w.writerow([lang, 0, 0, 0, 0, 0, '-', '-', '-', '-'])
                continue
            lengths = s['lengths']
            mx = max(lengths) if lengths else '-'
            mn = min(lengths) if lengths else '-'
            avg = round(mean(lengths), 1) if lengths else '-'
            med = median(lengths) if lengths else '-'
            w.writerow([lang, s['files'], s['code'], s['blank'], s['comment'],
                        s['funcs'], mx, mn, avg, med])

    # 2) 文件明细表
    det_name = f'代码统计明细_{ts}.csv'
    with open(os.path.join(base_dir, det_name), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['语言', '文件路径', '代码行数', '空行数', '注释行数', '函数个数'])
        for lang in langs:
            for rel, c, b, cm, fc in sorted(details.get(lang, [])):
                w.writerow([lang, rel, c, b, cm, fc])

    return sum_name, det_name


def main():
    # 弹出文件夹选择框
    root = tk.Tk()
    root.withdraw()
    root_dir = filedialog.askdirectory(title='选择要统计的文件夹')
    if not root_dir:
        return

    print(f'正在统计：{root_dir}')
    stats, details = scan_directory(root_dir)

    # 导出 CSV（汇总 + 明细）
    csv_names = export_csv(stats, details, os.path.dirname(os.path.abspath(__file__)))

    # 生成 HTML 报告（带 CSV 下载链接）
    html = build_report_html(stats, details, root_dir, csv_names)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            f'代码统计报告_{ts}.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'报告已生成：{out_path}')
    print(f'CSV 已生成：{csv_names[0]}、{csv_names[1]}')
    messagebox.showinfo('完成',
                        f'统计完成！\n\n报告：{out_path}\n\nCSV 汇总表：{csv_names[0]}\nCSV 明细表：{csv_names[1]}')
    webbrowser.open('file:///' + out_path.replace('\\', '/'))


if __name__ == '__main__':
    main()
