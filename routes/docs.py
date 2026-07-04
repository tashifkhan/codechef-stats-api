import json
import re
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

router = APIRouter(tags=["Documentation"])
docs_router = router

PLATFORM = "CodeChef"
ACCENT = "#c98a5e"
DESCRIPTION = "Competitive programming analytics for CodeChef handles, ratings, contest history, ranks, and daily activity."
PARAM = "handle"
TRY_PATH = "/tourist/profile"
SAMPLE = TRY_PATH.strip("/").split("/")[0]
PLATFORM_KEY = "codechef"
REPO = "tashifkhan/codechef-stats-api"
CODETRACE_URL = 'https://codetrace.tashif.codes'
POSTHOG_PROXY_HOST = 'https://eu.i.posthog.com'
CANONICAL_ENDPOINTS = [
    ("GET", "/{handle}", "Summary"),
    ("GET", "/{handle}/profile", "Profile"),
    ("GET", "/{handle}/stats", "Solved stats"),
    ("GET", "/{handle}/topics", "Topic analysis"),
    ("GET", "/{handle}/contests", "Contest history"),
    ("GET", "/{handle}/rating", "Rating timeline"),
    ("GET", "/{handle}/heatmap", "Submission heatmap"),
    ("GET", "/{handle}/badges", "Empty badges"),
]
LEGACY_ENDPOINTS = [
    ("GET", "/profile/{handle}", "Deprecated profile alias"),
    ("GET", "/heatmap/{handle}", "Deprecated heatmap alias"),
    ("GET", "/rating/{handle}", "Deprecated rating alias"),
]

_POSTHOG_SCRIPT = """
<script>
!function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.crossOrigin="anonymous",p.async=!0,p.src=s.api_host+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;void 0!==a?u=e[a]=[]:a="posthog";u.people=u.people||[];u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e};u.people.toString=function(){return u.toString(1)+".people (stub)"};o="capture identify alias people.set people.set_once set_config register register_once unregister opt_out_capturing has_opted_out_capturing opt_in_capturing reset isFeatureEnabled onFeatureFlags getFeatureFlag getFeatureFlagPayload reloadFeatureFlags group updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures getActiveMatchingSurveys getSurveys getNextSurveyStep onSessionId".split(" ");for(n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);
posthog.init('phc_xxpoU7jHjt4nKAb4ygdiNwheukaBi7QvoAT4AsrdBcZC',{api_host:'/ph',ui_host:'https://eu.posthog.com',defaults:'2026-05-30'});
</script>
"""

# ── Shared Command-Code-style design system (identical across every platform) ──

_BASE_CSS = """
*,*::before,*::after{box-sizing:border-box}
:root{
  --bg:#000;--panel:#0a0a0c;--panel-2:#121214;
  --ink:#fafafa;--muted:#9b9ba4;--faint:#6b6b73;
  --line:#1f1f22;--line-2:#2a2a2f;--guide:rgba(255,255,255,.12);
  --accent-ink:#050506;--r:6px;
  --sans:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
  --mono:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,'Liberation Mono','Courier New',monospace;
}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:15px;line-height:1.6;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
::selection{background:color-mix(in srgb,var(--accent) 38%,transparent)}
*::-webkit-scrollbar{width:9px;height:9px}
*::-webkit-scrollbar-thumb{background:var(--line-2);border-radius:6px}

.topbar{position:sticky;top:0;z-index:50;height:54px;display:flex;align-items:center;gap:14px;padding:0 20px;
  background:color-mix(in srgb,var(--bg) 78%,transparent);backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.brand{display:flex;align-items:center;gap:9px;font-family:var(--mono);font-weight:600;letter-spacing:-.01em;font-size:14.5px}
.brand .glyph{display:grid;place-items:center;width:24px;height:24px;border-radius:var(--r);background:var(--accent);color:var(--accent-ink);font-size:13px;font-weight:800;text-transform:uppercase}
.brand .glyph svg{width:15px;height:15px}
.brand .sub{color:var(--faint);font-weight:500}
.topnav{margin-left:auto;display:flex;align-items:center;gap:2px}
.topnav a{padding:6px 11px;border-radius:var(--r);color:var(--muted);font-size:13px;font-weight:500;transition:.15s}
.topnav a:hover{color:var(--ink);background:var(--panel-2)}
.topnav a.cta{color:var(--accent-ink);background:var(--accent);font-weight:600}
.topnav a.cta:hover{filter:brightness(1.08)}
.topnav a.icon{display:grid;place-items:center;width:32px;height:32px;padding:0;color:var(--muted);border:1px solid var(--line);border-radius:var(--r)}
.topnav a.icon:hover{color:var(--ink);background:var(--panel-2);border-color:var(--line-2)}
.topnav a.icon svg{width:16px;height:16px}
.topnav a.ct-link{display:inline-flex;align-items:center;gap:6px}.topnav a.ct-link svg{width:13px;height:13px;flex:none}

.wrap{display:grid;grid-template-columns:262px minmax(0,1fr) 224px;max-width:1480px;margin:0 auto}
aside.side{position:sticky;top:54px;align-self:start;height:calc(100vh - 54px);overflow:auto;padding:22px 14px 48px;border-right:1px solid var(--line)}
.search{display:flex;align-items:center;gap:8px;width:100%;padding:8px 10px;border:1px solid var(--line);border-radius:var(--r);background:var(--panel);color:var(--faint);font-size:13px;margin-bottom:20px}
.search svg{flex:none;opacity:.7}
.search input{border:0;background:transparent;color:var(--ink);font-family:var(--sans);font-size:13px;width:100%;outline:none}
.search kbd{font-family:var(--mono);font-size:11px;color:var(--faint);border:1px solid var(--line);border-radius:4px;padding:1px 5px}
.navgroup{margin-bottom:20px}
.navgroup h4{margin:0 0 6px;padding:0 8px;font-size:11px;font-weight:600;letter-spacing:.13em;text-transform:uppercase;color:var(--faint)}
.navgroup a{display:block;padding:6px 10px;border-radius:var(--r);color:var(--muted);font-size:13.5px;transition:.12s}
.navgroup a:hover{color:var(--ink);background:var(--panel-2)}
.navgroup a.active{color:var(--ink);background:color-mix(in srgb,var(--accent) 13%,transparent)}

main.doc{min-width:0;padding:42px 52px 96px}
.eyebrow{color:var(--accent);font-family:var(--mono);font-size:12px;letter-spacing:.15em;text-transform:uppercase;margin-bottom:13px}
h1.title{font-size:clamp(32px,4.4vw,46px);line-height:1.05;letter-spacing:-.025em;margin:0 0 16px;font-weight:700}
.lede{color:var(--muted);font-size:17px;line-height:1.7;max-width:660px;margin:0 0 4px}
.metarow{display:flex;flex-wrap:wrap;gap:7px;margin:22px 0 6px}
.chip{font-family:var(--mono);font-size:12px;color:var(--muted);border:1px solid var(--line);border-radius:var(--r);padding:4px 10px;background:var(--panel)}

.steps{position:relative;margin-top:10px;padding-left:34px;border-left:1px dashed var(--guide)}
.section{padding-top:48px;scroll-margin-top:78px}
.section-head{position:relative;display:flex;align-items:center;gap:13px;margin-bottom:14px}
.step{position:absolute;left:-49px;top:-2px;display:grid;place-items:center;width:30px;height:30px;border-radius:var(--r);
  background:var(--bg);border:1px solid var(--line-2);color:var(--ink);font-family:var(--mono);font-weight:600;font-size:13.5px}
.section-head h2{margin:0;font-size:21px;letter-spacing:-.02em;font-weight:650}
.section p{color:var(--muted);max-width:660px;margin:0 0 4px}
.section a.link{color:var(--accent);border-bottom:1px solid color-mix(in srgb,var(--accent) 45%,transparent)}

.code{position:relative;border:1px solid var(--line);border-radius:var(--r);background:var(--panel);overflow:hidden;margin:16px 0;max-width:740px}
.code::before{content:"";position:absolute;left:0;top:10px;bottom:10px;width:2px;border-radius:2px;background:var(--accent);z-index:1}
.code .cap{display:flex;align-items:center;gap:8px;padding:9px 13px;border-bottom:1px solid var(--line);font-family:var(--mono);font-size:12px;color:var(--muted)}
.code .cap .dot{width:8px;height:8px;border-radius:50%;background:var(--accent);opacity:.85}
.code .copy{margin-left:auto;cursor:pointer;color:var(--faint);font-size:11px;font-family:var(--mono);border:1px solid var(--line);border-radius:5px;padding:3px 8px;background:transparent}
.code .copy:hover{color:var(--ink);border-color:var(--line-2)}
.code pre{margin:0;padding:15px 16px;overflow:auto;font-family:var(--mono);font-size:13px;line-height:1.7;color:#d6d6dc}
.code.small pre{font-size:12.5px;max-height:360px}
.code .cmt{color:var(--faint)}

.callout{position:relative;display:flex;gap:11px;border:1px solid var(--line);border-radius:var(--r);background:color-mix(in srgb,var(--accent) 6%,var(--panel));padding:13px 15px 13px 18px;margin:16px 0;max-width:740px}
.callout::before{content:"";position:absolute;left:0;top:10px;bottom:10px;width:2px;border-radius:2px;background:var(--accent)}
.callout .ic{flex:none;color:var(--accent);font-weight:700;font-family:var(--mono)}
.callout .t{color:var(--accent);font-weight:600;font-size:13px}
.callout p{margin:3px 0 0;color:var(--muted);font-size:14px}
.callout b{color:var(--ink)}

.eps{display:grid;gap:8px;margin:16px 0;max-width:760px}
.ep{position:relative;border:1px solid var(--line);border-radius:var(--r);background:var(--panel);overflow:hidden;transition:border-color .15s}
.ep.open{border-color:color-mix(in srgb,var(--accent) 28%,var(--line))}
.ep.open::before{content:"";position:absolute;left:0;top:10px;bottom:10px;width:2px;border-radius:2px;background:var(--accent);z-index:3}
.ep-head{display:flex;align-items:center;gap:13px;width:100%;text-align:left;background:transparent;border:0;color:inherit;cursor:pointer;padding:12px 14px;font:inherit}
.ep-head:hover{background:var(--panel-2)}
.ep.open .ep-head{background:var(--panel-2)}
.ep .verb{font-family:var(--mono);font-weight:700;font-size:11px;letter-spacing:.04em;color:var(--accent-ink);background:var(--accent);border-radius:4px;padding:3px 8px}
.ep-path{font-family:var(--mono);font-size:13.5px;color:var(--ink)}
.ep-desc{margin-left:auto;color:var(--muted);font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:42%}
.chev{flex:none;color:var(--faint);font-family:var(--mono);transition:.2s;transform:rotate(0)}
.ep.open .chev{transform:rotate(90deg);color:var(--accent)}
.ep-body{display:none;padding:2px 15px 16px;border-top:1px solid var(--line)}
.ep.open .ep-body{display:block}
.ep-sub{font-size:11px;text-transform:uppercase;letter-spacing:.12em;color:var(--faint);margin:15px 0 8px;font-weight:600}
.ep-note{color:var(--muted);font-size:13px;margin:4px 0}
.ptable{width:100%;border-collapse:collapse;font-size:13px}
.ptable th{text-align:left;color:var(--faint);font-weight:500;font-size:11px;text-transform:uppercase;letter-spacing:.07em;padding:6px 10px;border-bottom:1px solid var(--line)}
.ptable td{padding:8px 10px;border-bottom:1px solid var(--line);color:var(--muted);vertical-align:top}
.ptable tr:last-child td{border-bottom:0}
.ptable td code{font-family:var(--mono);color:var(--ink)}
.req{font-family:var(--mono);font-size:11px;color:var(--accent)}

code.ic{font-family:var(--mono);font-size:.86em;background:var(--panel-2);border:1px solid var(--line);border-radius:4px;padding:1px 5px;color:var(--ink)}

.foot{margin-top:56px;padding-top:22px;border-top:1px solid var(--line);display:flex;flex-wrap:wrap;gap:14px;justify-content:space-between;color:var(--faint);font-size:13px}
.foot a{color:var(--muted)}.foot a:hover{color:var(--ink)}

aside.toc{position:sticky;top:54px;align-self:start;height:calc(100vh - 54px);overflow:auto;padding:44px 22px}
.toc h5{margin:0 0 13px;font-size:11px;font-weight:600;letter-spacing:.13em;text-transform:uppercase;color:var(--faint)}
.toc a{display:block;padding:6px 0 6px 13px;border-left:1px solid var(--line);color:var(--faint);font-size:13px;transition:.12s}
.toc a:hover{color:var(--ink)}
.toc a.active{color:var(--accent);border-left-color:var(--accent)}

.menu-btn{display:none}
@media(max-width:1180px){.wrap{grid-template-columns:262px minmax(0,1fr)}aside.toc{display:none}}
@media(max-width:860px){
  .wrap{grid-template-columns:1fr}
  aside.side{position:fixed;left:0;top:54px;width:280px;background:var(--bg);z-index:40;transform:translateX(-102%);transition:.2s}
  aside.side.open{transform:none}
  main.doc{padding:30px 20px 80px}
  .steps{padding-left:0;border-left:0}
  .step{position:static;left:auto;top:auto}
  .menu-btn{display:inline-grid;place-items:center;width:32px;height:32px;border:1px solid var(--line);border-radius:var(--r);background:var(--panel);color:var(--ink);cursor:pointer;font-size:16px}
  h1.title{font-size:32px}
  .ep-desc{display:none}
}
"""

