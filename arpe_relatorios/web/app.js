"use strict";
const $ = (s, r = document) => r.querySelector(s);
const fmt = (n, c = 0) => n == null ? "—" : Number(n).toLocaleString("pt-BR", {minimumFractionDigits: c, maximumFractionDigits: c});
const cssv = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
let S = null, charts = {}, periodoAlvo = null, anoLista = null;

async function api(rota, corpo) {
  const r = await fetch(rota, corpo === undefined ? {} : {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(corpo)});
  const j = await r.json();
  if (!r.ok || j.erro) throw new Error(j.erro || r.statusText);
  return j;
}
function toast(msg, erro) {
  const t = $("#toast"); t.textContent = msg; t.className = "toast" + (erro ? " err" : ""); t.hidden = false;
  clearTimeout(toast.t); toast.t = setTimeout(() => t.hidden = true, erro ? 7000 : 3800);
}
async function carregar(ano) {
  try { S = await api("/api/estado" + (ano ? "?ano=" + ano : "")); } catch (e) { toast(e.message, true); return; }
  desenhar();
}

// ---------------------------------------------------------------- KPIs
const KPI = [
  ["Meta anual", "meta", "#2f5fb8", "--azul-bg", "trend", v => fmt(v)],
  ["Realizado", "realizado", "#1f9d55", "--verde-bg", "brief", v => fmt(v)],
  ["% da meta", "pct_meta", "#ec7f2a", "--laranja-bg", "trend", v => fmt(v, 1) + "%"],
  ["Municípios fiscalizados", "municipios", "#7c3fd0", "--roxo-bg", "pin", v => fmt(v)],
  ["NCs detectadas", "nc_detectadas", "#d63a35", "--verm-bg", "target", v => fmt(v)],
  ["NCs pendentes", "nc_pendentes", "#8a4a37", "--marrom-bg", "alert", v => fmt(v)],
];
function desenharKpis() {
  $("#kpis").innerHTML = KPI.map(([rot, k, cor, bg, ic, f]) =>
    `<div class="kpi" style="--c:${cor};--cb:var(${bg})"><div class="rot">${rot}</div><div class="val">${f(S.kpis[k])}</div>
     <span class="chip"><svg class="i"><use href="#i-${ic}"/></svg></span></div>`).join("");
}

