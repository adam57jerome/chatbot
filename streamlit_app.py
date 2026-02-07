import importlib.util
import json
from dataclasses import asdict, dataclass
from typing import Dict, Optional, Tuple

import numpy as np
import pydeck as pdk
import streamlit as st


@dataclass
class StlInfo:
    name: str
    triangles: int
    bounds_mm: Tuple[float, float, float]
    vertices: np.ndarray
    faces: np.ndarray


@dataclass
class PrinterProfile:
    machine: Dict[str, float]
    resin: Dict[str, float]
    print_settings: Dict[str, float]
    advanced: Dict[str, float]


def _read_stl_vertices(data: bytes) -> Optional[Tuple[int, np.ndarray, np.ndarray]]:
    if len(data) < 84:
        return None
    triangles = int.from_bytes(data[80:84], byteorder="little", signed=False)
    expected_size = 84 + triangles * 50
    if len(data) >= expected_size:
        vertices = []
        faces = []
        offset = 84
        for _ in range(triangles):
            offset += 12
            face_indices = []
            for _ in range(3):
                vx = _bytes_to_float(data[offset : offset + 4])
                vy = _bytes_to_float(data[offset + 4 : offset + 8])
                vz = _bytes_to_float(data[offset + 8 : offset + 12])
                vertices.append((vx, vy, vz))
                face_indices.append(len(vertices) - 1)
                offset += 12
            offset += 2
            faces.append(face_indices)
        return triangles, np.array(vertices), np.array(faces)

    try:
        text = data.decode("utf-8", errors="ignore")
    except UnicodeDecodeError:
        return None
    if "vertex" not in text:
        return None
    vertices = []
    faces = []
    triangles = 0
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("vertex"):
            parts = line.split()
            if len(parts) == 4:
                vertices.append(tuple(float(p) for p in parts[1:]))
        if line.startswith("endfacet"):
            if len(vertices) >= (triangles + 1) * 3:
                start = triangles * 3
                faces.append([start, start + 1, start + 2])
            triangles += 1
    if not vertices:
        return None
    return triangles, np.array(vertices), np.array(faces)


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
    triangles, vertices, faces = parsed
    bounds = _bounds_from_vertices(vertices)
    return StlInfo(
        name=uploaded_file.name,
        triangles=triangles,
        bounds_mm=bounds,
        vertices=vertices,
        faces=faces,
    )


def recommend_scale(bounds: Tuple[float, float, float], build_size: Tuple[float, float, float]) -> float:
    ratios = [build / size if size > 0 else 1.0 for build, size in zip(build_size, bounds)]
    return min(ratios + [1.0])


def suggest_orientation(vertices: np.ndarray) -> Dict[str, str]:
    centered = vertices - vertices.mean(axis=0)
    cov = np.cov(centered.T)
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = np.argsort(eigvals)[::-1]
    axes = eigvecs[:, order]
    primary_axis = axes[:, 0]
    secondary_axis = axes[:, 1]
    axis_labels = ["X", "Y", "Z"]
    primary_label = axis_labels[int(np.argmax(np.abs(primary_axis)))]
    secondary_label = axis_labels[int(np.argmax(np.abs(secondary_axis)))]
    return {
        "primary": f"Axe principal ~ {primary_label}",
        "secondary": f"Axe secondaire ~ {secondary_label}",
        "tilt": "Inclinaison recommandée: 15° à 30° pour réduire les supports.",
    }


def build_analysis_text(stl_info: StlInfo, scale: float) -> Tuple[str, str]:
    volume_mm3 = stl_info.bounds_mm[0] * stl_info.bounds_mm[1] * stl_info.bounds_mm[2]
    analysis_lines = [
        f"Fichier : {stl_info.name}",
        f"Triangles : {stl_info.triangles:,}",
        (
            "Dimensions (mm) : "
            f"X {stl_info.bounds_mm[0]:.2f} / Y {stl_info.bounds_mm[1]:.2f} / Z {stl_info.bounds_mm[2]:.2f}"
        ),
        f"Volume approximatif (boîte englobante) : {volume_mm3:,.0f} mm³",
    ]
    recommendation_lines = [
        "Recommandations :",
        "- Orienter la pièce avec la face la plus large vers le plateau pour réduire les supports.",
        "- Inclinaison de 15° à 30° si la pièce présente de grandes surfaces planes.",
    ]
    if scale < 1.0:
        recommendation_lines.append(f"- Échelle recommandée : {scale:.2f} pour rentrer dans le volume.")
    else:
        recommendation_lines.append("- Le modèle rentre dans le volume : aucune réduction nécessaire.")
    return "\n".join(analysis_lines), "\n".join(recommendation_lines)


