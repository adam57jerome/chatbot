import io
import json
from dataclasses import asdict, dataclass
from typing import Dict, Optional, Tuple

import streamlit as st


@dataclass
class StlInfo:
    name: str
    triangles: int
    bounds_mm: Tuple[float, float, float]


@dataclass
class PrinterProfile:
    machine: Dict[str, float]
    resin: Dict[str, float]
    print_settings: Dict[str, float]
    advanced: Dict[str, float]


def _read_stl_vertices(data: bytes) -> Optional[Tuple[int, Tuple[float, float, float]]]:
    if len(data) < 84:
        return None
    triangles = int.from_bytes(data[80:84], byteorder="little", signed=False)
    expected_size = 84 + triangles * 50
    if len(data) >= expected_size:
        vertices = []
        offset = 84
        for _ in range(triangles):
            offset += 12
            for _ in range(3):
                vx = _bytes_to_float(data[offset : offset + 4])
                vy = _bytes_to_float(data[offset + 4 : offset + 8])
                vz = _bytes_to_float(data[offset + 8 : offset + 12])
                vertices.append((vx, vy, vz))
                offset += 12
            offset += 2
        return triangles, _bounds_from_vertices(vertices)

    try:
        text = data.decode("utf-8", errors="ignore")
    except UnicodeDecodeError:
        return None
    if "vertex" not in text:
        return None
    vertices = []
    triangles = 0
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("vertex"):
            parts = line.split()
            if len(parts) == 4:
                vertices.append(tuple(float(p) for p in parts[1:]))
        if line.startswith("endfacet"):
            triangles += 1
    if not vertices:
        return None
    return triangles, _bounds_from_vertices(vertices)


def _bytes_to_float(b: bytes) -> float:
    import struct

    return struct.unpack("<f", b)[0]


def _bounds_from_vertices(vertices) -> Tuple[float, float, float]:
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]
    return max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)


def parse_stl(uploaded_file) -> Optional[StlInfo]:
    if not uploaded_file:
        return None
    data = uploaded_file.getvalue()
    parsed = _read_stl_vertices(data)
    if not parsed:
        return None
    triangles, bounds = parsed
    return StlInfo(name=uploaded_file.name, triangles=triangles, bounds_mm=bounds)


def recommend_scale(bounds: Tuple[float, float, float], build_size: Tuple[float, float, float]) -> float:
    ratios = [build / size if size > 0 else 1.0 for build, size in zip(build_size, bounds)]
    return min(ratios + [1.0])


st.set_page_config(page_title="Flashforge Foto 8.9 - Configurateur", layout="wide")

st.title("🖨️ Configurateur Foto 8.9 (Résine)")
st.write(
    "Importez un STL et ajustez les paramètres de votre Flashforge Foto 8.9. "
    "Les valeurs proposées servent de base et peuvent être modifiées selon votre résine."
)

with st.sidebar:
    st.header("STL")
    uploaded_file = st.file_uploader("Importer un fichier STL", type=["stl"])
    st.caption("Analyse locale : dimensions et nombre de triangles.")

stl_info = parse_stl(uploaded_file)

machine_defaults = {
    "resolution_x": 3840.0,
    "resolution_y": 2400.0,
    "size_x": 192.0,
    "size_y": 120.0,
    "size_z": 200.0,
}

if "profile" not in st.session_state:
    st.session_state.profile = PrinterProfile(
        machine=machine_defaults,
        resin={"density": 1.1, "cost_per_kg": 30.0},
        print_settings={
            "layer_height": 0.1,
            "bottom_layers": 8,
            "exposure_time": 3.0,
            "bottom_exposure": 40.0,
            "lift_distance": 8.0,
            "lift_speed": 65.0,
            "retract_speed": 150.0,
        },
        advanced={
            "bottom_pwm": 255,
            "normal_pwm": 255,
            "gray_levels": 8,
        },
    )

profile = st.session_state.profile

