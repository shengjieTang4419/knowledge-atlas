"""视图层：把 data/ 的知识图谱渲染成一个**零依赖单文件 HTML**。

定位：这是「只读渲染」，不是前端工程——不引入框架、不起服务、不需要构建。
数据源就是 git 里的真相源（`data/wiki/` 卡片 + `data/graph/edges.md`），改完数据重生成即可。

用法：
    from app.view import render_html, write_html
    write_html()                      # -> deliverables/graph.html
"""
from __future__ import annotations

import html
import json
from typing import TYPE_CHECKING, Any

from app.config import ROOT
from app.layers import mechanism
from app.layers.graph import load_edges
from app.layers.topology import all_entities, entity_domains

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["DEFAULT_OUT", "build_graph_data", "render_html", "write_html"]

DEFAULT_OUT: Path = ROOT / "deliverables" / "graph.html"

# 版面常量（生成期算好坐标，前端只做点击高亮——避免依赖 JS 布局）
_NODE_W, _NODE_H, _GAP = 196, 46, 12
_BOX_W, _BOX_X0, _BOX_STEP, _BOX_Y = 360, 60, 420, 150
_TITLE_H, _PAD = 56, 22

_DOMAIN_COLORS = ["#4fd1c5", "#6ea8fe", "#b197fc", "#e8a33d", "#e5534b", "#f78da7"]
_UNTYPED = "（未归域）"
_CARD_GROUP = "机制卡（金线）"
_CARD_COLOR = "#d29922"


def build_graph_data() -> dict[str, Any]:
    """组装渲染所需数据：节点（含坐标）、领域分组、机制卡、边。"""
    entities = all_entities()
    domains = entity_domains()
    cards = mechanism.load_cards()

    grouped: dict[str, list[str]] = {}
    for key in sorted(entities):
        grouped.setdefault(domains.get(key, _UNTYPED), []).append(key)
    # 节点多的域排前面，稳定次序
    order = sorted(grouped, key=lambda d: (-len(grouped[d]), d))

    nodes: list[dict[str, Any]] = []
    boxes: list[dict[str, Any]] = []
    for col, domain in enumerate(order):
        keys = grouped[domain]
        bx = _BOX_X0 + col * _BOX_STEP
        bh = _TITLE_H + len(keys) * (_NODE_H + _GAP) + _PAD
        boxes.append(
            {
                "domain": domain,
                "x": bx,
                "y": _BOX_Y,
                "w": _BOX_W,
                "h": bh,
                "color": _DOMAIN_COLORS[col % len(_DOMAIN_COLORS)],
            }
        )
        for i, key in enumerate(keys):
            ent = entities[key]
            nodes.append(
                {
                    "key": key,
                    "name": ent.name,
                    "etype": ent.type,
                    "one_line": ent.one_line,
                    "domain": domain,
                    "color": _DOMAIN_COLORS[col % len(_DOMAIN_COLORS)],
                    "x": bx + (_BOX_W - _NODE_W) // 2,
                    "y": _BOX_Y + _TITLE_H + i * (_NODE_H + _GAP),
                    "w": _NODE_W,
                    "h": _NODE_H,
                }
            )

    # 机制卡分组（金线）：独立一列，排最后；应用边从卡指向实体
    if cards:
        col = len(order)
        bx = _BOX_X0 + col * _BOX_STEP
        bh = _TITLE_H + len(cards) * (_NODE_H + _GAP) + _PAD
        boxes.append(
            {"domain": _CARD_GROUP, "x": bx, "y": _BOX_Y, "w": _BOX_W, "h": bh, "color": _CARD_COLOR}
        )
        for i, card in enumerate(cards):
            nodes.append(
                {
                    "key": _norm(card.name),
                    "name": card.name,
                    "etype": "机制卡",
                    "one_line": card.mechanism,
                    "domain": _CARD_GROUP,
                    "color": _CARD_COLOR,
                    "x": bx + (_BOX_W - _NODE_W) // 2,
                    "y": _BOX_Y + _TITLE_H + i * (_NODE_H + _GAP),
                    "w": _NODE_W,
                    "h": _NODE_H,
                }
            )

    by_key = {n["key"]: n for n in nodes}
    links: list[dict[str, Any]] = []
    dangling: list[str] = []
    for e in load_edges():
        src = next((k for k in by_key if k == _norm(e.src)), None)
        dst = next((k for k in by_key if k == _norm(e.dst)), None)
        if src is None or dst is None:
            dangling.append(f"{e.src} → {e.dst}")
            continue
        links.append({"src": src, "dst": dst, "type": e.type, "reason": e.reason})

    height = max((b["y"] + b["h"] for b in boxes), default=600) + 90
    width = _BOX_X0 * 2 + max(len(order) - 1, 0) * _BOX_STEP + _BOX_W
    return {
        "nodes": nodes,
        "boxes": boxes,
        "links": links,
        "dangling": dangling,
        "width": max(width, 900),
        "height": max(height, 620),
    }