def recommend_print_settings(bounds: Tuple[float, float, float]) -> Dict[str, str]:
    x_dim, y_dim, z_dim = bounds
    max_dim = max(bounds)
    min_dim = min(bounds)

    if max_dim >= 120:
        layer_height = 0.1
        exposure = 3.5
        bottom_exposure = 45.0
        bottom_layers = 8
        lift_distance = 8.0
    elif max_dim >= 60:
        layer_height = 0.08
        exposure = 3.0
        bottom_exposure = 40.0
        bottom_layers = 6
        lift_distance = 7.0
    else:
        layer_height = 0.05
        exposure = 2.5
        bottom_exposure = 35.0
        bottom_layers = 5
        lift_distance = 6.0

    supports_needed = z_dim > min_dim * 1.5 or z_dim > 60
    raft_needed = min(x_dim, y_dim) < 25

    return {
        "layer_height": f"{layer_height:.2f} mm",
        "exposure": f"{exposure:.1f} s",
        "bottom_exposure": f"{bottom_exposure:.1f} s",
        "bottom_layers": str(bottom_layers),
        "lift_distance": f"{lift_distance:.1f} mm",
        "supports": "Oui" if supports_needed else "Non",
        "raft": "Oui" if raft_needed else "Non",
    }


def build_pdf_bytes(analysis: str, recommendations: str) -> bytes:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 8, "Analyse STL")
    pdf.ln(2)
    pdf.multi_cell(0, 6, analysis)
    pdf.ln(4)
    pdf.multi_cell(0, 8, "Recommandations")
    pdf.ln(2)
    pdf.multi_cell(0, 6, recommendations)
    return pdf.output(dest="S").encode("latin1")


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

    st.subheader("Aperçu 3D")
    max_points = 20000
    vertices = stl_info.vertices
    if vertices.shape[0] > max_points:
        indices = np.linspace(0, vertices.shape[0] - 1, max_points).astype(int)
        vertices = vertices[indices]
    center = stl_info.vertices.mean(axis=0)
    max_dim = max(stl_info.bounds_mm)
    scale_factor = 100.0 / max_dim if max_dim > 0 else 1.0
    preview_vertices = (vertices - center) * scale_factor
    points = [
        {"x": float(x), "y": float(y), "z": float(z), "color": [80, 180, 255]}
        for x, y, z in preview_vertices
    ]
    view_state = pdk.ViewState(
        target=[0, 0, 0],
        zoom=2.0,
        rotation_orbit=45,
        rotation_x=30,
    )
    point_layer = pdk.Layer(
        "PointCloudLayer",
        data=points,
        get_position="[x, y, z]",
        get_color="color",
        point_size=2,
    )
    view = pdk.View(type="OrbitView", controller=True)
    deck = pdk.Deck(layers=[point_layer], initial_view_state=view_state, views=[view])
    st.pydeck_chart(deck, use_container_width=True)

    st.subheader("Orientation conseillée")
    orientation = suggest_orientation(stl_info.vertices)
    st.markdown(
        "\n".join(
            [
                f"- {orientation['primary']}",
                f"- {orientation['secondary']}",
                f"- {orientation['tilt']}",
            ]
        )
    )

    st.subheader("Analyse & recommandations")
    analysis_text, recommendation_text = build_analysis_text(stl_info, scale)
    st.text_area("Analyse de la pièce", value=analysis_text, height=140)
    st.text_area("Recommandations", value=recommendation_text, height=120)
    st.subheader("Paramètres recommandés")
    recommendations = recommend_print_settings(stl_info.bounds_mm)
    rec_col1, rec_col2, rec_col3 = st.columns(3)
    rec_col1.metric("Hauteur de couche", recommendations["layer_height"])
    rec_col1.metric("Exposition", recommendations["exposure"])
    rec_col2.metric("Exposition base", recommendations["bottom_exposure"])
    rec_col2.metric("Couches base", recommendations["bottom_layers"])
    rec_col3.metric("Distance levage", recommendations["lift_distance"])
    rec_col3.metric("Supports nécessaires", recommendations["supports"])
    rec_col3.metric("Radeau nécessaire", recommendations["raft"])
    if importlib.util.find_spec("fpdf") is None:
        st.info("Installation requise pour le PDF : `pip install fpdf2`.")
    else:
        pdf_bytes = build_pdf_bytes(analysis_text, recommendation_text)
        st.download_button(
            "Télécharger le rapport PDF",
            data=pdf_bytes,
            file_name="rapport_stl_foto89.pdf",
            mime="application/pdf",
        )

