import os
import subprocess
import tempfile
import shutil


RESUMES_DIR = os.path.join(os.path.dirname(__file__), '..', 'resumes')


def compile_tex_to_pdf(tex_path, output_dir=None, output_name='Justin_S_Resume.pdf'):
    """
    Compile a .tex file to PDF using pdflatex.

    Args:
        tex_path: absolute path to the .tex file
        output_dir: directory to save the PDF (defaults to resumes/test/)
        output_name: filename for the output PDF

    Returns:
        dict with 'pdf_path' (absolute path to the generated PDF)
    """
    if not os.path.exists(tex_path):
        raise FileNotFoundError(f"TeX file not found: {tex_path}")

    if output_dir is None:
        output_dir = os.path.join(RESUMES_DIR, 'test')
    os.makedirs(output_dir, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Copy .tex to temp dir
        tmp_tex = os.path.join(tmpdir, 'resume.tex')
        shutil.copy2(tex_path, tmp_tex)

        # Run pdflatex twice (second pass resolves references)
        for i in range(2):
            result = subprocess.run(
                ['pdflatex', '-interaction=nonstopmode', '-output-directory', tmpdir, tmp_tex],
                capture_output=True,
                text=True,
                timeout=30
            )

        pdf_tmp = os.path.join(tmpdir, 'resume.pdf')
        if not os.path.exists(pdf_tmp):
            raise RuntimeError(
                f"pdflatex failed to produce PDF.\n"
                f"STDOUT:\n{result.stdout[-2000:]}\n"
                f"STDERR:\n{result.stderr[-2000:]}"
            )

        pdf_dest = os.path.join(output_dir, output_name)
        shutil.copy2(pdf_tmp, pdf_dest)

    return {'pdf_path': os.path.abspath(pdf_dest)}


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        # Recompile a specific .tex file: python compiler.py path/to/resume.tex
        tex_path = os.path.abspath(sys.argv[1])
        output_dir = os.path.dirname(tex_path)
        print(f"Compiling: {tex_path}")
        result = compile_tex_to_pdf(tex_path, output_dir=output_dir)
        print(f"PDF saved to: {result['pdf_path']}")
    else:
        print("Usage: python compiler.py <path/to/resume.tex>")