if stl_info:
    st.subheader("Analyse STL")
    col1, col2, col3 = st.columns(3)
    col1.metric("Fichier", stl_info.name)
    col2.metric("Triangles", f"{stl_info.triangles:,}")
    col3.metric(
        "Dimensions (mm)",
        f"X {stl_info.bounds_mm[0]:.2f} / Y {stl_info.bounds_mm[1]:.2f} / Z {stl_info.bounds_mm[2]:.2f}",
    )
    build_size = (profile.machine["size_x"], profile.machine["size_y"], profile.machine["size_z"])
    scale = recommend_scale(stl_info.bounds_mm, build_size)
    if scale < 1.0:
        st.warning(
            f"Le modèle dépasse le volume d'impression. Échelle recommandée: {scale:.2f}.",
            icon="⚠️",
        )
    else:
        st.success("Le modèle tient dans le volume d'impression.", icon="✅")

st.divider()

machine_tab, resin_tab, print_tab, advanced_tab = st.tabs(["Machine", "Résine", "Imprimer", "Avancé"])

with machine_tab:
    st.subheader("Machine")
    col1, col2 = st.columns(2)
    with col1:
        profile.machine["resolution_x"] = st.number_input(
            "Résolution X (px)", value=profile.machine["resolution_x"], step=1.0
        )
        profile.machine["resolution_y"] = st.number_input(
            "Résolution Y (px)", value=profile.machine["resolution_y"], step=1.0
        )
    with col2:
        profile.machine["size_x"] = st.number_input(
            "Taille X (mm)", value=profile.machine["size_x"], step=0.1
        )
        profile.machine["size_y"] = st.number_input(
            "Taille Y (mm)", value=profile.machine["size_y"], step=0.1
        )
        profile.machine["size_z"] = st.number_input(
            "Taille Z (mm)", value=profile.machine["size_z"], step=0.1
        )

with resin_tab:
    st.subheader("Résine")
    col1, col2 = st.columns(2)
    with col1:
        profile.resin["type"] = st.text_input("Type de résine", value=profile.resin.get("type", "standard"))
        profile.resin["name"] = st.text_input("Nom de la résine", value=profile.resin.get("name", "standard"))
    with col2:
        profile.resin["density"] = st.number_input(
            "Densité (g/ml)", value=profile.resin["density"], step=0.01
        )
        profile.resin["cost_per_kg"] = st.number_input(
            "Coût (€/kg)", value=profile.resin["cost_per_kg"], step=1.0
        )

with print_tab:
    st.subheader("Imprimer")
    col1, col2 = st.columns(2)
    with col1:
        profile.print_settings["layer_height"] = st.number_input(
            "Hauteur de couche (mm)", value=profile.print_settings["layer_height"], step=0.01
        )
        profile.print_settings["bottom_layers"] = st.number_input(
            "Couches inférieures", value=profile.print_settings["bottom_layers"], step=1
        )
        profile.print_settings["exposure_time"] = st.number_input(
            "Durée d'exposition (s)", value=profile.print_settings["exposure_time"], step=0.1
        )
        profile.print_settings["bottom_exposure"] = st.number_input(
            "Durée exposition base (s)", value=profile.print_settings["bottom_exposure"], step=0.5
        )
    with col2:
        profile.print_settings["lift_distance"] = st.number_input(
            "Distance de levage (mm)", value=profile.print_settings["lift_distance"], step=0.1
        )
        profile.print_settings["lift_speed"] = st.number_input(
            "Vitesse de levage (mm/min)", value=profile.print_settings["lift_speed"], step=1.0
        )
        profile.print_settings["retract_speed"] = st.number_input(
            "Vitesse de rétraction (mm/min)", value=profile.print_settings["retract_speed"], step=1.0
        )

with advanced_tab:
    st.subheader("Avancé")
    col1, col2 = st.columns(2)
    with col1:
        profile.advanced["bottom_pwm"] = st.number_input(
            "Éclairage base PWM", value=profile.advanced["bottom_pwm"], step=1
        )
        profile.advanced["normal_pwm"] = st.number_input(
            "Éclairage PWM", value=profile.advanced["normal_pwm"], step=1
        )
    with col2:
        profile.advanced["gray_levels"] = st.number_input(
            "Niveaux de gris", value=profile.advanced["gray_levels"], step=1
        )

st.divider()

st.subheader("Exporter")
profile_json = json.dumps(asdict(profile), indent=2, ensure_ascii=False)
st.download_button(
    "Télécharger le profil (.json)",
    data=profile_json.encode("utf-8"),
    file_name="flashforge_foto89_profile.json",
    mime="application/json",
)

st.caption("Astuce : ce profil peut être réimporté et adapté à chaque résine.")