_PLAYGROUND_CSS = """
.pg-main{max-width:760px;margin:0 auto;padding:56px 24px 110px}
.pg-eyebrow{text-align:center;color:var(--accent);font-family:var(--mono);font-size:12px;letter-spacing:.15em;text-transform:uppercase;margin-bottom:14px;animation:pg-fade-up .5s ease both}
.pg-h1{text-align:center;font-family:var(--mono);font-size:clamp(26px,4vw,38px);letter-spacing:-.02em;margin:0 0 14px;animation:pg-fade-up .5s .05s ease both}
.pg-sub{text-align:center;color:var(--muted);font-size:15px;line-height:1.65;max-width:600px;margin:0 auto 36px;animation:pg-fade-up .5s .1s ease both}

@keyframes pg-fade-up{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
@keyframes pg-spin{to{transform:rotate(360deg)}}
@keyframes pg-pulse-bar{0%,100%{opacity:1}50%{opacity:.3}}
@keyframes pg-shimmer{0%{background-position:-220px 0}100%{background-position:220px 0}}
@keyframes pg-shake{10%,90%{transform:translateX(-1px)}20%,80%{transform:translateX(2px)}30%,50%,70%{transform:translateX(-4px)}40%,60%{transform:translateX(4px)}}
@keyframes pg-ring{0%{box-shadow:0 0 0 0 color-mix(in srgb,var(--accent) 45%,transparent)}100%{box-shadow:0 0 0 9px transparent}}

.pg-bar{position:sticky;top:66px;z-index:10;background:color-mix(in srgb,var(--panel) 92%,transparent);backdrop-filter:blur(10px);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin-bottom:32px;animation:pg-fade-up .5s .15s ease both;transition:border-color .2s,box-shadow .2s}
.pg-bar:focus-within{border-color:color-mix(in srgb,var(--accent) 50%,var(--line));box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 12%,transparent)}
.pg-bar-row{display:flex;gap:10px;align-items:flex-start}
.pg-input-wrap{position:relative;flex:1;min-width:0}
.pg-input-icon{position:absolute;left:13px;top:50%;transform:translateY(-50%);color:var(--faint);display:flex;pointer-events:none;transition:color .15s}
.pg-input-wrap:focus-within .pg-input-icon{color:var(--accent)}
.pg-input{width:100%;background:var(--bg);border:1px solid var(--line-2);border-radius:var(--r);padding:11px 34px 11px 38px;color:var(--ink);font-family:var(--mono);font-size:14px;outline:none;transition:border-color .15s,box-shadow .15s}
.pg-input:focus{border-color:var(--accent);box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 16%,transparent)}
.pg-input.shake{animation:pg-shake .4s ease}
.pg-input-clear{position:absolute;right:6px;top:50%;transform:translateY(-50%);width:22px;height:22px;display:none;align-items:center;justify-content:center;border:0;border-radius:50%;background:transparent;color:var(--faint);font-size:16px;line-height:1;cursor:pointer;transition:.15s}
.pg-input-clear:hover{background:var(--line);color:var(--ink)}
.pg-input-wrap.has-value .pg-input-clear{display:flex}
.pg-btn{position:relative;display:flex;align-items:center;justify-content:center;gap:7px;background:var(--accent);color:var(--accent-ink);border:0;border-radius:var(--r);padding:0 18px;font-weight:700;font-family:var(--mono);cursor:pointer;font-size:14px;white-space:nowrap;transition:filter .15s,transform .08s}
.pg-btn:hover{filter:brightness(1.08)}
.pg-btn:active{transform:scale(.97)}
.pg-btn:disabled{opacity:.7;cursor:default;transform:none}
.pg-runall{flex:none;min-width:118px;height:42px}
.pg-hint{margin:12px 2px 0;color:var(--faint);font-size:12.5px;line-height:1.6}

.pg-progress{height:3px;border-radius:3px;background:var(--line);overflow:hidden;margin:14px 2px 0;max-height:0;opacity:0;transition:max-height .2s ease,opacity .2s ease,margin .2s ease}
.pg-progress.active{max-height:3px;opacity:1}
.pg-progress-bar{height:100%;width:0%;background:var(--accent);border-radius:3px;transition:width .3s ease}

.pg-recent{position:absolute;top:calc(100% + 8px);left:0;right:0;background:var(--panel-2);border:1px solid var(--line-2);border-radius:var(--r);padding:6px;z-index:20;max-height:230px;overflow:auto;box-shadow:0 12px 28px rgba(0,0,0,.45);opacity:0;transform:translateY(-6px) scale(.98);pointer-events:none;transition:opacity .15s ease,transform .15s ease}
.pg-recent.open{opacity:1;transform:translateY(0) scale(1);pointer-events:auto}
.pg-recent-head{display:flex;justify-content:space-between;align-items:center;padding:6px 8px;font-size:11px;text-transform:uppercase;letter-spacing:.1em;color:var(--faint)}
.pg-recent-head button{background:none;border:0;color:var(--faint);cursor:pointer;font-size:12px;font-family:var(--sans)}
.pg-recent-head button:hover{color:var(--ink)}
.pg-recent-item{display:block;width:100%;text-align:left;background:none;border:0;color:var(--muted);font-family:var(--mono);padding:8px;border-radius:6px;cursor:pointer;font-size:13.5px;transition:background .1s}
.pg-recent-item:hover{background:var(--line);color:var(--ink)}

.pg-group-label{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:8px 0 12px;font-size:11px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:var(--faint)}
.pg-legacy-toggle{display:flex;align-items:center;gap:6px;background:none;border:0;color:var(--faint);font-size:11px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;cursor:pointer;padding:0;font-family:inherit}
.pg-legacy-toggle:hover{color:var(--ink)}
.pg-legacy-toggle .chev{position:static}
.pg-legacy-toggle[aria-expanded="true"] .chev{transform:rotate(90deg);color:var(--accent)}
.pg-legacy-list{display:none}
.pg-legacy-list.open{display:grid}

.pg-canonical-list{animation:pg-fade-up .4s .2s ease both}

.pg-row{flex-wrap:wrap}
.pg-status{flex:none;display:inline-flex;align-items:center;gap:5px;font-family:var(--mono);font-size:11px;color:var(--faint);border:1px solid var(--line);border-radius:5px;padding:3px 8px;white-space:nowrap;transition:color .15s,border-color .15s}
.pg-status.ok{color:#3fb950;border-color:color-mix(in srgb,#3fb950 45%,var(--line))}
.pg-status.err{color:#f85149;border-color:color-mix(in srgb,#f85149 45%,var(--line))}
.pg-status.busy{color:var(--accent);border-color:color-mix(in srgb,var(--accent) 35%,var(--line))}
.pg-run-btn{position:relative;flex:none;display:inline-flex;align-items:center;justify-content:center;gap:6px;min-width:46px;background:var(--accent);color:var(--accent-ink);border:0;border-radius:5px;padding:5px 12px;font-weight:700;font-family:var(--mono);font-size:12px;cursor:pointer;transition:filter .15s,transform .08s}
.pg-run-btn:hover{filter:brightness(1.08)}
.pg-run-btn:active{transform:scale(.95)}
.pg-run-btn:disabled{opacity:.7;cursor:default;transform:none}
.ep[data-path]{transition:border-color .15s,transform .15s,box-shadow .15s}
.ep[data-path]:hover{transform:translateY(-1px);box-shadow:0 6px 18px rgba(0,0,0,.28)}
.ep.ok::before{background:#3fb950}
.ep.err::before{background:#f85149}
.ep.busy::before{background:var(--accent);animation:pg-pulse-bar 1s ease-in-out infinite}
.ep.ok{animation:pg-ring .5s ease}

.pg-spinner{width:13px;height:13px;flex:none;border-radius:50%;border:2px solid color-mix(in srgb,currentColor 25%,transparent);border-top-color:currentColor;animation:pg-spin .7s linear infinite}
.pg-run-btn .pg-spinner{width:11px;height:11px}

.pg-placeholder{color:var(--faint)}
.pg-ep-loading{padding:4px 0 12px}
.pg-ep-loading .req{color:var(--faint);font-family:var(--mono);font-size:12px;margin:0 0 10px;display:flex;align-items:center;gap:7px}
.pg-skel{height:11px;border-radius:4px;margin:8px 0;background:linear-gradient(90deg,var(--line) 25%,var(--line-2) 50%,var(--line) 75%);background-size:440px 100%;animation:pg-shimmer 1.3s linear infinite}
.pg-skel.w90{width:90%}.pg-skel.w70{width:70%}.pg-skel.w50{width:50%}.pg-skel.w35{width:35%}
.pg-ep-meta{display:flex;align-items:center;gap:8px;margin:10px 0 8px;animation:pg-fade-up .3s ease both}
.pg-ep-meta .url{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;font-family:var(--mono);font-size:11.5px;color:var(--muted)}
.pg-copy{flex:none;cursor:pointer;color:var(--faint);font-size:11px;font-family:var(--mono);border:1px solid var(--line);border-radius:5px;padding:3px 8px;background:transparent;transition:.15s}
.pg-copy:hover{color:var(--ink);border-color:var(--line-2)}
.pg-ep-resp{margin:0;padding:12px 14px;overflow:auto;max-height:420px;font-family:var(--mono);font-size:12.5px;line-height:1.7;color:#d6d6dc;background:var(--bg);border:1px solid var(--line);border-radius:var(--r)}

.pg-tabs{display:flex;gap:6px;margin:2px 0 14px;animation:pg-fade-up .3s ease both}
.pg-tab-btn{background:none;border:1px solid var(--line);color:var(--muted);font-family:var(--mono);font-size:11.5px;padding:5px 12px;border-radius:5px;cursor:pointer;transition:.15s}
.pg-tab-btn:hover{color:var(--ink)}
.pg-tab-btn.active{background:var(--panel-2);color:var(--ink);border-color:var(--line-2)}
.pg-view[hidden]{display:none}
.pg-view{animation:pg-fade-up .25s ease both}

.pg-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:10px;margin:2px 0}
.pg-card{background:var(--bg);border:1px solid var(--line);border-radius:var(--r);padding:11px 13px}
.pg-card-lbl{font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--faint);margin-bottom:6px;font-family:var(--mono)}
.pg-card-val{font-size:14px;font-weight:600;color:var(--ink);font-family:var(--mono);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

.pg-section{margin:18px 0 4px}
.pg-section-lbl{font-size:11px;text-transform:uppercase;letter-spacing:.1em;color:var(--faint);font-family:var(--mono);margin:0 0 8px}

.pg-table-wrap{overflow:auto;border:1px solid var(--line);border-radius:var(--r);max-height:360px}
.pg-table{width:100%;border-collapse:collapse;font-size:12.5px}
.pg-table th{position:sticky;top:0;text-align:left;color:var(--faint);font-weight:500;font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;padding:8px 10px;border-bottom:1px solid var(--line);background:var(--panel-2);white-space:nowrap}
.pg-table td{padding:7px 10px;border-bottom:1px solid var(--line);color:var(--muted);font-family:var(--mono);white-space:nowrap;max-width:240px;overflow:hidden;text-overflow:ellipsis}
.pg-table tr:last-child td{border-bottom:0}
.pg-table-note{color:var(--faint);font-size:11.5px;margin:6px 2px 0}

.pg-chips{display:flex;flex-wrap:wrap;gap:6px}
.pg-chip{font-family:var(--mono);font-size:12px;color:var(--muted);border:1px solid var(--line);border-radius:5px;padding:3px 9px;background:var(--bg)}
.pg-empty{color:var(--faint);font-size:12.5px;margin:4px 0}

.pg-foot-note{text-align:center;color:var(--faint);font-size:13px;margin-top:40px}

@media(max-width:640px){
  .pg-bar-row{flex-direction:column}
  .pg-runall{width:100%;justify-content:center}
}
"""

