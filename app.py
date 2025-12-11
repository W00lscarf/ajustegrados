import streamlit as st
import pandas as pd

# =========================
# Funciones de puntaje
# =========================

def puntos_antig_servicio(meses: float) -> int:
    if meses < 24:
        return 0
    if 24 <= meses <= 60:
        return 20
    if 61 <= meses <= 96:
        return 40
    if 97 <= meses <= 132:
        return 60
    if 133 <= meses <= 168:
        return 80
    if meses >= 169:
        return 100


def puntos_antig_grado(meses: float) -> int:
    if meses < 12:
        return 0
    if 12 <= meses <= 24:
        return 20
    if 25 <= meses <= 48:
        return 40
    if 49 <= meses <= 72:
        return 60
    if 73 <= meses <= 96:
        return 80
    if meses >= 97:
        return 100


def puntos_equidad(estamento: str, grado: int) -> int:
    """
    Tablas de equidad interna según estamento y grado,
    siguiendo la lógica de la presentación.
    """
    est = (estamento or "").strip().upper()

    if not isinstance(grado, (int, float)):
        return 0
    g = int(grado)

    # Profesional: grados 5-12
    if est.startswith("PROF"):
        if g in (5, 6):
            return 0
        if g in (7, 8):
            return 20
        if g == 9:
            return 40
        if g == 10:
            return 60
        if g == 11:
            return 80
        if g == 12:
            return 100

    # Técnico: grados 10-15
    if est.startswith("TÉC") or est.startswith("TEC"):
        if g == 10:
            return 0
        if g == 11:
            return 20
        if g == 12:
            return 40
        if g == 13:
            return 60
        if g == 14:
            return 80
        if g == 15:
            return 100

    # Administrativo: grados 11-16
    if est.startswith("ADMIN"):
        if g == 11:
            return 0
        if g == 12:
            return 20
        if g == 13:
            return 40
        if g == 14:
            return 60
        if g == 15:
            return 80
        if g == 16:
            return 100

    # Por defecto (si algo no calza con la tabla)
    return 0


def grado_siguiente(estamento: str, grado_actual: int) -> int:
    """
    Simula la mejora de grado. Asume:
    - Profesional: mínimo grado 5
    - Técnico: mínimo grado 10
    - Administrativo: mínimo grado 11
    """
    est = (estamento or "").strip().upper()
    if not isinstance(grado_actual, (int, float)):
        return grado_actual
    g = int(grado_actual)

    if est.startswith("PROF"):
        piso = 5
    elif est.startswith("TÉC") or est.startswith("TEC"):
        piso = 10
    elif est.startswith("ADMIN"):
        piso = 11
    else:
        piso = g  # si no se conoce el estamento, no baja

    if g > piso:
        return g - 1
    else:
        return g  # ya está en el mínimo


