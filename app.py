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
# Construcción de base de puntos (sin ponderaciones)
# =========================

def construir_base(df_raw: pd.DataFrame) -> pd.DataFrame:
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

    # Metadatos de columnas clave
    df["_col_ap_pat"] = col_ap_pat
    df["_col_ap_mat"] = col_ap_mat
    df["_col_nombres"] = col_nombres
    df["_col_grado"] = col_grado
    df["_col_estamento"] = col_estamento

    # Variables de simulación
    df["carencia"] = 0
    df["ajustes"] = 0

    return df


def aplicar_ponderaciones(df: pd.DataFrame,
                          w_serv: float,
                          w_grado: float,
                          w_eq: float,
                          w_calif: float) -> pd.DataFrame:
    """Aplica ponderaciones y recalcula Score."""
    df = df.copy()
    df["serv_pond"] = df["serv_pts"] * w_serv
    df["grado_pond"] = df["grado_pts"] * w_grado
    df["eq_pond"] = df["eq_pts"] * w_eq
    df["calif_pond"] = df["calif_pts"] * w_calif
    df["Score"] = df[["serv_pond", "grado_pond", "eq_pond", "calif_pond"]].sum(axis=1)
    return df


# =========================
# Simulación
# =========================

def simular_mejoras(df_base: pd.DataFrame,
                    id_objetivo: int,
                    mejoras_por_anio: int = 20,
                    carencia_anios: int = 2,
                    max_anios: int = 200,
                    w_serv: float = 0.30,
                    w_grado: float = 0.15,
                    w_eq: float = 0.30,
                    w_calif: float = 0.25):
    """
    Simula año a año hasta que la persona recibe mejora
    o hasta max_anios. Devuelve el año en que recibe la primera
    mejora, o None si no ocurre en el horizonte.
    """
    df = df_base.copy()

    col_grado = df["_col_grado"].iloc[0]
    col_estamento = df["_col_estamento"].iloc[0]

    # Ponderaciones iniciales
    df = aplicar_ponderaciones(df, w_serv, w_grado, w_eq, w_calif)

    for anio in range(1, max_anios + 1):
        elegibles = df[df["carencia"] == 0].copy()
        if elegibles.empty:
            break

        elegibles = elegibles.sort_values(["Score", "serv_m"], ascending=[False, False])
        seleccionados = elegibles.head(mejoras_por_anio)
        ids_sel = seleccionados["ID"].tolist()

        # ¿La persona objetivo está en los seleccionados este año?
        if id_objetivo in ids_sel:
            return anio

        mask_sel = df["ID"].isin(ids_sel)

        # Mejorar grado a seleccionados
        df.loc[mask_sel, col_grado] = df.loc[mask_sel].apply(
            lambda r: grado_siguiente(r[col_estamento], r[col_grado]),
            axis=1
        )

        # Reset de antigüedad en el grado (queda en 0 meses luego de la mejora)
        df.loc[mask_sel, "grado_m"] = 0
        df.loc[mask_sel, "grado_pts"] = df.loc[mask_sel, "grado_m"].apply(puntos_antig_grado)

        # Asignar carencia (en años) a quienes recibieron mejora
        if carencia_anios > 0:
            df.loc[mask_sel, "carencia"] = carencia_anios

        # Recalcular equidad según nuevo grado
        df["eq_pts"] = df.apply(
            lambda r: puntos_equidad(r[col_estamento], r[col_grado]),
            axis=1
        )

        # Reducir carencia en 1 año a quienes aún la tienen
        if carencia_anios > 0:
            df.loc[df["carencia"] > 0, "carencia"] -= 1

        # Reaplicar ponderaciones y Score con los pesos definidos
        df = aplicar_ponderaciones(df, w_serv, w_grado, w_eq, w_calif)

    return None


# =========================
# Carga de datos (desde el repo)
# =========================

@st.cache_data
def cargar_base():
    df_raw = pd.read_excel("Ranking.xlsx")
    return construir_base(df_raw)


# =========================
# Streamlit UI
# =========================

st.title("Simulador de Mejora de Grado")

st.write(
    "Esta aplicación usa la base `Ranking.xlsx` incluida en el repositorio para estimar "
    "en cuántos años una persona recibiría su primera mejora de grado, dados "
    "los parámetros del sistema."
)