_JS = """
document.querySelectorAll('[data-origin]').forEach(function(el){var o=location.origin;el.textContent=(o&&o!=='null')?o:'https://your-host'});
document.querySelectorAll('.copy').forEach(function(b){b.addEventListener('click',function(e){
  e.stopPropagation();
  var pre=b.closest('.code').querySelector('pre');
  navigator.clipboard.writeText(pre.innerText).then(function(){var t=b.textContent;b.textContent='Copied';setTimeout(function(){b.textContent=t},1200)});
})});
document.querySelectorAll('.ep-head').forEach(function(h){h.addEventListener('click',function(){
  var ep=h.parentElement,open=ep.classList.toggle('open');
  h.setAttribute('aria-expanded',open?'true':'false');
})});
var mb=document.querySelector('.menu-btn'),sb=document.querySelector('.side');
if(mb)mb.addEventListener('click',function(){sb.classList.toggle('open')});
var toc={},nav={};
document.querySelectorAll('[data-toc]').forEach(function(a){toc[a.getAttribute('href').slice(1)]=a});
document.querySelectorAll('[data-nav]').forEach(function(a){nav[a.getAttribute('href').slice(1)]=a});
var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){
  var id=e.target.id;
  Object.keys(toc).forEach(function(k){toc[k].classList.remove('active')});
  Object.keys(nav).forEach(function(k){nav[k].classList.remove('active')});
  if(toc[id])toc[id].classList.add('active');
  if(nav[id])nav[id].classList.add('active');
}})},{rootMargin:'-12% 0px -75% 0px'});
document.querySelectorAll('.section').forEach(function(s){io.observe(s)});
var si=document.querySelector('.search input');
if(si)si.addEventListener('input',function(){var q=si.value.toLowerCase();
  document.querySelectorAll('.navgroup a').forEach(function(a){a.style.display=a.textContent.toLowerCase().indexOf(q)>-1?'':'none'});
});
function playgroundPath(){
  var base = window.location.pathname.replace(new RegExp('/(docs|redoc)/?$'), '').replace(new RegExp('/$'), '');
  return (base || '') + '/playground';
}
document.querySelectorAll('a[href="/playground"]').forEach(function(a){
  var href = playgroundPath();
  a.setAttribute('href', href);
  a.addEventListener('click', function(e){ e.preventDefault(); window.location.assign(href); });
});
"""

