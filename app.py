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
    est = (estamento or "").strip().upper()

    if not isinstance(grado, (int, float)):
        return 0

    g = int(grado)

    # Profesional
    if est.startswith("PROF"):
        tabla = {5: 0, 6: 0, 7: 20, 8: 20, 9: 40, 10: 60, 11: 80, 12: 100}
        return tabla.get(g, 0)

    # Técnico
    if est.startswith("TÉC") or est.startswith("TEC"):
        tabla = {10: 0, 11: 20, 12: 40, 13: 60, 14: 80, 15: 100}
        return tabla.get(g, 0)

    # Administrativo
    if est.startswith("ADMIN"):
        tabla = {11: 0, 12: 20, 13: 40, 14: 60, 15: 80, 16: 100}
        return tabla.get(g, 0)

    return 0


def grado_siguiente(estamento: str, grado_actual: int) -> int:
    est = (estamento or "").strip().upper()

    if not isinstance(grado_actual, (int, float)):
        return grado_actual

    g = int(grado_actual)

    # Mínimos por estamento
    if est.startswith("PROF"):
        piso = 5
    elif est.startswith("TÉC") or est.startswith("TEC"):
        piso = 10
    elif est.startswith("ADMIN"):
        piso = 11
    else:
        piso = g

    return max(piso, g - 1)


# =========================
# Construcción del DataFrame
# =========================

def construir_dataframe(df_raw: pd.DataFrame) -> pd.DataFrame:
    # Normalizar nombres de columnas
    cols = {c: c.replace("\n", " ").strip() for c in df_raw.columns}
    df = df_raw.rename(columns=cols).copy()

    # Identificar columnas clave
    col_ap_pat = [c for c in df.columns if "Paterno" in c][0]
    col_ap_mat = [c for c in df.columns if "Materno" in c][0]
    col_nombres = [c for c in df.columns if "Nombre" in c][0]
    col_grado = "Grado"
    col_estamento = [c for c in df.columns if "Estamento" in c][0]
    col_ant_serv = [c for c in df.columns if "servicio" in c and "meses" in c][0]
    col_ant_grado = [c for c in df.columns if "grado" in c and "meses" in c][0]
    col_calif = [c for c in df.columns if "Puntaje" in c and "Calificación" in c][0]

    df["ID"] = df.index

    df["serv_m"] = pd.to_numeric(df[col_ant_serv], errors="coerce").fillna(0)
    df["grado_m"] = pd.to_numeric(df[col_ant_grado], errors="coerce").fillna(0)

    df["serv_pts"] = df["serv_m"].apply(puntos_antig_servicio)
    df["grado_pts"] = df["grado_m"].apply(puntos_antig_grado)
    df["eq_pts"] = df.apply(
        lambda r: puntos_equidad(r[col_estamento], r[col_grado]),
        axis=1
    )
    df["calif_pts"] = pd.to_numeric(df[col_calif], errors="coerce").fillna(0)

    df["serv_pond"] = df["serv_pts"] * 0.30
    df["grado_pond"] = df["grado_pts"] * 0.15
    df["eq_pond"] = df["eq_pts"] * 0.30
    df["calif_pond"] = df["calif_pts"] * 0.25

    df["Score"] = df[["serv_pond", "grado_pond", "eq_pond", "calif_pond"]].sum(axis=1)

    # Guardamos nombres de columnas clave como metadatos
    df["_col_ap_pat"] = col_ap_pat
    df["_col_ap_mat"] = col_ap_mat
    df["_col_nombres"] = col_nombres
    df["_col_grado"] = col_grado
    df["_col_estamento"] = col_estamento

    # Variables de simulación
    df["carencia"] = 0
    df["ajustes"] = 0

    return df


# =========================
# Simulación
# =========================

def simular_mejoras(df_inicial, id_objetivo, mejoras_por_anio=20, max_anios=200):
    """
    Simula año a año hasta que la persona recibe mejora
    o hasta max_anios (interno, no expuesto al usuario).
    Devuelve el año en que recibe la primera mejora, o None si no ocurre.
    """
    df = df_inicial.copy()

    col_grado = df["_col_grado"].iloc[0]
    col_estamento = df["_col_estamento"].iloc[0]

    for anio in range(1, max_anios + 1):
        elegibles = df[df["carencia"] == 0].copy()
        if elegibles.empty:
            break

        elegibles = elegibles.sort_values(["Score", "serv_m"], ascending=[False, False])
        seleccionados = elegibles.head(mejoras_por_anio)
        ids_sel = seleccionados["ID"].tolist()

        if id_objetivo in ids_sel:
            return anio

        mask_sel = df["ID"].isin(ids_sel)

        # Mejorar grado a seleccionados
        df.loc[mask_sel, col_grado] = df.loc[mask_sel].apply(
            lambda r: grado_siguiente(r[col_estamento], r[col_grado]),
            axis=1
        )

        # Reset de antigüedad en el grado
        df.loc[mask_sel, "grado_m"] = 0
        df.loc[mask_sel, "grado_pts"] = 0
        df.loc[mask_sel, "grado_pond"] = 0

        # Carencia de 2 años
        df.loc[mask_sel, "carencia"] = 2

        # Recalcular equidad
        df["eq_pts"] = df.apply(
            lambda r: puntos_equidad(r[col_estamento], r[col_grado]),
            axis=1
        )
        df["eq_pond"] = df["eq_pts"] * 0.30

        # Reducir carencia en 1 año
        df.loc[df["carencia"] > 0, "carencia"] -= 1

        # Recalcular Score
        df["Score"] = df[["serv_pond", "grado_pond", "eq_pond", "calif_pond"]].sum(axis=1)

    return None


# =========================
# Carga de datos (desde el repo)
# =========================

@st.cache_data
def cargar_ranking():
    df_raw = pd.read_excel("Ranking.xlsx")
    return construir_dataframe(df_raw)


# =========================
# Streamlit UI
# =========================

st.title("Simulador de Mejora de Grado")

st.write(
    "Esta aplicación usa la base `Ranking.xlsx` incluida en el repositorio "
    "para estimar en cuántos años una persona recibiría su primera mejora de grado, "
    "dado un número hipotético de mejoras que se otorgan cada año."
)

try:
    df = cargar_ranking()
except FileNotFoundError:
    st.error("No se encontró el archivo 'Ranking.xlsx' en el repositorio.")
    st.stop()

col_ap_pat = df["_col_ap_pat"].iloc[0]
col_ap_mat = df["_col_ap_mat"].iloc[0]
col_nombres = df["_col_nombres"].iloc[0]

df["persona"] = (
    df[col_ap_pat].astype(str).str.upper()
    + " "
    + df[col_ap_mat].astype(str).str.upper()
    + ", "
    + df[col_nombres].astype(str)
)

st.subheader("Parámetros de simulación")

persona = st.selectbox("Selecciona la persona:", df["persona"])
mejoras_por_anio = st.slider("Número de personas que reciben mejora por año:", 1, 50, 20)

if st.button("Calcular"):
    id_obj = df[df["persona"] == persona]["ID"].iloc[0]
    anio = simular_mejoras(df, id_obj, mejoras_por_anio=mejoras_por_anio, max_anios=200)

    if anio is None:
        st.error(
            f"Con {mejoras_por_anio} mejoras por año, la persona seleccionada "
            f"no alcanza a recibir una mejora en el horizonte de simulación del modelo."
        )
    else:
        st.success(
            f"Con {mejoras_por_anio} mejoras por año, "
            f"la persona seleccionada recibiría su **primera mejora en el año {anio}**."
        )