// ---------------------------------------------------------------- gráficos
Chart.defaults.font.family = '"Inter","Segoe UI",system-ui,sans-serif';
function base() {
  const tx = cssv("--tx2"), grade = cssv("--bd");
  Chart.defaults.color = tx;
  return {tx, grade};
}
function grafico(id, cfg) {
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart($("#" + id), cfg);
}
const rotulosBarra = {id: "rot", afterDatasetsDraw(c, _a, o) {
  if (!o.on) return;
  const {ctx} = c; ctx.save(); ctx.fillStyle = cssv("--tx"); ctx.font = "600 12px Inter,sans-serif"; ctx.textAlign = "center";
  c.data.datasets.forEach((d, i) => { if (d.rotulo === false) return; const m = c.getDatasetMeta(i); if (m.type !== "bar") return;
    m.data.forEach((b, j) => { const v = d.data[j]; if (v) { ctx.textBaseline = v >= 0 ? "bottom" : "top"; ctx.fillText(v, b.x, v >= 0 ? b.y - 4 : b.y + 4); } }); });
  ctx.restore();
}};
function desenharGraficos() {
  const s = S.series, {tx, grade} = base(), n = s.ultimo_mes;
  const opt = (extra = {}) => ({responsive: true, maintainAspectRatio: false, animation: {duration: 600},
    plugins: {legend: {labels: {boxWidth: 22, boxHeight: 3, padding: 16}}, rot: {on: false}, tooltip: {padding: 10, cornerRadius: 10}}, ...extra});
  const eixos = (extra = {}) => ({x: {grid: {display: false}, border: {color: grade}}, y: {grid: {color: grade}, border: {display: false}, beginAtZero: true, ...extra}});
  $("#tMensal").textContent = `Fiscalizações por mês · meta × realizado (${S.ano})`;
  grafico("cMensal", {type: "bar", plugins: [rotulosBarra], data: {labels: s.meses, datasets: [
    {label: "Realizado", data: s.realizado.map((v, i) => i < n ? v : null), backgroundColor: "#3361b5", borderRadius: {topLeft: 9, topRight: 9}, borderSkipped: false, maxBarThickness: 40, order: 2},
    {type: "line", label: `Meta mensal (${fmt(s.meta_mensal)})`, data: s.meses.map(() => s.meta_mensal), borderColor: "#ec8a3a", borderWidth: 2.5, pointRadius: 0, rotulo: false, order: 1}]},
    options: opt({scales: eixos(), plugins: {legend: {position: "top", align: "end", labels: {boxWidth: 22, boxHeight: 3, padding: 16}}, rot: {on: true}}})});
  grafico("cAcum", {type: "line", data: {labels: s.meses, datasets: [
    {label: "Meta acumulada", data: s.acum_meta, borderColor: "#ec8a3a", backgroundColor: "#ec8a3a", pointRadius: 4, borderWidth: 2.5, tension: 0},
    {label: "Realizado acumulado", data: s.acum_real, borderColor: "#3361b5", backgroundColor: "#3361b5", pointRadius: 4, borderWidth: 2.5, tension: 0, spanGaps: false}]},
    options: opt({scales: eixos(), interaction: {mode: "index", intersect: false}, plugins: {legend: {position: "top", align: "start", labels: {boxWidth: 22, boxHeight: 3, padding: 16}}, rot: {on: false}}})});
  const cores = ["#3361b5", "#1f9d55", "#ec8a3a", "#7c3fd0", "#d63a35", "#0e9fb3", "#8a4a37", "#7f8794"];
  grafico("cSeg", {type: "bar", data: {labels: s.segmentos.map(x => x.nome), datasets: [{label: "Fiscalizações", data: s.segmentos.map(x => x.total),
    backgroundColor: s.segmentos.map((_, i) => cores[i % cores.length]), borderRadius: 9, borderSkipped: false, maxBarThickness: 46}]},
    options: opt({indexAxis: "y", scales: {x: {grid: {color: grade}, border: {display: false}}, y: {grid: {display: false}}},
      plugins: {legend: {display: false}, rot: {on: false}, tooltip: {callbacks: {afterLabel: c => fmt(s.segmentos[c.dataIndex].pct, 2) + "% do total"}}}})});
  const mun = s.municipios.slice(0, 25);
  grafico("cMun", {type: "bar", data: {labels: mun.map(x => x.nome), datasets: [{label: "Fiscalizações", data: mun.map(x => x.total), backgroundColor: "#3361b5", borderRadius: 7, borderSkipped: false, maxBarThickness: 18}]},
    options: opt({indexAxis: "y", scales: {x: {grid: {color: grade}, border: {display: false}}, y: {grid: {display: false}, ticks: {font: {size: 11}, autoSkip: false}}}, plugins: {legend: {display: false}, rot: {on: false}}})});
  const L = s.meses.slice(0, n), neg = a => a.slice(0, n).map(v => v == null ? null : -v);
  grafico("cNC", {type: "bar", plugins: [rotulosBarra], data: {labels: L, datasets: [
    {label: "Detectadas", data: neg(s.nc_detectadas), backgroundColor: "#ec8a3a", borderRadius: 6, borderSkipped: false},
    {label: "Sanadas", data: s.nc_sanadas.slice(0, n), backgroundColor: "#1f9d55", borderRadius: 6, borderSkipped: false},
    {label: "Pendentes", data: neg(s.nc_pendentes), backgroundColor: "#d63a35", borderRadius: 6, borderSkipped: false}]},
    options: opt({scales: {x: {grid: {display: false}}, y: {grid: {color: grade}, border: {display: false}, ticks: {callback: v => Math.abs(v)}}},
      plugins: {legend: {position: "bottom", labels: {boxWidth: 22, boxHeight: 3, padding: 16}}, rot: {on: true},
        tooltip: {callbacks: {label: c => `${c.dataset.label}: ${Math.abs(c.parsed.y)}`}}}})});
  const fr = s.frequencia;
  grafico("cFreq", {type: "bar", data: {labels: fr.map(x => x["Não conformidade"].length > 46 ? x["Não conformidade"].slice(0, 44) + "…" : x["Não conformidade"]),
    datasets: [{label: "Ocorrências", data: fr.map(x => x["Frequência"]), backgroundColor: "#d63a35", borderRadius: 7, borderSkipped: false, maxBarThickness: 22}]},
    options: opt({indexAxis: "y", scales: {x: {grid: {color: grade}, border: {display: false}}, y: {grid: {display: false}, ticks: {font: {size: 11}}}}, plugins: {legend: {display: false}, rot: {on: false}}})});
}

