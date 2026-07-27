import math
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

# Page Configuration
st.set_page_config(page_title="Concrete Pile Reinforcement Optimizer", layout="wide")

st.title("🏗️ Concrete Pile Reinforcement Optimizer")
st.markdown("Adjust parameters on the left and click **Calculate** to find optimal rebar layouts.")

# --- Sidebar Inputs ---
st.sidebar.header("Optimization Goal & Parameters")

# Goal Selection (Outside form so it toggles target input instantly)
mode = st.sidebar.radio(
    "Optimization Goal:",
    ["Maximize Area", "Target Specific Area (cm²)"],
    help="Select whether to find the layout with the absolute maximum steel area or match a target area."
)

target_area_input = st.sidebar.number_input(
    "Target Reinforcement Area (cm²)", 
    value=200.0, 
    step=5.0, 
    disabled=(mode == "Maximize Area")
)

st.sidebar.markdown("---")

# Form for geometry and constraints
with st.sidebar.form(key="input_form"):
    st.subheader("Structural & Symmetry Rules")

    enforce_symmetry = st.checkbox(
        "Enforce Bending Symmetry (Min. 4 bars/layer & even counts)",
        value=True,
        help="Ensures every layer has at least 4 bars and an even count (4, 6, 8, 10...) for equal 180° structural bending capacity."
    )

    allow_mixed_dia = st.checkbox(
        "Allow mixed rebar diameters in same layer (Alternating / Symmetric)",
        value=False,
        help="Allows alternating two different bar sizes in a single layer (e.g. N/2 x Ø32 + N/2 x Ø25) while keeping full symmetry."
    )

    st.markdown("---")
    st.subheader("Concrete & Lapping Rules")

    lapping_option = st.radio(
        "Lapping Condition:",
        ["Consider Lapping (+1x rebar diameter extra space)", "No Lapping Required"],
        help="Lapping adds 1x rebar diameter extra space between single bars so that at lap joints the clear gap doesn't drop below the minimum."
    )

    is_no_lapping = (lapping_option == "No Lapping Required")

    agg_small = st.checkbox(
        "Aggregate size < 20 mm (Reduces min clear gap to 80 mm)",
        value=False,
        disabled=is_no_lapping,
        help="If checked, base minimum clear distance between bars in the same ring drops from 100 mm to 80 mm. Disabled when 'No Lapping Required' is active."
    )

    st.markdown("---")
    st.subheader("Pile Geometry & Rebars")

    # Dynamic Spacing Input: appears when No Lapping is chosen
    if is_no_lapping:
        custom_min_spacing = st.number_input(
            "Min. Edge Clear Spacing in Ring (mm)",
            value=100.0,
            step=5.0,
            help="Custom minimum clear edge-to-edge distance between rebars in the same layer."
        )
    else:
        custom_min_spacing = 80.0 if agg_small else 100.0

    pile_diameter = st.number_input("Pile Diameter (mm)", value=900.0, step=50.0)
    concrete_cover = st.number_input("Concrete Cover (mm)", value=75.0, step=5.0)
    shear_rebar_dia = st.number_input("Shear Reinforcement Diameter (mm)", value=14.0, step=1.0)

    max_layers = st.slider("Maximum Allowable Layers", min_value=1, max_value=5, value=4)

    available_rebars_str = st.text_input("Available Rebar Sizes (mm, comma-separated)", "16, 20, 25, 28, 32")

    submit_button = st.form_submit_button(label="🚀 Calculate", type="primary")

