"""투자프레임·브리핑 HTML -> GitHub용 마크다운
사용법: python html2gh.py <HTML 파일> <저장소의 기업 폴더> <영문 기업명>
결과: <폴더>/<영문이름>-<framework|briefing>-YYYYMMDD.md, <폴더>/charts/YYYYMMDD/<framework|briefing>-NN.svg,
      <폴더>/data/<영문이름>-<framework|briefing>-YYYYMMDD.json
(README.md 목록 갱신은 별도로 한다)"""
import json, re, sys, copy
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString, Tag
from markdownify import markdownify as mdify

src, outdir = Path(sys.argv[1]), Path(sys.argv[2])
import datetime as _dt
_hs = src.stem
_date = re.search(r"(\d{8})", _hs).group(1)
_kind = "briefing" if ("브리핑" in _hs or "briefing" in _hs) else "framework"
_slug = sys.argv[3] if len(sys.argv) > 3 else re.sub(r"[-_]?(framework|briefing)[-_]?\d{8}$", "", _hs)
stem = f"{_slug}-{_kind}-{_date}"   # 영문 출력 이름
(outdir / "charts" / _date).mkdir(parents=True, exist_ok=True)
(outdir / "data").mkdir(parents=True, exist_ok=True)
soup = BeautifulSoup(src.read_text(encoding="utf-8"), "lxml")
main = soup.find("main")

# 라이트 테마 색 (원본 :root 값)
COLORS = {"--surf": "#fcfcfb", "--bg": "#f3f2ee", "--t1": "#0b0b0b", "--t2": "#52514e",
          "--t3": "#8a8984", "--line": "#e2e0d8", "--s1": "#2a78d6", "--s2": "#eb6834",
          "--s3": "#1baf7a", "--s4": "#eda100", "--warn": "#b25b00"}
EMOJI = {"--s1": "🟦", "--s2": "🟧", "--s3": "🟩", "--s4": "🟨"}
SVG_CSS = (".grid{stroke:#e2e0d8;stroke-width:1}.zero{stroke:#8a8984;stroke-width:1}"
           ".base{stroke:#52514e;stroke-dasharray:5 4;stroke-width:1.2}"
           ".ax{fill:#52514e;font-size:11px}.dl{fill:#0b0b0b;font-size:11px;font-weight:600}"
           "text{font-family:-apple-system,'Apple SD Gothic Neo','Malgun Gothic','Noto Sans KR',sans-serif}")
ARROW_DEFS = '<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#52514e"/></marker></defs>'

def subvars(s):
    return re.sub(r"var\((--[a-z0-9]+)\)", lambda m: COLORS.get(m.group(1), "#888"), s)

n_svg = 0
def save_svg(svg, alt):
    global n_svg
    n_svg += 1
    vb = (svg.get("viewBox") or svg.get("viewbox") or "0 0 760 260").split()
    vb[2] = str(int(float(vb[2])) + 50)  # 오른쪽 끝 라벨 잘림 방지
    w, h = vb[2], vb[3]
    for t in svg.find_all("title"):          # 이미지에서는 툴팁이 안 보이므로 제거
        t.decompose()
    for c in svg.find_all("circle", attrs={"fill": "transparent"}):
        c.decompose()
    body = subvars(svg.decode_contents())
    if "url(#ar)" in body and 'id="ar"' not in body:
        body = ARROW_DEFS + body
    out = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{" ".join(vb)}" width="{w}" height="{h}">'
           f'<style>{SVG_CSS}</style><rect x="{vb[0]}" y="{vb[1]}" width="{w}" height="{h}" fill="#ffffff"/>'
           f'{body}</svg>')
    name = f"charts/{_date}/{_kind}-{n_svg:02d}.svg"
    (outdir / name).write_text(out, encoding="utf-8")
    alt = re.sub(r"[\[\]]", "", alt or f"그림 {n_svg}")
    return f"![{alt}]({name})"