// ---------------------------------------------------------------- tabelas
function desenharTabela() {
  const sel = $("#tabSel"), antes = sel.value;
  sel.innerHTML = Object.keys(S.tabelas).map(k => `<option>${k}</option>`).join("");
  if (antes && S.tabelas[antes]) sel.value = antes;
  const t = S.tabelas[sel.value], f = v => v == null ? "" : (typeof v === "number" ? fmt(v, Number.isInteger(v) ? 0 : 2) : v);
  $("#tabela").innerHTML = `<table><thead><tr><th></th>${t.colunas.map(c => `<th>${c}</th>`).join("")}</tr></thead><tbody>` +
    t.linhas.map(l => `<tr class="${/^total$/i.test(l.nome) ? "total" : ""}"><td>${l.nome}</td>${l.valores.map(v => `<td class="${v === 0 ? "z" : ""}">${f(v)}</td>`).join("")}</tr>`).join("") + "</tbody></table>";
}

// ---------------------------------------------------------------- relatórios
const esc = t => t.replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
function desenharAvisos(lista) {
  const box = $("#avisos");
  box.innerHTML = lista.map((a, i) => `<div class="aviso-item"><svg class="i"><use href="#i-alert"/></svg><span>${esc(a)}</span>
    <button class="btn" data-av="${i}" title="Confirmo a ocorrência: não exibir mais este alerta">Confirmar e dispensar</button></div>`).join("") +
    (S.avisos_dispensados ? `<button class="reexibir" id="reexibir">${S.avisos_dispensados} alerta(s) dispensado(s) · reexibir</button>` : "");
  box.querySelectorAll("[data-av]").forEach(b => b.onclick = async () => {
    await api("/api/alerta", {texto: lista[+b.dataset.av]}); await carregar(S.ano); toast("Alerta dispensado");
  });
  const r = $("#reexibir"); if (r) r.onclick = async () => { await api("/api/alerta", {acao: "reexibir"}); await carregar(S.ano); };
}
const optMes = (lista, sel) => lista.map(p => `<option value="${p.label}" ${p.label === sel ? "selected" : ""}>${p.nome}</option>`).join("");
function desenharRelatorios() {
  const box = $("#proximo");
  if (S.proximo) {
    const p = S.periodos.find(x => x.label === S.proximo);
    box.className = "proximo";
    box.innerHTML = `<div class="ic"><svg class="i"><use href="#i-doc"/></svg></div><div class="tx"><small>Próximo relatório</small><h2>${S.proximo_nome}</h2>
      <p>${p.n_fisc} fiscalizações · ${p.n_nc} não conformidades registradas no mês</p></div>
      <button class="btn" id="btnGerarProx"><svg class="i"><use href="#i-doc"/></svg>Gerar relatório</button>`;
    $("#btnGerarProx").onclick = () => abrirDialogo(S.proximo);
  } else {
    box.className = "proximo ok";
    box.innerHTML = `<div class="ic"><svg class="i"><use href="#i-check"/></svg></div><div class="tx"><small>Tudo em dia</small><h2>Nenhum relatório pendente</h2><p>Você ainda pode regerar qualquer mês na lista abaixo.</p></div>`;
  }
  desenharAvisos(S.avisos || []);
  const anos = [...new Set(S.periodos.map(p => p.ano))];
  if (!anos.includes(anoLista)) anoLista = anos.includes(S.ano) ? S.ano : anos[0];
  $("#filtroAno").innerHTML = anos.map(a => `<option ${a === anoLista ? "selected" : ""}>${a}</option>`).join("");
  $("#listaPeriodos").innerHTML = `<thead><tr><th>Período</th><th>Fiscalizações</th><th>NCs</th><th>Situação</th><th>Arquivo</th><th></th></tr></thead><tbody>` +
    S.periodos.filter(p => p.ano === anoLista).map(p => `<tr><td><b>${p.nome}</b></td><td>${p.n_fisc}</td><td>${p.n_nc}</td>
      <td><span class="selo ${p.status}">${p.status_txt}</span></td>
      <td>${p.arquivo ? `<a href="/api/download?nome=${encodeURIComponent(p.arquivo)}">${p.arquivo}</a>` : "—"}</td>
      <td><button class="btn" data-g="${p.label}">${p.status === "pendente" ? "Gerar" : "Gerar novamente"}</button>
      ${p.status === "gerado" ? `<button class="btn" data-d="${p.label}" title="Voltar a marcar como pendente">Desmarcar</button>` : ""}</td></tr>`).join("") + "</tbody>";
  $("#listaPeriodos").querySelectorAll("[data-g]").forEach(b => b.onclick = () => abrirDialogo(b.dataset.g));
  $("#listaPeriodos").querySelectorAll("[data-d]").forEach(b => b.onclick = async () => { await api("/api/desmarcar", {periodo: b.dataset.d}); carregar(S.ano); });
  $("#cfgSaida").value = S.saida; $("#cfgTemplate").value = S.template;
  $("#cfgBaseline").innerHTML = `<option value="">(nenhum)</option>` + optMes([...S.periodos].reverse(), S.baseline);
}