def construir_dataframe_inicial(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Limpia nombres de columnas, calcula todos los componentes de puntaje
    y deja el DataFrame listo para simular.
    """

    # Normalizar nombres de columnas (eliminamos saltos de línea, espacios duplicados)
    cols = {c: c.replace("\n", " ").strip() for c in df_raw.columns}
    df = df_raw.rename(columns=cols).copy()

    # Intentamos mapear nombres esperados (por si cambian ligeramente)
    col_ap_pat = [c for c in df.columns if "Apellido" in c and "Paterno" in c][0]
    col_ap_mat = [c for c in df.columns if "Apellido" in c and "Materno" in c][0]
    col_nombres = [c for c in df.columns if "Nombre" in c][0]
    col_grado = [c for c in df.columns if c.strip().upper() == "GRADO"][0]
    col_estamento = [c for c in df.columns if "Estamento" in c][0]
    col_ant_serv = [c for c in df.columns if "servicio" in c and "(meses)" in c][0]
    col_ant_grado = [c for c in df.columns if "grado" in c and "(meses)" in c][0]
    col_punt_calif = [c for c in df.columns if "Puntaje" in c and "Calificación" in c][0]

    df["ID"] = df.index

    df["serv_m"] = pd.to_numeric(df[col_ant_serv], errors="coerce").fillna(0)
    df["grado_m"] = pd.to_numeric(df[col_ant_grado], errors="coerce").fillna(0)

    df["serv_pts"] = df["serv_m"].apply(puntos_antig_servicio)
    df["grado_pts"] = df["grado_m"].apply(puntos_antig_grado)
    df["eq_pts"] = df.apply(
        lambda r: puntos_equidad(r[col_estamento], r[col_grado]), axis=1
    )
    df["calif_pts"] = pd.to_numeric(df[col_punt_calif], errors="coerce").fillna(0)

    # Ponderaciones según presentación: 30%, 15%, 30%, 25%
    df["serv_pond"] = df["serv_pts"] * 0.30
    df["grado_pond"] = df["grado_pts"] * 0.15
    df["eq_pond"] = df["eq_pts"] * 0.30
    df["calif_pond"] = df["calif_pts"] * 0.25

    df["Score"] = df["serv_pond"] + df["grado_pond"] + df["eq_pond"] + df["calif_pond"]

    # Guardamos nombres de columnas clave para usarlos luego
    df["_col_ap_pat"] = col_ap_pat
    df["_col_ap_mat"] = col_ap_mat
    df["_col_nombres"] = col_nombres
    df["_col_grado"] = col_grado
    df["_col_estamento"] = col_estamento

    # Variables para simulación
    df["ajustes"] = 0
    df["carencia"] = 0  # años restantes en que no puede recibir mejora

    return df


def simular_anios(df_inicial: pd.DataFrame, id_objetivo: int,
                  mejoras_por_anio: int = 20, max_anios: int = 200) -> int | None:
    """
    Simula año a año la asignación de mejoras de grado.
    Retorna el año (1-based) en que la persona con ID 'id_objetivo' recibe su primera mejora,
    o None si no la recibe en 'max_anios' años.
    """

    df = df_inicial.copy()

    col_estamento = df["_col_estamento"]
    col_grado = df["_col_grado"]

    anio_objetivo = None

    for anio in range(1, max_anios + 1):
        # Personas elegibles (sin carencia)
        elegibles = df[df["carencia"] == 0].copy()
        if elegibles.empty:
            break

        # Orden por puntaje (Score) y, como desempate, antigüedad en el servicio
        elegibles = elegibles.sort_values(
            ["Score", "serv_m"], ascending=[False, False]
        )

        seleccionados = elegibles.head(mejoras_por_anio)
        ids_sel = seleccionados["ID"].tolist()

        # Si nuestro objetivo está en los seleccionados, registramos el año y terminamos
        if (anio_objetivo is None) and (id_objetivo in ids_sel):
            anio_objetivo = anio
            break

        # Aplicar efectos de la mejora sobre los seleccionados
        mask_sel = df["ID"].isin(ids_sel)

        # Contar la mejora
        df.loc[mask_sel, "ajustes"] += 1

        # Mejorar grado
        df.loc[mask_sel, col_grado] = df.loc[mask_sel].apply(
            lambda r: grado_siguiente(r[col_estamento], r[col_grado]), axis=1
        )

        # La antigüedad en el grado se "resetea"
        df.loc[mask_sel, "grado_m"] = 0
        df.loc[mask_sel, "grado_pts"] = 0
        df.loc[mask_sel, "grado_pond"] = 0

        # Recalcular Equidad Interna y su ponderado según el nuevo grado
        df["eq_pts"] = df.apply(
            lambda r: puntos_equidad(r[col_estamento], r[col_grado]), axis=1
        )
        df["eq_pond"] = df["eq_pts"] * 0.30

        # Asignar carencia: 2 años para los seleccionados
        df.loc[mask_sel, "carencia"] = 2

        # Disminuir en 1 año la carencia de quienes aún la tienen
        df.loc[df["carencia"] > 0, "carencia"] -= 1

        # Recalcular Score
        df["Score"] = df["serv_pond"] + df["grado_pond"] + df["eq_pond"] + df["calif_pond"]

    return anio_objetivo


# =========================
# Interfaz Streamlit
# =========================

st.title("Simulador de tiempo para recibir mejora de grado")

st.write(
    """
Esta herramienta estima en cuántos años una persona recibiría su primera mejora de grado,
dado el ranking actual y una cantidad hipotética de mejoras que se otorgan cada año.
Los cálculos se basan en las reglas del sistema de ranking (antigüedad, equidad interna,
calificaciones y periodo de carencia de 2 años). 
"""
)

st.markdown("### 1. Cargar archivo de ranking")

uploaded_file = st.file_uploader(
    "Sube el archivo Ranking.xlsx (o un archivo con estructura equivalente)",
    type=["xlsx"],
)

if uploaded_file is not None:
    try:
        df_raw = pd.read_excel(uploaded_file)
        df_base = construir_dataframe_inicial(df_raw)
    except Exception as e:
        st.error(f"No se pudo leer / procesar el archivo: {e}")
        st.stop()

    col_ap_pat = df_base["_col_ap_pat"].iloc[0]
    col_ap_mat = df_base["_col_ap_mat"].iloc[0]
    col_nombres = df_base["_col_nombres"].iloc[0]

    # Construimos etiqueta de persona: "APELLIDO PATERNO APELLIDO MATERNO, Nombres"
    df_base["label_persona"] = (
        df_base[col_ap_pat].astype(str).str.strip().str.upper()
        + " "
        + df_base[col_ap_mat].astype(str).str.strip().str.upper()
        + ", "
        + df_base[col_nombres].astype(str).str.strip()
    )

    st.markdown("### 2. Seleccionar persona y parámetros")

    persona_label = st.selectbox(
        "Selecciona la persona",
        options=sorted(df_base["label_persona"].tolist()),
    )

    mejoras_por_anio = st.slider(
        "Cantidad de personas que reciben mejora de grado por año",
        min_value=1,
        max_value=50,
        value=20,
        step=1,
    )

    max_anios = st.slider(
        "Horizonte máximo de simulación (años)",
        min_value=10,
        max_value=300,
        value=200,
        step=10,
    )

    if st.button("Calcular años hasta la primera mejora"):
        persona_row = df_base[df_base["label_persona"] == persona_label].iloc[0]
        id_obj = int(persona_row["ID"])

        anio_mejora = simular_anios(
            df_inicial=df_base,
            id_objetivo=id_obj,
            mejoras_por_anio=mejoras_por_anio,
            max_anios=max_anios,
        )

        st.markdown("### Resultado")

        if anio_mejora is None:
            st.warning(
                f"Con las reglas del modelo y otorgando {mejoras_por_anio} mejoras por año, "
                f"la persona seleccionada **no alcanza a recibir una mejora** dentro de {max_anios} años de simulación."
            )
        else:
            st.success(
                f"La persona **{persona_label}** recibiría su **primera mejora de grado en el año {anio_mejora}** "
                f"del sistema, considerando {mejoras_por_anio} mejoras por año."
            )

else:
    st.info("Por favor, sube el archivo de ranking para comenzar la simulación.")
