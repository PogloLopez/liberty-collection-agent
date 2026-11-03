// Demo (D38): chat simulado, panel del pipeline y consola de cartera. Sin build ni dependencias.
const $ = (sel) => document.querySelector(sel);
let conversacion = null;
let ocupado = false;
let clientes = [];
let clienteActivo = null; // el de la conversación abierta, no el del selector
let inicio = 0; // cuándo empezó la conversación: el reloj del chat arranca a las 9:00

// En la nube la API pide un código de acceso (D46): se pregunta una vez y queda en el navegador.
const leerCodigo = () => { try { return localStorage.getItem("codigo") || ""; } catch { return ""; } };
const guardarCodigo = (c) => { try { localStorage.setItem("codigo", c); } catch {} };

const api = async (ruta, cuerpo, reintento = true) => {
  const headers = { "x-codigo-acceso": leerCodigo() };
  if (cuerpo !== undefined) headers["Content-Type"] = "application/json";
  const r = await fetch(`/api/${ruta}`, {
    method: cuerpo === undefined ? "GET" : "POST",
    headers,
    body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
  });
  if (r.status === 401 && reintento) {
    guardarCodigo(prompt("Código de acceso a la demo:") || "");
    return api(ruta, cuerpo, false);
  }
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
};

const escapar = (t) => t.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const enlaces = (t) => escapar(t).replace(/(https?:\/\/[^\s)]+?)([.,]?(\s|$))/g, '<a href="#" title="$1">$1</a>$2');

const SEGMENTOS = {
  olvidadizo: "Olvidadizo",
  dificultad_temporal: "Dificultad temporal",
  mora_avanzada: "Mora avanzada",
  reincidente: "Reincidente",
  valioso_churn: "Valioso con riesgo de baja",
};
const segmento = (s) => SEGMENTOS[s] || String(s ?? "").replace(/_/g, " ");

// Guía del evaluador: quién es cada cliente de la demo y qué vale la pena probar con él.
const GUIA = {
  "CL-1171492": ["Suele pagar a tiempo; esta vez se le pasó la fecha. Tiene pago total con link y una prórroga corta.",
    ["Hola, perdón, se me pasó", "Quiero una prórroga", "¿Qué otras ofertas tienen?", "Ya pagué, ¿lo ven?"]],
  "CL-1152549": ["Este mes no le alcanza. Tiene planes de cuotas y cambio de fecha de corte, pero no descuentos.",
    ["No puedo pagar todo ahora", "¿Me pueden dar un descuento?", "Quiero pagar en cuotas", "Me pagan el 15, ¿puedo cambiar la fecha de corte?"]],
  "CL-1140215": ["Lleva meses sin pagar. Tiene cuotas y liquidaciones con descuento; las más generosas pasan por un asesor.",
    ["No voy a pagar nada", "Quiero hablar con una persona", "¿Qué descuento me dan si pago hoy?", "No me escriban más"]],
  "CL-1191572": ["Se atrasa seguido y suele prometer. Tiene pago total y un plan de cuotas, pero no prórroga: si promete pagar otro día, la regla de negocio rechaza la promesa.",
    ["Le pago todo el viernes", "Ya pagué ayer", "Esta no es mi cuenta", "¿De dónde sacaron mi número?"]],
  "CL-1100708": ["Cliente valioso que podría irse. Tiene cuotas, cambio de fecha de corte y descuentos de retención.",
    ["¿Cómo obtuvieron mi número?", "El servicio ha estado pésimo", "¿Me pueden esperar hasta mañana?", "Me voy a cambiar de compañía"]],
};

