import importlib.util
import json
from dataclasses import asdict, dataclass
from io import BytesIO
from typing import Any, Dict, Optional, Tuple

import numpy as np
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


def compute_mesh_metrics(vertices: np.ndarray, faces: np.ndarray) -> Dict[str, float | None]:
    if faces.size == 0:
        return {
            "surface_area": None,
            "volume": None,
            "proj_xy": None,
            "proj_xz": None,
            "proj_yz": None,
        }
    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]
    cross = np.cross(v1 - v0, v2 - v0)
    area = 0.5 * np.linalg.norm(cross, axis=1)
    total_area = float(np.sum(area))
    normals = cross / (np.linalg.norm(cross, axis=1)[:, None] + 1e-9)
    proj_xy = float(np.sum(np.abs(normals[:, 2]) * area))
    proj_xz = float(np.sum(np.abs(normals[:, 1]) * area))
    proj_yz = float(np.sum(np.abs(normals[:, 0]) * area))
    volume = float(abs(np.sum(np.einsum("ij,ij->i", v0, np.cross(v1, v2))) / 6.0))
    return {
        "surface_area": total_area,
        "volume": volume,
        "proj_xy": proj_xy,
        "proj_xz": proj_xz,
        "proj_yz": proj_yz,
    }


def build_report(
    stl_info: StlInfo,
    scale: float,
    settings: Dict[str, float | str],
    resin_type: str,
    temp_c: float,
) -> Dict[str, str]:
    metrics = compute_mesh_metrics(stl_info.vertices, stl_info.faces)
    bbox_volume = stl_info.bounds_mm[0] * stl_info.bounds_mm[1] * stl_info.bounds_mm[2]
    surface = metrics["surface_area"]
    volume = metrics["volume"]
    thickness = (2 * volume / surface) if surface and volume else None
    flatness = (surface / volume) if surface and volume else None

    analysis_lines = [
        f"Fichier : {stl_info.name}",
        f"Triangles : {stl_info.triangles:,}",
        (
            "Dimensions (mm) : "
            f"X {stl_info.bounds_mm[0]:.2f} / Y {stl_info.bounds_mm[1]:.2f} / Z {stl_info.bounds_mm[2]:.2f}"
        ),
        f"Plus grande dimension : {max(stl_info.bounds_mm):.2f} mm",
        f"Volume boîte englobante : {bbox_volume:,.0f} mm³",
    ]
    if volume:
        analysis_lines.append(f"Volume estimé : {volume:,.0f} mm³")
    if surface:
        analysis_lines.append(f"Surface estimée : {surface:,.0f} mm²")
    if thickness:
        analysis_lines.append(f"Épaisseur moyenne approx : {thickness:.2f} mm")
    if flatness:
        analysis_lines.append(f"Rapport surface/volume : {flatness:.2f}")
    if metrics["proj_xy"]:
        analysis_lines.append(
            "Aires projetées (XY/XZ/YZ) : "
            f"{metrics['proj_xy']:.0f} / {metrics['proj_xz']:.0f} / {metrics['proj_yz']:.0f} mm²"
        )

    risks = []
    if metrics["proj_xy"] and surface and metrics["proj_xy"] / surface > 0.45:
        risks.append("Grande surface plane → risque de ventouse (peel).")
    if volume and bbox_volume and volume / bbox_volume < 0.2:
        risks.append("Volume faible vs bounding box → possible cavité/hollow.")
    if thickness and thickness < 1.0:
        risks.append("Parois fines → supports délicats et expo à ajuster.")
    if not risks:
        risks.append("Aucun risque majeur détecté (à confirmer visuellement).")

    orientation = [
        "Orientation conseillée :",
        "- Incliner 30–45° pour réduire l’aire projetée par couche.",
        "- Ajouter 10–15° d’inclinaison secondaire pour éviter une ligne de peel.",
        "- Préserver les zones visibles en limitant les supports sur ces faces.",
    ]

    supports = [
        "Plan supports :",
        "- Heavy sur les premiers points d’attaque.",
        "- Medium ailleurs, avec bracing si pièce haute.",
        "- Renforcer les grandes surfaces pour limiter l’arrachement.",
    ]

    params = [
        "Paramètres recommandés :",
        f"- Layer height : {settings['layer_height']:.2f} mm",
        f"- Normal exposure : {settings['exposure']:.1f} s",
        f"- Bottom layers : {int(settings['bottom_layers'])}",
        f"- Bottom exposure : {settings['bottom_exposure']:.1f} s",
        f"- Lift distance : {settings['lift_distance']:.1f} mm",
        f"- Lift speed : {settings['lift_speed']:.0f} mm/min",
        f"- Retract speed : {settings['retract_speed']:.0f} mm/min",
        f"- Transition layers : {int(settings['transition_layers'])}",
        f"- Rest/Light-off : {settings['rest_time']:.1f} s",
    ]

    explanation = [
        "Pourquoi ces paramètres :",
        (
            f"- Hauteur de couche {settings['layer_height']:.2f} mm "
            "pour équilibrer qualité et durée."
        ),
        (
            f"- Exposition {settings['exposure']:.1f} s "
            "pour une polymérisation correcte."
        ),
        (
            f"- Expo base {settings['bottom_exposure']:.1f} s et "
            f"{int(settings['bottom_layers'])} couches pour l’adhérence plateau."
        ),
        (
            f"- Lift {settings['lift_distance']:.1f} mm "
            "pour le décollement sans arrachement."
        ),
        f"- Supports : {settings['supports']} / Radeau : {settings['raft']}.",
        f"- Résine : {resin_type}, Température : {temp_c:.1f}°C.",
    ]

    diagnostics = [
        "Corrections si échec :",
        "- Pièce collée au FEP : +expo normale, supports plus épais, lift plus lent.",
        "- Radeau qui se décolle : +bottom layers/expo, vérifier nivellement.",
        "- Détails bouchés : -0,2 à -0,5 s d’expo normale.",
        "- Supports cassants : expo +0,2 s et bracing.",
    ]

    checklist = [
        "Checklist avant impression :",
        "- Résine mélangée, température stable.",
        "- Plateau nivelé, FEP propre.",
        "- Couvercle fermé, clé USB OK.",
    ]

    calibration = [
        "Plan de calibration :",
        "- Imprimer un test (AmeraLabs Town / Boxes).",
        "- Ajuster l’expo par pas de 0,2 s.",
    ]

    return {
        "analysis": "\n".join(analysis_lines),
        "risks": "\n".join(risks),
        "orientation": "\n".join(orientation),
        "supports": "\n".join(supports),
        "parameters": "\n".join(params),
        "explanations": "\n".join(explanation),
        "diagnostics": "\n".join(diagnostics),
        "checklist": "\n".join(checklist),
        "calibration": "\n".join(calibration),
    }


