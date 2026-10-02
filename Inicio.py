import base64
import io
import json

import numpy as np
import streamlit as st
from openai import OpenAI
from PIL import Image
from streamlit_drawable_canvas import st_canvas

# ---------------- Configuración ----------------
st.set_page_config(page_title="Pizarra Tutor", page_icon="✏️", layout="centered")

PIZARRA = "#1E3B2F"
PIZARRA_BORDE = "#5B4636"
TIZA = "#F2F2EC"
TIZA_AMARILLA = "#F4D35E"
TIZA_AZUL = "#8EC5E8"
TIZA_ROSA = "#F2A1B5"

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Caveat:wght@600;700&family=Inter:wght@400;500;600&display=swap');
    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
    .stApp {{ background: #14211B; color: {TIZA}; }}
    section[data-testid="stSidebar"] {{ background: #192A22; }}
    .titulo {{
        font-family: 'Caveat', cursive; font-size: 3.4rem; line-height: 1;
        color: {TIZA}; margin: 0.2rem 0 0.2rem 0;
        text-shadow: 0 0 1px rgba(242,242,236,.6), 1px 1px 0 rgba(242,242,236,.15);
    }}
    .subtitulo {{ color: #B9C7BE; font-size: 1rem; margin-bottom: 1.2rem; }}
    .marco iframe {{ border-radius: 6px; }}
    div[data-testid="stCanvas"], iframe[title="streamlit_drawable_canvas.st_canvas"] {{
        border: 10px solid {PIZARRA_BORDE}; border-radius: 12px;
        box-shadow: inset 0 0 30px rgba(0,0,0,.4);
    }}
    .stButton > button {{
        border-radius: 10px; border: 1px solid {TIZA_AMARILLA};
        background: transparent; color: {TIZA_AMARILLA}; font-weight: 600;
        padding: 0.55rem 1.2rem;
    }}
    .stButton > button:hover {{ background: {TIZA_AMARILLA}; color: #14211B; }}
    div[data-testid="stMetric"] {{
        background: #1B3027; border-radius: 12px; padding: 0.7rem 0.9rem;
    }}
    .respuesta {{
        background: {PIZARRA}; border-left: 4px solid {TIZA_AMARILLA};
        border-radius: 10px; padding: 0.9rem 1.1rem; margin: 0.8rem 0;
        font-size: 1.1rem;
    }}
    .transcripcion {{
        font-family: 'Caveat', cursive; font-size: 1.6rem; color: {TIZA};
        background: {PIZARRA}; border-radius: 10px; padding: 0.6rem 1rem;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------- Barra lateral ----------------
with st.sidebar:
    st.markdown("### 🔑 Clave")
    api_key = st.text_input("OpenAI API Key", type="password")

    st.markdown("### 📚 Clase")
    materia = st.selectbox(
        "Materia",
        ["Matemáticas", "Física", "Química", "Finanzas / Contabilidad", "Estadística", "Otra"],
    )
    nivel = st.radio("Nivel de explicación", ["Básico", "Detallado"], horizontal=True)

    st.markdown("### 🖍️ Tiza")
    modo = st.radio("Herramienta", ["Tiza", "Borrador"], horizontal=True)
    color_tiza = st.selectbox(
        "Color",
        ["Blanca", "Amarilla", "Azul", "Rosada"],
        disabled=(modo == "Borrador"),
    )
    grosor = st.slider("Grosor", 1, 25, 4 if modo == "Tiza" else 20)

colores = {"Blanca": TIZA, "Amarilla": TIZA_AMARILLA, "Azul": TIZA_AZUL, "Rosada": TIZA_ROSA}
trazo = PIZARRA if modo == "Borrador" else colores[color_tiza]

# ---------------- Estado ----------------
if "lienzo_id" not in st.session_state:
    st.session_state.lienzo_id = 0
if "resultado" not in st.session_state:
    st.session_state.resultado = None

# ---------------- Encabezado ----------------
st.markdown('<div class="titulo">Pizarra Tutor ✏️</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitulo">Escribe tu ejercicio a mano y te lo explico paso a paso.</div>',
    unsafe_allow_html=True,
)

# ---------------- Lienzo ----------------
lienzo = st_canvas(
    fill_color="rgba(0,0,0,0)",
    stroke_width=grosor,
    stroke_color=trazo,
    background_color=PIZARRA,
    height=380,
    width=680,
    drawing_mode="freedraw",
    key=f"pizarra_{st.session_state.lienzo_id}",
)

col_a, col_b = st.columns(2)
with col_a:
    resolver = st.button("Resolver ejercicio", use_container_width=True)
with col_b:
    if st.button("Borrar pizarra", use_container_width=True):
        st.session_state.lienzo_id += 1
        st.session_state.resultado = None
        st.rerun()


# ---------------- Funciones ----------------
def lienzo_a_base64(datos):
    img = Image.fromarray(datos.astype("uint8"), "RGBA")
    fondo = Image.new("RGBA", img.size, PIZARRA)
    fondo.alpha_composite(img)
    buffer = io.BytesIO()
    fondo.convert("RGB").save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def pizarra_vacia(resultado_lienzo):
    if resultado_lienzo.json_data is None:
        return True
    return len(resultado_lienzo.json_data.get("objects", [])) == 0


def pedir_tutor(clave, imagen_b64, materia, nivel):
    cliente = OpenAI(api_key=clave)
    detalle = (
        "Explica cada paso en una sola frase corta."
        if nivel == "Básico"
        else "Explica cada paso con detalle, diciendo qué regla o propiedad usas y por qué."
    )
    instrucciones = f"""
Eres un tutor universitario paciente de {materia}. En la imagen hay un ejercicio escrito a mano
con tiza sobre una pizarra. {detalle}
Usa LaTeX entre signos $ para las expresiones matemáticas.
Responde SOLO con un JSON con estas claves:
- "transcripcion": el ejercicio tal como lo lees, en texto.
- "tema": el tema específico (por ejemplo "Derivadas por regla de la cadena").
- "dificultad": "Fácil", "Media" o "Difícil".
- "pasos": lista de strings, cada uno un paso de la solución.
- "respuesta_final": la respuesta final.
- "concepto": explicación del concepto clave en 2 o 3 frases.
- "error_comun": un error típico que cometen los estudiantes en este tipo de ejercicio.
- "practica": un ejercicio nuevo parecido, de dificultad similar.
- "solucion_practica": la solución breve de ese ejercicio de práctica.
Si no hay un ejercicio legible, pon "transcripcion": "" y explica en "concepto" qué debe escribir el estudiante.
"""
    respuesta = cliente.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": instrucciones},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{imagen_b64}"},
                    },
                ],
            }
        ],
        max_tokens=1500,
    )
    return json.loads(respuesta.choices[0].message.content)


# ---------------- Acción ----------------
if resolver:
    if not api_key:
        st.warning("Escribe tu OpenAI API Key en la barra lateral para resolver el ejercicio.")
    elif lienzo.image_data is None or pizarra_vacia(lienzo):
        st.info("La pizarra está vacía. Escribe un ejercicio y vuelve a presionar Resolver.")
    else:
        with st.spinner("Leyendo tu pizarra..."):
            try:
                imagen = lienzo_a_base64(lienzo.image_data)
                st.session_state.resultado = pedir_tutor(api_key, imagen, materia, nivel)
                st.session_state.celebrar = True
            except Exception as e:
                st.session_state.resultado = None
                st.error(f"No se pudo resolver el ejercicio. Revisa tu API Key. Detalle: {e}")

# ---------------- Resultados ----------------
r = st.session_state.resultado
if r:
    if not r.get("transcripcion"):
        st.info(r.get("concepto", "No logré leer un ejercicio. Escribe más grande y claro."))
    else:
        st.markdown("#### Esto fue lo que leí")
        st.markdown(f'<div class="transcripcion">{r["transcripcion"]}</div>', unsafe_allow_html=True)
        st.caption("Si leí algo mal, corrígelo en la pizarra y vuelve a resolver.")

        m1, m2, m3 = st.columns(3)
        m1.metric("Materia", materia)
        m2.metric("Pasos", len(r.get("pasos", [])))
        m3.metric("Dificultad", r.get("dificultad", "—"))
        st.caption(f"Tema: {r.get('tema', '')}")

        tab1, tab2, tab3 = st.tabs(["Solución", "Concepto", "Practica"])

        with tab1:
            for i, paso in enumerate(r.get("pasos", []), start=1):
                st.markdown(f"**Paso {i}.** {paso}")
            st.markdown("**Respuesta final**")
            st.markdown(r.get("respuesta_final", ""))

        with tab2:
            st.markdown(r.get("concepto", ""))
            if r.get("error_comun"):
                st.warning(f"Error común: {r['error_comun']}")

        with tab3:
            st.markdown("Intenta este ejercicio en la pizarra antes de ver la solución:")
            st.markdown(f"> {r.get('practica', '')}")
            with st.expander("Ver solución"):
                st.markdown(r.get("solucion_practica", ""))

    if st.session_state.get("celebrar"):
        st.balloons()
        st.session_state.celebrar = False