// ---------------------------------------------------------------- diálogo de geração (confirma o mês antes de gerar)
function abrirDialogo(label) {
  periodoAlvo = label;
  const p = S.periodos.find(x => x.label === label);
  $("#dlgTitulo").textContent = `Gerar relatório de ${p.nome}`;
  $("#dlgSub").textContent = p.status === "pendente" ? "Confira o mês antes de gerar." : `Este período já consta como “${p.status_txt}”. O arquivo será gerado novamente.`;
  $("#dlgResumo").innerHTML = `<div><b>${p.label}</b><span>Período</span></div><div><b>${p.n_fisc}</b><span>Fiscalizações</span></div><div><b>${p.n_nc}</b><span>Não conformidades</span></div>`;
  $("#dlgPA").value = S.config.pa; $("#dlgSEI").value = S.config.sei;
  $("#dlgSint").checked = S.config.fotos_sinteticas; $("#dlgGerais").checked = S.config.condicoes_gerais;
  const av = $("#dlgAviso");
  if (S.proximo && label !== S.proximo) { av.hidden = false; av.textContent = `Atenção: o próximo pendente é ${S.proximo_nome}, mas você escolheu ${p.nome}.`; } else av.hidden = true;
  $("#veu").hidden = false; $("#dlgPA").focus();
}
async function gerar() {
  const b = $("#dlgOk"); b.disabled = true; b.querySelector("span").textContent = "Gerando…";
  try {
    const r = await api("/api/gerar", {periodo: periodoAlvo, pa: $("#dlgPA").value, sei: $("#dlgSEI").value,
      fotos_sinteticas: $("#dlgSint").checked, condicoes_gerais: $("#dlgGerais").checked});
    $("#veu").hidden = true;
    toast(`Relatório gerado: ${r.arquivo}` + (r.avisos.length ? ` · ${r.avisos.length} aviso(s)` : ""));
    S.ultimoResultado = r;
    await carregar(S.ano);
    if (r.avisos.length) desenharAvisos([...r.avisos, ...(S.avisos || [])]);
    mudarAba("rel");
    window.open("/api/download?nome=" + encodeURIComponent(r.arquivo), "_self");
  } catch (e) { toast(e.message, true); }
  b.disabled = false; b.querySelector("span").textContent = "Gerar relatório";
}