_PLAYGROUND_JS = """
(function(){
  var STORE_KEY = 'pg_recent_' + PLATFORM_KEY;
  var form = document.querySelector('.pg-form');
  var input = document.querySelector('.pg-input');
  var inputWrap = document.querySelector('.pg-input-wrap');
  var clearBtn = document.querySelector('.pg-input-clear');
  var runAllBtn = document.querySelector('.pg-runall');
  var runAllDefaultHTML = runAllBtn.innerHTML;
  var progressEl = document.querySelector('.pg-progress');
  var progressBarEl = document.querySelector('.pg-progress-bar');
  var recentBox = document.querySelector('.pg-recent');
  var canonicalEps = Array.prototype.slice.call(document.querySelectorAll('.pg-canonical-list .ep'));
  var allEps = Array.prototype.slice.call(document.querySelectorAll('.ep[data-path]'));

  function syncHasValue(){ inputWrap.classList.toggle('has-value', input.value.length > 0); }
  syncHasValue();
  input.addEventListener('input', syncHasValue);
  input.addEventListener('animationend', function(){ input.classList.remove('shake'); });
  if(clearBtn){
    clearBtn.addEventListener('click', function(){
      input.value = ''; syncHasValue(); input.focus(); recentBox.classList.remove('open');
    });
  }

  function getRecent(){ try{ return JSON.parse(localStorage.getItem(STORE_KEY)) || []; }catch(e){ return []; } }
  function saveRecent(list){ localStorage.setItem(STORE_KEY, JSON.stringify(list.slice(0, 6))); }
  function pushRecent(h){
    var list = getRecent().filter(function(x){ return x.toLowerCase() !== h.toLowerCase(); });
    list.unshift(h);
    saveRecent(list);
    renderRecent();
  }
  function renderRecent(){
    var list = getRecent();
    if(!list.length){ recentBox.classList.remove('open'); recentBox.innerHTML=''; return; }
    recentBox.innerHTML = '<div class="pg-recent-head">Recent Searches<button type="button" class="pg-clear">Clear</button></div>' +
      list.map(function(h){ return '<button type="button" class="pg-recent-item">' + h.replace(/</g,'&lt;') + '</button>'; }).join('');
    recentBox.querySelector('.pg-clear').addEventListener('click', function(e){ e.stopPropagation(); saveRecent([]); renderRecent(); });
    Array.prototype.forEach.call(recentBox.querySelectorAll('.pg-recent-item'), function(b){
      b.addEventListener('click', function(){ input.value = b.textContent; syncHasValue(); recentBox.classList.remove('open'); });
    });
  }
  renderRecent();
  input.addEventListener('focus', function(){ if(getRecent().length) recentBox.classList.add('open'); });
  document.addEventListener('click', function(e){ if(!recentBox.contains(e.target) && e.target !== input) recentBox.classList.remove('open'); });

  function escHtml(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
  function buildUrl(tmpl, value){ return tmpl.replace(/\\{[^}]+\\}/g, function(){ return encodeURIComponent(value); }); }

  function isPlainObject(v){ return v !== null && typeof v === 'object' && !Array.isArray(v); }
  function isScalar(v){ return v === null || typeof v !== 'object'; }
  function fmtScalar(v){
    if(v === null || v === undefined || v === '') return '\\u2014';
    if(typeof v === 'boolean') return v ? 'Yes' : 'No';
    return String(v);
  }
  function humanize(key){
    return String(key).replace(/([a-z0-9])([A-Z])/g, '$1 $2').replace(/_/g, ' ')
      .replace(/^./, function(c){ return c.toUpperCase(); });
  }

  function renderScalarGrid(obj, keys){
    return '<div class="pg-cards">' + keys.map(function(k){
      var v = fmtScalar(obj[k]);
      return '<div class="pg-card"><div class="pg-card-lbl">' + escHtml(humanize(k)) + '</div>' +
        '<div class="pg-card-val" title="' + escHtml(v) + '">' + escHtml(v) + '</div></div>';
    }).join('') + '</div>';
  }

  function renderTable(rows){
    var cap = 25;
    var cols = [];
    rows.slice(0, cap).forEach(function(r){
      if(isPlainObject(r)){
        Object.keys(r).forEach(function(k){ if(cols.indexOf(k) === -1) cols.push(k); });
      }
    });
    if(!cols.length){
      return '<div class="pg-chips">' + rows.slice(0, cap).map(function(v){
        return '<span class="pg-chip">' + escHtml(fmtScalar(v)) + '</span>';
      }).join('') + '</div>';
    }
    cols = cols.slice(0, 8);
    var thead = '<tr>' + cols.map(function(c){ return '<th>' + escHtml(humanize(c)) + '</th>'; }).join('') + '</tr>';
    var tbody = rows.slice(0, cap).map(function(r){
      return '<tr>' + cols.map(function(c){
        var v = isPlainObject(r) ? r[c] : undefined;
        var text = v === undefined ? '\\u2014' : (isScalar(v) ? fmtScalar(v) : JSON.stringify(v));
        return '<td title="' + escHtml(text) + '">' + escHtml(text) + '</td>';
      }).join('') + '</tr>';
    }).join('');
    var note = rows.length > cap ? '<p class="pg-table-note">Showing ' + cap + ' of ' + rows.length + ' rows.</p>' : '';
    return '<div class="pg-table-wrap"><table class="pg-table"><thead>' + thead + '</thead><tbody>' + tbody + '</tbody></table></div>' + note;
  }

  function renderSection(label, html){
    return '<div class="pg-section"><div class="pg-section-lbl">' + escHtml(label) + '</div>' + html + '</div>';
  }

  function renderNode(value){
    if(Array.isArray(value)) return value.length ? renderTable(value) : '<p class="pg-empty">Empty list.</p>';
    if(!isPlainObject(value)) return '<p class="pg-empty">' + escHtml(fmtScalar(value)) + '</p>';
    var keys = Object.keys(value);
    if(!keys.length) return '<p class="pg-empty">Empty response.</p>';
    var scalarKeys = keys.filter(function(k){ return isScalar(value[k]); });
    var complexKeys = keys.filter(function(k){ return !isScalar(value[k]); });
    var out = scalarKeys.length ? renderScalarGrid(value, scalarKeys) : '';
    complexKeys.forEach(function(k){
      var v = value[k];
      var inner;
      if(Array.isArray(v)){
        inner = v.length ? renderTable(v) : '<p class="pg-empty">Empty list.</p>';
      } else {
        var subKeys = Object.keys(v);
        inner = (subKeys.length && subKeys.every(function(sk){ return isScalar(v[sk]); }))
          ? renderScalarGrid(v, subKeys)
          : '<pre class="pg-ep-resp">' + escHtml(JSON.stringify(v, null, 2)) + '</pre>';
      }
      out += renderSection(humanize(k), inner);
    });
    return out;
  }

  function runOne(ep){
    var tmpl = ep.getAttribute('data-path');
    var hasParam = /\\{[^}]+\\}/.test(tmpl);
    var value = input.value.trim();
    if(hasParam && !value){ input.focus(); return Promise.resolve(); }
    var url = buildUrl(tmpl, value);
    var status = ep.querySelector('.pg-status');
    var body = ep.querySelector('.ep-body');
    var runBtn = ep.querySelector('.pg-run-btn');
    var runBtnHTML = runBtn.innerHTML;
    ep.classList.add('open', 'busy');
    ep.classList.remove('ok', 'err');
    runBtn.disabled = true;
    runBtn.innerHTML = '<span class="pg-spinner"></span>';
    status.innerHTML = '<span class="pg-spinner"></span>';
    status.className = 'pg-status busy';
    body.innerHTML = '<div class="pg-ep-loading"><div class="req"><span class="pg-spinner"></span>Requesting ' + escHtml(url) + '\\u2026</div>' +
      '<div class="pg-skel w90"></div><div class="pg-skel w70"></div><div class="pg-skel w50"></div><div class="pg-skel w35"></div></div>';
    var start = performance.now();
    return fetch(url).then(function(r){
      var ms = Math.round(performance.now() - start);
      return r.text().then(function(text){
        var parsed = null;
        try{ parsed = JSON.parse(text); }catch(e){}
        var pretty = parsed !== null ? JSON.stringify(parsed, null, 2) : text;
        var formatted = '';
        if(parsed !== null){
          var target = (isPlainObject(parsed) && Object.prototype.hasOwnProperty.call(parsed, 'data'))
            ? parsed.data : parsed;
          formatted = renderNode(target);
        }
        ep.classList.remove('busy');
        ep.classList.add(r.ok ? 'ok' : 'err');
        status.textContent = r.status + ' \\u00b7 ' + ms + 'ms';
        status.className = 'pg-status ' + (r.ok ? 'ok' : 'err');
        var meta = '<div class="pg-ep-meta"><span class="url">GET ' + escHtml(url) + '</span><button type="button" class="pg-copy">Copy</button></div>';
        var tabs = formatted
          ? '<div class="pg-tabs"><button type="button" class="pg-tab-btn active" data-view="pretty">Formatted</button>' +
            '<button type="button" class="pg-tab-btn" data-view="raw">Raw JSON</button></div>'
          : '';
        var prettyView = '<div class="pg-view" data-view="pretty"' + (formatted ? '' : ' hidden') + '>' + formatted + '</div>';
        var rawView = '<div class="pg-view" data-view="raw"' + (formatted ? ' hidden' : '') + '><pre class="pg-ep-resp">' + escHtml(pretty) + '</pre></div>';
        body.innerHTML = meta + tabs + prettyView + rawView;
        body.querySelector('.pg-copy').addEventListener('click', function(e){
          e.stopPropagation();
          navigator.clipboard.writeText(pretty).then(function(){
            var b = e.currentTarget, t = b.textContent;
            b.textContent = 'Copied'; setTimeout(function(){ b.textContent = t; }, 1200);
          });
        });
        Array.prototype.forEach.call(body.querySelectorAll('.pg-tab-btn'), function(btn){
          btn.addEventListener('click', function(e){
            e.stopPropagation();
            var view = btn.getAttribute('data-view');
            Array.prototype.forEach.call(body.querySelectorAll('.pg-tab-btn'), function(b){ b.classList.toggle('active', b === btn); });
            Array.prototype.forEach.call(body.querySelectorAll('.pg-view'), function(v){ v.hidden = v.getAttribute('data-view') !== view; });
          });
        });
      });
    }).catch(function(err){
      ep.classList.remove('busy'); ep.classList.add('err');
      status.textContent = 'error'; status.className = 'pg-status err';
      body.innerHTML = '<div class="pg-ep-loading">' + escHtml(err.message || 'Request failed.') + '</div>';
    }).finally(function(){ runBtn.disabled = false; runBtn.innerHTML = runBtnHTML; });
  }

  allEps.forEach(function(ep){
    var head = ep.querySelector('.ep-head');
    var runBtn = ep.querySelector('.pg-run-btn');
    head.addEventListener('click', function(){ ep.classList.toggle('open'); });
    head.addEventListener('keydown', function(e){ if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); ep.classList.toggle('open'); } });
    runBtn.addEventListener('click', function(e){ e.stopPropagation(); runOne(ep); });
  });

  var legacyToggle = document.querySelector('.pg-legacy-toggle');
  if(legacyToggle){
    legacyToggle.addEventListener('click', function(){
      var list = document.querySelector('.pg-legacy-list');
      var open = list.classList.toggle('open');
      legacyToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  form.addEventListener('submit', function(e){
    e.preventDefault();
    var value = input.value.trim();
    if(!value){
      input.classList.remove('shake');
      void input.offsetWidth;
      input.classList.add('shake');
      input.focus();
      return;
    }
    recentBox.classList.remove('open');
    pushRecent(value);
    runAllBtn.disabled = true;
    var total = canonicalEps.length, done = 0;
    if(progressEl) progressEl.classList.add('active');
    if(progressBarEl) progressBarEl.style.width = '0%';
    runAllBtn.innerHTML = '<span class="pg-spinner"></span>Running 0/' + total;
    function tick(){
      done++;
      runAllBtn.innerHTML = '<span class="pg-spinner"></span>Running ' + done + '/' + total;
      if(progressBarEl) progressBarEl.style.width = Math.round((done / total) * 100) + '%';
    }
    Promise.all(canonicalEps.map(function(ep){ return runOne(ep).then(tick); })).finally(function(){
      runAllBtn.disabled = false;
      runAllBtn.innerHTML = runAllDefaultHTML;
      if(progressEl) setTimeout(function(){ progressEl.classList.remove('active'); }, 400);
    });
  });
})();
"""

