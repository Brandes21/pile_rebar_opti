import math
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

# Page Configuration
st.set_page_config(page_title="Concrete Pile Reinforcement Optimizer", layout="wide")

st.title("🏗️ Concrete Pile Reinforcement Optimizer")
st.markdown("Adjust parameters on the left and click **Calculate** to find optimal rebar layouts.")

# --- Sidebar Inputs inside a FORM ---
st.sidebar.header("Optimization Goal & Parameters")

with st.sidebar.form(key="input_form"):
    mode = st.radio(
        "Optimization Goal:",
        ["Maximize Area", "Target Specific Area (cm²)"],
        help="Select whether to find the layout with the absolute maximum steel area or match a target area."
    )
    
    target_area_input = st.number_input(
        "Target Reinforcement Area (cm²)", 
        value=200.0, 
        step=5.0, 
        disabled=(mode == "Maximize Area")
    )
    
    st.markdown("---")
    st.subheader("Concrete & Lapping Rules")

    # Lapping Selection
    lapping_option = st.radio(
        "Lapping Condition:",
        ["Consider Lapping (+1x rebar diameter extra space)", "No Lapping Required"],
        help="Lapping adds 1x rebar diameter extra space between single bars so that at lap joints the clear gap doesn't drop below the minimum."
    )

    # Aggregate Size Selection
    agg_small = st.checkbox(
        "Aggregate size < 20 mm (Reduces min clear gap to 80 mm)",
        value=False,
        help="If checked, base minimum clear distance between bars in the same ring drops from 100 mm to 80 mm."
    )

    st.markdown("---")
    st.subheader("Pile Geometry & Rebars")
    
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

    # Base Spacing Calculation
    base_clear_spacing = 80.0 if agg_small else 100.0
    consider_lapping = (lapping_option == "Consider Lapping (+1x rebar diameter extra space)")

    r_outer_edge_max = (pile_diameter / 2.0) - concrete_cover - shear_rebar_dia

    def max_rebars_in_ring(r_center, d_rebar):
        # If lapping, required clear distance between single bars = base_clear + d_rebar
        # At lap joint, taking up d_rebar leaves base_clear gap.
        req_clear_spacing = base_clear_spacing + (d_rebar if consider_lapping else 0.0)
        
        # Chord distance formula: 2 * r_c * sin(pi / N) - d_rebar >= req_clear_spacing
        arg = (d_rebar + req_clear_spacing) / (2.0 * r_center)
        if arg >= 1.0:
            return 0
        return math.floor(math.pi / math.asin(arg))

    results = []

    def search_layers_recursive(layer_idx, current_outer_edge, parent_N, current_combo, d_current):
        r_center = current_outer_edge - (d_current / 2.0)
        if r_center <= d_current / 2.0:
            return

        N_max = max_rebars_in_ring(r_center, d_current)

        if layer_idx == 1:
            valid_N_list = list(range(1, N_max + 1))
        else:
            valid_N_list = [n for n in range(1, min(N_max, parent_N) + 1) if parent_N % n == 0]

        for N in valid_N_list:
            area_layer = N * math.pi * (d_current / 2.0)**2
            inner_edge = current_outer_edge - d_current
            
            new_combo = current_combo + [{
                'layer': layer_idx,
                'diameter': d_current,
                'count': N,
                'r_center': r_center,
                'area_mm2': area_layer,
                'r_outer_edge': current_outer_edge,
                'r_inner_edge': inner_edge
            }]

            results.append(new_combo)

            if layer_idx < max_layers:
                for d_next in rebar_sizes:
                    gap = 2.0 * max(d_current, d_next)
                    next_outer_edge = inner_edge - gap
                    search_layers_recursive(layer_idx + 1, next_outer_edge, N, new_combo, d_next)

    if r_outer_edge_max > 0:
        for d1 in rebar_sizes:
            search_layers_recursive(1, r_outer_edge_max, None, [], d1)

    # Save results into Session State
    st.session_state["results"] = results
    st.session_state["pile_diameter"] = pile_diameter
    st.session_state["concrete_cover"] = concrete_cover
    st.session_state["mode"] = mode
    st.session_state["target_area_input"] = target_area_input
    st.session_state["base_clear_spacing"] = base_clear_spacing
    st.session_state["consider_lapping"] = consider_lapping