// ---------------------------------------------------------------- estrutura geral
function desenhar() {
  document.documentElement.dataset.tema = S.config.tema === "claro" ? "claro" : "";
  $("#caminho").textContent = S.arquivo;
  const er = $("#faixaErro"); er.hidden = !S.erro; er.textContent = S.erro ? "Não foi possível ler a planilha: " + S.erro : "";
  if (!S.anos.length) { $("#kpis").innerHTML = ""; return; }
  $("#ano").innerHTML = S.anos.map(a => `<option ${a === S.ano ? "selected" : ""}>${a}</option>`).join("");
  desenharKpis(); desenharGraficos(); desenharTabela(); desenharRelatorios();
  const fi = $("#faixaInicio"); fi.hidden = !S.sem_historico;
  if (S.sem_historico) $("#baselineSel").innerHTML = optMes([...S.periodos].reverse(), S.baseline_sugerido);
}
function mudarAba(a) {
  document.querySelectorAll("#abas button").forEach(b => b.classList.toggle("ativa", b.dataset.aba === a));
  document.querySelectorAll(".aba").forEach(d => d.hidden = d.id !== "aba-" + a);
  Object.values(charts).forEach(c => c.resize());
}
async function escolher(tipo, destino) {
  const r = await api("/api/escolher", {tipo});
  if (r.erro) { const c = prompt(r.erro); if (c) r.caminho = c; }
  if (r.caminho) { await api("/api/config", {[destino]: r.caminho}); await carregar(S && S.ano); toast("Configuração atualizada"); }
}
document.addEventListener("DOMContentLoaded", () => {
  $("#abas").onclick = e => e.target.dataset.aba && mudarAba(e.target.dataset.aba);
  $("#ano").onchange = e => { anoLista = +e.target.value; carregar(anoLista); };
  $("#tabSel").onchange = desenharTabela;
  $("#filtroAno").onchange = e => { anoLista = +e.target.value; desenharRelatorios(); };
  $("#btnRecarregar").onclick = async () => { await api("/api/recarregar", {}); await carregar(S && S.ano); toast("Planilha recarregada"); };
  $("#btnPlanilha").onclick = () => escolher("arquivo", "excel_path");
  $("#btnAssets").onclick = () => escolher("pasta", "assets_dir");
  document.querySelector("[data-pasta=saida]").onclick = () => escolher("pasta", "saida_dir");
  $("#btnTemplate").onclick = () => escolher("arquivo", "template_path");
  $("#btnBaseline").onclick = async () => { await api("/api/baseline", {periodo: $("#baselineSel").value}); await carregar(S.ano); toast("Histórico definido. O próximo relatório é " + S.proximo_nome); };
  $("#btnBaseline2").onclick = async () => { await api("/api/baseline", {periodo: $("#cfgBaseline").value}); await carregar(S.ano); toast("Histórico atualizado"); };
  $("#dlgCancelar").onclick = () => $("#veu").hidden = true;
  $("#dlgOk").onclick = gerar;
  document.addEventListener("keydown", e => { if (e.key === "Escape") $("#veu").hidden = true; });
  matchMedia("(prefers-color-scheme: dark)").onchange = () => S && desenharGraficos();
  carregar();
});
