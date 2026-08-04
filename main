import streamlit as st
import pandas as pd
import barcode
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont
import io

st.set_page_config(page_title="Coil Shop Label Utility", layout="wide")

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
        
    st.subheader("1. Data Preview")
    st.dataframe(df.head(3))
    
    st.subheader("2. Configure Label Format")
    col1, col2 = st.columns(2)
    
    with col1:
        barcode_col = st.selectbox(
            "Select the Barcode Column (Part No / Stockcode / Drawing No):", 
            df.columns,
            help="This column will be converted into a Code128 barcode with the number printed underneath."
        )
    with col2:
        text_cols = st.multiselect(
            "Select additional text columns to print above the barcode:", 
            df.columns
        )

    if st.button("Generate Labels", type="primary"):
        # Setup for 203 DPI Thermal Printer Canvas
        # 89mm width = ~711 pixels
        # 35mm height = ~280 pixels
        WIDTH, HEIGHT = 711, 280
        
        # Try to load a standard font, fallback to default if missing
        try:
            custom_font = ImageFont.truetype("arial.ttf", 30)
            small_font = ImageFont.truetype("arial.ttf", 22)
        except IOError:
            custom_font = ImageFont.load_default()
            small_font = ImageFont.load_default()

        label_images = []
        progress_bar = st.progress(0)
        
        for index, row in df.iterrows():
            # Create a blank white canvas for each label
            img = Image.new('RGB', (WIDTH, HEIGHT), color='white')
            draw = ImageDraw.Draw(img)
            
            # --- DRAW ADDITIONAL TEXT ---
            y_text = 15
            for col in text_cols:
                # Print "Header: Value"
                text_line = f"{col}: {row[col]}"
                draw.text((20, y_text), text_line, fill="black", font=custom_font)
                y_text += 35 # Move down for the next line
                
            # --- DRAW BARCODE & NUMBER ---
            barcode_data = row[barcode_col]
            # Replace empty or NaN values with a placeholder to prevent crashing
            if barcode_data == 'nan' or not barcode_data:
                barcode_data = "0000"
                
            # Generate Code128 Image in memory
            rv = io.BytesIO()
            options = {
                "write_text": True,       # This automatically prints the number below the barcode
                "module_width": 0.4,      # Width of the bars
                "module_height": 10.0,    # Height of the bars
                "text_distance": 5.0,
                "font_size": 18
            }
            code128 = barcode.get('code128', barcode_data, writer=ImageWriter())
            code128.write(rv, options=options)
            
            # Open the barcode image and paste it onto our main canvas
            rv.seek(0)
            bc_img = Image.open(rv)
            
            # Position the barcode at the bottom right (or center)
            bc_width, bc_height = bc_img.size
            x_offset = WIDTH - bc_width - 20
            y_offset = HEIGHT - bc_height - 10
            
            # If the barcode overlaps text, you can adjust these offsets
            img.paste(bc_img, (x_offset, y_offset))
            
            label_images.append(img)
            progress_bar.progress((index + 1) / len(df))

        # Compile all images into a single PDF
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
        
        # Download Button for the PDF
        st.download_button(
            label="Download Print-Ready PDF",
            data=pdf_buffer,
            file_name="SATO_Labels_89x35.pdf",
            mime="application/pdf"
        )