# --- Optimization Engine ---
if submit_button:
    try:
        rebar_sizes = sorted([int(x.strip()) for x in available_rebars_str.split(",")])
    except ValueError:
        st.error("Invalid rebar sizes string. Please enter numbers separated by commas.")
        rebar_sizes = [16, 20, 25, 28, 32]

    # Evaluate Lapping & Spacing
    consider_lapping = (lapping_option == "Consider Lapping (+1x rebar diameter extra space)")
    base_clear_spacing = custom_min_spacing

    r_outer_edge_max = (pile_diameter / 2.0) - concrete_cover - shear_rebar_dia

    # Helper function: Check max bars in ring
    def max_rebars_in_ring(r_center, d1, d2=None):
        if d2 is None or d1 == d2:
            d_eff = d1
            req_clear_spacing = base_clear_spacing + (d_eff if consider_lapping else 0.0)
            arg = (d_eff + req_clear_spacing) / (2.0 * r_center)
            if arg >= 1.0:
                return 0
            return math.floor(math.pi / math.asin(arg))
        else:
            d_eff = (d1 + d2) / 2.0
            max_d = max(d1, d2)
            req_clear_spacing = base_clear_spacing + (max_d if consider_lapping else 0.0)
            arg = (d_eff + req_clear_spacing) / (2.0 * r_center)
            if arg >= 1.0:
                return 0
            n_raw = math.floor(math.pi / math.asin(arg))
            return n_raw - (n_raw % 2) # Must be even for alternating mixed

    results = []

    def search_layers_recursive(layer_idx, current_outer_edge, parent_N, current_combo, d1, d2):
        d_max_layer = max(d1, d2)
        r_center = current_outer_edge - (d_max_layer / 2.0)
        if r_center <= d_max_layer / 2.0:
            return

        N_max = max_rebars_in_ring(r_center, d1, d2)

        # Minimum bar count filter
        min_N = 4 if enforce_symmetry else 1

        if N_max < min_N:
            return

        if layer_idx == 1:
            raw_N_list = list(range(min_N, N_max + 1))
        else:
            raw_N_list = [n for n in range(min_N, min(N_max, parent_N) + 1) if parent_N % n == 0]

        # Symmetry Filter: Even counts only
        if enforce_symmetry or d1 != d2:
            valid_N_list = [n for n in raw_N_list if n % 2 == 0]
        else:
            valid_N_list = raw_N_list

        for N in valid_N_list:
            if d1 == d2:
                area_layer = N * math.pi * (d1 / 2.0)**2
                label_text = f"Ø{d1} mm"
            else:
                area_layer = (N / 2.0) * math.pi * (d1 / 2.0)**2 + (N / 2.0) * math.pi * (d2 / 2.0)**2
                label_text = f"{N//2}xØ{d1} + {N//2}xØ{d2} mm"

            inner_edge = current_outer_edge - d_max_layer
            
            new_combo = current_combo + [{
                'layer': layer_idx,
                'd1': d1,
                'd2': d2,
                'diameter_text': label_text,
                'max_d': d_max_layer,
                'count': N,
                'r_center': r_center,
                'area_mm2': area_layer,
                'r_outer_edge': current_outer_edge,
                'r_inner_edge': inner_edge
            }]

            results.append(new_combo)

            if layer_idx < max_layers:
                next_pairs = [(d, d) for d in rebar_sizes]
                if allow_mixed_dia:
                    for i_a in range(len(rebar_sizes)):
                        for i_b in range(i_a + 1, len(rebar_sizes)):
                            next_pairs.append((rebar_sizes[i_a], rebar_sizes[i_b]))

                for d_next1, d_next2 in next_pairs:
                    d_next_max = max(d_next1, d_next2)
                    gap = 2.0 * max(d_max_layer, d_next_max)
                    next_outer_edge = inner_edge - gap
                    search_layers_recursive(layer_idx + 1, next_outer_edge, N, new_combo, d_next1, d_next2)

    if r_outer_edge_max > 0:
        layer1_pairs = [(d, d) for d in rebar_sizes]
        if allow_mixed_dia:
            for i_a in range(len(rebar_sizes)):
                for i_b in range(i_a + 1, len(rebar_sizes)):
                    layer1_pairs.append((rebar_sizes[i_a], rebar_sizes[i_b]))

        for d1, d2 in layer1_pairs:
            search_layers_recursive(1, r_outer_edge_max, None, [], d1, d2)

    # Save results into Session State
    st.session_state["results"] = results
    st.session_state["pile_diameter"] = pile_diameter
    st.session_state["concrete_cover"] = concrete_cover
    st.session_state["mode"] = mode
    st.session_state["target_area_input"] = target_area_input
    st.session_state["base_clear_spacing"] = base_clear_spacing
    st.session_state["consider_lapping"] = consider_lapping
    st.session_state["enforce_symmetry"] = enforce_symmetry

