"""
Flask Web 应用：上传 Excel -> 自动分析 -> 下载 PDF 报告
"""
import os, uuid, threading
from flask import Flask, render_template, request, jsonify, send_file

from analyzer import run_analysis, generate_smart_filename
from pdf_generator import generate_pdf

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["OUTPUT_FOLDER"] = "outputs"

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["OUTPUT_FOLDER"], exist_ok=True)

tasks = {}


@app.route("/")
def index():
    return render_template("upload.html")


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "未找到上传文件"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "文件名为空"}), 400

    if not file.filename.lower().endswith((".xlsx", ".xls")):
        return jsonify({"error": "仅支持 .xlsx 或 .xls 格式的 Excel 文件"}), 400

    task_id = uuid.uuid4().hex[:12]
    ext = os.path.splitext(file.filename)[1]
    safe_name = f"{task_id}{ext}"
    upload_path = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)
    file.save(upload_path)

    task_output_dir = os.path.join(app.config["OUTPUT_FOLDER"], task_id)
    tasks[task_id] = {
        "status": "processing",
        "filename": file.filename,
        "pdf_path": None,
        "download_name": None,
        "error": None,
    }

    thread = threading.Thread(target=_run_analysis_task,
                              args=(task_id, upload_path, task_output_dir))
    thread.start()

    return jsonify({"task_id": task_id, "status": "processing"})


@app.route("/status/<task_id>")
def task_status(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    return jsonify(task)


@app.route("/download/<task_id>")
def download(task_id):
    task = tasks.get(task_id)
    if not task or not task.get("pdf_path"):
        return jsonify({"error": "报告尚未生成"}), 404

    pdf_path = task["pdf_path"]
    if not os.path.exists(pdf_path):
        return jsonify({"error": "报告文件不存在"}), 404

    download_name = task.get("download_name", "分析报告.pdf")
    return send_file(pdf_path, as_attachment=True, download_name=download_name)


def _run_analysis_task(task_id, filepath, output_dir):
    try:
        results = run_analysis(filepath, output_dir=output_dir)

        pdf_path = os.path.join(output_dir, "report.pdf")
        generate_pdf(results, pdf_path)

        tasks[task_id]["status"] = "completed"
        tasks[task_id]["pdf_path"] = pdf_path
        tasks[task_id]["download_name"] = results["smart_filename"]
    except Exception as e:
        tasks[task_id]["status"] = "error"
        tasks[task_id]["error"] = str(e)


if __name__ == "__main__":
    print("=" * 50)
    print("  自动化数据分析系统")
    print("  打开浏览器访问: http://127.0.0.1:5000")
    print("=" * 50)
    app.run(debug=False, host="127.0.0.1", port=5000)