st.markdown(
    """
**Nota metodológica:** este simulador no aplica una fórmula cerrada del tipo  
“años = personas por delante ÷ mejoras por año × carencia”.  
En cambio, realiza una **simulación año a año**, donde en cada ciclo:
- Se reordena el ranking según las ponderaciones definidas.
- Se aplican las carencias a quienes ya recibieron mejoras.
- Se recalculan los puntajes de equidad interna y antigüedad en el grado.
Por lo tanto, el resultado refleja un comportamiento dinámico del sistema y no una simple multiplicación.
"""
)

try:
    df_base = cargar_base()
except FileNotFoundError:
    st.error("No se encontró el archivo 'Ranking.xlsx' en el repositorio.")
    st.stop()

col_ap_pat = df_base["_col_ap_pat"].iloc[0]
col_ap_mat = df_base["_col_ap_mat"].iloc[0]
col_nombres = df_base["_col_nombres"].iloc[0]

df_base["persona"] = (
    df_base[col_ap_pat].astype(str).str.upper()
    + " "
    + df_base[col_ap_mat].astype(str).str.upper()
    + ", "
    + df_base[col_nombres].astype(str)
)

st.subheader("Parámetros del sistema")

# Selección de persona
persona = st.selectbox("Selecciona la persona:", df_base["persona"])

# Número de mejoras por año
mejoras_por_anio = st.slider(
    "Número de personas que reciben mejora por año:",
    min_value=1,
    max_value=50,
    value=20,
)

# Carencia
carencia_anios = st.slider(
    "Años de carencia luego de recibir una mejora:",
    min_value=0,
    max_value=5,
    value=2,
    help="Años durante los cuales una persona que recibe mejora no puede volver a ser considerada."
)

st.subheader("Ponderaciones de los componentes")

st.write(
    "Ingresa las ponderaciones en porcentaje. "
    "Se normalizan internamente, por lo que no es estrictamente necesario que sumen 100, "
    "aunque es lo recomendable para interpretarlas más fácilmente."
)

col1, col2 = st.columns(2)

with col1:
    w_serv_pct = st.number_input("Antigüedad en el servicio (%)", min_value=0.0, max_value=100.0, value=30.0, step=1.0)
    w_grado_pct = st.number_input("Antigüedad en el grado (%)", min_value=0.0, max_value=100.0, value=15.0, step=1.0)
with col2:
    w_eq_pct = st.number_input("Equidad interna (%)", min_value=0.0, max_value=100.0, value=30.0, step=1.0)
    w_calif_pct = st.number_input("Calificación (%)", min_value=0.0, max_value=100.0, value=25.0, step=1.0)

total_pct = w_serv_pct + w_grado_pct + w_eq_pct + w_calif_pct

if total_pct == 0:
    st.error("La suma de las ponderaciones no puede ser 0. Ajusta al menos una de ellas.")
    st.stop()

# Normalización a proporciones (para que la escala total sea irrelevante y solo importen las relaciones)
w_serv = w_serv_pct / total_pct
w_grado = w_grado_pct / total_pct
w_eq = w_eq_pct / total_pct
w_calif = w_calif_pct / total_pct

st.caption(
    f"Ponderaciones normalizadas usadas en el cálculo: "
    f"Servicio: {w_serv:.2f}, Grado: {w_grado:.2f}, "
    f"Equidad: {w_eq:.2f}, Calificación: {w_calif:.2f}."
)

if st.button("Calcular años hasta la primera mejora"):
    id_obj = df_base[df_base["persona"] == persona]["ID"].iloc[0]

    anio = simular_mejoras(
        df_base,
        id_objetivo=id_obj,
        mejoras_por_anio=mejoras_por_anio,
        carencia_anios=carencia_anios,
        max_anios=200,
        w_serv=w_serv,
        w_grado=w_grado,
        w_eq=w_eq,
        w_calif=w_calif,
    )

    st.subheader("Resultado")

    if anio is None:
        st.error(
            f"Con {mejoras_por_anio} mejoras por año y una carencia de {carencia_anios} años, "
            f"la persona seleccionada no alcanza a recibir una mejora dentro del horizonte de simulación del modelo."
        )
    else:
        st.success(
            f"Con {mejoras_por_anio} mejoras por año y una carencia de {carencia_anios} años, "
            f"la persona seleccionada recibiría su **primera mejora en el año {anio}** del sistema."
        )