def recommend_print_settings(
    bounds: Tuple[float, float, float],
    target_layer: float,
    resin_type: str,
    temp_c: float,
    profile: str,
) -> Dict[str, float | str]:
    x_dim, y_dim, z_dim = bounds
    max_dim = max(bounds)
    min_dim = min(bounds)
    volume_mm3 = x_dim * y_dim * z_dim

    if target_layer >= 0.09:
        layer_height = 0.10
        exposure = 4.5
        bottom_exposure = 50.0
        bottom_layers = 6
        lift_distance = 10.0
        lift_speed = 40.0
        retract_speed = 140.0
        transition_layers = 8
        rest_time = 0.8
    else:
        layer_height = 0.05
        exposure = 2.6
        bottom_exposure = 45.0
        bottom_layers = 6
        lift_distance = 8.0
        lift_speed = 50.0
        retract_speed = 150.0
        transition_layers = 8
        rest_time = 0.8

    if profile == "detailed":
        layer_height = max(0.03, layer_height - 0.02)
        exposure += 0.2
    elif profile == "fast":
        layer_height = min(0.12, layer_height + 0.02)
        exposure = max(2.0, exposure - 0.2)

    if resin_type in {"abs-like", "tough"}:
        exposure += 0.6
        bottom_exposure += 5.0
    if temp_c < 20:
        exposure *= 1.15
        lift_speed = max(30.0, lift_speed * 0.8)

    if max_dim >= 120:
        lift_distance += 2.0
        bottom_layers += 2

    supports_needed = z_dim > min_dim * 1.5 or z_dim > 60 or volume_mm3 > 200000
    raft_needed = min(x_dim, y_dim) < 25 or volume_mm3 < 20000

    return {
        "layer_height": layer_height,
        "exposure": exposure,
        "bottom_exposure": bottom_exposure,
        "bottom_layers": bottom_layers,
        "lift_distance": lift_distance,
        "lift_speed": lift_speed,
        "retract_speed": retract_speed,
        "transition_layers": transition_layers,
        "rest_time": rest_time,
        "supports": "Oui" if supports_needed else "Non",
        "raft": "Oui" if raft_needed else "Non",
    }