st.divider()

machine_tab, resin_tab, print_tab, advanced_tab = st.tabs(["Machine", "Résine", "Imprimer", "Avancé"])

with machine_tab:
    st.subheader("Machine")
    col1, col2 = st.columns(2)
    with col1:
        st.caption("Par défaut : 3840 px")
        profile.machine["resolution_x"] = st.number_input(
            "Résolution X (px)", value=profile.machine["resolution_x"], step=1.0
        )
        st.caption("Par défaut : 2400 px")
        profile.machine["resolution_y"] = st.number_input(
            "Résolution Y (px)", value=profile.machine["resolution_y"], step=1.0
        )
    with col2:
        st.caption("Par défaut : 192.0 mm")
        profile.machine["size_x"] = st.number_input(
            "Taille X (mm)", value=profile.machine["size_x"], step=0.1
        )
        st.caption("Par défaut : 120.0 mm")
        profile.machine["size_y"] = st.number_input(
            "Taille Y (mm)", value=profile.machine["size_y"], step=0.1
        )
        st.caption("Par défaut : 200.0 mm")
        profile.machine["size_z"] = st.number_input(
            "Taille Z (mm)", value=profile.machine["size_z"], step=0.1
        )

with resin_tab:
    st.subheader("Résine")
    col1, col2 = st.columns(2)
    with col1:
        st.caption("Par défaut : standard")
        profile.resin["type"] = st.text_input("Type de résine", value=profile.resin.get("type", "standard"))
        st.caption("Par défaut : standard")
        profile.resin["name"] = st.text_input("Nom de la résine", value=profile.resin.get("name", "standard"))
    with col2:
        st.caption("Par défaut : 1.10 g/ml")
        profile.resin["density"] = st.number_input(
            "Densité (g/ml)", value=profile.resin["density"], step=0.01
        )
        st.caption("Par défaut : 30 €/kg")
        profile.resin["cost_per_kg"] = st.number_input(
            "Coût (€/kg)", value=profile.resin["cost_per_kg"], step=1.0
        )

with print_tab:
    st.subheader("Imprimer")
    col1, col2 = st.columns(2)
    with col1:
        st.caption("Par défaut : 0.10 mm")
        profile.print_settings["layer_height"] = st.number_input(
            "Hauteur de couche (mm)", value=profile.print_settings["layer_height"], step=0.01
        )
        st.caption("Par défaut : 8")
        profile.print_settings["bottom_layers"] = st.number_input(
            "Couches inférieures", value=profile.print_settings["bottom_layers"], step=1
        )
        st.caption("Par défaut : 3.0 s")
        profile.print_settings["exposure_time"] = st.number_input(
            "Durée d'exposition (s)", value=profile.print_settings["exposure_time"], step=0.1
        )
        st.caption("Par défaut : 40.0 s")
        profile.print_settings["bottom_exposure"] = st.number_input(
            "Durée exposition base (s)", value=profile.print_settings["bottom_exposure"], step=0.5
        )
    with col2:
        st.caption("Par défaut : 8.0 mm")
        profile.print_settings["lift_distance"] = st.number_input(
            "Distance de levage (mm)", value=profile.print_settings["lift_distance"], step=0.1
        )
        st.caption("Par défaut : 65 mm/min")
        profile.print_settings["lift_speed"] = st.number_input(
            "Vitesse de levage (mm/min)", value=profile.print_settings["lift_speed"], step=1.0
        )
        st.caption("Par défaut : 150 mm/min")
        profile.print_settings["retract_speed"] = st.number_input(
            "Vitesse de rétraction (mm/min)", value=profile.print_settings["retract_speed"], step=1.0
        )

with advanced_tab:
    st.subheader("Avancé")
    col1, col2 = st.columns(2)
    with col1:
        st.caption("Par défaut : 255")
        profile.advanced["bottom_pwm"] = st.number_input(
            "Éclairage base PWM", value=profile.advanced["bottom_pwm"], step=1
        )
        st.caption("Par défaut : 255")
        profile.advanced["normal_pwm"] = st.number_input(
            "Éclairage PWM", value=profile.advanced["normal_pwm"], step=1
        )
    with col2:
        st.caption("Par défaut : 8")
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