# --- Render Results View ---
if "results" in st.session_state:
    results = st.session_state["results"]
    pile_diameter = st.session_state["pile_diameter"]
    concrete_cover = st.session_state["concrete_cover"]
    mode = st.session_state["mode"]
    target_area_input = st.session_state["target_area_input"]
    base_clear_spacing = st.session_state["base_clear_spacing"]
    consider_lapping = st.session_state["consider_lapping"]
    enforce_symmetry = st.session_state.get("enforce_symmetry", True)

    if not results:
        st.error("No valid layout found within the given constraints. Try unchecking symmetry or decreasing cover.")
    else:
        if mode == "Maximize Area":
            sorted_combos = sorted(results, key=lambda combo: sum(l['area_mm2'] for l in combo), reverse=True)
        else:
            target_area_mm2 = target_area_input * 100.0
            sorted_combos = sorted(results, key=lambda combo: abs(sum(l['area_mm2'] for l in combo) - target_area_mm2))

        st.subheader("🎯 Select Configuration Option")
        
        choice_options = []
        num_options = min(5, len(sorted_combos))
        
        for rank_idx in range(num_options):
            c_area = sum(l['area_mm2'] for l in sorted_combos[rank_idx]) / 100.0
            if mode == "Maximize Area":
                label = f"Rank {rank_idx+1}: {c_area:.2f} cm² ({len(sorted_combos[rank_idx])} layers)"
            else:
                diff = c_area - target_area_input
                label = f"Rank {rank_idx+1}: {c_area:.2f} cm² ({diff:+.2f} cm² vs target)"
            choice_options.append(label)

        selected_label = st.radio(
            "Choose rank choice to view detail & diagram:",
            options=choice_options,
            horizontal=True,
            key="rank_choice_selector"
        )
        
        selected_index = choice_options.index(selected_label)
        best_combo = sorted_combos[selected_index]
        total_area_cm2 = sum(l['area_mm2'] for l in best_combo) / 100.0

        st.markdown("---")

        col1, col2 = st.columns([1, 1])

        with col1:
            st.subheader(f"Layout Breakdown ({selected_label.split(':')[0]})")
            
            if mode == "Target Specific Area (cm²)":
                diff = total_area_cm2 - target_area_input
                st.metric(
                    label="Calculated Steel Area ($A_s$)", 
                    value=f"{total_area_cm2:.2f} cm²", 
                    delta=f"{diff:+.2f} cm² vs target"
                )
            else:
                st.metric(label="Total Steel Area ($A_s$)", value=f"{total_area_cm2:.2f} cm²")

            lap_text = f"Lapping (+{best_combo[0]['max_d']}mm extra)" if consider_lapping else "No Lapping"
            sym_text = "Enforced (Min 4, Even)" if enforce_symmetry else "Off"
            st.caption(f"ℹ️ **Active Criteria:** Bending Symmetry = {sym_text} | Min Base Clear = {base_clear_spacing:.0f} mm | {lap_text}")

            table_data = []
            for idx, l in enumerate(best_combo):
                chord_c2c = 2.0 * l['r_center'] * math.sin(math.pi / l['count'])
                d_eff = (l['d1'] + l['d2']) / 2.0
                straight_clear_single = chord_c2c - d_eff
                
                lap_clear = straight_clear_single - (l['max_d'] if consider_lapping else 0.0)
                
                if idx == 0:
                    gap = "—"
                else:
                    prev_d = best_combo[idx-1]['max_d']
                    req_gap = 2 * max(prev_d, l['max_d'])
                    gap = f"{best_combo[idx-1]['r_inner_edge'] - l['r_outer_edge']:.1f} mm (Req: {req_gap}mm)"
                
                table_data.append({
                    "Layer": f"Layer {l['layer']}",
                    "Rebar Configuration": l['diameter_text'],
                    "Count": l['count'],
                    "Single Bar Clear": f"{straight_clear_single:.1f} mm",
                    "Clear Gap at Lap": f"{lap_clear:.1f} mm",
                    "Gap to Outer Layer": gap,
                    "Layer Area": f"{l['area_mm2']/100.0:.2f} cm²"
                })
            
            st.table(pd.DataFrame(table_data))

        with col2:
            st.subheader("Cross-Section Diagram")
            fig, ax = plt.subplots(figsize=(7, 7))

            circle_concrete = plt.Circle((0, 0), pile_diameter / 2.0, color='#e0e0e0', ec='black', lw=2)
            ax.add_patch(circle_concrete)

            r_shear = (pile_diameter / 2.0) - concrete_cover
            circle_shear = plt.Circle((0, 0), r_shear, color='none', ec='red', lw=2, linestyle='--')
            ax.add_patch(circle_shear)

            colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
            N_l1 = best_combo[0]['count']
            base_angles = np.linspace(0, 2 * np.pi, N_l1, endpoint=False)

            for i, l in enumerate(best_combo):
                r_c = l['r_center']
                d1, d2 = l['d1'], l['d2']
                N = l['count']
                
                pitch_circle = plt.Circle((0, 0), r_c, color=colors[i], fill=False, linestyle=':', lw=1.5)
                ax.add_patch(pitch_circle)
                
                step = N_l1 // N
                layer_angles = base_angles[::step]
                
                for idx, angle in enumerate(layer_angles):
                    x = r_c * np.cos(angle)
                    y = r_c * np.sin(angle)
                    
                    d_current = d1 if (idx % 2 == 0 or d1 == d2) else d2
                    
                    label = f"Layer {l['layer']}: {l['diameter_text']}" if idx == 0 else None
                    bar = plt.Circle((x, y), d_current / 2.0, color=colors[i], ec='black', lw=1, label=label)
                    ax.add_patch(bar)

            lim = (pile_diameter / 2.0) * 1.1
            ax.set_aspect('equal')
            ax.set_xlim(-lim, lim)
            ax.set_ylim(-lim, lim)
            plt.xlabel("X (mm)")
            plt.ylabel("Y (mm)")
            plt.grid(True, linestyle='--', alpha=0.5)
            plt.legend(loc='lower center', bbox_to_anchor=(0.5, -0.25), ncol=2)
            
            st.pyplot(fig)
else:
    st.info("👈 Enter your parameters in the sidebar and click **Calculate** to display optimal layouts.")