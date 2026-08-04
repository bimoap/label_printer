import streamlit as st
import barcode
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont
import io
import textwrap
import os

st.set_page_config(page_title="SATO Label Utility", layout="wide")

st.title("SATO Label Printer Utility (35 x 89 mm)")
st.write("Enter your part details below to generate a perfectly sized PDF for the thermal printer.")

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

st.subheader("1. Label Data")
col1, col2, col3 = st.columns(3)

with col1:
    stockcode = st.text_input(
        "1. Stockcode:", 
        placeholder="e.g., 123456"
    )
with col2:
    prefix = st.text_input(
        "2. Barcode Prefix (Optional):", 
        value="P-",
        help="This is added to the front of the barcode data so scanners identify it as a part number."
    )
with col3:
    description = st.text_input(
        "3. Description (Prints on Top):", 
        placeholder="e.g., 10mm Steel Bracket"
    )

if st.button("Generate Label", type="primary"):
    if not stockcode.strip():
        st.error("Please enter a Stockcode before generating the label.")
    else:
        # Setup for 203 DPI Thermal Printer Canvas (89x35mm)
        WIDTH, HEIGHT = 711, 280
        
        font_filename = "arial.ttf"
        custom_font = get_font(font_filename, 24)
        barcode_text_font = get_font(font_filename, 60)

        img = Image.new('RGB', (WIDTH, HEIGHT), color='white')
        draw = ImageDraw.Draw(img)
        
        # --- 1. PREPARE TEXT DIMENSIONS ---
        lines_to_draw = []
        clean_description = description.strip()
        
        if clean_description:
            # Wrap to ~65 chars to fit across the label
            wrapped_lines = textwrap.wrap(clean_description, width=65)
            lines_to_draw.extend(wrapped_lines)
        
        text_measurements = []
        total_text_height = 0
        
        for line in lines_to_draw:
            bbox = draw.textbbox((0, 0), line, font=custom_font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            text_measurements.append((line, w, h))
            total_text_height += h + 8 # 8px vertical spacing between lines
            
        # --- 2. GENERATE BARCODE IMAGE ---
        full_barcode_data = f"{prefix.strip()}{stockcode.strip()}"
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
            st.error(f"Error generating barcode: {e}")
            st.stop()
        
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
        # Total height of all elements combined
        total_content_height = total_text_height + bc_height + bc_text_h + 20 
        
        # Find the starting Y position to center the whole block vertically
        current_y = (HEIGHT - total_content_height) // 2
        if current_y < 5: 
            current_y = 5 
            
        # --- 5. DRAW EVERYTHING CENTERED ---
        
        # Draw Description lines
        for line, w, h in text_measurements:
            x = (WIDTH - w) // 2
            draw.text((x, current_y), line, fill="black", font=custom_font)
            current_y += h + 8
            
        if lines_to_draw:
            current_y += 5 # Small gap before barcode if text exists
        
        # Draw Barcode Image
        bc_x = (WIDTH - bc_width) // 2
        img.paste(bc_img, (bc_x, current_y))
        current_y += bc_height + 5 
        
        # Draw Barcode Text
        bc_text_x = (WIDTH - bc_text_w) // 2
        draw.text((bc_text_x, current_y), full_barcode_data, fill="black", font=barcode_text_font)
        
        # --- 6. EXPORT ---
        pdf_buffer = io.BytesIO()
        img.save(
            pdf_buffer, 
            format='PDF', 
            resolution=203.0
        )
        pdf_buffer.seek(0)

        st.success("Label generated successfully!")
        
        st.subheader("Label Preview")
        st.image(img, use_container_width=False)
        
        st.download_button(
            label="Download Print-Ready PDF",
            data=pdf_buffer,
            file_name=f"Label_{stockcode.strip()}.pdf",
            mime="application/pdf"
        )
