import os
import sys
import fitz

def render_pages():
    template_path = "/home/hamzaelnajmi/report-agent/templates/template novo v2.pdf"
    output_dir = "/home/hamzaelnajmi/report-agent/static/template_pages"
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Opening template PDF: {template_path}")
    doc = fitz.open(template_path)
    print(f"Total pages: {len(doc)}")
    
    for i in range(len(doc)):
        print(f"Rendering page {i+1}/{len(doc)}...")
        page = doc[i]
        # Use 150 DPI for a balance between speed, file size, and visual quality
        pix = page.get_pixmap(dpi=150)
        out_path = os.path.join(output_dir, f"page_{i}.png")
        pix.save(out_path)
        print(f"Saved to {out_path}")
        
    doc.close()
    print("Done rendering pages!")

if __name__ == "__main__":
    render_pages()
