"""Check original JATS XML and regenerate the source/rights catalog.

Usage: python catalog.py [--failure PMCID=exact_error ...]
The XML files are never changed. Only CATALOG.md is generated.
"""

import argparse
import hashlib
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
API = "https://www.ebi.ac.uk/europepmc/webservices/rest/{}/fullTextXML"
ARTICLE = "https://europepmc.org/articles/{}"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"

GROUPS = {
    "design": [
        "PMC13200605", "PMC13063910", "PMC12969494", "PMC12873732",
        "PMC13082699", "PMC13134233", "PMC13068213", "PMC12970100",
    ],
    "results": [
        "PMC11674246", "PMC11701235", "PMC11727367",
        "PMC11688440", "PMC11695244", "PMC11655176",
    ],
    "boundary": ["PMC11664210", "PMC11703835", "PMC11689214"],
}
NOTES = {
    "PMC12970100": "设计组边界：非随机观察性/自然实施评估方案；并非随机受控实验。",
    "PMC11727367": "结果组边界：多项既有研究的合并再分析，非新实施实验。",
    "PMC11664210": "体裁边界：植被恢复类型与土壤温室气体的现场比较，不称严格受控实验。",
    "PMC11703835": "体裁边界：母亲与残障儿童兄弟姐妹心理健康的观察研究，不称严格受控实验。",
    "PMC11689214": "体裁边界：远程触觉交互的质性/互动研究，不称严格受控实验。",
}


def text(node):
    return " ".join("".join(node.itertext()).split()) if node is not None else ""


def authors(meta):
    people = []
    for group in meta.findall("./contrib-group"):
        for contrib in group.findall("./contrib"):
            if contrib.get("contrib-type") not in (None, "author") and group.get("content-type") != "author":
                continue
            name = contrib.find("./name")
            if name is not None:
                given = text(name.find("./given-names"))
                surname = text(name.find("./surname"))
                people.append(" ".join(part for part in (given, surname) if part))
            else:
                people.append(text(contrib.find("./collab")))
    return ", ".join(person for person in people if person)


def entry(identifier, group):
    file = ROOT / group / f"{identifier}.xml"
    raw = file.read_bytes()
    root = ET.fromstring(raw)
    if root.tag != "article":
        raise ValueError(f"{identifier}: root tag {root.tag!r} is not article")
    meta = root.find("./front/article-meta")
    if meta is None:
        raise ValueError(f"{identifier}: article-meta missing")
    pmcids = [text(tag) for tag in meta.findall("./article-id[@pub-id-type='pmcid']")]
    if pmcids != [identifier]:
        raise ValueError(f"{identifier}: embedded PMCID {pmcids!r}")
    body = root.find("./body")
    if len(text(body)) < 100:
        raise ValueError(f"{identifier}: body missing or empty")
    refs = root.findall(".//ref-list/ref")
    if not refs:
        raise ValueError(f"{identifier}: references missing")
    license_nodes = meta.findall("./permissions/license")
    licenses = []
    for node in license_nodes:
        declaration = " ".join(" ".join(node.itertext()).split())
        embedded_link = next((child.get(XLINK_HREF) for child in node.iter() if child.get(XLINK_HREF)), "")
        literal_link = re.search(r"https?://creativecommons\.org/licenses/by/[0-9.]+/", declaration, re.I)
        licenses.append((declaration, node.get(XLINK_HREF, "") or embedded_link or (literal_link.group(0) if literal_link else "")))
    if not licenses:
        raise ValueError(f"{identifier}: no article-level XML license")
    # CC BY-NC, CC BY-ND and CC BY-SA must never be silently mapped to CC BY.
    evidence = " ".join(t + " " + href for t, href in licenses)
    if re.search(r"\b(?:CC BY-(?:NC|ND|SA)|Attribution-NonCommercial|Attribution-NoDerivatives|by-(?:nc|nd|sa))", evidence, re.I):
        raise ValueError(f"{identifier}: restricted/different CC license in article XML")
    if not re.search(r"\bCC BY\b|Creative Commons Attribution(?: 4\.0 International)? License|creativecommons\.org/licenses/by/", evidence, re.I):
        raise ValueError(f"{identifier}: explicit CC BY grant absent from article XML")
    title = text(meta.find("./title-group/article-title"))
    creator = authors(meta)
    dois = [text(tag) for tag in meta.findall("./article-id[@pub-id-type='doi']")]
    if not title or not creator or len(dois) != 1 or not dois[0]:
        raise ValueError(f"{identifier}: title/authors/DOI missing")
    statement = text(meta.find("./permissions/copyright-statement"))
    holder = text(meta.find("./permissions/copyright-holder"))
    year = text(meta.find("./permissions/copyright-year"))
    copyrights = "; ".join(part for part in (statement, ("Copyright holder: " + holder) if holder else "", ("Copyright year: " + year) if year else "") if part)
    txt_file = ROOT / group / f"{identifier}.txt"
    txt_raw = txt_file.read_bytes()
    if not txt_raw.strip():
        raise ValueError(f"{identifier}: extracted TXT missing or empty")
    return {
        "id": identifier, "group": group, "path": f"{group}/{identifier}.xml",
        "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
        "txt_path": f"{group}/{identifier}.txt", "txt_sha256": hashlib.sha256(txt_raw).hexdigest(), "txt_bytes": len(txt_raw),
        "title": title, "authors": creator, "doi": dois[0],
        "type": root.attrib.get("article-type", "not specified"),
        "copyright": copyrights or "No separate copyright statement in the article XML; see XML <permissions>.",
        "licenses": licenses, "references": len(refs),
    }