_SEARCH_SVG = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-3.5-3.5"/></svg>'

_LOGOS = {"github": "M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12", "leetcode": "M13.483 0a1.374 1.374 0 0 0-.961.438L7.116 6.226l-3.854 4.126a5.266 5.266 0 0 0-1.209 2.104 5.35 5.35 0 0 0-.125.513 5.527 5.527 0 0 0 .062 2.362 5.83 5.83 0 0 0 .349 1.017 5.938 5.938 0 0 0 1.271 1.818l4.277 4.193.039.038c2.248 2.165 5.852 2.133 8.063-.074l2.396-2.392c.54-.54.54-1.414.003-1.955a1.378 1.378 0 0 0-1.951-.003l-2.396 2.392a3.021 3.021 0 0 1-4.205.038l-.02-.019-4.276-4.193c-.652-.64-.972-1.469-.948-2.263a2.68 2.68 0 0 1 .066-.523 2.545 2.545 0 0 1 .619-1.164L9.13 8.114c1.058-1.134 3.204-1.27 4.43-.278l3.501 2.831c.593.48 1.461.387 1.94-.207a1.384 1.384 0 0 0-.207-1.943l-3.5-2.831c-.8-.647-1.766-1.045-2.774-1.202l2.015-2.158A1.384 1.384 0 0 0 13.483 0zm-2.866 12.815a1.38 1.38 0 0 0-1.38 1.382 1.38 1.38 0 0 0 1.38 1.382H20.79a1.38 1.38 0 0 0 1.38-1.382 1.38 1.38 0 0 0-1.38-1.382z", "codeforces": "M4.5 7.5C5.328 7.5 6 8.172 6 9v10.5c0 .828-.672 1.5-1.5 1.5h-3C.673 21 0 20.328 0 19.5V9c0-.828.673-1.5 1.5-1.5h3zm9-4.5c.828 0 1.5.672 1.5 1.5v15c0 .828-.672 1.5-1.5 1.5h-3c-.827 0-1.5-.672-1.5-1.5v-15c0-.828.673-1.5 1.5-1.5h3zm9 7.5c.828 0 1.5.672 1.5 1.5v7.5c0 .828-.672 1.5-1.5 1.5h-3c-.828 0-1.5-.672-1.5-1.5V12c0-.828.672-1.5 1.5-1.5h3z", "gfg": "M21.45 14.315c-.143.28-.334.532-.565.745a3.691 3.691 0 0 1-1.104.695 4.51 4.51 0 0 1-3.116-.016 3.79 3.79 0 0 1-2.135-2.078 3.571 3.571 0 0 1-.13-.353h7.418a4.26 4.26 0 0 1-.368 1.008zm-11.99-.654a3.793 3.793 0 0 1-2.134 2.078 4.51 4.51 0 0 1-3.117.016 3.7 3.7 0 0 1-1.104-.695 2.652 2.652 0 0 1-.564-.745 4.221 4.221 0 0 1-.368-1.006H9.59c-.038.12-.08.238-.13.352zm14.501-1.758a3.849 3.849 0 0 0-.082-.475l-9.634-.008a3.932 3.932 0 0 1 1.143-2.348c.363-.35.79-.625 1.26-.809a3.97 3.97 0 0 1 4.484.957l1.521-1.49a5.7 5.7 0 0 0-1.922-1.357 6.283 6.283 0 0 0-2.544-.49 6.35 6.35 0 0 0-2.405.457 6.007 6.007 0 0 0-1.963 1.276 6.142 6.142 0 0 0-1.325 1.94 5.862 5.862 0 0 0-.466 1.864h-.063a5.857 5.857 0 0 0-.467-1.865 6.13 6.13 0 0 0-1.325-1.939A6 6 0 0 0 8.21 6.34a6.698 6.698 0 0 0-4.949.031A5.708 5.708 0 0 0 1.34 7.73l1.52 1.49a4.166 4.166 0 0 1 4.484-.958c.47.184.898.46 1.26.81.368.36.66.792.859 1.268.146.344.242.708.285 1.08l-9.635.008A4.714 4.714 0 0 0 0 12.457a6.493 6.493 0 0 0 .345 2.127 4.927 4.927 0 0 0 1.08 1.783c.528.56 1.17 1 1.88 1.293a6.454 6.454 0 0 0 2.504.457c.824.005 1.64-.15 2.404-.457a5.986 5.986 0 0 0 1.964-1.277 6.116 6.116 0 0 0 1.686-3.076h.273a6.13 6.13 0 0 0 1.686 3.077 5.99 5.99 0 0 0 1.964 1.276 6.345 6.345 0 0 0 2.405.457 6.45 6.45 0 0 0 2.502-.457 5.42 5.42 0 0 0 1.882-1.293 4.928 4.928 0 0 0 1.08-1.783A6.52 6.52 0 0 0 24 12.457a4.757 4.757 0 0 0-.039-.554z", "codechef": "M11.2574.0039c-.37.0101-.7353.041-1.1003.095C9.6164.153 9.0766.4236 8.482.694c-.757.3244-1.5147.6486-2.2176.7027-1.1896.3785-1.568.919-1.8925 1.3516 0 .054-.054.1079-.054.1079-.4325.865-.4873 1.73-.325 2.5952.1621.5407.3786 1.0282.5408 1.5148.3785 1.0274.7578 2.0007.92 3.1362.1622.3244.3235.7571.4316 1.1897.2704.8651.542 1.8383 1.353 2.5952l.0057-.0028c.0175.0183.0301.0387.0482.0568.0072-.0036.0141-.0063.0213-.0099l-.0213-.5849c.6489-.9733 1.5673-1.6221 2.865-1.8925.5195-.1093 1.081-.1497 1.6625-.1278a8.7733 8.7733 0 0 1 1.7988.2357c1.4599.3785 2.595 1.1358 2.6492 1.7846.0273.3549.0398.6952.0326 1.0364-.001.064-.0046.1285-.007.193l.1362.0682c.075-.0375.1424-.107.2059-.1902.0008-.001.002-.002.0028-.0028.0018-.0023.0039-.0061.0057-.0085.0396-.0536.0747-.1236.1107-.1931.0188-.0377.0372-.0866.0554-.1292.2048-.4622.362-1.1536.538-1.9635.0541-.2703.1092-.4864.1633-.7027.4326-.9733 1.0266-1.8382 1.6213-2.6492.9733-1.3518 1.8928-2.5962 1.7846-4.0561-1.784-3.4608-4.2718-4.0017-5.5695-4.272-.2163-.0541-.3233-.0539-.4856-.108-1.3382-.2433-2.4945-.3953-3.6046-.3648zm5.0428 14.3788a9.8602 9.8602 0 0 0-.0326-.9824c-.0541-.703-1.1892-1.46-2.7032-1.8386-.588-.1336-1.1764-.2142-1.7448-.2356-.539-.0137-1.0657.0248-1.5546.1277-1.2436.2704-2.2162.9193-2.811 1.8925l.0511 1.431c.6672-.3558 1.7326-.8747 3.139-.9994.0662-.0059.1368-.0059.2044-.0099.1177-.013.2667-.044.4444-.044 1.6075 0 3.2682.5336 4.8767 1.6483.039-.2744.0611-.549.071-.8234l.044.0227c.0028-.0622.0143-.1268.0156-.1888zM11.256.0578c.1239-.0034.2538.01.379.0114-.23-.0022-.4588.0026-.6871.0156.103-.0061.2046-.0242.308-.027zm.4983.0156c.6552.014 1.3255.0711 2.0387.1803-.6834-.0987-1.3646-.1671-2.0387-.1803zm-1.3147.0554c-.076.0087-.1527.0133-.2285.0241-.8168.1167-1.7742.7015-2.75 1.045.3545-.1323.7143-.2957 1.0747-.4501C9.0765.4774 9.6705.207 10.1571.1529c.0939-.0139.1886-.0133.2825-.0241zm-.2285.24c.1622 0 .3787-.0002.5409.0539-.1425-.0357-.2595-.026-.3706-.0142a1.174 1.174 0 0 1 .3166.0681c.5796 1.0012-.4264 5.2791-.6786 8.1492.1559 1.0276.3138 1.9963.4628 2.7201-.7029-1.7843-1.4067-4.921-1.5148-7.354-.054-.9733.001-1.8386.2172-2.4874C9.401.8557 9.7244.4228 10.2111.3687zm3.1361.271c-.811 2.1088-.9184 6.1092-.9725 7.3528-.054.5407-.0001 1.73.054 2.5952 0 .2163.054.4325.054.6488 0-.2163-.054-.3786-.054-.5948-.4326-3.2442-.974-7.1362.9185-10.002zm3.352.3777c-.2704 2.1628-1.4047 3.191-1.7832 5.2998-.1081 1.6762-.325 3.6222-.379 5.2984-.0541-1.6762-.0007-3.4601.2697-5.2444.2703-1.8384.8651-3.6776 1.8925-5.3538zm-10.381.433c-.3581.1194-.632.248-.8575.3805.2317-.1358.4996-.2666.8575-.3805zm.2101.1974c.2155.0025.4384.0734.6006.2357-.0067-.004-.0078-.0033-.0142-.0071.1331.0929.2666.2093.3932.3847-.2036.9673.2553 3.0317.0398 4.6694.0763 1.5485.0717 3.1804.849 4.4594-.9796-1.5107-1.176-3.4375-1.3218-5.236-.1128-1.0907-.2035-2.0969-.4642-2.9033-.144-.3047-.2684-.5745-.3833-.822-.0247-.0369-.0447-.0784-.071-.1135-.1082-.1082-.1619-.2696-.1619-.3777 0-.054.0539-.1618.108-.1618.054-.0541.1616-.0553.2157-.1094a1.013 1.013 0 0 1 .2101-.0184zm-1.3459.6133c-.0604.0201-.0923.041-.1405.061.1768-.034.3617.0339.5196.318-.1877.8916.4364 3.3685.4288 5.104.3124 1.8478.5496 3.8498 1.5716 5.1152C6.3723 11.5076 5.886 9.1286 5.5076 7.128 5.183 5.56 4.9125 4.2086 4.3718 3.776c-.054-.1081-.1079-.163-.1079-.2711 0-.1622-.0002-.3786.1079-.5949-.2772.6337-.4047 1.2673-.3706 1.901-.0445-.6487.0857-1.2905.3706-1.901 0-.054.054-.0538.054-.1079.012-.016.0314-.0349.044-.0511.0618-.0983.1308-.189.2257-.257.0557-.0615.0965-.1191.159-.1817-.0526.0555-.0872.1092-.1335.1647.0273-.018.0523-.0368.0838-.0525.1081-.1082.2154-.1633.3776-.1633zm-.3776.1633c-.0038.0075-.0076.0111-.0114.0184.0125-.0099.0242-.0208.037-.0298-.0074.0037-.0182.0077-.0256.0114zm14.7608 1.1343c-.0017.0052-.004.0104-.0057.0156.0378-.005.0751-.0173.1135-.0156-.0378-.0022-.0763.0103-.115.0199-.8634 2.6418-1.8874 5.2844-2.9118 7.9262a.0184.0184 0 0 1-.0015.0028c-.0874.4652-.234.8842-.5395 1.1898.4326-.4867.4854-1.1907.5395-2.0558.054-.811.0544-1.6761.487-2.5413 0-.0531.0012-.1058.0525-.159.0003-.0009.0012-.0019.0015-.0028.0973-.3524.202-.6885.3166-1.018.4183-1.2896 1.1396-3.1653 2.0131-3.3405.0163-.0052.034-.018.0497-.0213zM8.3726 16.2113l-.3238.1079c.1623.2163.2696.379.3777.433.1081.054.2168.108.379.108.0541 0 .1618 0 .2159-.054l.812-.2698c.0541 0 .1078-.054.1619-.054.1081 0 .1616 0 .2697.054l.2712.2698.2697-.054c-.1081-.1622-.2695-.3236-.3776-.3776-.1082-.0541-.2169-.1094-.379-.1094h-.108l-.866.3252h-.1618c-.1082 0-.2157 0-.2698-.054-.054-.054-.163-.1629-.2712-.3251zm-2.5953.541c-.2703.1621-.649.4324-1.1897.6487-.5407.2163-.9734.4325-1.1897.6488-.2163.2163-.3237.4326-.3237.6488 0 .1082.0537.1632.1618.2172.054.0541.1632.0539.2172.108.757.3244 1.5133.7019 2.2162 1.0803.1082.0541.2171.1632.2712.2173.054.054.1078.054.1618.054.1082 0 .2695-.0538.3777-.162.1081-.108.1632-.217.1632-.325 0-.1082-.055-.1618-.1632-.2158 0 0-.4328-.2165-1.1898-.541-.4866-.2162-.9179-.4326-1.1883-.5948.1623-.2704.486-.4865.9726-.7028.5407-.2163.9196-.4326 1.0818-.5948.054-.0541.054-.1078.054-.1619 0-.054-.0539-.1631-.108-.2172-.054-.054-.163-.1079-.2711-.1079zm11.247 0c-.054 0-.1618.0537-.2158.1078-.0541.1081-.1093.1632-.1093.2172v.054c.1622.1622.3797.2695.7041.3776.2704.054.5403.1632.8107.2172.3244.1082.5407.2693.6488.4856v.0553c0 .0541-.1088.1616-.3251.2698-.1082.054-.3245.2167-.5949.433-.2703.1622-.4326.3236-.5948.3776-.2163.1082-.3776.217-.4316.3252-.0541.054-.054.1077-.054.1618 0 .1081.0539.1077.108.2158.054.1081.1616.1093.2157.1093.054 0 .1078-.0554.1619-.0554.2703-.1622.6492-.3782 1.0818-.7567.4866-.3784.8655-.6484 1.0818-.8106.2163-.1082.3237-.2169.3237-.379 0-.0541.0002-.1618-.1079-.2159-.3785-.4325-.9185-.7022-1.5674-.9185-.1081-.0541-.2704-.1092-.5948-.1633-.1622-.054-.3249-.1079-.433-.1079zm-2.9743.8106c-.2704 0-.4866.055-.6488.2172-.2163.1622-.2699.4323-.2158.7567 0 .2703.1075.4865.2697.7027.1622.2163.3786.3252.5949.3252.1622 0 .2708-.0553.433-.1094.2703-.1622.379-.4319.379-.9185 0-.3785-.109-.6485-.2711-.8107-.1622-.1081-.3246-.1632-.541-.1632zm-4.4877.054c-.2704 0-.4866.055-.6488.2171-.2163.1622-.27.4323-.2158.7567 0 .2704.1075.4865.2697.7028s.3786.3251.5949.3251c.1622 0 .2708-.0552.433-.1093.2703-.1622.3776-.432.3776-.9186 0-.4325-.1075-.7025-.2697-.8106-.1622-.1082-.3247-.1633-.541-.1633zm0 .6501c.1622 0 .2711.1076.2711.2698 0 .1622-.163.2697-.2711.2697-.1622 0-.2698-.1075-.2698-.2697s.1076-.2698.2698-.2698zm4.3798.054c.1622 0 .2711.1075.2711.2697 0 .1082-.109.2698-.2711.2698-.1622 0-.2698-.1076-.2698-.2698 0-.1622.1076-.2697.2698-.2697zm-2.7032 2.1083l.1619.3237c.054.1081.1076.163.2158.2711.054.054.163.1619.2712.1619h.1078c.1082 0 .1618 0 .2158-.054.0541-.054.1632-.0538.2173-.1079l.1618-.1618c.054-.054.108-.1092.108-.1633.054-.054.0537-.1078.1078-.1618 0-.0541.054-.108.054-.108-.0541.1082-.1618.2156-.2158.3238-.1082.054-.1616.1632-.2698.1632-.1081.0541-.217.054-.3251.054s-.2157.0001-.2697-.054c-.1082 0-.1632-.0538-.2173-.1079l-.1618-.1632c-.054-.0541-.1078-.1618-.1619-.2158zm-.866 1.0278c-1.1355 0-1.8377 1.5136-3.4598.1619-.4326 2.6494 2.7583 2.866 4.11 1.7306.9192-.811.6475-1.9465-.6502-1.8925zm2.8664 0c-1.2977-.054-1.568 1.0815-.6488 1.8925 1.3518 1.1355 4.5412.9188 4.1087-1.7306-1.6221 1.3517-2.2703-.1619-3.4599-.1619z", "hackerrank": "M0 0v24h24V0zm9.95 8.002h1.805c.061 0 .111.05.111.111v7.767c0 .061-.05.111-.11.111H9.95c-.061 0-.111-.05-.111-.11v-2.87H7.894v2.87c0 .06-.05.11-.11.11H5.976a.11.11 0 01-.11-.11V8.112c0-.06.05-.11.11-.11h1.806c.061 0 .11.05.11.11v2.869H9.84v-2.87c0-.06.05-.11.11-.11zm2.999 0h5.778c.061 0 .111.05.111.11v7.767a.11.11 0 01-.11.112h-5.78a.11.11 0 01-.11-.11V8.111c0-.06.05-.11.11-.11z"}
_GITHUB_ICON = "<svg viewBox=\"0 0 24 24\" fill=\"currentColor\" aria-hidden=\"true\"><path d=\"M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12\"/></svg>"


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _section_of(path: str) -> str | None:
    p = path.strip("/")
    for s in ("profile", "stats", "topics", "contests", "rating", "heatmap", "badges"):
        if p == s or p.endswith("/" + s):
            return s
    segs = [x for x in p.split("/") if x]
    if len(segs) == 1 and segs[0].startswith("{"):
        return "summary"
    return None


