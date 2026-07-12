"""Deterministic Markdown-to-LaTeX conversion for the verified paper draft."""

from __future__ import annotations

import json
import re
from pathlib import Path

CITE_RE = re.compile(r"\[cite:([A-Za-z0-9_-]+)\]")
EVIDENCE_TAG_RE = re.compile(r"\[(E-[A-Z]+-\d{3}[^\]]*)\]")
CODE_SPAN_RE = re.compile(r"`([^`]+)`")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
ITALIC_RE = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")

TEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}
UNICODE_REPLACEMENTS = {
    "×": r"$\times$",
    "→": r"$\rightarrow$",
    "≥": r"$\geq$",
    "≤": r"$\leq$",
}


def escape_tex(text: str) -> str:
    out = []
    for char in text:
        if char in TEX_ESCAPES:
            out.append(TEX_ESCAPES[char])
        elif char in UNICODE_REPLACEMENTS:
            out.append(UNICODE_REPLACEMENTS[char])
        else:
            out.append(char)
    return "".join(out)


def convert_inline(text: str) -> str:
    """Escape TeX specials, then apply markdown inline markup."""
    spans: list[str] = []

    def stash(match: re.Match) -> str:
        spans.append(match.group(1))
        return f"@@CODESPAN{len(spans) - 1}@@"

    text = CODE_SPAN_RE.sub(stash, text)
    text = escape_tex(text)
    text = BOLD_RE.sub(r"\\textbf{\1}", text)
    text = ITALIC_RE.sub(r"\\emph{\1}", text)
    text = CITE_RE.sub(r"\\citep{\1}", text)
    text = EVIDENCE_TAG_RE.sub(lambda m: r"\evtag{" + m.group(1) + "}", text)
    for index, span in enumerate(spans):
        text = text.replace(f"@@CODESPAN{index}@@", r"\texttt{" + escape_tex(span) + "}")
    return text


def convert_table(rows: list[str]) -> list[str]:
    parsed = []
    for row in rows:
        cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
        parsed.append(cells)
    if len(parsed) >= 2 and all(set(cell) <= set("-: ") for cell in parsed[1]):
        header, body = parsed[0], parsed[2:]
    else:
        header, body = parsed[0], parsed[1:]
    columns = len(header)
    spec = "X" * columns
    lines = [
        r"\begin{table}[ht]",
        r"\small",
        r"\begin{tabularx}{\textwidth}{" + spec + "}",
        r"\toprule",
        " & ".join(convert_inline(cell) for cell in header) + r" \\",
        r"\midrule",
    ]
    for cells in body:
        cells = cells + [""] * (columns - len(cells))
        lines.append(" & ".join(convert_inline(cell) for cell in cells[:columns]) + r" \\")
    lines += [r"\bottomrule", r"\end{tabularx}", r"\end{table}"]
    return lines


def markdown_to_latex_body(md_text: str) -> tuple[str, str, str]:
    """Return (title, abstract_tex, body_tex) from the verified draft markdown."""
    lines = md_text.splitlines()
    title = "Untitled"
    sections: list[tuple[str, list[str]]] = []
    current: list[str] | None = None
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph and current is not None:
            current.append(convert_inline(" ".join(paragraph)))
            current.append("")
        paragraph.clear()

    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("# ") and not line.startswith("## "):
            flush_paragraph()
            title = line[2:].strip()
            index += 1
            continue
        if line.startswith("## ") and not line.startswith("### "):
            flush_paragraph()
            current = []
            sections.append((line[3:].strip(), current))
            index += 1
            continue
        if current is None:
            index += 1
            continue
        if not line.strip():
            flush_paragraph()
            index += 1
            continue
        if line.strip().startswith("```"):
            flush_paragraph()
            block: list[str] = [r"\begin{verbatim}"]
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                block.append(lines[index])
                index += 1
            block.append(r"\end{verbatim}")
            current.extend(block)
            index += 1
            continue
        if line.strip().startswith("|"):
            flush_paragraph()
            rows = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(lines[index])
                index += 1
            current.extend(convert_table(rows))
            continue
        if line.startswith("### "):
            flush_paragraph()
            current.append(r"\subsection{" + convert_inline(line[4:].strip()) + "}")
            index += 1
            continue
        image = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", line.strip())
        if image is not None:
            flush_paragraph()
            caption, path = image.group(1), image.group(2)
            current += [
                r"\begin{figure}[ht]",
                r"\centering",
                r"\includegraphics[width=\linewidth]{" + path + "}",
                r"\caption{" + convert_inline(caption) + "}",
                r"\end{figure}",
            ]
            index += 1
            continue
        if line.lstrip().startswith("- "):
            flush_paragraph()
            items: list[str] = []
            while index < len(lines) and lines[index].lstrip().startswith("- "):
                items.append(lines[index].lstrip()[2:].strip())
                index += 1
            current.append(r"\begin{itemize}")
            current.extend(r"\item " + convert_inline(item) for item in items)
            current.append(r"\end{itemize}")
            continue
        paragraph.append(line.strip())
        index += 1
    flush_paragraph()

    abstract_tex = ""
    body_parts: list[str] = []
    for name, content in sections:
        text = "\n".join(content).strip()
        if name.lower() == "abstract":
            abstract_tex = text
            continue
        body_parts.append(r"\section{" + convert_inline(name) + "}")
        body_parts.append(text)
    return title, abstract_tex, "\n\n".join(body_parts)


