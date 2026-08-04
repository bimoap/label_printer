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
st.write("Generating labels from default data.")

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

# --- 1. HARDCODED DEFAULT DATA ---
# This dictionary replaces the CSV/Excel upload process
data = {
    "stockcode": ["151"],
    "Description": ["114 V DC Electromagnet Assembly"]
}

# Convert the dictionary into a pandas DataFrame
df = pd.DataFrame(data).astype(str)
    
st.subheader("1. Data Configuration")

# Show the current default data on the screen for reference
st.dataframe(df, use_container_width=True)

col1, col2, col3 = st.columns(3)

with col1:
    barcode_col = st.selectbox(
        "Barcode Column:", 
        df.columns,
        index=list(df.columns).index("stockcode") # Auto-select stockcode
    )
with col2:
    barcode_prefix = st.text_input(
        "Barcode Prefix (Optional):", 
        placeholder="e.g., P-",
        help="This will be added to the front of the barcode data so the scanner knows what it is reading."
    )
with col3:
    text_cols = st.multiselect(
        "Additional Text Columns (Prints on Left):", 
        df.columns,
        default=["Description"] # Auto-select Description
    )

if st.button("Generate Labels", type="primary"):
    # Setup for 203 DPI Thermal Printer Canvas (89x35mm)
    WIDTH, HEIGHT = 711, 280
    
    font_filename = "arial.ttf"
    custom_font = get_font(font_filename, 20)
    barcode_text_font = get_font(font_filename, 60)

    label_images = []
    progress_bar = st.progress(0)
    
    for index, row in df.iterrows():
        img = Image.new('RGB', (WIDTH, HEIGHT), color='white')
        draw = ImageDraw.Draw(img)
        
        # --- 1. DRAW TEXT (Strictly on the left side) ---
        y_text = 20
        for col in text_cols:
            text_val = str(row[col])
            text_line = f"{col}: {text_val}"
            
            wrapped_lines = textwrap.wrap(text_line, width=16)
            
            for line in wrapped_lines:
                draw.text((20, y_text), line, fill="black", font=custom_font)
                y_text += 40 
            
            y_text += 10 
            
        # --- 2. GENERATE BARCODE (Without Text) ---
        raw_data = str(row[barcode_col])
        if raw_data == 'nan' or not raw_data.strip():
            raw_data = "0000"
            
        full_barcode_data = f"{barcode_prefix}{raw_data}"
        
        rv = io.BytesIO()
        
        options = {
            "write_text": False, 
            "module_width": 0.4,
            "module_height": 12.0
        }
        
        try:
            code128 = barcode.get('code128', full_barcode_data, writer=ImageWriter())
            code128.write(rv, options=options)
        except Exception as e:
            st.error(f"Error generating barcode for {full_barcode_data}: {e}")
            continue
        
        rv.seek(0)
        bc_img = Image.open(rv)
        
        MAX_BC_WIDTH = 450
        MAX_BC_HEIGHT = 160 
        
        bc_img.thumbnail((MAX_BC_WIDTH, MAX_BC_HEIGHT), Image.Resampling.LANCZOS)
        bc_width, bc_height = bc_img.size
        
        x_offset = WIDTH - bc_width - 20
        y_offset = (HEIGHT - bc_height) // 2 - 30
        
        img.paste(bc_img, (x_offset, y_offset))
        
        # --- 3. MANUALLY DRAW THE LARGER BARCODE TEXT ---
        text_bbox = draw.textbbox((0, 0), full_barcode_data, font=barcode_text_font)
        text_width = text_bbox[2] - text_bbox[0]
        
        text_x = x_offset + (bc_width // 2) - (text_width // 2)
        text_y = y_offset + bc_height + 15 
        
        draw.text((text_x, text_y), full_barcode_data, fill="black", font=barcode_text_font)
        
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
