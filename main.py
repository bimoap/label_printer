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
st.write("Upload your data, select your columns, and download a perfectly sized PDF for the thermal printer.")

def get_font(primary_font_path, size):
    """
    Attempts to load the primary font. If missing, attempts to load common 
    Linux server fonts before falling back to the tiny PIL default.
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
        
        st.warning(f"⚠️ Font '{primary_font_path}' not found and no system fallbacks available. Text will appear exceptionally small.")
        return ImageFont.load_default()

# Upload file
uploaded_file = st.file_uploader("Upload Data (CSV or Excel)", type=["csv", "xlsx"])

if uploaded_file:
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file).astype(str)
    else:
        df = pd.read_excel(uploaded_file).astype(str)
        
    st.subheader("1. Data Configuration")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        barcode_col = st.selectbox(
            "Barcode Column:", 
            df.columns
        )
    with col2:
        barcode_prefix = st.text_input(
            "Barcode Prefix (Optional):", 
            placeholder="e.g., P-",
            help="This will be added to the front of the barcode data so the scanner knows what it is reading."
        )
    with col3:
        text_cols = st.multiselect(
            "Additional Text Columns (Prints on Top):", 
            df.columns
        )

    if st.button("Generate Labels", type="primary"):
        # Setup for 203 DPI Thermal Printer Canvas (89x35mm)
        WIDTH, HEIGHT = 711, 280
        
        font_filename = "arial.ttf"
        custom_font = get_font(font_filename, 24) # Slightly larger font for description
        barcode_text_font = get_font(font_filename, 60)

        label_images = []
        progress_bar = st.progress(0)
        
        for index, row in df.iterrows():
            img = Image.new('RGB', (WIDTH, HEIGHT), color='white')
            draw = ImageDraw.Draw(img)
            
            # --- 1. PREPARE TEXT DIMENSIONS ---
            lines_to_draw = []
            for col in text_cols:
                text_val = str(row[col])
                text_line = f"{col}: {text_val}"
                # Wrap to ~65 chars since it now spans the full width
                wrapped_lines = textwrap.wrap(text_line, width=65)
                lines_to_draw.extend(wrapped_lines)
            
            text_measurements = []
            total_text_height = 0
            
            for line in lines_to_draw:
                bbox = draw.textbbox((0, 0), line, font=custom_font)
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
                text_measurements.append((line, w, h))
                total_text_height += h + 8 # 8px spacing between lines
                
            # --- 2. GENERATE BARCODE IMAGE ---
            raw_data = str(row[barcode_col])
            if raw_data == 'nan' or not raw_data.strip():
                raw_data = "0000"
                
            full_barcode_data = f"{barcode_prefix}{raw_data}"
            rv = io.BytesIO()
            
            options = {
                "write_text": False, 
                "module_width": 0.4,
                "module_height": 10.0 # Slightly shorter to fit vertical layout
            }
            
            try:
                code128 = barcode.get('code128', full_barcode_data, writer=ImageWriter())
                code128.write(rv, options=options)
            except Exception as e:
                st.error(f"Error generating barcode for {full_barcode_data}: {e}")
                continue
            
            rv.seek(0)
            bc_img = Image.open(rv)
            
            # Reduce max height to ensure it fits with the top description
            MAX_BC_WIDTH = 650
            MAX_BC_HEIGHT = 120 
            
            bc_img.thumbnail((MAX_BC_WIDTH, MAX_BC_HEIGHT), Image.Resampling.LANCZOS)
            bc_width, bc_height = bc_img.size
            
            # --- 3. PRE-CALCULATE BARCODE TEXT DIMENSIONS ---
            bc_text_bbox = draw.textbbox((0, 0), full_barcode_data, font=barcode_text_font)
            bc_text_w = bc_text_bbox[2] - bc_text_bbox[0]
            bc_text_h = bc_text_bbox[3] - bc_text_bbox[1]
            
            # --- 4. CALCULATE VERTICAL CENTERING ---
            # Total height of all elements combined
            total_content_height = total_text_height + bc_height + bc_text_h + 20 
            
            # Find the starting Y position to center the whole block vertically
            current_y = (HEIGHT - total_content_height) // 2
            if current_y < 5: 
                current_y = 5 # Safety margin so text isn't cut off at the top
                
            # --- 5. DRAW EVERYTHING CENTERED ---
            
            # Draw Description lines
            for line, w, h in text_measurements:
                x = (WIDTH - w) // 2
                draw.text((x, current_y), line, fill="black", font=custom_font)
                current_y += h + 8
                
            current_y += 5 # Small gap before barcode
            
            # Draw Barcode Image
            bc_x = (WIDTH - bc_width) // 2
            img.paste(bc_img, (bc_x, current_y))
            current_y += bc_height + 5 # Small gap before bottom text
            
            # Draw Barcode Text
            bc_text_x = (WIDTH - bc_text_w) // 2
            draw.text((bc_text_x, current_y), full_barcode_data, fill="black", font=barcode_text_font)
            
            label_images.append(img)
            progress_bar.progress((index + 1) / len(df))

        # Compile all images into a single PDF
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
            
            st.subheader("Preview of Label 1")
            st.image(label_images[0], use_container_width=False)
            
            st.download_button(
                label="Download Print-Ready PDF",
                data=pdf_buffer,
                file_name="SATO_Labels_89x35.pdf",
                mime="application/pdf"
            )