def cited_keys(md_text: str) -> list[str]:
    return sorted(set(CITE_RE.findall(md_text)))


def build_bibliography(keys: list[str], references: dict) -> tuple[str, list[str]]:
    """Return (bibtex, unresolved_keys). Missing keys get explicit placeholders."""
    entries: list[str] = []
    unresolved: list[str] = []
    for key in keys:
        entry = references.get(key)
        if not isinstance(entry, dict) or "title" not in entry:
            unresolved.append(key)
            entries.append(
                "@misc{" + key + ",\n"
                "  title = {[UNRESOLVED CITATION: " + key + "]},\n"
                "  note = {Placeholder generated by paper-writer; resolve with a "
                "verified source before submission}\n}"
            )
            continue
        fields = ["  title = {" + entry["title"] + "}"]
        if entry.get("authors"):
            fields.append("  author = {" + entry["authors"] + "}")
        if entry.get("year"):
            fields.append("  year = {" + str(entry["year"]) + "}")
        if entry.get("venue"):
            fields.append("  howpublished = {" + entry["venue"] + "}")
        if entry.get("url"):
            fields.append(r"  url = {" + entry["url"] + "}")
        if entry.get("note"):
            fields.append("  note = {" + entry["note"] + "}")
        entries.append("@misc{" + key + ",\n" + ",\n".join(fields) + "\n}")
    return "\n\n".join(entries) + "\n", unresolved


