#!/usr/bin/env python3
"""Flag explicit fraction/percentage contradictions in UTF-8 reports.

Only expressions such as ``22/110 (39.6%)`` and ``39.6% (22/110)``
are checked. A finding is a candidate for source review, not proof of an
error: a stated percentage may use a different population or be adjusted.
Absence of findings does not establish numerical or scientific correctness.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import sys

NUMBER = r'\d+(?:\.\d+)?'
FRACTION = rf'(?P<num>\d+)\s*/\s*(?P<den>\d+)'
PERCENT = rf'(?P<pct>{NUMBER})\s*[%％]'
FORMS = (
    re.compile(rf'(?<![\d./]){FRACTION}\s*[（(]\s*{PERCENT}\s*[）)]'),
    re.compile(rf'(?<![\d.]){PERCENT}\s*[（(]\s*{FRACTION}\s*[）)]'),
)


def check(text: str) -> list[dict]:
    findings = []
    for line_number, line in enumerate(text.splitlines(), 1):
        for pattern in FORMS:
            for match in pattern.finditer(line):
                numerator = int(match.group('num'))
                denominator = int(match.group('den'))
                displayed = match.group('pct')
                if denominator == 0:
                    findings.append({'line': line_number, 'expression': match.group(),
                                     'kind': 'zero_denominator',
                                     'message': '分母为零，无法计算比例；请核对来源。'})
                    continue
                try:
                    percentage = Decimal(displayed)
                    actual = Decimal(numerator) * 100 / Decimal(denominator)
                except InvalidOperation:
                    continue
                decimals = len(displayed.partition('.')[2])
                rounding_margin = Decimal('0.5') * Decimal(10) ** -decimals
                if abs(actual - percentage) > rounding_margin:
                    findings.append({'line': line_number, 'expression': match.group(),
                                     'kind': 'percentage_mismatch',
                                     'numerator': numerator, 'denominator': denominator,
                                     'reported_percent': displayed,
                                     'calculated_percent': str(actual.quantize(Decimal('0.01'))),
                                     'message': '按所示分数计算的比例与标注不同；请核对分母、舍入及是否为调整后比例。'})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path, help='UTF-8 Markdown 或纯文本报告')
    parser.add_argument('--json', action='store_true', help='输出 JSON')
    args = parser.parse_args()
    try:
        text = args.report.read_text(encoding='utf-8-sig')
    except (OSError, UnicodeError) as exc:
        print(f'无法读取报告: {exc}', file=sys.stderr)
        return 2
    findings = check(text)
    if args.json:
        print(json.dumps({'file': str(args.report), 'findings': findings,
                          'scope': '仅检查相邻括号内的明确分数与百分比；不检查其他数字或科学正确性。'}, ensure_ascii=False, indent=2))
    else:
        print('检查范围：仅检查 22/110（39.6%）或 39.6%（22/110）形式的明确分数与百分比。')
        for finding in findings:
            print(f"第 {finding['line']} 行：{finding['expression']} — {finding['message']}")
        if not findings:
            print('未发现该形式的比例矛盾；其他数值及科学内容未由本工具验证。')
    return 1 if findings else 0


if __name__ == '__main__':
    raise SystemExit(main())