def md(s):
    return s.replace("|", "\\|").replace("\n", " ")


def render(entries, failures):
    lines = [
        "# 原始 JATS 全文语料目录", "",
        f"已保存 **{len(entries)}/17 篇**原样 XML（设计 {sum(e['group']=='design' for e in entries)}；结果 {sum(e['group']=='results' for e in entries)}；边界 {sum(e['group']=='boundary' for e in entries)}）。",
        "所有文件均通过 XML 内 PMCID、明确 CC BY 授权、非空 `<body>` 和非空 `<ref-list>` 检查；每篇 SHA-256 对应本目录实际保存的原始字节。",
        "设计组八篇按原样复制自先前获取的 Europe PMC JATS 文件，其中 `design/PMC12970100.xml` 为观察性边界反例；其余九篇从下述逐篇 Europe PMC `fullTextXML` URL 获取，未改变响应体字节。",
        "每篇同名 `.txt` 是先前生成、此处原样复制的**非原件提取文本**，并非本次从 XML 转换所得；设计组来自本地 `corpus/design/text/`，其余来自本地 `corpus/results/fulltext/`。TXT 可能不含参考文献、版权或许可声明，也可能与此次 JATS 获取版本不同；核对完整正文与参考文献、版权和许可时**只以原始 XML 为准**。",
        "", "**内容边界：**XML 包含文章文字、表格、图题和参考文献（具体以各文件为准）；它**不包含图片像素/PDF/补充文件**，不是完整出版包。未下载或再分发任何许可未单独确认的图片与补充材料。文件中的原作者、原文版权和许可声明未修改；如图表或第三方材料标注不同权利，请遵从原文具体署名/许可要求。", "",
        "**体裁边界：**`design/` 含研究设计/方案，不应当成已经观察到的结果，其中 PMC12970100 是非随机观察性反例；`results/PMC11727367.xml` 是既有研究合并再分析而非新实验；`boundary/` 三篇均不得宣称严格受控实验。体裁分类仅用于选例，不是原作者的许可声明。",
        "## 逐篇索引", "",
        "| 分组 / PMCID | 原标题 | 作者 | DOI | XML article-type | SHA-256 |", "| --- | --- | --- | --- | --- | --- |",
    ]
    for e in entries:
        lines.append("| {group} / [{id}]({path}) | {title} | {authors} | [{doi}](https://doi.org/{doi}) | {type} | `{sha256}` |".format(**{key: md(str(value)) for key, value in e.items()}))
    lines.extend(["", "## 来源、版权与许可原文（逐篇）", "",
                  "许可原文下列文字由 XML `<license>` 的可见文字合并空白而来；非改写许可，不补写未在 XML 指明的许可版本。URL 来自 XML `<license>` 自身/内部链接的 `xlink:href` 或许可文字中的原始 URL（若无，明确标注）；完整标签及版权仍在原 XML。", ""])
    for e in entries:
        lines.extend([
            f"### {e['id']} · {e['group']}", "",
            f"- 文件：`{e['path']}`；大小：{e['bytes']} 字节；SHA-256：`{e['sha256']}`。",
            f"- 非原件提取文本：[{e['txt_path']}]({e['txt_path']})；大小：{e['txt_bytes']} 字节；SHA-256：`{e['txt_sha256']}`；可能省略参考文献/版权/许可，不能替代 XML。",
            f"- 原文：[Europe PMC 文章页]({ARTICLE.format(e['id'])})；[原始全文 XML 接口]({API.format(e['id'])})。",
            f"- 原标题：{e['title']}", f"- 作者：{e['authors']}",
            f"- DOI：[{e['doi']}](https://doi.org/{e['doi']})；原始 JATS article-type：`{e['type']}`；参考文献条目：{e['references']}。",
            f"- 版权原文/字段：{e['copyright']}",
        ])
        for license_text, href in e["licenses"]:
            lines.append(f"- 许可原文：{license_text or '(XML license contains no text; see its link)'}")
            lines.append(f"- 许可链接（原 XML）：{href or 'XML 未提供许可 URL；不要推定许可版本。'}")
        if e["id"] in NOTES:
            lines.append(f"- 体裁标记：{NOTES[e['id']]}")
        lines.append("")
    lines.extend([
        "## 权利排除与获取失败", "",
        "- **未收录 PMC11685986**（DOI `10.1038/s41598-024-83704-w`）：先前取得的原文许可声明为 Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International（[CC BY-NC-ND 4.0](http://creativecommons.org/licenses/by-nc-nd/4.0/)），不是 unrestricted CC BY。",
        "- **未收录 PMC11686207**（DOI `10.1038/s41598-024-83282-x`）：先前取得的原文同样标注 [CC BY-NC-ND 4.0](http://creativecommons.org/licenses/by-nc-nd/4.0/)，不是 unrestricted CC BY。",
        "- 排除依据为先前采集的 [PMC11685986](https://europepmc.org/articles/PMC11685986) 和 [PMC11686207](https://europepmc.org/articles/PMC11686207) 的全文版权声明；不把非商业/禁止演绎条款抹除，也未纳入两篇 XML。",
    ])
    if failures:
        lines.extend(["- 下列请求失败，未假称取得原文："] + [f"  - `{identifier}`：{error}" for identifier, error in failures.items()])
    else:
        lines.append("- 本次九篇新增原始 XML 获取：无失败。")
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--failure", action="append", default=[], metavar="PMCID=ERROR")
    args = parser.parse_args()
    failures = dict(item.split("=", 1) for item in args.failure)
    entries = []
    for group, identifiers in GROUPS.items():
        for identifier in identifiers:
            if identifier in failures:
                continue
            entries.append(entry(identifier, group))
    (ROOT / "CATALOG.md").write_text(render(entries, failures), encoding="utf-8", newline="\n")
    for e in entries:
        print(f"VERIFIED {e['id']} {e['group']} {e['sha256']} license={'; '.join(href or 'no URL' for _, href in e['licenses'])}")
    print(f"CATALOG {len(entries)} XML; {len(failures)} failures")


if __name__ == "__main__":
    main()
