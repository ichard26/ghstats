import{c as a,l as e,a as l,b as d,d as t}from"./lib.js";const r=t+"mypyc/mypyc/issue-counts.json",p=t+"mypyc/mypyc/issue-deltas.json";async function u(){let o=performance.now(),s=await fetch(r);const n=await s.json();a("issues",{type:"line",data:{datasets:e(n)},options:l("Open issues")}),s=await fetch(p);const i=await s.json();a("issue-deltas",{type:"bar",data:{datasets:e(i,!0,!1)},options:d("changes")});const c=Math.round(performance.now()-o);console.log(`[debug] loading charts took ${c} milliseconds`)}u();
