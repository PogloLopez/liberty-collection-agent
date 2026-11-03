// Demo local (D38): chat simulado, panel del pipeline y consola de cartera. Sin build ni dependencias.
const $ = (sel) => document.querySelector(sel);
let conversacion = null;
let ocupado = false;
let clientes = [];
let clienteActivo = null; // el de la conversación abierta, no el del selector

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

// --- Chat ---

function burbuja(clase, texto, etiqueta) {
  const chat = $("#chat");
  chat.querySelector(".vacio")?.remove();
  const div = document.createElement("div");
  div.className = `burbuja ${clase}`;
  div.innerHTML = (etiqueta ? `<span class="etiqueta">${etiqueta}</span>` : "") + enlaces(texto);
  chat.append(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

function aviso(texto) {
  const p = document.createElement("p");
  p.className = "sistema";
  p.textContent = texto;
  $("#chat").append(p);
  $("#chat").scrollTop = $("#chat").scrollHeight;
}

function tarjeta(t) {
  const div = burbuja("agente", t.texto, "Tarjeta con botones");
  const botones = document.createElement("div");
  botones.className = "botones";
  for (const [boton, rotulo] of [["btn_confirmar", "Confirmar"], ["btn_cancelar", "Cancelar"]]) {
    const b = document.createElement("button");
    b.textContent = rotulo;
    b.onclick = () => {
      document.querySelectorAll(".botones button").forEach((x) => (x.disabled = true));
      enviar({ boton }, `[toca «${rotulo}»]`);
    };
    botones.append(b);
  }
  div.append(botones);
}

// Solo demo (D40): el globo muestra los cuatro dígitos cuando el agente los pide.
function globo(visible) {
  const c = clientes.find((x) => x.customer_id === clienteActivo);
  const g = $("#globo");
  if (visible && c?.cedula_demo) {
    g.innerHTML = `Solo demo: la cédula de ${escapar(c.nombre.split(" ")[0])} termina en<b>${escapar(c.cedula_demo)}</b>`;
    g.classList.remove("apagado");
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
  if (!cuerpo.boton) burbuja("cliente", cuerpo.texto);
  estado("El agente está escribiendo…");
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
    estado("");
    if (conversacion) habilitar(true);
  }
}

function habilitar(si) {
  $("#texto").disabled = !si;
  $("#enviar").disabled = !si;
  if (si) $("#texto").focus();
}

const estado = (t) => ($("#estado").textContent = t);

// --- Panel del pipeline ---

function grupo(titulo, pasos) {
  const li = document.createElement("li");
  li.className = "grupo";
  li.innerHTML = `<h3>${escapar(titulo)}</h3>` + pasos.map(([nombre, detalle]) => {
    const alerta = /bloqueada|rechazad|abusivo|fallida|vencida/.test(detalle) ? " alerta" : "";
    return `<div class="paso${alerta}"><b>${escapar(nombre)}</b><span>${escapar(detalle)}</span></div>`;
  }).join("");
  $("#pasos").append(li);
  li.scrollIntoView({ block: "nearest" });
}

// --- Campaña ---

async function campana() {
  const cid = $("#cliente").value;
  $("#chat").innerHTML = "";
  $("#pasos").innerHTML = "";
  conversacion = null;
  habilitar(false);
  globo(false);
  try {
    const datos = await api("campana", { customer_id: cid });
    grupo("Campaña saliente", datos.pasos);
    if (!datos.conversacion_id) {
      aviso("El filtro no dejó enviar la plantilla");
      return;
    }
    conversacion = datos.conversacion_id;
    clienteActivo = cid;
    burbuja("plantilla", datos.plantilla, "Plantilla aprobada");
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
const fila = (celdas, extra = "") => `<tr ${extra}>${celdas.map((c) => `<td>${escapar(String(c ?? ""))}</td>`).join("")}</tr>`;
const tarjetaConsola = (titulo, contenido) => `<article class="tarjeta"><h3>${titulo}</h3>${contenido}</article>`;

async function consola() {
  const d = await api("cartera");
  const colas = ["basica", "negociacion", "especializada", "reclamos"];
  $("#vivo").innerHTML = [
    tarjetaConsola("Conversaciones", tabla(["ID", "Cliente", "Segmento", "Turno", "Estado"],
      d.conversaciones.map((c, i) => fila([c.conversacion_id, c.nombre, c.segmento, c.turno,
        c.cerrada ? `cerrada (${c.motivo_cierre})` : "abierta"], `class="clic" data-i="${i}"`)))),
    tarjetaConsola("Bandeja de handoff", colas.map((cola) => {
      const casos = d.handoffs.filter((h) => h.cola === cola);
      return `<p><b>${cola}</b> · ${casos.length}</p>` + casos.map((h) => `<p class="nota">${escapar(h.customer_id)} · ${escapar(h.motivo)}: ${escapar(h.resumen)}</p>`).join("");
    }).join("")),
    tarjetaConsola("Promesas de pago", tabla(["Cliente", "Fecha", "Monto"],
      d.promesas.map((p) => fila([p.customer_id, p.fecha_promesa, `$${p.monto}`])))),
    tarjetaConsola("Ofertas aceptadas", tabla(["Cliente", "Oferta", "Base"],
      d.aceptaciones.map((a) => fila([a.customer_id, a.oferta_id, `$${a.monto_base}`])))),
    tarjetaConsola("Links de pago", tabla(["Cliente", "Monto", "Link"],
      d.links.map((l) => fila([l.customer_id, `$${l.monto}`, l.link_id])))),
    tarjetaConsola("No contactar y feedback", tabla(["Cliente", "Tipo", "Texto"],
      [...d.solicitudes_no_contacto.map((s) => fila([s.customer_id, "no contactar", s.texto])),
       ...d.feedbacks.map((f) => fila([f.customer_id, f.etiquetas.join(", "), f.texto]))])),
  ].join("");
  document.querySelectorAll("#vivo tr.clic").forEach((tr) => (tr.onclick = () => transcripcion(d.conversaciones[tr.dataset.i])));
}

function transcripcion(c) {
  $("#dialogo-cuerpo").innerHTML = `<h3>${escapar(c.conversacion_id)} · ${escapar(c.nombre)}</h3>` +
    c.transcripcion.map(([rol, texto]) => `<p><b>${escapar(rol)}:</b> ${escapar(texto)}</p>`).join("");
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
$("#reiniciar").onclick = async () => {
  if (!confirm("¿Borrar conversaciones y escrituras y recargar los datos de ejemplo?")) return;
  $("#reiniciar").disabled = true;
  try { await api("reiniciar", {}); location.reload(); }
  catch (e) { alert(`No se pudo reiniciar: ${e.message}`); $("#reiniciar").disabled = false; }
};

api("demo").then((d) => {
  clientes = d.clientes;
  $("#hoy").textContent = `Hoy en la demo: ${d.hoy}`;
  $("#cliente").innerHTML = clientes.map((c) =>
    `<option value="${escapar(c.customer_id)}">${escapar(c.nombre)} · ${escapar(c.segmento)}</option>`).join("");
});
modulos();