def legend_md(div):
    items = []
    for lg in div.find_all(class_="lg"):
        i = lg.find("i")
        style = i.get("style", "") if i else ""
        m = re.search(r"var\((--s\d)\)", style)
        mark = EMOJI.get(m.group(1), "■") if m else "■"
        items.append(f"{mark} {lg.get_text(' ', strip=True)}")
    return " · ".join(items)

def inline_fix(el):
    """md 변환 전 인라인 요소 정리"""
    for s in el.find_all("span", class_="hi"):
        s.name = "b"; s.attrs = {}
    for s in el.find_all("span", class_="formula"):
        txt = s.get_text()
        s.replace_with(NavigableString(f"`{txt}`") if el.name not in ("table",) else txt)
    for s in el.find_all("span", class_="note"):
        s.name = "sub"; s.attrs = {}
    for s in el.find_all("span", class_="tag"):
        s.unwrap()
    return el

def table_html(tbl):
    t = copy.copy(tbl)
    inline_fix(t)
    for x in [t] + t.find_all(True):
        keep = {k: v for k, v in x.attrs.items() if k in ("colspan", "rowspan")}
        x.attrs = keep
    if tbl.get("class") and "num" in tbl.get("class"):
        for tr in t.find_all("tr"):
            for td in tr.find_all("td")[1:]:
                td["align"] = "right"
    html = re.sub(r"\s*\n\s*", " ", str(t))
    return html

def md(el):
    el = inline_fix(copy.copy(el))
    return mdify(str(el), heading_style="ATX", bullets="-", strip=["span"]).strip()

def render(nodes):
    out = []
    for el in nodes:
        if isinstance(el, NavigableString):
            if el.strip(): out.append(el.strip())
            continue
        if not isinstance(el, Tag): continue
        cls = el.get("class") or []
        if el.name in ("nav", "style"):
            continue
        if el.name == "script":
            (outdir / "data" / f"{stem}.json").write_text(
                json.dumps(json.loads(el.string), ensure_ascii=False, indent=1), encoding="utf-8")
            continue
        if el.name in ("h1", "h2", "h3", "h4"):
            out.append("#" * int(el.name[1]) + " " + el.get_text(" ", strip=True))
        elif el.name == "figure":
            cap = el.find("figcaption")
            title = cap.get_text(" ", strip=True) if cap else ""
            parts = [f"**{title}**"] if title else []
            leg = el.find(class_="legend")
            if leg and legend_md(leg): parts.append(legend_md(leg))
            svg = el.find("svg")
            if svg: parts.append(save_svg(svg, title))
            for n in el.find_all("p", class_="note"):
                parts.append("<sub>" + md(n) + "</sub>")
            out.append("\n\n".join(parts))
        elif el.name == "svg":
            out.append(save_svg(el, el.get("aria-label")))
        elif el.name == "div" and "tw" in cls:
            t = el.find("table")
            if t: out.append(table_html(t))
        elif el.name == "table":
            out.append(table_html(el))
        elif el.name == "div" and "card" in cls:
            kind = "[!WARNING]" if "warnbox" in cls else ("[!NOTE]" if "key" in cls else "")
            inner = render(el.contents) if el.find(["table", "figure", "ul", "ol", "p"]) else md(el)
            lines = ([kind] if kind else []) + inner.split("\n")
            out.append("\n".join("> " + l if l else ">" for l in lines))
        elif el.name == "div":
            out.append(render(el.contents))
        elif el.name == "p" and "note" in cls:
            out.append("<sub>" + md(el) + "</sub>")
        else:
            out.append(md(el))
    return "\n\n".join(x for x in out if x)

text = render(main.contents)
text = re.sub(r"\n{3,}", "\n\n", text)
text += f"\n\n---\n\n<sub>숫자 블록: [data/{stem}.json](data/{stem}.json) · 원본은 같은 이름의 HTML(로컬 보관)</sub>"
(outdir / f"{stem}.md").write_text(text + "\n", encoding="utf-8")
print("svgs:", n_svg, "md chars:", len(text))
