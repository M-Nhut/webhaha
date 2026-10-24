# LaTeX Renderer Service

Service server-side dùng để render các block LaTeX mà MathJax không hỗ trợ,
đặc biệt là `tikzpicture` và `tabular`. Browser của người dùng không cần cài
LaTeX.

Image cài XeLaTeX, TikZ/PGFPlots và các package bảng thường gặp như
`booktabs`, `tabularx`, `longtable`, `multirow`, `makecell`, `siunitx`,
`colortbl`, `diagbox`. Preamble do file tải lên cung cấp được lọc bằng
allowlist trước khi biên dịch.

## Chạy bằng Docker

```bash
docker build -t question-latex-renderer latex_renderer_service
docker run --rm -p 8080:8080 question-latex-renderer
```

Kiểm tra service trước:

```bash
curl http://localhost:8080/health
curl -X POST http://localhost:8080/render \
  -H 'Content-Type: application/json' \
  -d '{"source":"\\begin{tabular}{cc} A & B \\\\ C & D \\end{tabular}"}'
```

Đặt trong web app:

```env
LATEX_RENDERER_URL=http://localhost:8080
```

Production có thể deploy image này lên Cloud Run, Render, Railway hoặc VPS.
Service không bật `shell-escape`, chặn các lệnh TeX đọc/ghi file, giới hạn
source 200 KB, preamble 50 KB và timeout mỗi lượt biên dịch.

Để bảo vệ endpoint công khai, đặt cùng một token ở renderer và web app:

```env
LATEX_RENDERER_TOKEN=thay-bang-chuoi-bi-mat-dai
```

Health check: `GET /health`. Chỉ coi service sẵn sàng khi response có
`"ready": true`.
