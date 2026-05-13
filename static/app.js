// 自动化数据分析系统 - 前端交互
const dropZone = document.getElementById("dropZone");
const fileInput = document.getElementById("fileInput");
const selectBtn = document.getElementById("selectBtn");
const fileInfo = document.getElementById("fileInfo");
const fileName = document.getElementById("fileName");
const uploadBtn = document.getElementById("uploadBtn");
const uploadSection = document.getElementById("uploadSection");
const progressSection = document.getElementById("progressSection");
const resultSection = document.getElementById("resultSection");
const errorSection = document.getElementById("errorSection");
const features = document.getElementById("features");

let selectedFile = null;
let pollTimer = null;

// 选择文件按钮
selectBtn.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", (e) => handleFile(e.target.files[0]));

// 拖拽事件
dropZone.addEventListener("dragover", (e) => { e.preventDefault(); dropZone.classList.add("drag-over"); });
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("drag-over");
    handleFile(e.dataTransfer.files[0]);
});

function handleFile(file) {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".xlsx") && !file.name.toLowerCase().endsWith(".xls")) {
        alert("仅支持 .xlsx 或 .xls 格式的文件");
        return;
    }
    selectedFile = file;
    fileName.textContent = `📄 ${file.name}（${formatSize(file.size)}）`;
    fileInfo.style.display = "flex";
}

function formatSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

// 开始分析
uploadBtn.addEventListener("click", async () => {
    if (!selectedFile) return;

    // 切换到进度界面
    uploadSection.style.display = "none";
    features.style.display = "none";
    resultSection.style.display = "none";
    errorSection.style.display = "none";
    progressSection.style.display = "block";
    document.getElementById("progressText").textContent = "正在上传并分析数据...";
    document.getElementById("progressDetail").textContent = "";

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
        const resp = await fetch("/upload", { method: "POST", body: formData });
        const data = await resp.json();

        if (data.error) {
            showError(data.error);
            return;
        }

        // 轮询状态
        document.getElementById("progressText").textContent = "正在分析数据，请稍候...";
        pollStatus(data.task_id);
    } catch (err) {
        showError("网络请求失败：" + err.message);
    }
});

function pollStatus(taskId) {
    let dots = 0;
    pollTimer = setInterval(async () => {
        try {
            const resp = await fetch(`/status/${taskId}`);
            const data = await resp.json();

            // 动态进度提示
            dots = (dots + 1) % 4;
            const dotStr = ".".repeat(dots);
            const messages = [
                "正在读取数据" + dotStr,
                "正在清洗数据" + dotStr,
                "正在生成图表" + dotStr,
                "正在编写报告" + dotStr,
            ];
            const idx = Math.floor(dots * messages.length / 4);
            document.getElementById("progressDetail").textContent = messages[Math.min(idx, messages.length - 1)];

            if (data.status === "completed") {
                clearInterval(pollTimer);
                showResult(taskId, data.filename);
            } else if (data.status === "error") {
                clearInterval(pollTimer);
                showError(data.error || "分析过程中出现未知错误");
            }
        } catch (err) {
            // 继续轮询
        }
    }, 1000);
}

function showResult(taskId, filename) {
    progressSection.style.display = "none";
    resultSection.style.display = "block";
    document.getElementById("resultInfo").textContent = `文件「${filename}」的分析报告已生成，点击下方按钮下载。`;

    document.getElementById("downloadBtn").onclick = () => {
        window.location.href = `/download/${taskId}`;
    };

    document.getElementById("resetBtn").onclick = resetAll;
}

function showError(msg) {
    if (pollTimer) clearInterval(pollTimer);
    progressSection.style.display = "none";
    errorSection.style.display = "block";
    document.getElementById("errorText").textContent = msg;
    document.getElementById("resetErrorBtn").onclick = resetAll;
}

function resetAll() {
    if (pollTimer) clearInterval(pollTimer);
    selectedFile = null;
    fileInput.value = "";
    uploadSection.style.display = "block";
    features.style.display = "grid";
    fileInfo.style.display = "none";
    progressSection.style.display = "none";
    resultSection.style.display = "none";
    errorSection.style.display = "none";
}