# --- Render Results View ---
if "results" in st.session_state:
    results = st.session_state["results"]
    pile_diameter = st.session_state["pile_diameter"]
    concrete_cover = st.session_state["concrete_cover"]
    mode = st.session_state["mode"]
    target_area_input = st.session_state["target_area_input"]
    base_clear_spacing = st.session_state["base_clear_spacing"]
    consider_lapping = st.session_state["consider_lapping"]

    if not results:
        st.error("No valid layout found within the given constraints.")
    else:
        # Sort layouts based on mode
        if mode == "Maximize Area":
            sorted_combos = sorted(results, key=lambda combo: sum(l['area_mm2'] for l in combo), reverse=True)
        else:
            target_area_mm2 = target_area_input * 100.0
            sorted_combos = sorted(results, key=lambda combo: abs(sum(l['area_mm2'] for l in combo) - target_area_mm2))

        # Top Options Radio Selection Bar
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

        # --- Display Selected Option Details ---
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

            # Active rules banner
            lap_text = f"Lapping (+{best_combo[0]['diameter']}mm extra)" if consider_lapping else "No Lapping"
            st.caption(f"ℹ️ **Active Criteria:** Min Base Clear = {base_clear_spacing:.0f} mm | {lap_text}")

            table_data = []
            for idx, l in enumerate(best_combo):
                chord_c2c = 2.0 * l['r_center'] * math.sin(math.pi / l['count'])
                straight_clear_single = chord_c2c - l['diameter']
                
                # Effective clear gap at lap location
                lap_clear = straight_clear_single - (l['diameter'] if consider_lapping else 0.0)
                
                if idx == 0:
                    gap = "—"
                else:
                    prev_d = best_combo[idx-1]['diameter']
                    req_gap = 2 * max(prev_d, l['diameter'])
                    gap = f"{best_combo[idx-1]['r_inner_edge'] - l['r_outer_edge']:.1f} mm (Req: {req_gap}mm)"
                
                table_data.append({
                    "Layer": f"Layer {l['layer']}",
                    "Rebar Size": f"Ø{l['diameter']} mm",
                    "Count": l['count'],
                    "Single Bar Clear": f"{straight_clear_single:.1f} mm",
                    "Clear Gap at Lap": f"{lap_clear:.1f} mm (Min: {base_clear_spacing:.0f}mm)",
                    "Gap to Outer Layer": gap,
                    "Layer Area": f"{l['area_mm2']/100.0:.2f} cm²"
                })
            
            st.table(pd.DataFrame(table_data))

        with col2:
            st.subheader("Cross-Section Diagram")
            fig, ax = plt.subplots(figsize=(7, 7))

            # Concrete Pile
            circle_concrete = plt.Circle((0, 0), pile_diameter / 2.0, color='#e0e0e0', ec='black', lw=2)
            ax.add_patch(circle_concrete)

            # Shear Stirrup Ring
            r_shear = (pile_diameter / 2.0) - concrete_cover
            circle_shear = plt.Circle((0, 0), r_shear, color='none', ec='red', lw=2, linestyle='--')
            ax.add_patch(circle_shear)

            colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
            N_l1 = best_combo[0]['count']
            base_angles = np.linspace(0, 2 * np.pi, N_l1, endpoint=False)

            for i, l in enumerate(best_combo):
                r_c = l['r_center']
                d = l['diameter']
                N = l['count']
                
                pitch_circle = plt.Circle((0, 0), r_c, color=colors[i], fill=False, linestyle=':', lw=1.5)
                ax.add_patch(pitch_circle)
                
                step = N_l1 // N
                layer_angles = base_angles[::step]
                
                for idx, angle in enumerate(layer_angles):
                    x = r_c * np.cos(angle)
                    y = r_c * np.sin(angle)
                    label = f"Layer {l['layer']}: {N}xØ{d}mm" if idx == 0 else None
                    bar = plt.Circle((x, y), d / 2.0, color=colors[i], ec='black', lw=1, label=label)
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