def build_latex_document(
    *,
    title: str,
    abstract_tex: str,
    body_tex: str,
    venue_name: str,
    bib_stem: str,
    official_style: str | None = None,
    official_bst: str | None = None,
    style_family: str | None = None,
) -> str:
    if official_style and style_family == "icml":
        # ICML is two-column: tables produced at \textwidth must span both
        # columns via table*, and the title block is the \twocolumn[...] header.
        body_tex = body_tex.replace(r"\begin{table}[ht]", r"\begin{table*}[t]")
        body_tex = body_tex.replace(r"\end{table}", r"\end{table*}")
        preamble = [
            "% Generated by the ouroboros paper-writer plugin.",
            f"% Using the official venue template: {official_style}.sty",
            "% Submission mode is anonymous; camera-ready switches to"
            f" \\usepackage[accepted]{{{official_style}}}.",
            r"\documentclass{article}",
            r"\usepackage{microtype}",
            r"\usepackage{graphicx}",
            r"\usepackage{booktabs}",
            r"\usepackage{tabularx}",
            r"\usepackage{hyperref}",
            r"\usepackage{" + official_style + "}",
            r"\newcommand{\evtag}[1]{{\scriptsize\texttt{[#1]}}}",
            "",
            r"\icmltitlerunning{" + convert_inline(title) + "}",
        ]
        bib_style = official_bst or "plainnat"
        return "\n".join(
            preamble
            + [
                "",
                r"\begin{document}",
                "",
                r"\twocolumn[",
                r"\icmltitle{" + convert_inline(title) + "}",
                r"\begin{icmlauthorlist}",
                r"\icmlauthor{Anonymous Authors}{anon}",
                r"\end{icmlauthorlist}",
                r"\icmlaffiliation{anon}{Anonymous Institution}",
                r"\icmlcorrespondingauthor{Anonymous Authors}{anon@example.com}",
                r"\icmlkeywords{agent evaluation, claim verification, reliability}",
                r"\vskip 0.3in",
                r"]",
                r"\printAffiliationsAndNotice{}",
                "",
                r"\begin{abstract}",
                abstract_tex,
                r"\end{abstract}",
                "",
                body_tex,
                "",
                r"\bibliographystyle{" + bib_style + "}",
                r"\bibliography{" + bib_stem + "}",
                "",
                r"\end{document}",
                "",
            ]
        )
    if official_style:
        preamble = [
            "% Generated by the ouroboros paper-writer plugin.",
            f"% Using the official venue template: {official_style}.sty",
            "% \\iclrfinalcopy stays commented out for anonymous submission.",
            r"\documentclass{article}",
            r"\usepackage{" + official_style + ",times}",
            r"\usepackage{hyperref}",
            r"\usepackage{url}",
            r"\usepackage{graphicx}",
            r"\usepackage{booktabs}",
            r"\usepackage{tabularx}",
            r"\newcommand{\evtag}[1]{{\scriptsize\texttt{[#1]}}}",
            "",
            r"\title{" + convert_inline(title) + "}",
            r"\author{Anonymous authors\\Paper under double-blind review}",
            "",
            r"%\iclrfinalcopy % Uncomment for camera-ready only.",
        ]
        bib_style = official_bst or "plainnat"
    else:
        preamble = [
            "% Generated by the ouroboros paper-writer plugin.",
            "% Preprint layout approximating " + venue_name + ". For submission,",
            "% switch to the official venue style file (e.g. \\usepackage{iclr<year>})",
            "% and re-check the current CFP formatting rules.",
            r"\documentclass[10pt,letterpaper]{article}",
            r"\usepackage[margin=1in]{geometry}",
            r"\usepackage[numbers]{natbib}",
            r"\usepackage{booktabs}",
            r"\usepackage{tabularx}",
            r"\usepackage{graphicx}",
            r"\usepackage[hidelinks]{hyperref}",
            r"\newcommand{\evtag}[1]{{\scriptsize\texttt{[#1]}}}",
            r"\setlength{\parskip}{4pt}",
            "",
            r"\title{" + convert_inline(title) + "}",
            r"\author{Anonymous authors\\Paper under double-blind review}",
            r"\date{}",
        ]
        bib_style = "plainnat"
    return "\n".join(
        preamble
        + [
            "",
            r"\begin{document}",
            r"\maketitle",
            "",
            r"\begin{abstract}",
            abstract_tex,
            r"\end{abstract}",
            "",
            body_tex,
            "",
            r"\bibliographystyle{" + bib_style + "}",
            r"\bibliography{" + bib_stem + "}",
            "",
            r"\end{document}",
            "",
        ]
    )


def render_latex(
    paper_md: Path,
    *,
    references_json: Path | None,
    out_dir: Path,
    venue_name: str,
) -> dict:
    md_text = paper_md.read_text(encoding="utf-8")
    title, abstract_tex, body_tex = markdown_to_latex_body(md_text)
    references = {}
    if references_json is not None and references_json.is_file():
        references = json.loads(references_json.read_text(encoding="utf-8"))
    keys = cited_keys(md_text)
    bibtex, unresolved = build_bibliography(keys, references)
    official_style = None
    official_bst = None
    style_family = None
    for sty in sorted(out_dir.glob("*_conference.sty")):
        official_style = sty.stem
        style_family = "iclr"
        if (out_dir / f"{sty.stem}.bst").is_file():
            official_bst = sty.stem
        break
    if official_style is None:
        for sty in sorted(out_dir.glob("icml[0-9]*.sty")):
            official_style = sty.stem
            style_family = "icml"
            if (out_dir / f"{sty.stem}.bst").is_file():
                official_bst = sty.stem
            break
    tex = build_latex_document(
        title=title,
        abstract_tex=abstract_tex,
        body_tex=body_tex,
        venue_name=venue_name,
        bib_stem="references",
        official_style=official_style,
        official_bst=official_bst,
        style_family=style_family,
    )
    tex_path = out_dir / "paper.tex"
    bib_path = out_dir / "references.bib"
    tex_path.write_text(tex, encoding="utf-8")
    bib_path.write_text(bibtex, encoding="utf-8")
    return {
        "tex_path": str(tex_path),
        "bib_path": str(bib_path),
        "title": title,
        "style": official_style or "generic-preprint",
        "cited_keys": keys,
        "unresolved_citations": unresolved,
        "build_hint": f"tectonic {tex_path}  # or: latexmk -pdf -cd {tex_path}",
    }