function ficha() {
  const c = clientes.find((x) => x.customer_id === $("#cliente").value);
  if (!c) return;
  const [texto, sugerencias] = GUIA[c.customer_id] || ["", []];
  $("#ficha").innerHTML = `<h2>${escapar(c.nombre)}</h2><span class="segmento">${escapar(segmento(c.segmento))}</span>
    <p>${escapar(texto)}</p>
    <h3>Para probar</h3>
    <div class="sugerencias">${sugerencias.map((s) => `<button class="sugerencia">${escapar(s)}</button>`).join("")}</div>
    <p class="nota" style="margin-top:12px">También puede escribir lo que quiera: el agente no sigue un guion.</p>`;
  document.querySelectorAll(".sugerencia").forEach((b) => (b.onclick = () => {
    if (!conversacion || c.customer_id !== clienteActivo) return estado("Primero pulse «Que sean las 9 AM».");
    $("#texto").value = b.textContent;
    $("#texto").focus();
  }));
}

// --- Chat ---

function hora() {
  const min = Math.floor((Date.now() - inicio) / 60000);
  return `${9 + Math.floor(min / 60)}:${String(min % 60).padStart(2, "0")}`;
}

function burbuja(clase, texto, etiqueta) {
  const chat = $("#chat");
  chat.querySelector(".vacio")?.remove();
  const div = document.createElement("div");
  div.className = `burbuja ${clase}`;
  const check = clase === "cliente" ? '<span class="check">✓✓</span>' : "";
  div.innerHTML = (etiqueta ? `<span class="etiqueta">${etiqueta}</span>` : "") + enlaces(texto) +
    `<span class="meta">${hora()}${check}</span>`;
  $("#tecleo") ? chat.insertBefore(div, $("#tecleo")) : chat.append(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

function aviso(texto, clase = "sistema") {
  const p = document.createElement("p");
  p.className = clase;
  p.textContent = texto;
  $("#chat").append(p);
  $("#chat").scrollTop = $("#chat").scrollHeight;
}

function tarjeta(t) {
  const div = burbuja("agente", t.texto, "Mensaje con botones");
  const botones = document.createElement("div");
  botones.className = "botones";
  for (const [boton, rotulo] of [["btn_confirmar", "Confirmar"], ["btn_cancelar", "Cancelar"]]) {
    const b = document.createElement("button");
    b.textContent = rotulo;
    b.onclick = () => {
      document.querySelectorAll(".botones button").forEach((x) => (x.disabled = true));
      enviar({ boton }, `Botón: «${rotulo}»`);
    };
    botones.append(b);
  }
  div.append(botones);
  $("#chat").scrollTop = $("#chat").scrollHeight;
}

function escribiendo(si) {
  $("#tecleo")?.remove();
  $("#presencia").textContent = si ? "escribiendo…" : conversacion ? "en línea" : "Cuenta de empresa · simulado";
  if (!si) return;
  const div = document.createElement("div");
  div.id = "tecleo";
  div.className = "escribiendo";
  div.setAttribute("aria-label", "El agente está escribiendo");
  div.innerHTML = "<i></i><i></i><i></i>";
  $("#chat").append(div);
  $("#chat").scrollTop = $("#chat").scrollHeight;
}

// Solo demo (D40): cuando el agente pide la cédula, la guía muestra los cuatro dígitos.
function globo(visible) {
  const c = clientes.find((x) => x.customer_id === clienteActivo);
  const g = $("#globo");
  if (visible && c?.cedula_demo) {
    g.innerHTML = `Solo en la demo: la cédula de ${escapar(c.nombre.split(" ")[0])} termina en<b>${escapar(c.cedula_demo)}</b>
      <div class="acciones-globo"><button id="usar">Escribir en el chat</button><button id="copiar">Copiar</button></div>`;
    g.classList.remove("apagado");
    $("#usar").onclick = () => { $("#texto").value = c.cedula_demo; $("#texto").focus(); };
    $("#copiar").onclick = async () => {
      try { await navigator.clipboard.writeText(c.cedula_demo); $("#copiar").textContent = "Copiado"; }
      catch { $("#copiar").textContent = "No se pudo copiar"; }
    };
  } else {
    g.classList.add("apagado");
  }
}

function mostrar(r) {
  globo(r.pide_cedula);
  r.mensajes.forEach((m) => burbuja("agente", m));
  if (r.tarjeta) {
    document.querySelectorAll(".botones button").forEach((x) => (x.disabled = true));
    tarjeta(r.tarjeta);
  }
  if (r.cerrada) {
    aviso("Conversación cerrada");
    habilitar(false);
    conversacion = null;
  }
}

async function enviar(cuerpo, rotulo) {
  if (!conversacion || ocupado) return;
  ocupado = true;
  habilitar(false);
  const ruta = cuerpo.boton ? "botones" : "mensajes";
  globo(false);
  estado("");
  if (!cuerpo.boton) burbuja("cliente", cuerpo.texto);
  escribiendo(true);
  try {
    const r = await api(`conversaciones/${conversacion}/${ruta}`, cuerpo);
    grupo(rotulo, r.pasos);
    mostrar(r);
  } catch (e) {
    aviso(`Error: ${e.message}`);
    // La tarjeta sigue pendiente en el servidor (D22): se puede volver a tocar.
    if (cuerpo.boton) [...document.querySelectorAll(".botones")].pop()?.querySelectorAll("button").forEach((x) => (x.disabled = false));
  } finally {
    ocupado = false;
    if (conversacion) habilitar(true);
    escribiendo(false);
  }
}

function habilitar(si) {
  $("#texto").disabled = !si;
  $("#enviar").disabled = !si;
  if (si) $("#texto").focus();
}

const estado = (t) => ($("#estado").textContent = t);

// --- Panel del pipeline ---

// Quién decide cada paso, con los mismos colores del documento de arquitectura.
const DEL_MODELO = /^(Moderación|Estratega|Reintento|Confirmación en texto)/;
const DE_CONTROL = /^(Validador|Filtro de contacto|Verificación|Datos enmascarados|Sin sentido|Respuesta fija|Pide un asesor|No contactar)/;
const ALERTA = /bloquead|rechazad|abusivo|fallida|vencida|no coincide/;

function grupo(titulo, pasos) {
  const li = document.createElement("li");
  li.className = "grupo";
  li.innerHTML = `<h3>${escapar(titulo)}</h3><ol>` + pasos.map(([nombre, detalle]) => {
    const tipo = ALERTA.test(detalle) ? "alerta" : DEL_MODELO.test(nombre) ? "llm" : DE_CONTROL.test(nombre) ? "val" : "det";
    return `<li class="paso ${tipo}"><b>${escapar(nombre)}</b><span>${escapar(detalle)}</span></li>`;
  }).join("") + "</ol>";
  $("#pasos").append(li);
  li.scrollIntoView({ block: "nearest" });
}

// --- Campaña ---

async function campana() {
  if (ocupado) return; // una respuesta en curso caería en el chat recién limpiado
  const cid = $("#cliente").value;
  $("#chat").innerHTML = "";
  $("#pasos").innerHTML = "";
  conversacion = null;
  escribiendo(false);
  habilitar(false);
  globo(false);
  estado("");
  inicio = Date.now();
  try {
    const datos = await api("campana", { customer_id: cid });
    grupo("Campaña saliente", datos.pasos);
    if (!datos.conversacion_id) {
      aviso("El filtro no dejó enviar la plantilla");
      return;
    }
    conversacion = datos.conversacion_id;
    clienteActivo = cid;
    aviso("Hoy", "dia");
    burbuja("plantilla", datos.plantilla, "Plantilla aprobada");
    escribiendo(false);
    habilitar(true);
  } catch (e) {
    aviso(`Error: ${e.message}`);
  }
}

// --- Consola de cartera ---

const tabla = (cabeceras, filas) =>
  filas.length
    ? `<table><tr>${cabeceras.map((c) => `<th>${c}</th>`).join("")}</tr>${filas.join("")}</table>`
    : '<p class="nota">Aún no hay registros en esta sesión de la demo.</p>';
// Las celdas llegan escapadas o como HTML propio (pastillas): nunca texto del cliente sin escapar.
const fila = (celdas, extra = "") => `<tr ${extra}>${celdas.map((c) => `<td>${c}</td>`).join("")}</tr>`;
const txt = (v) => escapar(String(v ?? ""));
const pastilla = (t, clase = "") => `<span class="pastilla ${clase}">${txt(t)}</span>`;
const tarjetaConsola = (titulo, contenido, clase = "") => `<article class="tarjeta ${clase}"><h3>${titulo}</h3>${contenido}</article>`;
// En las tablas, el nombre del cliente de la demo en vez de su ID.
const quien = (cid) => txt(clientes.find((c) => c.customer_id === cid)?.nombre || cid);
const COLAS = { basica: "Básica", negociacion: "Negociación", especializada: "Especializada", reclamos: "Reclamos" };

async function consola() {
  const d = await api("cartera");
  const abiertas = d.conversaciones.filter((c) => !c.cerrada).length;
  $("#indicadores").innerHTML = [
    ["Conversaciones", d.conversaciones.length, `${abiertas} abiertas`],
    ["Handoffs", d.handoffs.length],
    ["Promesas de pago", d.promesas.length],
    ["Ofertas aceptadas", d.aceptaciones.length],
    ["Links de pago", d.links.length],
  ].map(([t, n, extra]) => `<div class="indicador"><span>${t}</span><b>${n}</b>${extra ? `<span>${extra}</span>` : ""}</div>`).join("");
  $("#vivo").innerHTML = [
    tarjetaConsola("Conversaciones <span class=\"nota\">· toque una para ver la transcripción</span>",
      tabla(["ID", "Cliente", "Segmento", "Turno", "Estado"],
        d.conversaciones.map((c, i) => fila([txt(c.conversacion_id), txt(c.nombre), txt(segmento(c.segmento)),
          txt(c.turno),
          c.cerrada ? pastilla(`cerrada · ${c.motivo_cierre}`, "cerrada") : pastilla("abierta", "abierta")],
          `class="clic" data-i="${i}" tabindex="0" role="button"`))), "ancha"),
    tarjetaConsola("Bandeja de handoff", Object.entries(COLAS).map(([cola, nombre]) => {
      const casos = d.handoffs.filter((h) => h.cola === cola);
      return `<section class="cola"><header>${nombre}${pastilla(casos.length)}</header>` +
        casos.map((h) => `<p class="caso">${quien(h.customer_id)} · ${txt(h.motivo)}: ${txt(h.resumen)}</p>`).join("") + "</section>";
    }).join("")),
    tarjetaConsola("Promesas de pago", tabla(["Cliente", "Fecha", "Monto"],
      d.promesas.map((p) => fila([quien(p.customer_id), txt(p.fecha_promesa), txt(`$${p.monto}`)])))),
    tarjetaConsola("Ofertas aceptadas", tabla(["Cliente", "Oferta", "Base"],
      d.aceptaciones.map((a) => fila([quien(a.customer_id), txt(a.oferta_id), txt(`$${a.monto_base}`)])))),
    tarjetaConsola("Links de pago", tabla(["Cliente", "Monto", "Link"],
      d.links.map((l) => fila([quien(l.customer_id), txt(`$${l.monto}`), txt(l.link_id)])))),
    tarjetaConsola("No contactar y feedback", tabla(["Cliente", "Tipo", "Texto"],
      [...d.solicitudes_no_contacto.map((s) => fila([quien(s.customer_id), pastilla("no contactar"), txt(s.texto)])),
       ...d.feedbacks.map((f) => fila([quien(f.customer_id), f.etiquetas.map((e) => pastilla(e)).join(" "), txt(f.texto)]))])),
  ].join("");
  document.querySelectorAll("#vivo tr.clic").forEach((tr) => {
    const abrir = () => transcripcion(d.conversaciones[tr.dataset.i]);
    tr.onclick = abrir;
    tr.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); abrir(); } };
  });
}