@st.cache_data(show_spinner=False)
def load_stl_mesh(data: bytes) -> Any:
    import trimesh

    mesh = trimesh.load(BytesIO(data), file_type="stl", force="mesh")
    if isinstance(mesh, trimesh.Scene):
        parts = mesh.dump()
        mesh = trimesh.util.concatenate(tuple(parts))
    if hasattr(mesh, "remove_duplicate_faces"):
        mesh.remove_duplicate_faces()
    if hasattr(mesh, "remove_degenerate_faces"):
        mesh.remove_degenerate_faces()
    if hasattr(mesh, "remove_unreferenced_vertices"):
        mesh.remove_unreferenced_vertices()
    mesh.process(validate=True)
    return mesh


def render_stl_viewer(mesh: Any) -> None:
    import plotly.graph_objects as go

    vertices = mesh.vertices
    faces = mesh.faces
    if vertices.size == 0 or faces.size == 0:
        st.info("Impossible de générer l'aperçu 3D : STL sans faces.")
        return
    fig = go.Figure()
    fig.add_trace(
        go.Mesh3d(
            x=vertices[:, 0],
            y=vertices[:, 1],
            z=vertices[:, 2],
            i=faces[:, 0],
            j=faces[:, 1],
            k=faces[:, 2],
            color="rgb(74,163,255)",
            opacity=1.0,
            flatshading=True,
        )
    )
    fig.update_layout(
        scene_aspectmode="data",
        margin=dict(l=0, r=0, t=0, b=0),
        scene=dict(
            bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showbackground=False, visible=False),
            yaxis=dict(showbackground=False, visible=False),
            zaxis=dict(showbackground=False, visible=False),
        ),
    )
    st.plotly_chart(fig, use_container_width=True)


def build_pdf_bytes(analysis: str, recommendations: str, explanations: str) -> bytes:
    from fpdf import FPDF

    def _sanitize(text: str) -> str:
        replacements = {
            "\u2019": "'",
            "\u2018": "'",
            "\u2013": "-",
            "\u2014": "-",
            "\u2026": "...",
        }
        for src, dest in replacements.items():
            text = text.replace(src, dest)
        return text

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 8, "Analyse STL")
    pdf.ln(2)
    pdf.multi_cell(0, 6, _sanitize(analysis))
    pdf.ln(4)
    pdf.multi_cell(0, 8, "Recommandations")
    pdf.ln(2)
    pdf.multi_cell(0, 6, _sanitize(recommendations))
    pdf.ln(4)
    pdf.multi_cell(0, 8, "Explications des paramètres")
    pdf.ln(2)
    pdf.multi_cell(0, 6, _sanitize(explanations))
    return pdf.output(dest="S").encode("latin1", errors="replace")


st.set_page_config(page_title="ADAM PARM3D", layout="wide")

