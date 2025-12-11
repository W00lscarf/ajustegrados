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
    cols = {c: c.replace("\n", " ").strip() for c in df_raw.columns}
    df = df_raw.rename(columns=cols).copy()

    col_ap_pat = [c for c in df.columns if "Paterno" in c][0]
    col_ap_mat = [c for c in df.columns if "Materno" in c][0]
    col_nombres = [c for c in df.columns if "Nombre" in c][0]
    col_grado = "Grado"
    col_estamento = [c for c in df.columns if "Estamento" in c][0]
    col_ant_serv = [c for c in df.columns if "servicio" in c and "meses" in c][0]
    col_ant_grado = [c for c in df.columns if "grado" in c and "meses" in c][0]
    col_calif = [c for c in df.columns if "Calificación" in c][0]

    df["ID"] = df.index

    df["serv_m"] = pd.to_numeric(df[col_ant_serv], errors="coerce").fillna(0)
    df["grado_m"] = pd.to_numeric(df[col_ant_grado], errors="coerce").fillna(0)

    df["serv_pts"] = df["serv_m"].apply(puntos_antig_servicio)
    df["grado_pts"] = df["grado_m"].apply(puntos_antig_grado)
    df["eq_pts"] = df.apply(lambda r: puntos_equidad(r[col_estamento], r[col_grado]), axis=1)
    df["calif_pts"] = pd.to_numeric(df[col_calif], errors="coerce").fillna(0)

    df["serv_pond"] = df["serv_pts"] * 0.30
    df["grado_pond"] = df["grado_pts"] * 0.15
    df["eq_pond"] = df["eq_pts"] * 0.30
    df["calif_pond"] = df["calif_pts"] * 0.25

    df["Score"] = df[["serv_pond", "grado_pond", "eq_pond", "calif_pond"]].sum(axis=1)

    df["_col_ap_pat"] = col_ap_pat
    df["_col_ap_mat"] = col_ap_mat
    df["_col_nombres"] = col_nombres
    df["_col_grado"] = col_grado
    df["_col_estamento"] = col_estamento

    df["carencia"] = 0
    df["ajustes"] = 0

    return df


# =========================
# Simulación
# =========================

def simular_mejoras(df_inicial, id_objetivo, mejoras_por_anio=20, max_anios=20):

    df = df_inicial.copy()

    col_grado = df["_col_grado"].iloc[0]
    col_estamento = df["_col_estamento"].iloc[0]

    for anio in range(1, max_anios + 1):

        elegibles = df[df["carencia"] == 0].copy()
        elegibles = elegibles.sort_values(["Score", "serv_m"], ascending=[False, False])

        seleccionados = elegibles.head(mejoras_por_anio)
        ids_sel = seleccionados["ID"].tolist()

        if id_objetivo in ids_sel:
            return anio

        mask_sel = df["ID"].isin(ids_sel)

        df.loc[mask_sel, col_grado] = df.loc[mask_sel].apply(
            lambda r: grado_siguiente(r[col_estamento], r[col_grado]), axis=1
        )

        df.loc[mask_sel, "grado_m"] = 0
        df.loc[mask_sel, "grado_pts"] = 0
        df.loc[mask_sel, "grado_pond"] = 0
        df.loc[mask_sel, "carencia"] = 2

        df["eq_pts"] = df.apply(lambda r: puntos_equidad(r[col_estamento], r[col_grado]), axis=1)
        df["eq_pond"] = df["eq_pts"] * 0.30

        df.loc[df["carencia"] > 0, "carencia"] -= 1

        df["Score"] = df[["serv_pond", "grado_pond", "eq_pond", "calif_pond"]].sum(axis=1)

    return None


# =========================
# Streamlit UI
# =========================

st.title("Simulador de Mejora de Grado")

st.write("Sube el archivo del ranking y simula cuántos años tardaría una persona en recibir una mejora.")

archivo = st.file_uploader("Sube Ranking.xlsx", type=["xlsx"])

if archivo:
    df_raw = pd.read_excel(archivo)
    df = construir_dataframe(df_raw)

    col_ap_pat = df["_col_ap_pat"].iloc[0]
    col_ap_mat = df["_col_ap_mat"].iloc[0]
    col_nombres = df["_col_nombres"].iloc[0]

    df["persona"] = (
        df[col_ap_pat].astype(str).str.upper()
        + " "
        + df[col_ap_mat].astype(str).str.upper()
        + ", "
        + df[col_nombres]
    )

    persona = st.selectbox("Selecciona persona:", df["persona"])
    mejoras_por_anio = st.slider("Mejoras por año:", 1, 50, 20)
    max_anios = st.slider("Años a simular:", 1, 20, 20)

    if st.button("Calcular"):
        id_obj = df[df["persona"] == persona]["ID"].iloc[0]
        anio = simular_mejoras(df, id_obj, mejoras_por_anio, max_anios)

        if anio is None:
            st.error(f"La persona NO recibe mejora en {max_anios} años.")
        else:
            st.success(f"La persona recibe su primera mejora en el año {anio}.")
