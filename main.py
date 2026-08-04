import streamlit as st
import pandas as pd
import barcode
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont
import io

st.set_page_config(page_title="SATO Label Utility", layout="wide")

st.title("SATO Label Printer Utility (35 x 89 mm)")
st.write("Upload your data, select your columns, and download a perfectly sized PDF for the thermal printer.")

# Upload file
uploaded_file = st.file_uploader("Upload Data (CSV or Excel)", type=["csv", "xlsx"])

if uploaded_file:
    # Read the data
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
            "Additional Text Columns (Prints on Left):", 
            df.columns
        )

    if st.button("Generate Labels", type="primary"):
        # Setup for 203 DPI Thermal Printer Canvas (89x35mm)
        WIDTH, HEIGHT = 711, 280
        
        try:
            # Using Arial for both the side text and the barcode number
            custom_font = ImageFont.truetype("arial.ttf", 28)
            barcode_text_font = ImageFont.truetype("arial.ttf", 24)
        except IOError:
            custom_font = ImageFont.load_default()
            barcode_text_font = ImageFont.load_default()

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
                
                # Truncate text if it's too long
                if len(text_line) > 22: 
                    text_line = text_line[:22] + "..."
                
                draw.text((20, y_text), text_line, fill="black", font=custom_font)
                y_text += 40
                
            # --- 2. GENERATE BARCODE (Without Text) ---
            raw_data = str(row[barcode_col])
            if raw_data == 'nan' or not raw_data.strip():
                raw_data = "0000"
                
            full_barcode_data = f"{barcode_prefix}{raw_data}"
            
            rv = io.BytesIO()
            
            # We turn write_text to False so we can manually control the spacing later
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
            
            # Reserve space for the text we will draw below it
            MAX_BC_WIDTH = 450
            MAX_BC_HEIGHT = 200 
            
            bc_img.thumbnail((MAX_BC_WIDTH, MAX_BC_HEIGHT), Image.Resampling.LANCZOS)
            bc_width, bc_height = bc_img.size
            
            # Position barcode on the right side, shifted slightly up to leave room for the text
            x_offset = WIDTH - bc_width - 20
            y_offset = (HEIGHT - bc_height) // 2 - 20
            
            img.paste(bc_img, (x_offset, y_offset))
            
            # --- 3. MANUALLY DRAW THE BARCODE TEXT ---
            # Calculate the exact center of the barcode to place the text
            text_bbox = draw.textbbox((0, 0), full_barcode_data, font=barcode_text_font)
            text_width = text_bbox[2] - text_bbox[0]
            
            text_x = x_offset + (bc_width // 2) - (text_width // 2)
            
            # Set the distance between the barcode and the text here (e.g., + 10 pixels)
            text_y = y_offset + bc_height + 10 
            
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
            
            # Show a preview of the first label
            st.subheader("Preview of Label 1")
            st.image(label_images[0], use_container_width=False)
            
            st.download_button(
                label="Download Print-Ready PDF",
                data=pdf_buffer,
                file_name="SATO_Labels_89x35.pdf",
                mime="application/pdf"
            )