def _params_of(path: str) -> list[tuple[str, str]]:
    rows = []
    for t in re.findall(r"{([^}]+)}", path):
        if t.endswith("s") and t not in ("handle", "username", "userid", "userids"):
            desc = f"Comma-separated list of {PLATFORM} handles."
        elif t == "userids":
            desc = f"Comma-separated list of {PLATFORM} handles."
        else:
            desc = f"The {PLATFORM} {PARAM} to look up."
        rows.append((t, desc))
    return rows


def _example_block(section: str, empty: bool) -> str | None:
    platform, username = PLATFORM.lower(), SAMPLE
    data: dict | None
    if section == "summary":
        data = {
            "totalSolved": 1263, "totalActiveDays": 608, "totalContests": 57,
            "currentRating": 1745, "maxRating": 1803, "rank": "Knight", "badgesCount": 24,
        }
    elif section == "profile":
        data = {
            "displayName": "Shaurya Rahlon", "username": username, "avatar": "https://...",
            "country": "India", "countryFlag": "https://...",
            "institution": "Jaypee Institute of Information Technology",
            "company": None, "bio": None, "websites": [],
            "social": {"github": None, "twitter": None, "linkedin": None}, "verified": False,
        }
    elif section == "stats":
        data = {
            "totalSolved": 859, "totalQuestions": 3000, "acceptanceRate": 65.5,
            "byDifficulty": {"easy": 267, "medium": 472, "hard": 120},
            "topicAnalysis": [
                {"topic": "Arrays", "count": 506},
                {"topic": "Dynamic Programming", "count": 152},
            ],
        }
    elif section == "topics":
        data = {"topicAnalysis": [
            {"topic": "Arrays", "count": 506},
            {"topic": "Dynamic Programming", "count": 152},
            {"topic": "Graphs", "count": 88},
        ]}
    elif section == "contests":
        data = {"count": 0, "rating": None, "maxRating": None, "rank": None,
                "globalRanking": None, "topPercentage": None, "history": []} if empty else {
            "count": 28, "rating": 1745, "maxRating": 1803, "rank": "Knight",
            "globalRanking": 38357, "topPercentage": 5.0,
            "history": [{"name": "Starters 175", "date": "2026-01-31", "timestamp": 1769817600,
                         "rating": 1745, "ranking": 38357, "problemsSolved": 3, "totalProblems": 4}],
        }
    elif section == "rating":
        data = {"current": None, "max": None, "history": []} if empty else {
            "current": 1745, "max": 1803,
            "history": [{"timestamp": 1769817600, "rating": 1745, "contestName": "Starters 175"}],
        }
    elif section == "heatmap":
        data = {
            "totalSubmissions": 592, "totalActiveDays": 608, "currentStreak": 4,
            "longestStreak": 138, "maxDailySubmissions": 12,
            "firstActiveDate": "2024-01-03", "lastActiveDate": "2026-05-29",
            "dailyContributions": [{"date": "2024-01-03", "count": 3, "level": 1}],
            "yearlyContributions": [{"year": 2025, "totalSubmissions": 320, "activeDays": 120}],
        }
    elif section == "badges":
        data = {"count": 0, "active": None, "list": []} if empty else {
            "count": 24, "active": {"id": "k1", "name": "Knight", "icon": "https://...", "level": None},
            "list": [{"id": "1", "name": "Problem Solver", "icon": "https://...", "level": None}],
        }
    else:
        return None
    envelope = {"status": "success", "platform": platform, "username": username,
                "cached": False, "data": data}
    return json.dumps(envelope, indent=2)