function transcripcion(c) {
  const burbujas = c.transcripcion.map(([rol, texto]) =>
    `<div class="burbuja ${rol === "cliente" ? "cliente" : "agente"}">${escapar(texto)}</div>`).join("");
  $("#dialogo-cuerpo").innerHTML = `<h3>${escapar(c.conversacion_id)} · ${escapar(c.nombre)}</h3><div class="chat">${burbujas}</div>`;
  $("#dialogo").showModal();
}

const MODULOS = [
  ["Creación de agentes", "Segmento olvidadizo → perfil «recordatorio amable», 8 turnos. A/B: 50 % plantilla v1, 50 % v2.",
    "Asignaría un perfil (tono, ofertas, plantillas) a cada segmento y lanzaría pruebas A/B entre perfiles. Cada cambio pasa por la aprobación de cartera y legal."],
  ["Histórico con flags", "18 conversaciones de ejemplo · 3 marcadas para revisión · 2 con alerta de vulnerabilidad.",
    "Listaría todas las conversaciones con sus flags (revisar, protocolo, alerta) y filtros por segmento, resultado y fecha."],
  ["Feedback del asesor", "«El agente insistió demasiado con un cliente en duelo» → etiqueta: tono_inadecuado.",
    "El asesor escribiría en lenguaje natural; un modelo lo clasificaría en un catálogo cerrado y lo sumaría a los evals, no a un reentrenamiento."],
  ["Evaluación por agente y segmento", "Olvidadizo: 62 % recuperado sin descuento · Mora avanzada: 2,4 negociaciones por acuerdo.",
    "Mostraría recuperación, descuentos concedidos, tools usadas y en qué punto terminan las conversaciones, por agente y segmento."],
  ["Recomendaciones semanales", "«Dificultad temporal: ofrecer cuotas antes de la prórroga sube la tasa de acuerdo».",
    "Un agente analizaría el histórico cada semana y escribiría recomendaciones; el humano decide si cambia la configuración."],
];

