"""视图层验收：数据组装 + 单文件 HTML 渲染（不依赖浏览器）。"""
import re

from app.view import build_graph_data, render_html, write_html


def test_graph_data_shape():
    data = build_graph_data()
    assert data["nodes"], "应有节点"
    assert data["boxes"], "应有领域框"
    assert data["width"] > 0 and data["height"] > 0
    for n in data["nodes"]:
        assert {"key", "name", "domain", "x", "y", "w", "h"} <= set(n)


def test_boxes_do_not_overlap_horizontally():
    data = build_graph_data()
    boxes = sorted(data["boxes"], key=lambda b: b["x"])
    for left, right in zip(boxes, boxes[1:], strict=False):
        assert left["x"] + left["w"] <= right["x"], "领域框不应横向重叠"


def test_nodes_stay_inside_their_box():
    data = build_graph_data()
    boxes = {b["domain"]: b for b in data["boxes"]}
    for n in data["nodes"]:
        b = boxes[n["domain"]]
        assert b["x"] <= n["x"] and n["x"] + n["w"] <= b["x"] + b["w"]
        assert b["y"] <= n["y"] and n["y"] + n["h"] <= b["y"] + b["h"]


def test_links_reference_existing_nodes():
    data = build_graph_data()
    keys = {n["key"] for n in data["nodes"]}
    for link in data["links"]:
        assert link["src"] in keys and link["dst"] in keys
        assert link["type"] in {"递进", "应用"}


def test_render_html_is_self_contained():
    html = render_html()
    assert html.startswith("<!DOCTYPE html>")
    assert "__DATA__" not in html, "模板占位必须被替换"
    # 零外链：不应有 http(s) 资源引用
    assert not re.search(r'(src|href)="https?://', html)
    assert "<svg id=\"s\">" in html


def test_render_html_embeds_json_payload():
    html = render_html()
    assert "const D = {" in html
    assert '"nodes"' in html and '"links"' in html


def test_write_html_creates_file(tmp_path):
    out = write_html(tmp_path / "graph.html")
    assert out.exists()
    assert out.stat().st_size > 1000


def test_dangling_edges_are_surfaced_not_dropped():
    """未建卡端点的边必须显式暴露，不能静默消失（否则「借鉴」边会凭空不见）。"""
    data = build_graph_data()
    html = render_html()
    # 数据里 dangling 与 links 不重叠
    shown = {(lnk["src"], lnk["dst"]) for lnk in data["links"]}
    assert len(shown) == len(data["links"])
    if data["dangling"]:
        assert 'id="dangling"' in html
        assert "端点尚未建卡" in html


def test_view_registered_in_cli():
    from app.cli import build_parser

    ns = build_parser().parse_args(["view"])
    assert ns.cmd == "view"