def _endpoint_rows(endpoints: list[tuple[str, str, str]], is_legacy: bool = False) -> str:
    out = []
    for method, path, summary in endpoints:
        section = _section_of(path)
        params = _params_of(path)
        if params:
            prows = "".join(
                f'<tr><td><code>{n}</code></td><td>string</td><td><span class="req">required</span></td>'
                f"<td>{d}</td></tr>"
                for n, d in params
            )
            ptable = (
                '<div class="ep-sub">Path parameters</div>'
                '<table class="ptable"><thead><tr><th>Name</th><th>Type</th><th></th>'
                f"<th>Description</th></tr></thead><tbody>{prows}</tbody></table>"
            )
        else:
            ptable = '<div class="ep-sub">Path parameters</div><p class="ep-note">None.</p>'
        example = _example_block(section, empty="Empty" in summary) if section else None
        if example:
            block = (
                '<div class="ep-sub">Response &middot; 200 OK</div>'
                '<div class="code small"><div class="cap"><span class="dot"></span>application/json'
                f'<button class="copy">Copy</button></div><pre>{_esc(example)}</pre></div>'
            )
        elif is_legacy:
            block = (
                '<div class="ep-sub">Response &middot; 200 OK</div>'
                '<p class="ep-note">Deprecated alias &mdash; returns the standard envelope '
                "wrapping the legacy payload.</p>"
            )
        else:
            block = (
                '<div class="ep-sub">Response &middot; 200 OK</div>'
                '<p class="ep-note">No inline example for this shape &mdash; see the '
                '<a class="link" href="/docs">OpenAPI schema</a> for the exact response.</p>'
            )
        out.append(
            '<div class="ep"><button class="ep-head" aria-expanded="false">'
            f'<span class="verb">{method}</span><code class="ep-path">{path}</code>'
            f'<span class="ep-desc">{summary}</span><span class="chev">&rsaquo;</span></button>'
            f'<div class="ep-body">{ptable}{block}</div></div>'
        )
    return "".join(out)


def _playground_rows(endpoints: list[tuple[str, str, str]]) -> str:
    out = []
    for method, path, summary in endpoints:
        out.append(
            f'<div class="ep" data-path="{_esc(path)}">'
            '<div class="ep-head pg-row" role="button" tabindex="0">'
            f'<span class="verb">{method}</span>'
            f'<code class="ep-path">{path}</code>'
            f'<span class="ep-desc">{summary}</span>'
            '<span class="pg-status"></span>'
            '<button type="button" class="pg-run-btn">Run</button>'
            '<span class="chev">&rsaquo;</span>'
            "</div>"
            '<div class="ep-body">'
            '<pre class="pg-ep-resp"><span class="pg-placeholder">Run this endpoint to see the live response here.</span></pre>'
            "</div>"
            "</div>"
        )
    return "".join(out)


_ACCENT_INK = "#050506"

# Browser-tab favicon — the accent chip that mirrors the topbar brand mark.
_FAVICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    f'<rect width="24" height="24" rx="5" fill="{ACCENT}"/>'
    f'<g transform="translate(4.5 4.5) scale(0.625)" fill="{_ACCENT_INK}">'
    f'<path d="{_LOGOS[PLATFORM_KEY]}"/></g></svg>'
)
_FAVICON_LINK = (
    '<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,'
    + quote(_FAVICON_SVG) + '"/>'
)

# Prompt ">_" mark for the CodeTrace cross-link, echoing the CodeTrace favicon.
_CODETRACE_GLYPH = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"'
    ' stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<path d="M6 8l4 4-4 4"/><path d="M13.5 16h4.5"/></svg>'
)


def _topbar(logo_svg: str, show_menu_btn: bool = True) -> str:
    menu_btn = '<button class="menu-btn" aria-label="Toggle navigation">&#9776;</button>' if show_menu_btn else ""
    return f"""
<header class="topbar">
  {menu_btn}
  <a class="brand" href="/"><span class="glyph">{logo_svg}</span>{PLATFORM}<span class="sub">/ API</span></a>
  <nav class="topnav">
    <a href="/">Home</a>
    <a href="/docs">OpenAPI</a>
    <a href="/redoc">ReDoc</a>
    <a class="icon" href="https://github.com/{REPO}" target="_blank" rel="noreferrer" title="View source on GitHub" aria-label="GitHub repository">{_GITHUB_ICON}</a>
    <a class="ct-link" href="{CODETRACE_URL}" target="_blank" rel="noreferrer" title="Browse every platform on CodeTrace">{_CODETRACE_GLYPH}CodeTrace&nbsp;&#8599;</a>
    <a class="cta" href="/playground">Try it</a>
  </nav>
</header>"""