function modulos() {
  $("#modulos").innerHTML = MODULOS.map(([titulo, ejemplo], i) =>
    tarjetaConsola(titulo, `<p class="nota">${escapar(ejemplo)}</p><button data-i="${i}">¿Qué haría?</button>`)).join("");
  document.querySelectorAll("#modulos button").forEach((b) => (b.onclick = () => {
    const [titulo, , explicacion] = MODULOS[b.dataset.i];
    $("#dialogo-cuerpo").innerHTML = `<h3>${escapar(titulo)}</h3><p>${escapar(explicacion)}</p>`;
    $("#dialogo").showModal();
  }));
}

// --- Arranque ---

document.querySelectorAll(".pestana").forEach((b) => (b.onclick = () => {
  document.querySelectorAll(".pestana").forEach((x) => x.classList.toggle("activa", x === b));
  document.querySelectorAll(".vista").forEach((v) => v.classList.toggle("oculta", v.id !== b.dataset.vista));
  if (b.dataset.vista === "consola") consola();
}));

$("#formulario").onsubmit = (e) => {
  e.preventDefault();
  const texto = $("#texto").value.trim();
  if (!texto) return;
  $("#texto").value = "";
  enviar({ texto }, `Mensaje: «${texto}»`);
};
$("#nueve").onclick = campana;
$("#cliente").onchange = ficha;
$("#reiniciar").onclick = async () => {
  if (!confirm("¿Borrar conversaciones y escrituras y recargar los datos de ejemplo?")) return;
  $("#reiniciar").disabled = true;
  try { await api("reiniciar", {}); location.reload(); }
  catch (e) { alert(`No se pudo reiniciar: ${e.message}`); $("#reiniciar").disabled = false; }
};

api("demo").then((d) => {
  clientes = d.clientes;
  $("#hoy").textContent = `Fecha de la demo: ${d.hoy}`;
  $("#cliente").innerHTML = clientes.map((c) =>
    `<option value="${escapar(c.customer_id)}">${escapar(c.nombre)} · ${escapar(segmento(c.segmento))}</option>`).join("");
  ficha();
});
modulos();