def _norm(name: str) -> str:
    import re

    # 与 topology.normalize 同口径：去空白 + 小写（实体键/边端点都是归一化后的）
    return re.sub(r"\s+", "", name or "").lower()


def render_html() -> str:
    """渲染单文件 HTML（数据内联为 JSON，无外部依赖）。"""
    data = build_graph_data()
    payload = json.dumps(data, ensure_ascii=False)
    bom = len(data["dangling"])
    subtitle = f"{len(data['nodes'])} 实体 · {len(data['links'])} 条边"
    if bom:
        subtitle += f" · {bom} 条边端点未建卡"
    return _TEMPLATE.replace("__DATA__", payload).replace("__SUBTITLE__", html.escape(subtitle))


def write_html(path: Path | None = None) -> Path:
    """生成到文件（默认 deliverables/graph.html）。"""
    out = path or DEFAULT_OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(), encoding="utf-8")
    return out


_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>知识图谱 · knowledge-atlas</title>
<style>
  :root{ --bg:#0b0e13; --ink:#e6edf3; --dim:#8b949e; --line:#26303d;
         --flow:#4fd1c5; --amber:#e8a33d; --red:#e5534b; }
  *{box-sizing:border-box;margin:0;padding:0}
  html{background:var(--bg)}
  body{color:var(--ink);min-height:100vh;overflow-x:hidden;
    font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;
    background-color:var(--bg);
    background-image:
      linear-gradient(rgba(255,255,255,.030) 1px,transparent 1px),
      linear-gradient(90deg,rgba(255,255,255,.030) 1px,transparent 1px),
      linear-gradient(rgba(255,255,255,.012) 1px,transparent 1px),
      linear-gradient(90deg,rgba(255,255,255,.012) 1px,transparent 1px);
    background-size:44px 44px,44px 44px,11px 11px,11px 11px;}
  .page{max-width:1500px;margin:0 auto;padding:24px 20px 40px}
  h1{font-family:"Songti SC","Noto Serif SC",serif;font-size:25px;letter-spacing:1px}
  h1 .en{color:var(--dim);font-size:12px;font-family:ui-monospace,Menlo,monospace;margin-left:10px}
  .sub{color:var(--dim);font-size:13px;margin-top:8px;font-family:ui-monospace,Menlo,monospace}
  .bar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:16px 0 6px}
  button{background:#111721;color:var(--ink);border:1px solid var(--line);border-radius:8px;
    padding:7px 14px;font-size:13px;cursor:pointer;font-family:inherit}
  button:hover{border-color:var(--flow)}
  button.on{border-color:var(--flow);color:var(--flow)}
  .main{display:flex;gap:18px;align-items:flex-start;margin-top:12px}
  .stage{flex:1 1 auto;min-width:0;overflow-x:auto;border:1px solid var(--line);
    border-radius:12px;background:rgba(255,255,255,.012)}
  .stage svg{display:block}
  .detail{flex:0 0 320px;background:#111721;border:1px solid var(--line);border-radius:12px;padding:20px}
  .detail h2{font-size:17px;margin-bottom:6px}
  .detail .meta{color:var(--dim);font-size:12px;font-family:ui-monospace,Menlo,monospace;margin-bottom:14px}
  .detail .h{font-size:12px;color:var(--dim);letter-spacing:1px;margin:16px 0 8px;
    border-bottom:1px solid var(--line);padding-bottom:6px}
  .detail li{list-style:none;padding:5px 0 5px 15px;position:relative;font-size:13px;line-height:1.5}
  .detail li::before{content:"›";position:absolute;left:0;color:var(--flow)}
  .tag{display:inline-block;padding:2px 8px;border-radius:9px;font-size:11px;font-weight:700;
    color:#0b0e13;margin-right:7px;font-family:ui-monospace,Menlo,monospace}
  .warn{color:var(--amber);font-size:12px;margin-top:10px;line-height:1.6}
  .empty{color:var(--dim);font-size:13px}
  .dangling{margin-top:10px}
  .dangling .dt{color:var(--amber);font-size:12px;font-family:ui-monospace,Menlo,monospace;margin-bottom:6px}
  .dangling ul{display:flex;flex-wrap:wrap;gap:8px;list-style:none}
  .dangling li{border:1px dashed #4a3b1f;border-radius:8px;padding:5px 10px;font-size:12px;color:#c9b48a}
  @media(max-width:1100px){ .main{flex-direction:column;align-items:stretch}
    .detail{flex:1 1 auto;width:100%} h1{font-size:21px} h1 .en{display:block;margin:4px 0 0} }
</style>
</head>
<body>
<div class="page">
  <h1>知识图谱<span class="en">knowledge-atlas / data-driven view</span></h1>
  <div class="sub">__SUBTITLE__ · 数据源 data/wiki/ + data/graph/edges.md（改数据后重生成）</div>
  <div class="bar">
    <button id="f-all" class="on">全部边</button>
    <button id="f-递进">只看递进（竖·深度）</button>
    <button id="f-应用">只看应用（锚点·卡→实体）</button>
  </div>
  <div id="dangling" class="dangling"></div>
  <div class="main">
    <div class="stage"><svg id="s"></svg></div>
    <div class="detail" id="detail"></div>
  </div>
</div>
<script>
const D = __DATA__;
const NS='http://www.w3.org/2000/svg';
const svg=document.getElementById('s'), detail=document.getElementById('detail');
svg.setAttribute('viewBox','0 0 '+D.width+' '+D.height);
svg.setAttribute('width',D.width); svg.setAttribute('height',D.height);
const el=(t,a)=>{const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);return e;};
const mono=x=>{x.style.fontFamily='ui-monospace,Menlo,monospace';};
const pos={}; D.nodes.forEach(n=>pos[n.key]=n);

// 箭头
const defs=el('defs',{});
[['ah','#4fd1c5'],['ah-b','#e8a33d']].forEach(([id,c])=>{
  const m=el('marker',{id:id,markerWidth:'9',markerHeight:'9',refX:'7',refY:'3',
    orient:'auto',markerUnits:'userSpaceOnUse'});
  m.appendChild(el('path',{d:'M0,0 L7,3 L0,6 z',fill:c}));
  defs.appendChild(m);
});
svg.appendChild(defs);

// 领域框
D.boxes.forEach(b=>{
  svg.appendChild(el('rect',{x:b.x,y:b.y,width:b.w,height:b.h,rx:12,
    fill:'rgba(255,255,255,0.012)',stroke:b.color,'stroke-opacity':'.4','stroke-width':'1'}));
  const t=el('text',{x:b.x+18,y:b.y+30,fill:b.color,'font-size':'14','font-weight':'700'});
  t.style.fontFamily='"Songti SC","Noto Serif SC",serif'; t.textContent=b.domain;
  svg.appendChild(t);
  const n=el('text',{x:b.x+18,y:b.y+46,fill:'#8b949e','font-size':'11'}); mono(n);
  n.textContent=D.nodes.filter(x=>x.domain===b.domain).length+' 个实体';
  svg.appendChild(n);
});

// 边：从源节点右边到目标节点左边（跨框走贝塞尔）
D.links.forEach((l,i)=>{
  const a=pos[l.src], b=pos[l.dst];
  if(!a||!b) return;
  const ax=a.x+a.w, ay=a.y+a.h/2, bx2=b.x, by=b.y+b.h/2;
  const d = (b.x > a.x)
    ? `M ${ax} ${ay} C ${ax+60} ${ay}, ${bx2-60} ${by}, ${bx2} ${by}`
    : `M ${a.x+a.w/2} ${a.y+a.h} C ${a.x+a.w/2} ${a.y+a.h+70}, ${b.x+b.w/2} ${b.y-70}, ${b.x+b.w/2} ${b.y}`;
  const p=el('path',{d:d,fill:'none',
    stroke: l.type==='应用' ? '#e8a33d' : '#4fd1c5',
    'stroke-width':'1.6','stroke-opacity':'.6','marker-end': 'url(#'+(l.type==='应用'?'ah-b':'ah')+')'});
  p.dataset.type=l.type; p.dataset.src=l.src; p.dataset.dst=l.dst; p.setAttribute('class','edge');
  const ti=el('title',{});
  ti.textContent=l.src+' --'+l.type+'--> '+l.dst+(l.reason?'（'+l.reason+'）':'');
  p.appendChild(ti);
  svg.appendChild(p);
});

// 节点
D.nodes.forEach(n=>{
  const g=el('g',{class:'node'}); g.style.cursor='pointer'; g.dataset.key=n.key;
  g.appendChild(el('rect',{x:n.x,y:n.y,width:n.w,height:n.h,rx:9,fill:'#0f1620',
    stroke:n.color,'stroke-width':'1.2','stroke-opacity':'.8'}));
  const t=el('text',{x:n.x+14,y:n.y+21,fill:'#e6edf3','font-size':'13.5','font-weight':'600'});
  t.textContent=n.name.length>14? n.name.slice(0,14)+'…' : n.name; g.appendChild(t);
  const s=el('text',{x:n.x+14,y:n.y+37,fill:'#8b949e','font-size':'10.5'}); mono(s);
  s.textContent=n.etype; g.appendChild(s);
  const ti=el('title',{}); ti.textContent=n.name+(n.one_line?'：'+n.one_line:''); g.appendChild(ti);
  g.addEventListener('click',()=>select(n.key));
  svg.appendChild(g);
});

let filter='all';
function applyFilter(){
  document.querySelectorAll('.edge').forEach(e=>{
    e.style.display = (filter==='all'||e.dataset.type===filter) ? '' : 'none';
  });
}
['all','递进','应用'].forEach(t=>{
  const btn=document.getElementById('f-'+t);
  if(!btn) return;
  btn.addEventListener('click',()=>{
    filter=t;
    ['f-all','f-递进','f-应用'].forEach(id=>document.getElementById(id).classList.remove('on'));
    btn.classList.add('on'); applyFilter();
  });
});

function select(key){
  const n=pos[key];
  document.querySelectorAll('.node rect').forEach(r=>{
    r.setAttribute('stroke-width','1.2');r.setAttribute('stroke-opacity','.8');
  });
  document.querySelectorAll('.edge').forEach(e=>e.setAttribute('stroke-opacity','.6'));
  const g=document.querySelector('.node[data-key="'+key+'"] rect');
  if(g){g.setAttribute('stroke-width','2.6');g.setAttribute('stroke-opacity','1');}
  const out=D.links.filter(l=>l.src===key), inn=D.links.filter(l=>l.dst===key);
  D.links.forEach(l=>{ if(l.src===key||l.dst===key){
    const e=document.querySelector('.edge[data-src="'+l.src+'"][data-dst="'+l.dst+'"]');
    if(e) e.setAttribute('stroke-opacity','1');
  }});
  const li=arr=>arr.length? '<ul>'+arr.map(l=>{
    const other = l.src===key ? l.dst : l.src;
    const dir = l.src===key ? '→' : '←';
    const otherName = pos[other] ? pos[other].name : other;
    const note = l.reason ? '<br><span style="color:#8b949e">'+l.reason+'</span>' : '';
    return '<li>'+dir+' <b>'+(l.type)+'</b> '+otherName+note+'</li>';
  }).join('')+'</ul>' : '<div class="empty">无</div>';
  detail.innerHTML =
    '<div><span class="tag" style="background:'+n.color+'">'+n.domain+'</span>'+
    '<span style="color:#8b949e;font-size:12px;font-family:ui-monospace,Menlo,monospace">'+n.etype+'</span></div>'+
    '<h2>'+n.name+'</h2>'+
    '<div class="meta">'+n.key+'</div>'+
    (n.one_line?'<div style="font-size:13px;line-height:1.6">'+n.one_line+'</div>':'')+
    '<div class="h">出边（本实体指向）</div>'+li(out)+
    '<div class="h">入边（指向本实体）</div>'+li(inn);
}
const dz=document.getElementById('dangling');
if(D.dangling && D.dangling.length){
  dz.innerHTML='<div class="dt">⚠ 以下 '+D.dangling.length+' 条边的端点尚未建卡（跨域节点，设计允许先挂名）：</div>'+
    '<ul>'+D.dangling.map(x=>'<li>'+x+'</li>').join('')+'</ul>';
} else { dz.remove(); }

if(D.nodes.length) select(D.nodes[0].key);
else detail.innerHTML='<div class="empty">data/wiki/ 下暂无实体卡片</div>';
</script>
</body>
</html>
"""
