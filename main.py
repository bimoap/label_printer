import streamlit as st
import pandas as pd
import barcode
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont
import io
import textwrap
import os

st.set_page_config(page_title="SATO Label Utility", layout="wide")

st.title("SATO Label Printer Utility (35 x 89 mm)")
st.write("Generate perfectly sized labels for your thermal printer.")

def get_font(primary_font_path, size):
    """
    Attempts to load the primary font. If missing, attempts to load common 
    Linux server fonts before falling back to the PIL default.
    """
    try:
        return ImageFont.truetype(primary_font_path, size)
    except IOError:
        linux_fallbacks = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf"
        ]
        
        for fallback in linux_fallbacks:
            if os.path.exists(fallback):
                try:
                    return ImageFont.truetype(fallback, size)
                except IOError:
                    continue
        
        return ImageFont.load_default()

def create_label_image(stockcode, prefix, description_lines):
    """Helper function to generate a centered label image."""
    WIDTH, HEIGHT = 711, 280
    
    font_filename = "arial.ttf"
    custom_font = get_font(font_filename, 24)
    barcode_text_font = get_font(font_filename, 60)

    img = Image.new('RGB', (WIDTH, HEIGHT), color='white')
    draw = ImageDraw.Draw(img)
    
    # --- 1. PREPARE TEXT DIMENSIONS ---
    text_measurements = []
    total_text_height = 0
    
    for line in description_lines:
        bbox = draw.textbbox((0, 0), line, font=custom_font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        text_measurements.append((line, w, h))
        total_text_height += h + 8 # 8px spacing
        
    # --- 2. GENERATE BARCODE IMAGE ---
    # Fallback if stockcode is empty (from spreadsheet NaN)
    if not stockcode or str(stockcode) == 'nan':
        stockcode = "0000"
        
    full_barcode_data = f"{prefix.strip()}{str(stockcode).strip()}"
    rv = io.BytesIO()
    
    options = {
        "write_text": False, 
        "module_width": 0.4,
        "module_height": 10.0
    }
    
    try:
        code128 = barcode.get('code128', full_barcode_data, writer=ImageWriter())
        code128.write(rv, options=options)
    except Exception as e:
        return None, f"Error generating barcode: {e}"
    
    rv.seek(0)
    bc_img = Image.open(rv)
    
    MAX_BC_WIDTH = 650
    MAX_BC_HEIGHT = 120 
    
    bc_img.thumbnail((MAX_BC_WIDTH, MAX_BC_HEIGHT), Image.Resampling.LANCZOS)
    bc_width, bc_height = bc_img.size
    
    # --- 3. PRE-CALCULATE BARCODE TEXT DIMENSIONS ---
    bc_text_bbox = draw.textbbox((0, 0), full_barcode_data, font=barcode_text_font)
    bc_text_w = bc_text_bbox[2] - bc_text_bbox[0]
    bc_text_h = bc_text_bbox[3] - bc_text_bbox[1]
    
    # --- 4. CALCULATE VERTICAL CENTERING ---
    total_content_height = total_text_height + bc_height + bc_text_h + 20 
    current_y = (HEIGHT - total_content_height) // 2
    if current_y < 5: 
        current_y = 5 
        
    # --- 5. DRAW EVERYTHING CENTERED ---
    for line, w, h in text_measurements:
        x = (WIDTH - w) // 2
        draw.text((x, current_y), line, fill="black", font=custom_font)
        current_y += h + 8
        
    if description_lines:
        current_y += 5 
    
    bc_x = (WIDTH - bc_width) // 2
    img.paste(bc_img, (bc_x, current_y))
    current_y += bc_height + 5 
    
    bc_text_x = (WIDTH - bc_text_w) // 2
    draw.text((bc_text_x, current_y), full_barcode_data, fill="black", font=barcode_text_font)
    
    return img, None


# --- UI LAYOUT WITH TABS ---
tab1, tab2 = st.tabs(["📁 Batch Upload (Spreadsheet)", "✍️ Manual Entry (Single Label)"])

with tab1:
    st.subheader("Spreadsheet Upload")
    uploaded_file = st.file_uploader("Upload Data (CSV or Excel)", type=["csv", "xlsx"])

    if uploaded_file:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file).astype(str)
        else:
            df = pd.read_excel(uploaded_file).astype(str)
            
        col1, col2, col3 = st.columns(3)
        
        with col1:
            barcode_col = st.selectbox("Stockcode Column:", df.columns, key="batch_stock")
        with col2:
            barcode_prefix = st.text_input("Barcode Prefix (Optional):", placeholder="e.g., P", key="batch_prefix")
        with col3:
            # Letting you select multiple description columns if needed, but it will just print the text, not the column name.
            text_cols = st.multiselect("Description Column(s):", df.columns, key="batch_desc")

        if st.button("Generate Batch Labels", type="primary"):
            label_images = []
            progress_bar = st.progress(0)
            
            for index, row in df.iterrows():
                lines_to_draw = []
                for col in text_cols:
                    text_val = str(row[col])
                    if text_val != 'nan' and text_val.strip():
                        # Wraps text across the label width, no "Description:" prefix added
                        wrapped_lines = textwrap.wrap(text_val.strip(), width=65)
                        lines_to_draw.extend(wrapped_lines)
                
                stockcode_val = row[barcode_col]
                img, error = create_label_image(stockcode_val, barcode_prefix, lines_to_draw)
                
                if error:
                    st.error(error)
                elif img:
                    label_images.append(img)
                    
                progress_bar.progress((index + 1) / len(df))

            if label_images:
                pdf_buffer = io.BytesIO()
                label_images[0].save(
                    pdf_buffer, 
                    format='PDF', 
                    resolution=203.0, 
                    save_all=True, 
                    append_images=label_images[1:]
                )
                pdf_buffer.seek(0)

                st.success(f"Successfully generated {len(label_images)} labels!")
                st.image(label_images[0], caption="Preview of Label 1", use_container_width=False)
                st.download_button(
                    label="Download Batch PDF",
                    data=pdf_buffer,
                    file_name="SATO_Batch_Labels.pdf",
                    mime="application/pdf"
                )

with tab2:
    st.subheader("Manual Data Entry")
    col_m1, col_m2, col_m3 = st.columns(3)

    with col_m1:
        manual_stockcode = st.text_input("1. Stockcode:", placeholder="e.g., 123456")
    with col_m2:
        manual_prefix = st.text_input("2. Barcode Prefix (Optional):", value="P-")
    with col_m3:
        manual_desc = st.text_input("3. Description (Prints on Top):", placeholder="e.g., 10mm Steel Bracket")

    if st.button("Generate Single Label", type="primary"):
        if not manual_stockcode.strip():
            st.error("Please enter a Stockcode before generating the label.")
        else:
            lines_to_draw = []
            clean_description = manual_desc.strip()
            if clean_description:
                wrapped_lines = textwrap.wrap(clean_description, width=65)
                lines_to_draw.extend(wrapped_lines)
                
            img, error = create_label_image(manual_stockcode, manual_prefix, lines_to_draw)
            
            if error:
                st.error(error)
            elif img:
                pdf_buffer = io.BytesIO()
                img.save(pdf_buffer, format='PDF', resolution=203.0)
                pdf_buffer.seek(0)

                st.success("Label generated successfully!")
                st.image(img, caption="Label Preview", use_container_width=False)
                st.download_button(
                    label="Download Single PDF",
                    data=pdf_buffer,
                    file_name=f"Label_{manual_stockcode.strip()}.pdf",
                    mime="application/pdf"
                )
