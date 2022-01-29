import{C as b,p as m,r as y,D as O}from"./vendor.a72f7d22.js";const k=function(){const e=document.createElement("link").relList;if(e&&e.supports&&e.supports("modulepreload"))return;for(const t of document.querySelectorAll('link[rel="modulepreload"]'))a(t);new MutationObserver(t=>{for(const o of t)if(o.type==="childList")for(const r of o.addedNodes)r.tagName==="LINK"&&r.rel==="modulepreload"&&a(r)}).observe(document,{childList:!0,subtree:!0});function n(t){const o={};return t.integrity&&(o.integrity=t.integrity),t.referrerpolicy&&(o.referrerPolicy=t.referrerpolicy),t.crossorigin==="use-credentials"?o.credentials="include":t.crossorigin==="anonymous"?o.credentials="omit":o.credentials="same-origin",o}function a(t){if(t.ep)return;t.ep=!0;const o=n(t);fetch(t.href,o)}};k();const w="https://ichard26.github.io/ghstats/issue-counts.json",v="https://ichard26.github.io/ghstats/pull-counts.json",C="https://ichard26.github.io/ghstats/issue-deltas.json",x="https://ichard26.github.io/ghstats/issue-closers.json",N={id:"custom_bg",beforeDraw:s=>{const e=s.canvas.getContext("2d");e.save(),e.globalCompositeOperation="destination-over",e.fillStyle="white",e.fillRect(0,0,s.width,s.height),e.restore()}},S={id:"reset_on_doubleclick",beforeEvent:(s,e,n)=>{e.event.type=="dblclick"&&!e.replay&&(console.log("[debug] caught dblclick: reseting zoon & pan"),s.resetZoom())}};b.register(m,N,S,...y);function i(s,e){const n=document.querySelector(`#${s}-chart-section`),a=n.children[n.children.length-1].children[0];return new b(a,e)}const l=["rgba(255, 99, 132, 1)","rgba(54, 162, 235, 1)","rgba(255, 206, 86, 1)","rgba(75, 192, 192, 1)","rgba(153, 102, 255, 1)","rgba(255, 159, 64, 1)","rgba(255, 192, 203, 1)","rgb(201, 203, 207)","rgba(0, 0, 0, 1) "],L=l[0],j=l[3];function c(s,e=!1,n=!0){const a=[];for(const[t,o]of s.entries()){const r=[];o.data.forEach(f=>{const d=f.x.split("-"),h=O.utc(Number(d[0]),Number(d[1]),Number(d[2]));r.push({x:h,y:f.y})});const u={label:o.label,data:r,fill:!1,borderWidth:e?0:2};n&&(u.backgroundColor=l[t],u.borderColor=l[t]),a.push(u)}return a}const g={animation:!1,elements:{point:{radius:0}},events:["mousemove","mouseout","click","touchstart","touchmove","dblclick"],interaction:{axis:"xy",mode:"nearest",intersect:!1},layout:{padding:8},plugins:{zoom:{pan:{enabled:!0},zoom:{mode:"xy",drag:{enabled:!0,modifierKey:"ctrl"}}}},scales:{x:{type:"time",time:{tooltipFormat:"DD T"},title:{display:!0,text:"Date"}},y:{title:{display:!0,text:"undefined"}}}};function p(s){const e=JSON.parse(JSON.stringify(g));return e.scales.y.title.text=s,e}function _(s){const e=JSON.parse(JSON.stringify(g));return e.scales.y.title.text=s,e.elements={bar:{}},e.elements.bar.backgroundColor=n=>n.parsed.y>0?j:L,e}async function D(){let s=performance.now(),e=await fetch(w);const n=await e.json();i("black-issues",{type:"line",data:{datasets:c(n)},options:p("Open issues")}),e=await fetch(v);const a=await e.json();i("black-pulls",{type:"line",data:{datasets:c(a)},options:p("Open pulls")}),e=await fetch(C);const t=await e.json();i("black-issue-deltas",{type:"bar",data:{datasets:c(t,!0,!1)},options:_("changes")}),e=await fetch(x);const o=await e.json();i("black-issue-closers",{type:"line",data:{datasets:c(o)},options:p("Closed issues")});const r=Math.round(performance.now()-s);console.log(`[debug] loading charts took ${r} milliseconds`)}D();