st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"] {
        background: radial-gradient(circle at top, #1b2b3a 0%, #0c1118 60%);
        color: #f5f7fa;
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #111827 0%, #1f2937 100%);
    }
    .block-container {
        padding-top: 2rem;
    }
    .stMetric {
        background-color: #111827;
        border-radius: 12px;
        padding: 8px 12px;
        border: 1px solid #1f2937;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🖨️ ADAM PARM3D")
st.write(
    "Importez un STL et ajustez les paramètres de votre Flashforge Foto 8.9. "
    "Les valeurs proposées servent de base et peuvent être modifiées selon votre résine."
)

with st.sidebar:
    st.header("STL")
    uploaded_file = st.file_uploader("Importer un fichier STL", type=["stl"])
    st.caption("Analyse locale : dimensions et nombre de triangles.")
    st.subheader("Machine")
    machine_model = st.text_input(
        "Modèle imprimante",
        value="Flashforge Foto 8.9",
        help="Ex : Flashforge Foto 8.9",
    )
    machine_tech = st.text_input(
        "Technologie",
        value="MSLA mono 405 nm",
        help="Ex : MSLA mono 405 nm",
    )
    export_format = st.text_input(
        "Format export",
        value=".ctb",
        help="Ex : .ctb ou .svgx",
    )
    st.subheader("Résine")
    resin_brand = st.text_input(
        "Marque / modèle",
        value="Standard Resin",
        help="Ex : Anycubic Standard Resin V2",
    )
    resin_color = st.selectbox(
        "Couleur",
        options=["gris", "blanc", "noir", "transparente", "autre"],
    )
    resin_type = st.selectbox(
        "Type",
        options=["standard", "abs-like", "tough", "water-washable", "flexible"],
    )
    temp_c = st.number_input(
        "Température ambiante (°C)",
        value=22.0,
        step=0.5,
        help="Température de la pièce d'impression.",
    )
    st.subheader("Objectif")
    target_layer = st.selectbox(
        "Hauteur de couche",
        options=[0.05, 0.1],
        format_func=lambda v: "0.05 mm (qualité)" if v < 0.1 else "0.10 mm (rapide)",
    )
    profile_choice = st.selectbox(
        "Profil d'impression",
        options=["standard", "detailed", "fast"],
        format_func=lambda v: {
            "standard": "Standard (équilibré)",
            "detailed": "Détaillé (qualité)",
            "fast": "Rapide",
        }[v],
        help="Change la hauteur de couche et l'exposition selon la priorité.",
    )

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
            "transition_layers": 8,
            "rest_time": 0.8,
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
    if importlib.util.find_spec("trimesh") is None or importlib.util.find_spec("plotly") is None:
        st.info("Aperçu 3D indisponible : installez `trimesh` et `plotly`.")
    else:
        debug = st.expander("Debug aperçu 3D", expanded=False)
        debug.write(
            "Si l'aperçu ne s'affiche pas, vérifiez les dépendances, la taille du STL "
            "et si le navigateur autorise WebGL."
        )
        try:
            mesh = load_stl_mesh(uploaded_file.getvalue())
        except Exception as exc:
            debug.error(f"Erreur chargement STL : {exc}")
            mesh = None
        if mesh is None:
            st.info("Impossible de charger le STL pour l'aperçu 3D.")
        else:
            debug.write(f"Sommets : {len(mesh.vertices):,} | Faces : {len(mesh.faces):,}")
            if len(mesh.faces) > 250_000:
                st.warning(
                    "STL très lourd : l’affichage peut ramer. Simplifie le STL si besoin."
                )
            try:
                render_stl_viewer(mesh)
            except Exception as exc:
                debug.error(f"Erreur affichage 3D : {exc}")
                st.info("Impossible d'afficher le STL dans la vue 3D.")

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
    recommendations = recommend_print_settings(
        stl_info.bounds_mm, target_layer, resin_type, temp_c, profile_choice
    )
    report = build_report(stl_info, scale, recommendations, resin_type, temp_c)
    st.text_area("Résumé STL", value=report["analysis"], height=160)
    st.text_area("Risques STL", value=report["risks"], height=120)
    st.text_area("Orientation conseillée", value=report["orientation"], height=120)
    st.text_area("Plan supports", value=report["supports"], height=120)
    st.text_area("Paramètres recommandés", value=report["parameters"], height=180)
    st.text_area("Explication des paramètres", value=report["explanations"], height=180)
    st.text_area("Corrections si échec", value=report["diagnostics"], height=160)
    st.text_area("Checklist avant impression", value=report["checklist"], height=120)
    st.text_area("Plan de calibration", value=report["calibration"], height=120)
    st.subheader("Paramètres recommandés")
    if st.session_state.get("last_stl") != stl_info.name:
        profile.print_settings["layer_height"] = recommendations["layer_height"]
        profile.print_settings["bottom_layers"] = recommendations["bottom_layers"]
        profile.print_settings["exposure_time"] = recommendations["exposure"]
        profile.print_settings["bottom_exposure"] = recommendations["bottom_exposure"]
        profile.print_settings["lift_distance"] = recommendations["lift_distance"]
        profile.print_settings["lift_speed"] = recommendations["lift_speed"]
        profile.print_settings["retract_speed"] = recommendations["retract_speed"]
        profile.print_settings["transition_layers"] = recommendations["transition_layers"]
        profile.print_settings["rest_time"] = recommendations["rest_time"]
        st.session_state.last_stl = stl_info.name
        st.info("Paramètres recommandés appliqués à la pièce.")
    rec_col1, rec_col2, rec_col3 = st.columns(3)
    rec_col1.metric("Hauteur de couche", f"{recommendations['layer_height']:.2f} mm")
    rec_col1.metric("Exposition", f"{recommendations['exposure']:.1f} s")
    rec_col2.metric("Exposition base", f"{recommendations['bottom_exposure']:.1f} s")
    rec_col2.metric("Couches base", str(recommendations["bottom_layers"]))
    rec_col3.metric("Distance levage", f"{recommendations['lift_distance']:.1f} mm")
    rec_col3.metric("Supports nécessaires", recommendations["supports"])
    rec_col3.metric("Radeau nécessaire", recommendations["raft"])
    if importlib.util.find_spec("fpdf") is None:
        st.info("Installation requise pour le PDF : `pip install fpdf2`.")
    else:
        pdf_bytes = build_pdf_bytes(report["analysis"], report["parameters"], report["explanations"])
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
        profile.machine["resolution_x"] = st.number_input(
            "Résolution X (px)",
            value=profile.machine["resolution_x"],
            step=1.0,
            help="Valeur par défaut : 3840 px",
        )
        profile.machine["resolution_y"] = st.number_input(
            "Résolution Y (px)",
            value=profile.machine["resolution_y"],
            step=1.0,
            help="Valeur par défaut : 2400 px",
        )
    with col2:
        profile.machine["size_x"] = st.number_input(
            "Taille X (mm)",
            value=profile.machine["size_x"],
            step=0.1,
            help="Valeur par défaut : 192.0 mm",
        )
        profile.machine["size_y"] = st.number_input(
            "Taille Y (mm)",
            value=profile.machine["size_y"],
            step=0.1,
            help="Valeur par défaut : 120.0 mm",
        )
        profile.machine["size_z"] = st.number_input(
            "Taille Z (mm)",
            value=profile.machine["size_z"],
            step=0.1,
            help="Valeur par défaut : 200.0 mm",
        )

with resin_tab:
    st.subheader("Résine")
    col1, col2 = st.columns(2)
    with col1:
        profile.resin["type"] = st.text_input(
            "Type de résine",
            value=profile.resin.get("type", "standard"),
            help="Valeur par défaut : standard",
        )
        profile.resin["name"] = st.text_input(
            "Nom de la résine",
            value=profile.resin.get("name", "standard"),
            help="Valeur par défaut : standard",
        )
    with col2:
        profile.resin["density"] = st.number_input(
            "Densité (g/ml)",
            value=profile.resin["density"],
            step=0.01,
            help="Valeur par défaut : 1.10 g/ml",
        )
        profile.resin["cost_per_kg"] = st.number_input(
            "Coût (€/kg)",
            value=profile.resin["cost_per_kg"],
            step=1.0,
            help="Valeur par défaut : 30 €/kg",
        )

with print_tab:
    st.subheader("Imprimer")
    col1, col2 = st.columns(2)
    with col1:
        profile.print_settings["layer_height"] = st.number_input(
            "Hauteur de couche (mm)",
            value=profile.print_settings["layer_height"],
            step=0.01,
            help="Valeur par défaut : 0.10 mm",
        )
        profile.print_settings["bottom_layers"] = st.number_input(
            "Couches inférieures",
            value=profile.print_settings["bottom_layers"],
            step=1,
            help="Valeur par défaut : 8",
        )
        profile.print_settings["exposure_time"] = st.number_input(
            "Durée d'exposition (s)",
            value=profile.print_settings["exposure_time"],
            step=0.1,
            help="Valeur par défaut : 3.0 s",
        )
        profile.print_settings["bottom_exposure"] = st.number_input(
            "Durée exposition base (s)",
            value=profile.print_settings["bottom_exposure"],
            step=0.5,
            help="Valeur par défaut : 40.0 s",
        )
    with col2:
        profile.print_settings["lift_distance"] = st.number_input(
            "Distance de levage (mm)",
            value=profile.print_settings["lift_distance"],
            step=0.1,
            help="Valeur par défaut : 8.0 mm",
        )
        profile.print_settings["transition_layers"] = st.number_input(
            "Couches de transition",
            value=profile.print_settings.get("transition_layers", 8),
            step=1,
            help="Valeur par défaut : 8",
        )
        profile.print_settings["rest_time"] = st.number_input(
            "Rest / light-off (s)",
            value=profile.print_settings.get("rest_time", 0.8),
            step=0.1,
            help="Valeur par défaut : 0.8 s",
        )
        profile.print_settings["lift_speed"] = st.number_input(
            "Vitesse de levage (mm/min)",
            value=profile.print_settings["lift_speed"],
            step=1.0,
            help="Valeur par défaut : 65 mm/min",
        )
        profile.print_settings["retract_speed"] = st.number_input(
            "Vitesse de rétraction (mm/min)",
            value=profile.print_settings["retract_speed"],
            step=1.0,
            help="Valeur par défaut : 150 mm/min",
        )

with advanced_tab:
    st.subheader("Avancé")
    col1, col2 = st.columns(2)
    with col1:
        profile.advanced["bottom_pwm"] = st.number_input(
            "Éclairage base PWM",
            value=profile.advanced["bottom_pwm"],
            step=1,
            help="Valeur par défaut : 255",
        )
        profile.advanced["normal_pwm"] = st.number_input(
            "Éclairage PWM",
            value=profile.advanced["normal_pwm"],
            step=1,
            help="Valeur par défaut : 255",
        )
    with col2:
        profile.advanced["gray_levels"] = st.number_input(
            "Niveaux de gris",
            value=profile.advanced["gray_levels"],
            step=1,
            help="Valeur par défaut : 8",
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