def _playground_html() -> str:
    logo_svg = f'<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="{_LOGOS[PLATFORM_KEY]}"/></svg>'
    canonical_rows = _playground_rows(CANONICAL_ENDPOINTS)
    legacy_section = ""
    if LEGACY_ENDPOINTS:
        legacy_section = f"""
  <div class="pg-group-label">
    <span>Legacy endpoints &middot; {len(LEGACY_ENDPOINTS)}</span>
    <button type="button" class="pg-legacy-toggle" aria-expanded="false">Show<span class="chev">&rsaquo;</span></button>
  </div>
  <div class="eps pg-legacy-list">{_playground_rows(LEGACY_ENDPOINTS)}</div>
"""
    body = f"""
{_topbar(logo_svg, show_menu_btn=False)}
<main class="pg-main">
  <div class="pg-eyebrow">Live Playground &middot; {PLATFORM}</div>
  <h1 class="pg-h1">Try every {PLATFORM} endpoint</h1>
  <p class="pg-sub">Enter a {PARAM} once, then run any endpoint below straight against the live API. Requests are made directly from your browser &mdash; nothing is sent anywhere else.</p>

  <div class="pg-bar">
    <form class="pg-form" autocomplete="off">
      <div class="pg-bar-row">
        <div class="pg-input-wrap">
          <span class="pg-input-icon">{_SEARCH_SVG}</span>
          <input class="pg-input" type="text" placeholder="Enter {PLATFORM} {PARAM} (e.g. {SAMPLE})" aria-label="{PLATFORM} {PARAM}"/>
          <button type="button" class="pg-input-clear" aria-label="Clear {PARAM}" tabindex="-1">&times;</button>
          <div class="pg-recent"></div>
        </div>
        <button class="pg-btn pg-runall" type="submit">{_SEARCH_SVG}Run all</button>
      </div>
      <div class="pg-progress"><div class="pg-progress-bar"></div></div>
    </form>
    <p class="pg-hint">Path parameters such as <code class="ic">{{{PARAM}}}</code> are filled in with the value above. Prefer raw JSON in a new tab? Open <a class="link" href="{TRY_PATH}">{TRY_PATH}</a>.</p>
  </div>

  <div class="pg-group-label"><span>Canonical endpoints &middot; {len(CANONICAL_ENDPOINTS)}</span></div>
  <div class="eps pg-canonical-list">{canonical_rows}</div>
  {legacy_section}

  <p class="pg-foot-note">Want every platform in one place? Check out <a class="link" href="{CODETRACE_URL}" target="_blank" rel="noreferrer">CodeTrace</a>.</p>
</main>
"""
    script = f"var PLATFORM_KEY={json.dumps(PLATFORM_KEY)};{_PLAYGROUND_JS}"
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"/>'
        '<meta name="viewport" content="width=device-width, initial-scale=1"/>'
        + _FAVICON_LINK +
        f"<title>{PLATFORM} Playground</title>"
        '<link rel="preconnect" href="https://fonts.googleapis.com"/>'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet"/>'
        f"<style>:root{{--accent:{ACCENT};}}</style>"
        f"<style>{_BASE_CSS}{_PLAYGROUND_CSS}</style></head><body>"
        f"{body}<script>{script}</script></body></html>"
    )




def _docs_html(title_suffix: str = "Stats API") -> str:
    param = "{" + PARAM + "}"
    logo_svg = f'<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="{_LOGOS[PLATFORM_KEY]}"/></svg>'
    canonical = _endpoint_rows(CANONICAL_ENDPOINTS)
    legacy = (
        f'<div class="eps">{_endpoint_rows(LEGACY_ENDPOINTS, is_legacy=True)}</div>'
        if LEGACY_ENDPOINTS
        else '<p>No legacy aliases &mdash; every path already uses the canonical route files.</p>'
    )

    curl_sample = (
        f'<span class="cmt"># Fetch a {PLATFORM} profile</span>\n'
        f'curl <span data-origin></span>/{SAMPLE}/profile'
    )
    envelope_sample = _esc(
        "{\n"
        '  "status": "success",\n'
        f'  "platform": "{PLATFORM.lower()}",\n'
        f'  "{PARAM}": "{SAMPLE}",\n'
        '  "cached": false,\n'
        '  "data": { ... }\n'
        "}"
    )

    body = f"""
{_topbar(logo_svg)}
<div class="wrap">
  <aside class="side">
    <div class="search">{_SEARCH_SVG}<input placeholder="Search the docs..." aria-label="Search"/><kbd>/</kbd></div>
    <div class="navgroup"><h4>Get Started</h4>
      <a href="#introduction" data-nav>Introduction</a>
      <a href="#quickstart" data-nav>Quickstart</a>
      <a href="#envelope" data-nav>Response Envelope</a>
    </div>
    <div class="navgroup"><h4>Endpoints</h4>
      <a href="#canonical" data-nav>Canonical</a>
      <a href="#legacy" data-nav>Legacy</a>
    </div>
    <div class="navgroup"><h4>Reference</h4>
      <a href="/playground">Live Playground</a>
      <a href="/docs">OpenAPI Explorer</a>
      <a href="/redoc">ReDoc</a>
      <a href="{CODETRACE_URL}" target="_blank" rel="noreferrer">CodeTrace &#8599;</a>
    </div>
  </aside>

  <main class="doc">
    <section id="introduction">
      <div class="eyebrow">Stat API &middot; {PLATFORM}</div>
      <h1 class="title">{PLATFORM} {title_suffix}</h1>
      <p class="lede">{DESCRIPTION}</p>
      <p class="lede">Every canonical endpoint shares one response envelope across all platforms, so you can swap providers without rewriting your client. Legacy aliases stay available and are clearly marked.</p>
      <div class="metarow">
        <span class="chip">REST</span>
        <span class="chip">JSON</span>
        <span class="chip">No auth</span>
        <span class="chip">{param}</span>
      </div>
    </section>

    <div class="steps">
      <section class="section" id="quickstart">
        <div class="section-head"><span class="step">1</span><h2>Make your first request</h2></div>
        <p>Send a <code class="ic">GET</code> request to any handle. Replace <code class="ic">{SAMPLE}</code> with the {PARAM} you want to inspect &mdash; no API key required.</p>
        <div class="code">
          <div class="cap"><span class="dot"></span>Terminal<button class="copy">Copy</button></div>
          <pre>{curl_sample}</pre>
        </div>
        <div class="callout">
          <span class="ic">i</span>
          <div><span class="t">Tip</span>
            <p>Prefer a browser? Try the <a class="link" href="/playground">live playground</a>, open <a class="link" href="{TRY_PATH}">{TRY_PATH}</a> for raw JSON, or explore every route interactively in the <a class="link" href="/docs">OpenAPI explorer</a>.</p>
          </div>
        </div>
      </section>

      <section class="section" id="envelope">
        <div class="section-head"><span class="step">2</span><h2>Response envelope</h2></div>
        <p>Successful responses follow one consistent shape. The <code class="ic">data</code> object carries the endpoint-specific payload while the outer fields stay identical everywhere.</p>
        <div class="code">
          <div class="cap"><span class="dot"></span>200 OK &middot; application/json<button class="copy">Copy</button></div>
          <pre>{envelope_sample}</pre>
        </div>
      </section>

      <section class="section" id="canonical">
        <div class="section-head"><span class="step">3</span><h2>Canonical endpoints</h2></div>
        <p>The canonical surface &mdash; build against these. Click any endpoint to see its path parameters and an example response.</p>
        <div class="eps">{canonical}</div>
      </section>

      <section class="section" id="legacy">
        <div class="section-head"><span class="step">4</span><h2>Legacy compatibility</h2></div>
        <p>Kept working for existing integrations. Prefer the canonical routes above for anything new.</p>
        {legacy}
      </section>
    </div>

    <div class="foot">
      <span>{PLATFORM} {title_suffix} &middot; part of the Stat API</span>
      <span><a href="/docs">OpenAPI</a> &middot; <a href="/redoc">ReDoc</a></span>
    </div>
  </main>

  <aside class="toc">
    <h5>On this page</h5>
    <a href="#introduction" data-toc>Introduction</a>
    <a href="#quickstart" data-toc>Quickstart</a>
    <a href="#envelope" data-toc>Response Envelope</a>
    <a href="#canonical" data-toc>Canonical Endpoints</a>
    <a href="#legacy" data-toc>Legacy Compatibility</a>
  </aside>
</div>
"""

    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"/>'
        '<meta name="viewport" content="width=device-width, initial-scale=1"/>'
        + _FAVICON_LINK +
        f"<title>{PLATFORM} {title_suffix}</title>"
        '<link rel="preconnect" href="https://fonts.googleapis.com"/>'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet"/>'
        f"<style>:root{{--accent:{ACCENT};}}</style>"
        f"<style>{_BASE_CSS}</style></head><body>"
        f"{body}<script>{_JS}</script>{_POSTHOG_SCRIPT}</body></html>"
    )


@router.api_route("/ph/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"], include_in_schema=False)
async def posthog_proxy(path: str, request: Request) -> Response:
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in {"host", "content-length"}
    }
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        upstream = await client.request(
            request.method,
            f"{POSTHOG_PROXY_HOST}/{path}",
            params=request.query_params,
            content=await request.body(),
            headers=headers,
        )
    response_headers = {
        key: value
        for key, value in upstream.headers.items()
        if key.lower() not in {"connection", "content-encoding", "transfer-encoding"}
    }
    return Response(content=upstream.content, status_code=upstream.status_code, headers=response_headers)


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def docs() -> HTMLResponse:
    return HTMLResponse(_docs_html())


@router.get("/playground", response_class=HTMLResponse, include_in_schema=False)
async def playground() -> HTMLResponse:
    return HTMLResponse(_playground_html())


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard() -> HTMLResponse:
    return HTMLResponse(_docs_html("Dashboard"))
